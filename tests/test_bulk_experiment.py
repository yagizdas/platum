import copy
import itertools

from bulk_experiment import attach_experiment, build_experiment, exhaustive_candidates, search_space
from common import dish_id, normalize
from pair import food
from pick import portion_options, valid_plate


def four_mains(make_dish):
    dishes, cache = [], {}
    for index in range(4):
        d, t = make_dish(f'Main {index}', vegan=index < 2, piece=True, piece_g=200, kcal=100, protein=10)
        dishes.append(d)
        cache[normalize(d['name'])] = t
    return {'state': 'open', 'dishes': dishes, 'campus': 'arcisstr'}, cache


def test_exhaustive_search_visits_every_one_to_four_dish_set(config, make_dish):
    menu, cache = four_mains(make_dish)
    items = [food(d, cache) for d in menu['dishes']]
    options = [portion_options(i, i, config, paired=True) for i in items]
    results = list(exhaustive_candidates(options, config))
    expected = {frozenset(dish_id(i) for i in group) for size in range(1, 5)
                for group in itertools.combinations(items, size)}
    assert {frozenset(dish_id(i) for i in p['items']) for p in results} == expected
    assert len(results) == 15
    assert search_space(options)['portion_combinations'] == 15
    assert not valid_plate(results[-1]['items'], config)  # A retains its three-item maximum
    assert valid_plate(results[-1]['items'], config, max_items=4)


def test_b_ranks_with_existing_score_limits_and_diet_filters(config, make_dish, monkeypatch):
    menu, cache = four_mains(make_dish)
    def no_model(*args, **kwargs):
        raise AssertionError('B must not call a meal-proposal or copy model')
    monkeypatch.setattr('proposals.daily_proposals', no_model)
    monkeypatch.setattr('judge.choose_variants', no_model)
    b = build_experiment(menu, cache, config)
    first = b['variants']['bulk_all']['plates'][0]
    assert len(first['items']) == 4  # This fixture's optimum is all four mains.
    assert first['total']['kcal'] == 800
    assert first['total']['protein_g'] == 80
    assert first['total']['price_cents'] == 720
    for profile, variant in b['variants'].items():
        for plate in variant['plates']:
            assert plate['total']['price_cents'] <= config['plate_maximums']['bulk']['price_cents']
            assert plate['total']['kcal'] <= config['plate_maximums']['bulk']['kcal']
            assert len({i['id'] for i in plate['items']}) == len(plate['items']) <= 4
            if profile in {'bulk_vegan', 'bulk_vegetarian'}:
                assert all(i['is_vegan'] for i in plate['items'])


def test_attaching_b_preserves_every_a_field_and_does_not_modify_garching(config, make_dish):
    menu, cache = four_mains(make_dish)
    a = {'campus': 'arcisstr', 'variants': {'bulk_all': {'plates': [{'title': 'Existing winner'}]}},
         'extras': {'all': ['existing extra']}, 'filtered_variants': {'unchanged': True}}
    original = copy.deepcopy(a)
    attached = attach_experiment(a, menu, cache, config)
    assert a == original
    assert {k: v for k, v in attached.items() if k != 'experiments'} == original
    garching = {**a, 'campus': 'garching'}
    assert attach_experiment(garching, menu, cache, config) is garching


def test_large_or_incomplete_search_does_not_break_a(config, make_dish):
    menu, cache = four_mains(make_dish)
    b = build_experiment(menu, cache, config, max_combinations=1)
    assert b['stats']['valid_candidates'] == 0
    assert b['variants']['bulk_all']['state'] == 'unavailable'
    assert 'too large' in b['variants']['bulk_all']['message']
    del cache[normalize(menu['dishes'][0]['name'])]
    b = build_experiment(menu, cache, config)
    assert b['variants']['bulk_all']['state'] == 'unavailable'
    assert 'nutrition estimates' in b['variants']['bulk_all']['message']


def test_staging_rescore_adds_b_and_preserves_a_recommendations(tmp_path, fixture_menu):
    from campuses import campus_config
    from common import load_config, read_json, write_json
    from pick import build_today
    from rescore_cached import rescore
    menu, cache = fixture_menu
    config = campus_config(load_config(), 'arcisstr')
    day = menu['date']
    baseline = build_today(menu, cache, config, no_llm=True)
    write_json(tmp_path / 'data/week.json', {'week_start': day, 'days': [{'date': day}]})
    write_json(tmp_path / 'data/menus' / f'{day}.json', menu)
    write_json(tmp_path / 'data/dish_cache.json', cache)
    rescore(tmp_path)
    updated = read_json(tmp_path / 'data/days' / f'{day}.json')
    assert updated['variants'] == baseline['variants']
    assert updated['filtered_variants'] == baseline['filtered_variants']
    assert updated['extras'] == baseline['extras']
    assert updated['experiments']['bulk_ab']['stats']['valid_candidates'] > 0
    assert read_json(tmp_path / 'data/today.json') == updated
