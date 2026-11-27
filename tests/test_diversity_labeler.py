from pathlib import Path
import math

from common import ROOT, load_config, read_json
from diversity_features import pair_features
from label.diversity.build_data import build, matches


def test_frozen_pilot_is_balanced_real_and_features_are_symmetric():
    data = read_json(ROOT / 'label/diversity/data.json')
    assert len(data['pairs']) == 100
    assert sorted(data['summary']['goals'].values()) == [33, 33, 34]
    assert data['summary']['dates'] >= 20
    assert set(data['summary']['strategies']) == {'core_swap', 'side_change', 'component_change', 'portion_change', 'rank_neighbors', 'explore'}
    plates = {p['id']: p for p in data['plates']}
    assert len({p['id'] for p in data['pairs']}) == 100
    for pair in data['pairs']:
        a, b = plates[pair['a']], plates[pair['b']]
        assert a['id'] != b['id']
        assert pair['features'] == pair_features(a, b, pair['goal']) == pair_features(b, a, pair['goal'])
        assert all(math.isfinite(v) for v in pair['features'].values())
        assert matches(pair['strategy'], a, b, pair['features'])
        for p in (a, b):
            assert 1 <= p['dish_count'] <= 4
            assert sum(i['weight_g'] for i in p['items'] if i['role'] != 'soup') <= 900
            assert p['weight_g'] == sum(i['weight_g'] for i in p['items'])
            assert all(i['name'] and i['id'] for i in p['items'])


def test_absent_groups_have_no_similarity_bonus_and_grams_remain_visible():
    data = read_json(ROOT / 'label/diversity/data.json')
    a = next(p for p in data['plates'] if all(i['role'] == 'main' for i in p['items']))
    f = pair_features(a, a, 'bulk')
    assert f['accompaniment_both_absent'] == 1
    assert f['accompaniment_identity_overlap'] == 0
    assert f['core_identity_overlap'] == 1 and f['core_gram_overlap'] == 1
    assert f['weight_g_min'] == a['weight_g']


def test_builder_is_reproducible_without_models(tmp_path, fixture_menu, monkeypatch):
    from common import write_json
    menu, cache = fixture_menu
    write_json(tmp_path / 'data/menus' / f"{menu['date']}.json", menu)
    write_json(tmp_path / 'data/dish_cache.json', cache)
    def bomb(*args, **kwargs):raise AssertionError('No model calls when creating a label queue')
    monkeypatch.setattr('combination_c.generate_json', bomb)
    one = build(tmp_path, load_config(), count=12)
    assert one == build(tmp_path, load_config(), count=12)
    assert len(one['pairs']) == 12 and one['summary']['goals'] == {'bulk': 4, 'cut': 4, 'budget': 4}
