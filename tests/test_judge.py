import copy
from unittest.mock import Mock

import pytest

import judge
from common import read_json, write_json
from pick import build_today, candidates, plate_result, rank_variant
from proposals import fallback_proposals


@pytest.fixture(autouse=True)
def mock_proposals(monkeypatch):
    monkeypatch.setattr("proposals.call_proposals", lambda items, *a, **kw: {"combos": fallback_proposals(items)})


def pools_for(menu, tags, config, pairing):
    result = {}
    for vegan in (False, True):
        values = list(candidates(menu["dishes"], tags, config, vegan, pairing))
        for goal in ("bulk", "cut", "budget"):
            result[f"{goal}_{'vegan' if vegan else 'all'}"] = rank_variant(values, goal, vegan, config)[0]
    return result


def answer(pools):
    return {key: [{"id": p["id"], "title": "A coherent lunch", "reason": "A satisfying main with a sensible pairing."}
                  for p in reversed(values)]
            for key, values in pools.items() if values}


def test_judge_ranked_ids_keep_exact_code_totals(config, fixture_menu, pairing):
    config["llm"]["enabled"] = True
    menu, tags = fixture_menu
    pool = pools_for(menu, tags, config, pairing)
    caller = Mock(side_effect=lambda pools, *args: answer(pools))
    result = build_today(menu, tags, config, pairing=pairing, api_key="test", judge_caller=caller)
    caller.assert_called_once()
    payload = caller.call_args.args[0]
    assert len(payload) == 6
    for key, variant in result["variants"].items():
        for index, selected in enumerate(variant["plates"]):
            expected = plate_result(pool[key][index])
            assert selected["items"] == expected["items"] and selected["total"] == expected["total"]
            assert selected["picked_by"] == "rules" # copy cannot select or reorder
            assert selected["reason"] is not None
            assert selected["score"] == expected["score"]


@pytest.mark.parametrize("bad", [None, {}, [{"id": "c99", "title": "Unknown", "reason": "Good."}],
    [{"id": "c0", "title": "x" * 41, "reason": "Good."}],
    [{"id": "c0", "title": "Fish 2", "reason": "Good."}],
    [{"id": "c0", "title": "Fish", "reason": ""}],
    [{"id": "c0", "title": "Fish", "reason": "Good.", "items": ["invented"]}]])
def test_invalid_variant_falls_back_to_code_order(config, fixture_menu, pairing, bad):
    config["llm"]["enabled"] = True
    menu, tags = fixture_menu
    expected = build_today(menu, tags, config, pairing=pairing, no_llm=True)
    caller = Mock(return_value={"bulk_all": bad})
    assert build_today(menu, tags, config, pairing=pairing, api_key="test", judge_caller=caller) == expected


def test_duplicate_ids_are_invalid_and_every_final_plate_has_a_reason():
    pools = {"bulk_all": [{"id": "c0"}, {"id": "c1"}]}
    choices = [{"id": "c0", "title": "Fish", "reason": "A good lunch."}, {"id": "c0", "title": "Curry"}]
    assert judge.validate_choices({"bulk_all": choices}, pools) == {}
    choices[1].update(id="c1", reason="Extra reason")
    assert judge.validate_choices({"bulk_all": choices}, pools)["bulk_all"] == choices


def test_single_bad_variant_preserves_valid_siblings(config, fixture_menu, pairing):
    config["llm"]["enabled"] = True
    menu, tags = fixture_menu
    def caller(pools, *args):
        result = answer(pools)
        result["bulk_all"] = [{"id": "bad"}]
        return result
    result = build_today(menu, tags, config, pairing=pairing, api_key="test", judge_caller=caller)
    assert result["variants"]["bulk_all"]["plates"][0]["picked_by"] == "rules"
    assert result["variants"]["cut_all"]["plates"][0]["title"] == "A coherent lunch"
    assert result["variants"]["cut_all"]["plates"][0]["picked_by"] == "rules"


@pytest.mark.parametrize("error", [TimeoutError(), OSError(), ValueError(), RuntimeError()])
def test_exception_is_nonfatal_and_today_can_be_written(config, fixture_menu, pairing, tmp_path, error):
    config["llm"]["enabled"] = True
    menu, tags = fixture_menu
    result = build_today(menu, tags, config, pairing=pairing, api_key="test", judge_caller=Mock(side_effect=error))
    path = tmp_path / "today.json"; write_json(path, result)
    assert all(p["picked_by"] == "rules" for v in read_json(path)["variants"].values() for p in v["plates"])


def test_schema_and_temperature(monkeypatch):
    pools = {"bulk_all": [{"id": "c0"}, {"id": "c1"}], "cut_vegan": []}
    client = Mock(return_value={})
    monkeypatch.setattr("judge.generate_json", client)
    judge.call_judge(pools, "model", "test")
    assert client.call_args.kwargs == {"temperature": 0}
    schema = client.call_args.args[2]["properties"]["bulk_all"]
    assert schema["minItems"] == schema["maxItems"] == 2
    assert schema["prefixItems"][0]["required"] == ["id", "title", "reason"]
    assert schema["prefixItems"][1]["required"] == ["id", "title", "reason"]


def test_fewer_than_three_candidates_and_daily_cache(tmp_path):
    pools = {"bulk_all": [{"id": "c0"}]}
    client = Mock(side_effect=lambda pools, *a: answer(pools))
    path = tmp_path / "judge.json"
    args = dict(api_key="test", caller=client, cache_path=path)
    first = judge.choose_variants(pools, "model", "2026-11-02", **args)
    assert len(first["bulk_all"]) == 1
    assert judge.choose_variants(pools, "model", "2026-11-02", **args) == first
    changed = {"bulk_all": [{"id": "c0", "changed": True}]}
    assert judge.choose_variants(changed, "model", "2026-11-02", **args) == {}
    client.assert_called_once()
    judge.choose_variants(pools, "model", "2026-11-03", **args)
    assert client.call_count == 2
    assert judge.choose_variants(pools, "model", "2026-11-02", api_key="", caller=client, cache_path=path) == first


def test_failures_are_cached_and_missing_key_is_no_call(tmp_path):
    path = tmp_path / "judge.json"
    pools = {"bulk_all": [{"id": "c0"}]}
    client = Mock(side_effect=TimeoutError())
    for _ in range(2):
        assert judge.choose_variants(pools, "model", "2026-11-02", api_key="test", caller=client, cache_path=path) == {}
    client.assert_called_once()
    assert judge.choose_variants(pools, "model", "2026-11-03", api_key="", caller=client, cache_path=path) == {}


@pytest.mark.parametrize("disable", ["config", "flag"])
def test_disable_judge(config, fixture_menu, pairing, disable):
    config["llm"]["enabled"] = disable != "config"
    menu, tags = fixture_menu
    client = Mock(side_effect=AssertionError("No request"))
    build_today(menu, tags, config, pairing=pairing, no_llm=disable == "flag", api_key="test", judge_caller=client)
    client.assert_not_called()
