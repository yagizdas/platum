import copy
import json
from unittest.mock import Mock

import pytest

import judge
from common import read_json, write_json
from pick import build_today, candidates, judge_payload, main, plate_result, rank_variant


@pytest.fixture
def enabled(config):
    config["llm"]["enabled"] = True
    return config


def pools_for(menu, cache, config):
    pools = {}
    for vegan in (False, True):
        plates = list(candidates(menu["dishes"], cache, config, vegan))
        for goal in ("bulk", "cut", "budget"):
            pools[f"{goal}_{'vegan' if vegan else 'all'}"] = rank_variant(plates, goal, vegan, config)[0]
    return pools


def test_judge_picks_only_code_candidates_with_exact_totals(enabled, fixture_menu):
    menu, cache = fixture_menu
    pools = pools_for(menu, cache, enabled)
    response = {key: {"id": f"c{len(plates)-1}", "reason": "A satisfying main with a sensible pairing."} for key, plates in pools.items()}
    caller = Mock(return_value=response)
    result = build_today(menu, cache, enabled, api_key="test", judge_caller=caller)
    caller.assert_called_once()
    payload = caller.call_args.args[0]
    assert len(payload) == 6
    for key, variant in result["variants"].items():
        assert variant["picked_by"] == "llm" and variant["reason"] == response[key]["reason"]
        goal, diet = key.split("_")
        expected = plate_result(pools[key][-1], goal, diet == "vegan", enabled)
        assert variant["items"] == expected["items"] and variant["total"] == expected["total"]
        for candidate in payload[key]:
            assert set(candidate) == {"id", "dishes", "totals"}
            assert set(candidate["totals"]) == {"price_eur", "kcal", "protein_g"}
            assert all(set(d) == {"name_de", "name_en", "station", "serving"} for d in candidate["dishes"])


@pytest.mark.parametrize("response", [
    {"bulk_all": {"id": "c999", "reason": "Looks good."}},
    {"bulk_all": {"id": "steak", "reason": "A coherent lunch."}},
    {"bulk_all": {"id": "c0", "reason": "Looks good.", "dishes": ["Invented steak"]}},
    {"bulk_all": {"id": "c0", "reason": "", "total": {"kcal": 9000}}},
    ["invalid root"], None,
])
def test_invalid_or_hallucinated_response_falls_back_per_variant(enabled, fixture_menu, response):
    menu, cache = fixture_menu
    expected = build_today(menu, cache, enabled, no_llm=True)
    result = build_today(menu, cache, enabled, api_key="test", judge_caller=Mock(return_value=response))
    assert result == expected
    assert all(v["picked_by"] == "rules" and v["reason"] is None for v in result["variants"].values())


def test_one_bad_variant_does_not_discard_good_siblings(enabled, fixture_menu):
    menu, cache = fixture_menu
    response = {"bulk_all": {"id": "not-real", "reason": "A good pairing."},
                "cut_all": {"id": "c0", "reason": "Lean protein with a vegetable side."},
                "imaginary_variant": {"id": "c0", "reason": "Ignored."}}
    result = build_today(menu, cache, enabled, api_key="test", judge_caller=Mock(return_value=response))
    assert len(result["variants"]) == 6
    assert result["variants"]["bulk_all"]["picked_by"] == "rules"
    assert result["variants"]["cut_all"]["picked_by"] == "llm"


@pytest.mark.parametrize("error", [TimeoutError("timeout"), OSError("offline"), RuntimeError("client failure"), json.JSONDecodeError("malformed JSON", "bad", 0)])
def test_judge_failures_still_allow_writing_today(enabled, fixture_menu, tmp_path, error):
    menu, cache = fixture_menu
    result = build_today(menu, cache, enabled, api_key="test", judge_caller=Mock(side_effect=error))
    path = tmp_path / "today.json"
    write_json(path, result)
    saved = read_json(path)
    assert all(v["state"] == "ready" and v["picked_by"] == "rules" and v["reason"] is None for v in saved["variants"].values())


def test_missing_key_falls_back_without_network(enabled, fixture_menu, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("judge.dotenv_values", lambda *a: {})
    menu, cache = fixture_menu
    caller = Mock(side_effect=AssertionError("Must not request without key"))
    result = build_today(menu, cache, enabled, judge_caller=caller)
    caller.assert_not_called()
    assert all(v["picked_by"] == "rules" for v in result["variants"].values())


@pytest.mark.parametrize("reason", ["", " ", "x" * 121, 5, "Contains 30g protein."])
def test_reason_validation(reason):
    pools = {"bulk_all": [{"id": "c0"}]}
    assert judge.validate_choices({"bulk_all": {"id": "c0", "reason": reason}}, pools) == {}
    assert judge.validate_choices({"bulk_all": {"id": "c0", "reason": "x" * 120}}, pools)


def test_judge_schema_temperature_and_model(monkeypatch):
    pools = {"bulk_all": [{"id": "c0"}, {"id": "c1"}], "cut_vegan": []}
    client = Mock(return_value={})
    monkeypatch.setattr("judge.generate_json", client)
    judge.call_judge(pools, "configured-model", "test-key")
    client.assert_called_once()
    prompt, payload, schema, model, key = client.call_args.args
    assert payload is pools and model == "configured-model" and key == "test-key"
    assert client.call_args.kwargs == {"temperature": 0}
    assert schema["properties"]["bulk_all"]["properties"]["id"]["enum"] == ["c0", "c1"]
    assert "cut_vegan" not in schema["properties"]
    assert schema["additionalProperties"] is False


def test_daily_cache_reuses_decisions_and_handles_changed_candidates(tmp_path):
    pools = {"bulk_all": [{"id": "c0", "dishes": [{"name_de": "Curry"}]}]}
    caller = Mock(return_value={"bulk_all": {"id": "c0", "reason": "A coherent lunch."}})
    path = tmp_path / "judge.json"
    args = dict(api_key="test", caller=caller, cache_path=path)
    first = judge.choose_variants(pools, "model", "2026-11-02", **args)
    assert judge.choose_variants(pools, "model", "2026-11-02", **args) == first
    changed = copy.deepcopy(pools); changed["bulk_all"][0]["dishes"][0]["name_de"] = "Different recipe"
    assert judge.choose_variants(changed, "model", "2026-11-02", **args) == {}
    assert caller.call_count == 1
    judge.choose_variants(pools, "model", "2026-11-03", **args)
    assert caller.call_count == 2


def test_failed_daily_attempt_is_not_repeated(tmp_path):
    pools = {"bulk_all": [{"id": "c0"}]}
    caller = Mock(side_effect=TimeoutError())
    path = tmp_path / "judge.json"
    for _ in range(2):
        assert judge.choose_variants(pools, "model", "2026-11-02", api_key="test", caller=caller, cache_path=path) == {}
    caller.assert_called_once()


def test_corrupt_judge_cache_is_nonfatal(tmp_path):
    path = tmp_path / "judge.json"; path.write_text("not JSON")
    caller = Mock()
    assert judge.choose_variants({"bulk_all": [{"id": "c0"}]}, "model", "2026-11-02", api_key="test", caller=caller, cache_path=path) == {}
    caller.assert_not_called()


@pytest.mark.parametrize("disable", ["flag", "config"])
def test_disabled_judge_makes_no_call(enabled, fixture_menu, disable):
    menu, cache = fixture_menu
    caller = Mock(side_effect=AssertionError("Judge disabled"))
    if disable == "config":
        enabled["llm"]["enabled"] = False
    result = build_today(menu, cache, enabled, no_llm=disable == "flag", api_key="test", judge_caller=caller)
    caller.assert_not_called()
    assert all(v["picked_by"] == "rules" for v in result["variants"].values())


def test_no_llm_cli_flag_writes_rules_without_judge(enabled, fixture_menu, tmp_path, monkeypatch):
    import yaml
    menu, cache = fixture_menu
    write_json(tmp_path / "menu.json", menu); write_json(tmp_path / "cache.json", cache)
    config_path = tmp_path / "config.yaml"; config_path.write_text(yaml.safe_dump(enabled))
    client = Mock(side_effect=AssertionError("No judge call"))
    monkeypatch.setattr("pick.choose_variants", client)
    output = tmp_path / "today.json"
    monkeypatch.setattr("sys.argv", ["pick.py", "--no-llm", "--config", str(config_path), "--menu", str(tmp_path / "menu.json"), "--cache", str(tmp_path / "cache.json"), "--output", str(output)])
    main()
    assert all(v["picked_by"] == "rules" for v in read_json(output)["variants"].values())
    client.assert_not_called()
