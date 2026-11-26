import copy

import pytest

from bulk_experiment import attach_experiment, build_experiment
from combination_c import (GOAL_CONTEXT, TOP_K, attach_c_experiment, build_c_experiment,
                           fingerprint, run_call, selection_payload, validate_selection)
from common import read_json, write_json
from pick import GOALS
from tag import GeminiAPIError


def choose(payload, ids=None):
    ids = ids or [p['id'] for p in payload['candidates'][:payload['choose']]]
    return {'selections': [{'id': key, 'reason': 'A practical lunch for this goal.'} for key in ids]}


def test_top20_pool_and_c_do_not_change_a_or_existing_bulk_b(config, fixture_menu):
    menu, tags = fixture_menu
    ranking = build_experiment(menu, tags, config, goals=GOALS, top_k=TOP_K)
    original_b = build_experiment(menu, tags, config)
    a = {'campus': 'arcisstr', 'variants': {'untouched': True}, 'extras': {'all': []}}
    before = copy.deepcopy(a)
    b = attach_experiment(a, menu, tags, config, ranking=ranking)
    assert a == before
    assert set(key.split('_', 1)[0] for key in ranking['variants']) == set(GOALS)
    assert len(ranking['variants']) == 18
    for key, original in original_b['variants'].items():
        assert b['experiments']['bulk_ab']['variants'][key] == original
    assert all(len(v['plates']) <= 20 for v in ranking['variants'].values())
    cache = {}
    for key, variant in ranking['variants'].items():
        payload = selection_payload(key.split('_', 1)[0], variant['plates'])
        if variant['plates']:
            ids = [p['id'] for p in payload['candidates'][-payload['choose']:]][::-1]
            cache[fingerprint(payload, config['gemini_model'])] = {'status': 'ready', **choose(payload, ids)}
    updated, audit = attach_c_experiment(b, ranking, config, cache)
    assert {k: v for k, v in updated.items() if k != 'experiments'} == before
    for key, variant in updated['experiments']['combination_c']['variants'].items():
        candidates = ranking['variants'][key]['plates']
        assert len(variant['plates']) == min(5, len(candidates))
        for p in variant['plates']:
            expected = candidates[p['preference_rank'] - 1]
            assert p['items'] == expected['items'] and p['total'] == expected['total']
            assert p['score'] == expected['score'] and p['picked_by'] == 'llm_from_top20'
        assert audit['variants'][key]['goal'] in GOAL_CONTEXT


def test_selection_validation_only_accepts_exact_distinct_supplied_ids(config, fixture_menu):
    menu, tags = fixture_menu
    pool = build_experiment(menu, tags, config, top_k=20)['variants']['bulk_all']['plates']
    payload = selection_payload('bulk', pool)
    response = choose(payload)
    assert len(validate_selection(response, payload)) == payload['choose']
    invalid = [None, {'selections': []}, {**response, 'extra': True}]
    for change in ('invented', 'duplicate', 'dish_edit', 'empty_reason'):
        bad = copy.deepcopy(response)
        if change == 'invented':bad['selections'][0]['id'] = 'not-a-candidate'
        if change == 'duplicate':bad['selections'][1]['id'] = bad['selections'][0]['id']
        if change == 'dish_edit':bad['selections'][0]['items'] = []
        if change == 'empty_reason':bad['selections'][0]['reason'] = ' '
        invalid.append(bad)
    for bad in invalid:
        with pytest.raises(ValueError):validate_selection(bad, payload)


def test_fingerprints_invalidate_changed_goal_model_portions_and_scores(config, fixture_menu):
    menu, tags = fixture_menu
    pool = build_experiment(menu, tags, config, top_k=20)['variants']['bulk_all']['plates']
    payload = selection_payload('bulk', pool)
    token = fingerprint(payload, 'model-a')
    assert token == fingerprint(copy.deepcopy(payload), 'model-a')
    assert token != fingerprint(payload, 'model-b')
    assert token != fingerprint(selection_payload('cut', pool), 'model-a')
    changed = copy.deepcopy(payload);changed['candidates'][0]['items'][0]['weight_g'] += 1
    assert token != fingerprint(changed, 'model-a')
    changed = copy.deepcopy(payload);changed['candidates'][0]['preference_score'] += .1
    assert token != fingerprint(changed, 'model-a')


def test_missing_or_invalid_cache_is_not_presented_as_llm_selection(config, fixture_menu, monkeypatch):
    menu, tags = fixture_menu
    ranking = build_experiment(menu, tags, config, top_k=20)
    def bomb(*args, **kwargs):raise AssertionError('Read-only C rendering must not call a model')
    monkeypatch.setattr('combination_c.generate_json', bomb)
    c, _ = build_c_experiment(ranking, config, {})
    assert c['variants']['bulk_all']['state'] == 'unavailable'
    assert c['variants']['bulk_all']['plates'] == []
    payload = selection_payload('bulk', ranking['variants']['bulk_all']['plates'])
    cache = {fingerprint(payload, config['gemini_model']): {'status': 'ready', 'selections': [{'id': 'unknown', 'reason': 'x'}]}}
    c, _ = build_c_experiment(ranking, config, cache)
    assert c['variants']['bulk_all']['plates'] == []
    assert 'invalid' in c['variants']['bulk_all']['message']


def test_small_pools_are_not_padded(config, fixture_menu):
    menu, tags = fixture_menu
    pool = build_experiment(menu, tags, config)['variants']['bulk_all']['plates'][:2]
    payload = selection_payload('bulk', pool)
    assert payload['choose'] == 2
    assert len(validate_selection(choose(payload), payload)) == 2


def test_model_call_retries_transient_errors_and_redacts_key(config, fixture_menu, monkeypatch):
    menu, tags = fixture_menu
    payload = selection_payload('bulk', build_experiment(menu, tags, config)['variants']['bulk_all']['plates'])
    calls = []
    def caller(p, model, key):
        calls.append(1)
        if len(calls) == 1:raise GeminiAPIError(503, f'try later {key}')
        return choose(p)
    monkeypatch.setattr('combination_c.time.sleep', lambda seconds: None)
    result = run_call(payload, 'test-model', 'secret-test-key', caller=caller)
    assert result['status'] == 'ready' and len(calls) == 2
    assert 'secret-test-key' not in str(result)
    assert '[redacted]' in str(result)


def test_rescore_publishes_c_audit_and_all_goal_b_without_model_calls(tmp_path, config, fixture_menu, monkeypatch):
    from rescore_cached import rescore
    menu, tags = fixture_menu;day = menu['date']
    write_json(tmp_path / 'data/week.json', {'week_start': day, 'days': [{'date': day}]})
    write_json(tmp_path / 'data/menus' / f'{day}.json', menu)
    write_json(tmp_path / 'data/dish_cache.json', tags)
    def bomb(*args, **kwargs):raise AssertionError('Publishing must not call an LLM')
    monkeypatch.setattr('combination_c.generate_json', bomb)
    rescore(tmp_path)
    public = read_json(tmp_path / 'data/days' / f'{day}.json')
    assert len(public['experiments']['bulk_ab']['variants']) == 18
    assert len(public['experiments']['combination_c']['variants']) == 18
    assert read_json(tmp_path / 'label/c/data/index.json')['days'] == [{'date': day, 'file': day + '.json'}]
    audit = read_json(tmp_path / 'label/c/data' / f'{day}.json')
    assert audit['date'] == day and audit['variants']['bulk_all']['candidates']
