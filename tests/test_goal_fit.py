"""Staging F must use new labels without modifying the existing comparisons."""
from copy import deepcopy
import math

import pytest

from combination_f import attach_f_experiment, build_f_experiment
from goal_fit import FEATURES, features, predict, predict_ensemble
from pick import candidates


def test_portable_trees_use_declared_branch_boundary():
    model={'intercept':.2,'learning_rate':.5,'trees':[{'left':[1,-1,-1],'right':[2,-1,-1],
        'feature':[0,-2,-2],'threshold':[3.,-2.,-2.],'value':[0.,-1.,2.]}]}
    assert predict_ensemble(model,[3.])==pytest.approx(-.3)
    assert predict_ensemble(model,[3.01])==pytest.approx(1.2)


def test_feature_parity_with_frozen_training_snapshots(config,fixture_menu):
    from label.v2.build_data import serialize
    menu,cache=fixture_menu
    for p in list(candidates(menu['dishes'],cache,config))[:30]:
        assert features(p)==features(serialize(p,config))
        assert len(features(p))==len(FEATURES)
        for goal in ('cut','budget'):
            s=predict(p,goal)
            assert math.isfinite(s['total']) and 0<=s['acceptability']<=1


def test_goal_fit_does_not_pad_with_rejected_plates_or_change_other_methods(config,fixture_menu,monkeypatch):
    menu,cache=fixture_menu
    original={'campus':'arcisstr','variants':{'keep':True},'experiments':{'bulk_ab':{'keep':True}}}
    before=deepcopy(original)
    monkeypatch.setattr('combination_f.predict',lambda *args:{'total':1.,'acceptability':.1,'eligible':False})
    result=attach_f_experiment(original,menu,cache,config)
    assert original==before and result['variants']==before['variants']
    assert result['experiments']['bulk_ab']==before['experiments']['bulk_ab']
    for v in result['experiments']['combination_f']['variants'].values():
        assert not v['plates'] and v['state']=='unavailable'
    garching={**original,'campus':'garching'}
    assert attach_f_experiment(garching,menu,cache,config) is garching


def test_goal_fit_searches_all_physical_candidates_and_preserves_diet_constraints(config,fixture_menu,monkeypatch):
    menu,cache=fixture_menu
    # No new nutritional floor/ceiling is invented by F; learned acceptance decides.
    config['plate_minimums']={'cut':{'kcal':100000},'budget':{'kcal':100000}}
    monkeypatch.setattr('combination_f.predict',lambda p,*args:{'total':p['protein'],'acceptability':.9,'eligible':True})
    result=build_f_experiment(menu,cache,config)
    assert len(result['variants'])==12 and all(not k.startswith('bulk') for k in result['variants'])
    for key,v in result['variants'].items():
        assert len(v['plates'])<=5
        identities=[]
        for p in v['plates']:
            assert p['total']['non_soup_weight_g']<=900
            assert 1<=len(p['items'])<=4
            identities.append(tuple(sorted(i['id'] for i in p['items'])))
            if key.endswith('_vegan'):assert all(i['is_vegan'] for i in p['items'])
            if key.endswith('_no_beef'):assert all('beef' not in i['meat_types'] and 'unknown' not in i['meat_types'] for i in p['items'] if not i['is_vegan'] and i['diet'] not in ('vegan','vegetarian'))
        assert len(identities)==len(set(identities))
    assert result['variants']['cut_all']['plates']
