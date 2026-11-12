import copy
import json
from unittest.mock import Mock

import pytest

from common import dish_id, read_json, write_json
from pair import food
from pick import build_today
from proposals import call_proposals, daily_proposals, fallback_proposals, validate_proposals


def test_six_goal_specific_calls_and_variant_caches(config, fixture_menu, tmp_path):
    config["llm"]["enabled"] = True
    menu, tags = fixture_menu
    def answer(items, model, key, *, instruction):
        assert instruction in config["proposals"]["instructions"].values()
        return {"combos": fallback_proposals(items)}
    caller = Mock(side_effect=answer)
    options = dict(api_key="test", proposal_caller=caller, judge_caller=Mock(return_value={}),
                   proposals_dir=tmp_path)
    first = build_today(menu, tags, config, **options)
    assert caller.call_count == 6
    for goal in ("bulk", "cut", "budget"):
        assert sum(call.kwargs["instruction"] == config["proposals"]["instructions"][goal] for call in caller.call_args_list) == 2
        assert (tmp_path / menu["date"] / f"{goal}_all.json").exists()
        vegan = read_json(tmp_path / menu["date"] / f"{goal}_vegan.json")
        vegan_ids = {dish_id(d) for d in menu["dishes"] if d.get("is_vegan") is True}
        assert all(set(combo) <= vegan_ids for combo in vegan["combos"])
    second = build_today(menu, tags, config, **options)
    assert caller.call_count == 6
    write_json(tmp_path / "first-day.json", first)
    write_json(tmp_path / "second-day.json", second)
    assert (tmp_path / "first-day.json").read_bytes() == (tmp_path / "second-day.json").read_bytes()


def test_vegan_input_excludes_unknown_and_nonvegan(config, fixture_menu, tmp_path):
    config["llm"]["enabled"] = True
    menu, tags = copy.deepcopy(fixture_menu)
    menu["dishes"][0]["is_vegan"] = None
    items = [food(d, tags) for d in menu["dishes"]]
    def answer(received, *args, **kwargs):
        assert received and all(i.get("is_vegan") is True for i in received)
        assert all(i["name"] != menu["dishes"][0]["name"] for i in received)
        return {"combos": fallback_proposals(received)}
    daily_proposals(menu["date"], items, config, "cut_vegan", api_key="test", caller=answer, cache_dir=tmp_path)


def test_existing_variant_cache_never_calls_even_without_key(config, fixture_menu, tmp_path):
    menu, tags = fixture_menu
    items = [food(d, tags) for d in menu["dishes"]]
    combos = [[dish_id(items[0])]]
    write_json(tmp_path / menu["date"] / "bulk_all.json", {"combos": combos})
    caller = Mock(side_effect=AssertionError("Must reuse cache"))
    assert daily_proposals(menu["date"], items, config, "bulk_all", cache_dir=tmp_path, caller=caller, api_key="") == combos
    caller.assert_not_called()


@pytest.mark.parametrize("failure", [TimeoutError(), ValueError("bad JSON"), RuntimeError()])
def test_failed_calls_cache_deterministic_fallback(config, fixture_menu, tmp_path, failure):
    config["llm"]["enabled"] = True
    menu, tags = fixture_menu
    items = [food(d, tags) for d in menu["dishes"]]
    caller = Mock(side_effect=failure)
    for _ in range(2):
        result = daily_proposals(menu["date"], items, config, "bulk_all", cache_dir=tmp_path, caller=caller, api_key="test")
        assert result == fallback_proposals(items)
    caller.assert_called_once()


def test_validation_unknown_duplicates_soups_dessert_and_vegan(make_dish):
    items = []
    for name, role, vegan in [("Main", "main", True), ("Soup A", "soup", True),
                               ("Soup B", "soup", True), ("Dessert", "dessert", True),
                               ("Meat", "main", False)]:
        dish, tag = make_dish(name, role=role, vegan=vegan)
        items.append({**dish, **tag})
    main, a, b, dessert, meat = map(dish_id, items)
    response = {"combos": [[main], [main, main], [main, "unknown"], [main, a, b],
                            [dessert], [main, meat], [main, a], [a, main], [dessert, dessert], []]}
    assert validate_proposals(response, items) == [list(c) for c in sorted([(main,), tuple(sorted([main, meat])), tuple(sorted([main, a]))])]
    assert all(meat not in combo for combo in validate_proposals(response, items, vegan=True))


def test_proposal_adapter_sends_existing_macros_and_requests_up_to_15_combinations(monkeypatch, fixture_menu):
    menu, tags = fixture_menu
    items = [food(d, tags) for d in menu["dishes"]]
    model = Mock(return_value={"combos": []})
    monkeypatch.setattr("proposals.generate_json", model)
    call_proposals(items, "model", "secret", instruction="Filling trays.")
    prompt, payload, schema, model_name, key = model.call_args.args
    assert "Filling trays." in prompt
    assert schema["properties"]["combos"]["minItems"] == 0
    assert schema["properties"]["combos"]["maxItems"] == 15
    assert "Propose up to 15 different lunches" in prompt
    assert "Never pad the list" in prompt
    assert "grams per 100 grams of prepared food" in prompt
    nutrition_fields = {"kcal_per_100g", "protein_per_100g", "carbs_per_100g",
                        "fat_per_100g", "typical_portion_g", "is_per_piece", "piece_weight_g"}
    for sent, original in zip(payload["dishes"], items, strict=True):
        assert set(sent) == {"id", "name_en", "role", "station", "standing"} | nutrition_fields
        assert sent["id"] == dish_id(original)
        assert all(sent[field] == original[field] for field in nutrition_fields)
    assert model.call_args.kwargs == {"temperature": 0}


def test_audit_preserves_raw_duplicates_and_per_entry_reasons(config, fixture_menu, tmp_path):
    config['llm']['enabled'] = True
    menu, tags = fixture_menu
    items = [food(dish, tags) for dish in menu['dishes']]
    valid = fallback_proposals(items)[0]
    response = {'combos': [valid, valid[::-1], ['unknown'], [valid[0], valid[0]]]}
    caller = Mock(return_value=response)
    combos = daily_proposals(menu['date'], items, config, 'bulk_all', cache_dir=tmp_path,
                             caller=caller, api_key='private-api-key')
    cache = read_json(tmp_path / menu['date'] / 'bulk_all.json')
    audit_path = tmp_path / menu['date'] / cache['audit_file']
    audit = read_json(audit_path)
    assert audit['raw_response'] == response
    assert audit['selected_combos'] == combos == [sorted(valid)]
    assert audit['validation']['returned_count'] == 4
    assert audit['validation']['accepted_count'] == 1
    assert audit['validation']['rejected_counts'] == {
        'duplicate_combination': 1, 'unknown_dish_id': 1, 'repeated_dish_id': 1}
    assert 'private-api-key' not in audit_path.read_text()
    daily_proposals(menu['date'], items, config, 'bulk_all', cache_dir=tmp_path,
                    caller=caller, api_key='private-api-key')
    caller.assert_called_once()
    assert len(list((tmp_path / menu['date'] / 'audits' / 'bulk_all').glob('*.json'))) == 1


@pytest.mark.parametrize('response', [TimeoutError('private-api-key'), {'combos': [['unknown']]}])
def test_failed_refresh_preserves_existing_cache_and_records_attempt(config, fixture_menu, tmp_path, response):
    config['llm']['enabled'] = True
    menu, tags = fixture_menu
    items = [food(dish, tags) for dish in menu['dishes']]
    combos = fallback_proposals(items)
    path = tmp_path / menu['date'] / 'bulk_all.json'
    write_json(path, {'combos': combos, 'source': 'llm'})
    previous = path.read_bytes()
    caller = Mock(side_effect=response) if isinstance(response, Exception) else Mock(return_value=response)
    assert daily_proposals(menu['date'], items, config, 'bulk_all', cache_dir=tmp_path,
                           caller=caller, api_key='private-api-key', refresh=True) == combos
    assert path.read_bytes() == previous
    audit_path = next((path.parent / 'audits' / 'bulk_all').glob('*.json'))
    audit = read_json(audit_path)
    assert audit['source'] == 'previous_cache'
    assert audit['cache_updated'] is False
    assert audit['previous_cache']['combos'] == combos
    assert 'private-api-key' not in audit_path.read_text()


def test_provider_audit_keeps_visible_output_when_json_cannot_be_parsed(monkeypatch, fixture_menu):
    from proposals import record_response
    from tag import generate_json
    result = {'modelVersion': 'test-model', 'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
        {'text': 'provider reasoning', 'thought': True}, {'text': 'invalid JSON response'}]}}]}
    response = Mock()
    response.read.return_value = json.dumps(result).encode()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    monkeypatch.setattr('tag.urlopen', Mock(return_value=response))
    audit = {}
    with pytest.raises(ValueError):
        generate_json('prompt', {}, {}, 'model', 'private-api-key',
                      response_observer=lambda value: record_response(audit, value))
    assert audit['provider_response']['candidates'] == [{'finish_reason': 'STOP', 'text': 'invalid JSON response'}]
