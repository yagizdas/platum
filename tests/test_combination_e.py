from copy import deepcopy
import math

import pytest

from bulk_experiment import build_experiment
from combination_e import (BALANCES, attach_e_experiment, build_e_experiment, quality,
                           select_mmr, similarity)
from combination_d import similarity as d_similarity
from common import read_json, write_json
from pick import GOALS


def item(name, role='main', grams=150):
    return {'id': name, 'name': name, 'role': role, 'weight_g': grams}


def plate(score, *items):
    return {'score': {'total': score}, 'title': ' + '.join(i['name'] for i in items),
            'items': list(items), 'total': {'weight_g': sum(i['weight_g'] for i in items)}}


def test_empty_accompaniments_do_not_inflate_similarity_and_identity_remains_one():
    a = plate(1, item('A'), item('B'), item('C'))
    b = plate(.9, item('A'), item('B'), item('D'))
    assert d_similarity(a, b)['total'] == pytest.approx(.8 * 2/3 + .2)
    assert similarity(a, b)['total'] == pytest.approx(2/3)
    assert similarity(a, b)['accompaniment'] is None
    assert similarity(a, a)['total'] == pytest.approx(1)
    assert similarity(a, b) == similarity(b, a)
    assert similarity(plate(1, item('A')), plate(1, item('Z')))['total'] == 0


def test_core_swaps_remain_different_and_portions_do_not_manufacture_novelty():
    rice = item('Rice', 'side')
    a = plate(1, item('Chicken'), rice)
    b = plate(.99, item('Kofte'), rice)
    assert similarity(a, b)['total'] == pytest.approx(.2)
    c = plate(.98, item('Chicken', grams=450), item('Rice', 'side', 300))
    assert similarity(a, c)['total'] == pytest.approx(1)


def test_bounded_quality_preserves_score_gaps_without_menu_min_max_stretching():
    assert quality(40, 40) == 1
    assert quality(-40, -40) == 1
    assert quality(39.995, 40) > .99
    assert quality(-40.01, -40) == pytest.approx(quality(39.99, 40))
    assert quality(-10000, 40) == 0
    with pytest.raises(ValueError):quality(math.nan, 40)
    with pytest.raises(ValueError):quality(41, 40)


def test_soft_penalty_allows_high_overlap_and_balance_changes_the_winner():
    pool = [plate(1, item('Chicken'), item('Rice', 'side')),
            plate(.99, item('Chicken'), item('Pasta', 'side')),
            plate(.7, item('Kofte'), item('Rice', 'side')),
            plate(.2, item('Tofu'))]
    original = deepcopy(pool)
    assert similarity(pool[0], pool[1])['total'] > .65
    high, _ = select_mmr(pool, .95)
    varied, _ = select_mmr(pool, .65)
    assert [p['preference_rank'] for p in high][:2] == [1, 2]
    assert [p['preference_rank'] for p in varied][:2] == [1, 3]
    assert pool == original
    assert len(high) == 4  # No hard exclusion or padding.
    assert [p['preference_rank'] for p in select_mmr(pool, 1)[0]] == [1, 2, 3, 4]
    for bad in (-.1, 1.1, math.nan):
        with pytest.raises(ValueError):select_mmr(pool, bad)


def test_every_step_maximizes_mmr_against_all_previously_selected_plates():
    pool = [plate(1 - i * .05, item(f'Core {i % 3}'), item(f'Side {i}', 'side')) for i in range(12)]
    selected, steps = select_mmr(pool, .8)
    chosen = []
    for p, step in zip(selected, steps):
        assert p['preference_rank'] not in chosen
        if chosen:
            values = []
            for rank, candidate in enumerate(pool, 1):
                if rank in chosen:continue
                sim = max(similarity(candidate, pool[r-1])['total'] for r in chosen)
                values.append(.8 * quality(candidate['score']['total'], 1) - .2 * sim)
            assert step['value'] == pytest.approx(max(values))
        chosen.append(p['preference_rank'])
    assert len(selected) == 5
    assert select_mmr(pool, .8) == (selected, steps)
    assert select_mmr([], .8) == ([], [])


def test_e_preserves_all_goal_diet_candidates_and_a_to_d(config, fixture_menu, monkeypatch):
    def bomb(*args, **kwargs):raise AssertionError('E must not call a model')
    monkeypatch.setattr('combination_c.generate_json', bomb)
    menu, tags = fixture_menu
    ranking = build_experiment(menu, tags, config, goals=GOALS, top_k=100)
    a = {'campus': 'arcisstr', 'variants': {'unchanged': True}, 'experiments': {'combination_d': {'unchanged': True}}}
    before = deepcopy(a)
    result, audit = attach_e_experiment(a, ranking)
    assert a == before and result['experiments']['combination_d'] == before['experiments']['combination_d']
    assert result['variants'] == a['variants']
    e = result['experiments']['combination_e']
    assert set(e['balances']) == set(BALANCES)
    for balance in e['balances'].values():
        assert len(balance['variants']) == 18
        for key, v in balance['variants'].items():
            pool = ranking['variants'][key]['plates']
            assert len(v['plates']) == min(5, len(pool))
            if pool:assert v['plates'][0]['preference_rank'] == 1
            for p in v['plates']:
                original = pool[p['preference_rank'] - 1]
                assert p['items'] == original['items'] and p['total'] == original['total'] and p['score'] == original['score']
                assert p['total']['non_soup_weight_g'] <= 900
                if key.endswith('_vegan'):assert all(i['is_vegan'] for i in p['items'])
    assert set(audit['variants']) == set(ranking['variants'])
    garching = {**a, 'campus': 'garching'}
    assert attach_e_experiment(garching, ranking) == (garching, None)


def test_rescore_generates_mmr_choices_and_audit_without_new_models(tmp_path, fixture_menu):
    from rescore_cached import rescore
    menu, tags = fixture_menu;day = menu['date']
    write_json(tmp_path / 'data/week.json', {'week_start': day, 'days': [{'date': day}]})
    write_json(tmp_path / 'data/menus' / f'{day}.json', menu)
    write_json(tmp_path / 'data/dish_cache.json', tags)
    rescore(tmp_path)
    v = read_json(tmp_path / 'data/days' / f'{day}.json')
    assert v['experiments']['combination_e']['method'] == 'mmr_simple_overlap'
    assert read_json(tmp_path / 'label/e/data/index.json')['days'] == [{'date': day, 'file': day + '.json'}]
    assert read_json(tmp_path / 'label/e/data' / f'{day}.json')['variants']['bulk_all']['candidates']
