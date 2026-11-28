"""The public recommendation policy: Bulk E/Balanced; Cut and Budget G/Quality first."""
from bulk_experiment import build_experiment
from combination_d import SCAN_K
from combination_e import BALANCES, select_mmr
from combination_f import build_f_experiment
from diet_filters import FILTERS

POLICY = {'bulk': {'method': 'e', 'balance': 'balanced'},
          'cut': {'method': 'g', 'balance': 'quality'},
          'budget': {'method': 'g', 'balance': 'quality'}}
EMPTY_PROPOSALS = {goal+'_'+profile: [] for goal in POLICY for profile in ('all', 'vegan')}


def apply_recommendations(payload, menu, cache, config):
    policy = config['recommendations']
    if policy != POLICY:raise ValueError('Unsupported public recommendation policy')
    bulk = build_experiment(menu, cache, config, goals=('bulk',), top_k=SCAN_K)
    goal_fit = build_f_experiment(menu, cache, config, top_k=SCAN_K)
    result = {k:v for k,v in payload.items() if k not in ('experiments', 'scoring', 'nutrition_note')}
    result.update(variants={}, filtered_variants={}, recommendation_policy=policy)
    for goal, setting in policy.items():
        ranking = bulk if goal == 'bulk' else goal_fit
        for profile in ('all', 'vegan', *FILTERS):
            key = goal+'_'+profile
            ranked = ranking['variants'][key]
            plates, _ = select_mmr(ranked['plates'], BALANCES[setting['balance']]['lambda'],
                                   candidate_prefix=setting['method'],
                                   picked_by='mmr' if goal == 'bulk' else 'goal_fit_mmr_v2')
            public = []
            for p in plates:
                item = {k:v for k,v in p.items() if k not in ('candidate_id', 'preference_rank', 'mmr')}
                item['reason'] = None
                public.append(item)
            state = 'ready' if public else ranked['state']
            message = '' if public else ('No menu is published for this date.' if state == 'closed' else
                         'These lunch ideas are waiting for nutrition estimates.' if payload.get('missing_tags') else
                         'No lunch combination fits this goal and these dietary filters today.')
            variant = {'state':state, 'plates':public, 'message':message,
                       'goal':goal, 'vegan':profile=='vegan', 'relaxed':False, 'note':None}
            target = 'variants' if profile in ('all', 'vegan') else 'filtered_variants'
            result[target][key] = variant
    return result
