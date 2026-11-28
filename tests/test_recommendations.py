from copy import deepcopy
from datetime import date
from unittest.mock import Mock

import pytest

from bulk_experiment import build_experiment
from campuses import campus_config, campus_data
from combination_e import build_e_experiment
from combination_f import build_f_experiment
from combination_g import build_g_experiment
from common import read_json, write_json, week_dates
from recommendations import POLICY, apply_recommendations
from rescore_cached import rescore
from weekly_batch import run_batch


@pytest.mark.parametrize('campus', ['arcisstr', 'garching'])
def test_public_variants_match_exact_e_balanced_and_g_quality_choices(config, fixture_menu, campus):
    menu, cache = fixture_menu
    cfg = campus_config(config, campus)
    menu = {**menu, 'campus':campus}
    original = {'schema_version':2, 'campus':campus, 'experiments':{'old':True}, 'scoring':{}, 'extras':{'all':[], 'vegan':[]}}
    expected_bulk, _ = build_e_experiment(build_experiment(menu, cache, cfg, goals=('bulk',), top_k=100))
    expected_goals, _ = build_g_experiment(build_f_experiment(menu, cache, cfg, top_k=100))
    result = apply_recommendations(original, menu, cache, cfg)
    assert result['recommendation_policy'] == POLICY
    assert 'experiments' not in result and 'scoring' not in result
    assert original['experiments'] == {'old':True}
    assert len(result['variants']) == 6 and len(result['filtered_variants']) == 12
    for key,v in {**result['variants'], **result['filtered_variants']}.items():
        goal = key.split('_')[0]
        expected = (expected_bulk if goal=='bulk' else expected_goals)['balances']['balanced' if goal=='bulk' else 'quality']['variants'][key]
        assert v['state'] == expected['state']
        assert [(p['items'],p['total']) for p in v['plates']] == [(p['items'],p['total']) for p in expected['plates']]
        for p in v['plates']:
            assert p['reason'] is None and 'mmr' not in p and 'preference_rank' not in p
            assert len(p['items'])<=4 and p['total']['non_soup_weight_g']<=900


@pytest.mark.parametrize('campus', ['arcisstr', 'garching'])
def test_rescore_publishes_fixed_policy_without_experiments_or_model_calls(tmp_path, fixture_menu, monkeypatch, campus):
    menu, cache = fixture_menu;day=menu['date'];data=campus_data(tmp_path,campus)
    write_json(data/'week.json', {'week_start':day, 'days':[{'date':day}]})
    write_json(data/'menus'/f'{day}.json', {**menu,'campus':campus})
    write_json(tmp_path/'data/dish_cache.json', cache)
    def bomb(*args,**kwargs):raise AssertionError('No LLM meal curation or proposals may run')
    monkeypatch.setattr('pick.daily_proposals',bomb)
    monkeypatch.setattr('pick.choose_variants',bomb)
    rescore(tmp_path,campus)
    result=read_json(data/'days'/f'{day}.json')
    assert result['recommendation_policy']==POLICY and 'experiments' not in result
    assert read_json(data/'today.json')==result
    assert not (tmp_path/'label/g/data/index.json').exists()


def test_weekly_generation_uses_fixed_methods_without_proposal_gate(tmp_path, config, fixture_menu, monkeypatch):
    menu,cache=fixture_menu;monday=date(2026,11,30)
    menus={d.isoformat():{**deepcopy(menu),'date':d.isoformat(),'published':True} for d in week_dates(monday,1)}
    write_json(tmp_path/'data/dish_cache.json',cache)
    def bomb(*args,**kwargs):raise AssertionError('Fixed recommendations must not call the proposal or copy LLM')
    monkeypatch.setattr('pick.daily_proposals',bomb);monkeypatch.setattr('pick.choose_variants',bomb)
    assert run_batch(monday,config,root=tmp_path,scraper=Mock(return_value=menus),tagger=Mock(),proposer=bomb)
    for d in menus:assert read_json(tmp_path/'data/days'/f'{d}.json')['recommendation_policy']==POLICY
    assert run_batch(monday,config,root=tmp_path,scraper=bomb,tagger=bomb,proposer=bomb)
