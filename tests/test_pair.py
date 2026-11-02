import copy
from unittest.mock import Mock

import pytest

import pair
from common import normalize, read_json, write_json


def valid_response(request):
    return {"dishes": {k: {"stands_alone": True} for k in request["dishes"]},
            "pairs": {k: {"score": 2} for k in request["pairs"]}}


def test_request_shape_and_reuse_only_missing(config, fixture_menu, tmp_path):
    menu, tags = fixture_menu
    path = tmp_path / "pairs.json"
    caller = Mock(side_effect=lambda request, *args: valid_response(request))
    result = pair.build_pairing(menu, tags, config, path, api_key="test", caller=caller)
    request = caller.call_args.args[0]
    assert all(set(d) == {"name_de", "name_en", "station"} for d in request["items"].values())
    assert all(key == "||".join(sorted(values)) for key, values in request["pairs"].items())
    assert all(tags[k]["role"] == "main" or request["items"][k]["station"] == "Beilagen" for k in request["items"])
    assert result["dishes"] and result["pairs"] and menu["date"] in result["attempts"]
    pair.build_pairing(menu, tags, config, path, api_key="test", caller=caller)
    caller.assert_called_once()
    # Another date only asks for the entries deliberately removed from the cache.
    removed = next(iter(result["pairs"]))
    del result["pairs"][removed]
    write_json(path, result)
    next_day = {**menu, "date": "2026-11-03"}
    pair.build_pairing(next_day, tags, config, path, api_key="test", caller=caller)
    new = caller.call_args.args[0]
    assert new["dishes"] == {} and list(new["pairs"]) == [removed]


def test_model_request_uses_schema_and_temperature(config, fixture_menu, monkeypatch):
    menu, tags = fixture_menu
    request = pair.missing_request(menu, tags, pair.empty_cache())
    model = Mock(return_value={})
    monkeypatch.setattr("pair.generate_json", model)
    pair.call_pair(request, "model", "test")
    args = model.call_args.args
    assert args[1] == request and args[3:] == ("model", "test")
    assert args[2]["required"] == ["dishes", "pairs"]
    assert model.call_args.kwargs == {"temperature": 0}


@pytest.mark.parametrize("bad", [None, {}, {"dishes": {}, "pairs": {}}, {"dishes": [], "pairs": {}}])
def test_missing_response_keys_rejected(config, fixture_menu, bad):
    menu, tags = fixture_menu
    request = pair.missing_request(menu, tags, pair.empty_cache())
    with pytest.raises(ValueError):
        pair.validate_response(bad, request)


def test_strict_entry_types_and_enums(config, fixture_menu):
    menu, tags = fixture_menu
    request = pair.missing_request(menu, tags, pair.empty_cache())
    response = valid_response(request)
    d, p = next(iter(response["dishes"])), next(iter(response["pairs"]))
    response["dishes"][d]["stands_alone"] = "true"
    response["pairs"][p]["score"] = True
    valid = pair.validate_response(response, request)
    assert d not in valid["dishes"] and p not in valid["pairs"]
    response["pairs"][p]["score"] = 4
    assert p not in pair.validate_response(response, request)["pairs"]
    response["pairs"][p] = {"score": 2, "price": 3}
    assert p not in pair.validate_response(response, request)["pairs"]


@pytest.mark.parametrize("error", [TimeoutError(), OSError(), ValueError(), RuntimeError()])
def test_failure_is_nonfatal_and_attempt_is_recorded(config, fixture_menu, tmp_path, error):
    menu, tags = fixture_menu
    path = tmp_path / "pairs.json"
    caller = Mock(side_effect=error)
    for _ in range(2):
        result = pair.build_pairing(menu, tags, config, path, api_key="test", caller=caller)
    caller.assert_called_once()
    assert menu["date"] in read_json(path)["attempts"]
    assert not result["dishes"] and not result["pairs"]


def test_missing_key_and_closed_do_not_consume_attempt(config, fixture_menu, tmp_path):
    menu, tags = fixture_menu
    caller = Mock()
    result = pair.build_pairing(menu, tags, config, tmp_path / "pairs.json", api_key="", caller=caller)
    assert not result["attempts"]
    pair.build_pairing({**menu, "state": "closed", "dishes": []}, tags, config, tmp_path / "pairs.json", api_key="test", caller=caller)
    caller.assert_not_called()


def test_fallback_heuristics_and_pizza(config, fixture_menu):
    menu, tags = fixture_menu
    items = [pair.food(d, tags) for d in menu["dishes"]]
    find = lambda prefix: next(i for i in items if i["name"].startswith(prefix))
    fish, curry, rice, pizza = find("Seelachs"), find("Gemüsecurry"), find("Reis"), find("PINSA")
    assert pair.stands_alone(pizza, {})
    assert not pair.stands_alone(fish, {})
    assert pair.stands_alone(curry, {}) # specified conservative fallback, not model knowledge
    assert not pair.stands_alone(rice, {})
    assert pair.pair_score(fish, rice, {}) == 2
    assert pair.pair_score(curry, rice, {}) == 0
    assert pair.pair_score(pizza, curry, {}) == 0
