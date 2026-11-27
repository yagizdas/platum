from copy import deepcopy

import pytest

from bulk_experiment import build_experiment
from combination_d import (CORE_WEIGHT, SCAN_K, SIMILARITY_THRESHOLD, attach_d_experiment,
                           build_d_experiment, component_group, select_distinct, similarity)
from common import read_json, write_json
from pick import GOALS


def item(name, role='main', grams=150, **kwargs):
    return {'id': name, 'name': name, 'role': role, 'weight_g': grams, **kwargs}


def plate(*items, score=10):
    return {'items': list(items), 'title': ' + '.join(i['name'] for i in items),
            'total': {'weight_g': sum(i['weight_g'] for i in items)}, 'score': {'total': score}}


def test_core_swaps_survive_shared_rice_and_pasta():
    rice, pasta = item('Rice', 'side'), item('Plain pasta', 'side')
    chicken = plate(item('Chicken'), rice, pasta)
    kofte = plate(item('Kofte'), rice, pasta)
    assert similarity(chicken, kofte)['total'] == pytest.approx(.2)
    selected, walked = select_distinct([chicken, kofte])
    assert len(selected) == 2 and all(r['decision'] == 'selected' for r in walked)
    # Even when pasta is a complete main dish, the meaningful core swap survives.
    pasta['role'] = 'main'
    assert similarity(chicken, kofte)['total'] == pytest.approx(.6)
    assert len(select_distinct([chicken, kofte])[0]) == 2


def test_same_cores_with_side_swaps_are_skipped():
    chicken = item('Chicken')
    a = plate(chicken, item('Rice', 'side'))
    b = plate(chicken, item('Potatoes', 'side'))
    assert similarity(a, b)['total'] == pytest.approx(.8)
    selected, walk = select_distinct([a, b, plate(item('Tofu'), item('Rice', 'side'))])
    assert [p['preference_rank'] for p in selected] == [1, 3]
    assert walk[1]['decision'] == 'skipped' and walk[1]['closest_selected_rank'] == 1


def test_portions_and_tiny_additions_do_not_manufacture_novelty():
    a = plate(item('Chicken', grams=150), item('Rice', 'side'))
    b = plate(item('Chicken', grams=450), item('Rice', 'side', 300))
    assert similarity(a, b)['total'] == pytest.approx(1)
    b['items'].append(item('Extra core', grams=20))
    assert similarity(a, b)['total'] > .9
    assert len(select_distinct([a, b])[0]) == 1
    assert component_group(item('Rice', standing=True)) == 'accompaniment'
    assert component_group(item('Lasagna')) == 'core'
    assert component_group(item('Soup', 'soup')) == 'accompaniment'


def test_symmetry_empty_groups_and_exact_threshold():
    a = plate(item('A')); b = plate(item('B'))
    assert similarity(a, a)['total'] == pytest.approx(1)
    assert similarity(a, b) == similarity(b, a)
    assert similarity(a, b)['total'] == pytest.approx(.2)  # Both lack accompaniments.
    # Core dice = .5625, accompaniments = 1 -> total exactly .65.
    b = plate(item('A', grams=150 * 9 / 23))
    assert similarity(a, b)['total'] == pytest.approx(SIMILARITY_THRESHOLD)
    assert len(select_distinct([a, b])[0]) == 1


def test_checks_every_prior_pick_not_only_previous_one_and_keeps_rank_order():
    a, b = plate(item('A')), plate(item('B'))
    selected, walk = select_distinct([a, b, deepcopy(a), plate(item('C'))])
    assert [p['preference_rank'] for p in selected] == [1, 2, 4]
    assert walk[2]['closest_selected_rank'] == 1
    assert walk[2]['decision'] == 'skipped'


def test_scans_beyond_twenty_stops_at_five_and_never_pads():
    first = plate(item('Repeated'))
    pool = [first] * 25 + [plate(item(f'New {i}')) for i in range(8)]
    selected, walk = select_distinct(pool)
    assert [p['preference_rank'] for p in selected] == [1, 26, 27, 28, 29]
    assert len(walk) == 29
    selected, walk = select_distinct([first] * SCAN_K + [plate(item('Beyond limit'))])
    assert len(selected) == 1 and len(walk) == SCAN_K


def test_d_is_deterministic_preserves_candidates_and_all_goal_diets(config, fixture_menu, monkeypatch):
    def bomb(*args, **kwargs):raise AssertionError('D must never call an LLM')
    monkeypatch.setattr('combination_c.generate_json', bomb)
    menu, cache = fixture_menu
    ranking = build_experiment(menu, cache, config, goals=GOALS, top_k=SCAN_K)
    before = deepcopy(ranking)
    d, audit = build_d_experiment(ranking)
    assert build_d_experiment(ranking) == (d, audit)
    assert ranking == before and len(d['variants']) == 18
    assert d['core_weight'] == CORE_WEIGHT
    for key, v in d['variants'].items():
        assert len(v['plates']) <= 5
        for i, p in enumerate(v['plates']):
            source = ranking['variants'][key]['plates'][p['preference_rank'] - 1]
            assert p['items'] == source['items'] and p['total'] == source['total'] and p['score'] == source['score']
            assert p['total']['non_soup_weight_g'] <= 900
            assert all(similarity(p, earlier)['total'] < SIMILARITY_THRESHOLD for earlier in v['plates'][:i])
            if key.endswith('_vegan'):assert all(i['is_vegan'] for i in p['items'])
    a = {'campus': 'arcisstr', 'variants': {'untouched': True}, 'experiments': {'existing': True}}
    attached, _ = attach_d_experiment(a, ranking)
    assert attached['variants'] == a['variants'] and attached['experiments']['existing'] is True
    assert 'combination_d' not in a['experiments']
    garching = {**a, 'campus': 'garching'}
    assert attach_d_experiment(garching, ranking) == (garching, None)


def test_rescore_writes_d_and_preserves_the_same_b_c_shortlists(tmp_path, fixture_menu, config):
    from rescore_cached import rescore
    menu, cache = fixture_menu;day = menu['date']
    write_json(tmp_path / 'data/week.json', {'week_start': day, 'days': [{'date': day}]})
    write_json(tmp_path / 'data/menus' / f'{day}.json', menu)
    write_json(tmp_path / 'data/dish_cache.json', cache)
    old = build_experiment(menu, cache, config, goals=GOALS, top_k=20)
    rescore(tmp_path)
    public = read_json(tmp_path / 'data/days' / f'{day}.json')
    for key, v in old['variants'].items():
        assert public['experiments']['bulk_ab']['variants'][key]['plates'] == v['plates'][:5]
        audit = read_json(tmp_path / 'label/c/data' / f'{day}.json')
        assert [p['items'] for p in audit['variants'][key]['candidates']] == [p['items'] for p in v['plates']]
    assert len(public['experiments']['combination_d']['variants']) == 18
    assert read_json(tmp_path / 'label/d/data/index.json')['days'] == [{'date': day, 'file': day + '.json'}]
