import json
from pathlib import Path

import pytest

from common import normalize, write_json
from label.v2.build_data import STRATEGIES, build, features, serialize
from pair import food
from pick import plate, portion_options


def test_v2_exports_macros_portions_and_meat_dish_weight(config, make_dish):
    d, tag = make_dish('Chicken in sauce', vegan=False)
    raw = food(d, {normalize(d['name']): tag})
    value = plate([portion_options(raw, raw, config)[1]])
    f = features(value)
    assert f['weight_g'] == f['meat_dish_weight_g'] == 300
    assert f['fat_g'] == 15
    assert f['fat_energy_pct'] == 22.5  # 15g * 9 / 600kcal
    assert f['dish_count'] == f['meat_dish_count'] == 1
    serialized = serialize(value, config)
    assert serialized['items'][0]['fat_g'] == 15
    assert serialized['items'][0]['count'] == 2
    assert serialized['items'][0]['weight_g'] == 300
    other = serialize(plate([portion_options(raw, raw, config)[0]]), config)
    assert other['id'] != serialized['id']  # Different portions remain separate learning examples.


def test_v2_does_not_count_unknown_diet_labels_as_confirmed_meat(config, make_dish):
    d, tag = make_dish('Potato salad', vegan=False, role='side')
    raw = food(d, {normalize(d['name']): tag})
    f = features(plate([portion_options(raw, raw, config)[0]]))
    assert f['meat_dish_weight_g'] == f['meat_dish_count'] == 0
    assert f['unknown_diet_weight_g'] == 150


def test_v2_build_is_frozen_reproducible_and_covers_one_to_four_dishes(tmp_path, config, make_dish):
    dishes, cache = [], {}
    for i in range(4):
        d, t = make_dish(f'Main {i}', vegan=i % 2 == 0, piece=True, piece_g=250, kcal=150, protein=10)
        dishes.append(d);cache[normalize(d['name'])] = t
    write_json(tmp_path / 'data/menus/2026-11-25.json', {'date': '2026-11-25', 'state': 'open', 'dishes': dishes})
    write_json(tmp_path / 'data/dish_cache.json', cache)
    a, b = build(tmp_path, config), build(tmp_path, config)
    assert a == b
    assert a['summary']['eligible_candidates'] == 15
    assert a['summary']['comparisons'] == 24
    assert set(a['summary']['dish_counts']) == {1, 2, 3, 4}
    assert set(a['summary']['strategies']) == set(STRATEGIES)
    pairs = a['days'][0]['pairs']
    assert len({tuple(sorted((p['a'], p['b']))) for p in pairs}) == len(pairs)
    ids = {p['id'] for p in a['days'][0]['plates']}
    assert all(p['a'] in ids and p['b'] in ids and p['a'] != p['b'] for p in pairs)
    cache.pop(next(iter(cache)))
    write_json(tmp_path / 'data/dish_cache.json', cache)
    with pytest.raises(ValueError, match='No complete Arcisstraße'):
        build(tmp_path, config)


def test_published_v2_dataset_has_consistent_portions_features_and_independent_queue():
    data = json.loads((Path(__file__).parents[1] / 'label/v2/data.json').read_text())
    assert data['schema_version'] == 2
    assert data['experiment'] == 'bulk-exhaustive-v2'
    assert len(data['queue']) == data['summary']['comparisons'] >= 300
    assert data['summary']['skipped_days'] == []
    for day in data['days']:
        for p in day['plates']:
            assert p['weight_g'] == sum(i['weight_g'] for i in p['items'])
            assert 1 <= p['dish_count'] == len(p['items']) <= 4
            assert p['fat_g'] == pytest.approx(sum(i['fat_g'] for i in p['items']), abs=.025)
            assert p['fat_energy_pct'] == pytest.approx(p['fat_g'] * 900 / p['kcal'], abs=.02)
            assert p['meat_dish_weight_g'] == sum(i['weight_g'] for i in p['items'] if set(i['meat_types']) - {'unknown', 'fish'})
            assert p['unknown_diet_weight_g'] == sum(i['weight_g'] for i in p['items'] if 'unknown' in i['meat_types'])
            assert 350 <= p['kcal'] <= 1500 and p['protein'] >= 25 and p['price'] <= 9
