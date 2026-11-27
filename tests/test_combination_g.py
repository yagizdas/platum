from copy import deepcopy
import pytest

from combination_e import BALANCES
from combination_f import attach_f_experiment, build_f_experiment
from combination_g import attach_g_experiment, build_g_experiment
from common import read_json, write_json
from rescore_cached import rescore


def test_g_uses_full_f_pool_without_changing_f_or_accepting_rejected_plates(config, fixture_menu):
    menu, cache = fixture_menu
    f = build_f_experiment(menu, cache, config)
    ranking = build_f_experiment(menu, cache, config, top_k=100)
    before = deepcopy(ranking)
    a = {'variants': {'original': True}, 'experiments': {'combination_f': f}}
    result, audit = attach_g_experiment(a, ranking)
    assert ranking == before and a['experiments'] == {'combination_f': f}
    assert result['experiments']['combination_f'] == f
    g = result['experiments']['combination_g']
    assert g['method'] == 'goal_fit_mmr_v2'
    assert g['dataset_id'] == f['dataset_id'] and g['acceptability_filter'] == 'goal_fit_v2'
    assert set(g['balances']) == set(BALANCES)
    assert any(len(v['plates']) > 5 for v in ranking['variants'].values())
    for key, ranked in ranking['variants'].items():
        assert ranked['plates'][:5] == f['variants'][key]['plates']
        assert len(audit['variants'][key]['candidates']) == len(ranked['plates'])
        for balance in g['balances'].values():
            selected = balance['variants'][key]['plates']
            assert len(selected) == min(5, len(ranked['plates']))
            if selected:assert selected[0]['items'] == ranked['plates'][0]['items']
            for p in selected:
                original = ranked['plates'][p['preference_rank'] - 1]
                assert p['items'] == original['items'] and p['total'] == original['total']
                assert p['score'] == original['score'] and p['score']['eligible']
                assert p['candidate_id'].startswith('g') and p['picked_by'] == 'goal_fit_mmr_v2'
                assert p['total']['non_soup_weight_g'] <= 900
    assert attach_f_experiment({}, menu, cache, config, ranking=ranking)['experiments']['combination_f'] == f
    garching = {**a, 'campus': 'garching'}
    assert attach_g_experiment(garching, ranking) == (garching, None)


def test_g_diversifies_without_padding_or_modifying_nutrition():
    def p(score, name, extra):
        return {'score': {'total': score, 'eligible': True}, 'items': [{'id': name, 'role': 'main', 'weight_g': 150},
            {'id': extra, 'role': 'side', 'weight_g': 150}], 'total': {'kcal': 500}}
    pool = [p(1-i*.01, 'chicken', 'side'+str(i)) for i in range(5)] + [p(.8, 'tofu', 'side0'), p(.7, 'beans', 'side0')]
    ranking = {'method': 'learned_goal_fit_v2', 'dataset_id': 'test', 'max_dishes': 4, 'max_non_soup_weight_g': 900,
               'variants': {'cut_all': {'state': 'ready', 'plates': pool}, 'budget_all': {'state': 'unavailable', 'plates': [], 'message': 'No accepted plates.'}}}
    g, audit = build_g_experiment(ranking)
    selected = g['balances']['balanced']['variants']['cut_all']['plates']
    assert selected[0]['preference_rank'] == 1
    assert any(p['preference_rank'] > 5 for p in selected)
    assert not g['balances']['balanced']['variants']['budget_all']['plates']
    assert g['balances']['balanced']['variants']['budget_all']['message'] == 'No accepted plates.'
    assert len({p['candidate_id'] for p in selected}) == len(selected)
    rejected = deepcopy(ranking)
    rejected['variants']['cut_all']['plates'][0]['score']['eligible'] = False
    with pytest.raises(ValueError):build_g_experiment(rejected)


def test_rescore_generates_g_audit_for_all_f_contexts(tmp_path, config, fixture_menu):
    menu, cache = fixture_menu
    day = menu['date']
    write_json(tmp_path / 'data/week.json', {'week_start': day, 'days': [{'date': day}]})
    write_json(tmp_path / 'data/menus' / f'{day}.json', menu)
    write_json(tmp_path / 'data/dish_cache.json', cache)
    rescore(tmp_path)
    payload = read_json(tmp_path / 'data/days' / f'{day}.json')
    assert 'combination_g' in payload['experiments']
    audit = read_json(tmp_path / 'label/g/data' / f'{day}.json')
    assert set(audit['variants']) == set(payload['experiments']['combination_f']['variants'])
    assert read_json(tmp_path / 'label/g/data/index.json')['days'] == [{'date': day, 'file': day + '.json'}]
