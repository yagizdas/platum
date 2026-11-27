"""Train staging F from separately attributed proxy/human labels; requires scikit-learn."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.tree import DecisionTreeRegressor

from bulk_experiment import exhaustive_candidates
from common import ROOT, dish_id, load_config, read_json, write_json
from goal_fit import FEATURES, features, predict
from label.v2.build_data import serialize
from pair import food
from pick import portion_options

PARAMS = dict(n_estimators=100, learning_rate=.05, max_depth=2, min_samples_leaf=5, random_state=20261127)


def recover(raw, source, config):
    def key(p):return (tuple(sorted(p['id'].split('+'))),round(p['kcal'],2),round(p['protein'],2),round(p['price'],2))
    wanted=defaultdict(set)
    for r in raw:
        for s in ('a','b'):wanted[r['date']].add(key(r['plate_'+s]))
    cache=read_json(source/'data/dish_cache.json');matches={}
    for day, keys in sorted(wanted.items()):
        menu=read_json(source/'data/menus'/f'{day}.json')
        foods=[food(i,cache) for i in menu['dishes']]
        options=[portion_options(i,i,config,paired=True) for i in foods]
        found=defaultdict(dict)
        for p in exhaustive_candidates(options,config):
            k=(tuple(sorted(dish_id(i) for i in p['items'])),round(p['kcal'],2),round(p['protein'],2),round(p['price_cents']/100,2))
            if k not in keys:continue
            snap=serialize(p,config);snap.pop('baseline_score')
            found[k][json.dumps(snap,sort_keys=True)]=snap
        for k, values in found.items():
            if len(values)==1:matches[day,k]=next(iter(values.values()))
    result=[]
    for r in raw:
        a=matches.get((r['date'],key(r['plate_a'])));b=matches.get((r['date'],key(r['plate_b'])))
        if a is None or b is None:continue
        # A decisive human label says the winner is usable; it does NOT say the loser is unusable.
        result.append({**r,'plate_a':a,'plate_b':b,'annotation_source':'human_direct',
                       'acceptable_a':False if r['winner']=='both_bad' else True if r['winner']=='a' else None,
                       'acceptable_b':False if r['winner']=='both_bad' else True if r['winner']=='b' else None})
    return result


def portable_tree(t):
    t=t.tree_
    return {'left':t.children_left.tolist(),'right':t.children_right.tolist(),
            'feature':t.feature.tolist(),'threshold':t.threshold.tolist(),'value':t.value[:,0,0].tolist()}


def fit(rows):
    sx=[];sy=[];sw=[];pairs=[];index={};vectors=[]
    def register(p):
        v=tuple(features(p))
        if v not in index:index[v]=len(vectors);vectors.append(v)
        return index[v]
    for r in rows:
        w=2. if r['annotation_source']=='human_direct' else 1.
        for side in ('a','b'):
            known=r['acceptable_'+side]
            if known is not None:
                sx.append(features(r['plate_'+side]));sy.append(int(known));sw.append(w)
        if r['winner']!='both_bad':
            winner=r['winner'];loser='b' if winner=='a' else 'a'
            pairs.append((register(r['plate_'+winner]),register(r['plate_'+loser]),w))
    accept=GradientBoostingClassifier(**PARAMS).fit(sx,sy,sample_weight=sw)
    prior=accept.init_.class_prior_[1]
    accept_model={'intercept':float(math.log(prior/(1-prior))),'learning_rate':accept.learning_rate,
                  'trees':[portable_tree(t) for t in accept.estimators_[:,0]]}
    # Shared scalar utility, optimized by pairwise logistic gradients. No target calories,
    # target protein or invented numeric utilities are assigned to human preferences.
    x=np.asarray(vectors,dtype=np.float32);utility=np.zeros(len(x));trees=[]
    for _ in range(PARAMS['n_estimators']):
        gradient=np.zeros(len(x));curvature=np.zeros(len(x))
        for winner,loser,w in pairs:
            q=1/(1+math.exp(max(-40,min(40,utility[winner]-utility[loser]))))
            gradient[winner]+=w*q;gradient[loser]-=w*q
            curvature[winner]+=w*q*(1-q);curvature[loser]+=w*q*(1-q)
        weight=curvature+1.  # Leaf shrinkage limits jumps from a handful of examples.
        tree=DecisionTreeRegressor(max_depth=PARAMS['max_depth'],min_samples_leaf=PARAMS['min_samples_leaf'],random_state=PARAMS['random_state'])
        tree.fit(x,gradient/weight,sample_weight=weight)
        utility+=PARAMS['learning_rate']*tree.predict(x);trees.append(portable_tree(tree))
    model={'acceptability':accept_model,'preference':{'intercept':0.,'learning_rate':PARAMS['learning_rate'],'trees':trees},
           'acceptability_threshold':.5}
    # Check deployed pure-Python inference against the actual fitted trees.
    package={'goals':{rows[0]['goal']:model}}
    for p in [r['plate_a'] for r in rows][:30]:
        expected=accept.predict_proba([features(p)])[0,1]
        assert abs(predict(p,rows[0]['goal'],package)['acceptability']-expected)<1e-7
    return model


def decisions(model, rows):
    result=[]
    for r in rows:
        a=predict(r['plate_a'],r['goal'],{'goals':{r['goal']:model}})
        b=predict(r['plate_b'],r['goal'],{'goals':{r['goal']:model}})
        winner='both_bad' if not(a['eligible'] or b['eligible']) else 'a' if not b['eligible'] else 'b' if not a['eligible'] else 'a' if a['total']>=b['total'] else 'b'
        result.append({'date':r['date'],'actual':r['winner'],'predicted':winner})
    return result


def metrics(rows):
    decisive=[r for r in rows if r['actual']!='both_bad'];bad=[r for r in rows if r['actual']=='both_bad']
    return {'n':len(rows),'correct':sum(r['actual']==r['predicted'] for r in rows),
            'decisive_n':len(decisive),'decisive_correct':sum(r['actual']==r['predicted'] for r in decisive),
            'both_bad_n':len(bad),'both_bad_correct':sum(r['predicted']=='both_bad' for r in bad)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy',type=Path,required=True);parser.add_argument('--human',type=Path,required=True)
    parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();proxy=read_json(args.proxy)
    rows=proxy['records'];assert all(r['annotation_source']=='assistant_proxy' and r['is_human_judgment'] is False for r in rows)
    raw=read_json(args.human);human=recover(raw,args.source_root,load_config())
    result={'schema_version':1,'features':list(FEATURES),'method':'gradient_boosted_pairwise_utility_and_acceptability',
            'status':'staging_experiment','source_dataset':proxy['dataset_id'],'training_parameters':PARAMS,
            'human_weight':2,'assistant_weight':1,'goals':{}}
    validation={}
    for goal in ('cut','budget'):
        subset=[r for r in rows+human if r['goal']==goal];h=[r for r in human if r['goal']==goal];held=[]
        # Human judgments held out by menu date; all labels from the test date are purged.
        # Budget has no raw human labels, so its date folds only measure proxy imitation.
        targets=h or [r for r in rows if r['goal']==goal]
        for date in sorted({r['date'] for r in targets}):
            train=[r for r in subset if r['date']!=date];test=[r for r in targets if r['date']==date]
            held+=decisions(fit(train),test)
        validation[goal]={'evaluation_source':'human_direct' if h else 'assistant_proxy',
                          'leave_one_menu_date_out':metrics(held),'training_comparisons':len(subset),
                          'human_comparisons':len(h),'assistant_comparisons':sum(r['annotation_source']=='assistant_proxy' for r in subset)}
        result['goals'][goal]=fit(subset)
    validation['human_recovery']={'available':len(raw),'exactly_recovered':len(human),'unrecovered_or_ambiguous':len(raw)-len(human)}
    validation['limitations']=['Budget is validated against AI proxy labels only.','Recurring recipes can overlap between menu dates.',
                               'Classifier probabilities are not calibrated confidence estimates.','Small training set; staging experiment, not a proven replacement.']
    result['validation']=validation
    write_json(args.output,result);print(json.dumps(validation,indent=2))

if __name__=='__main__':main()
