"""Staging F: exhaustive Cut/Budget search with learned preference and rejection."""
from bulk_experiment import MAX_PORTION_COMBINATIONS, exhaustive_candidates, non_soup_weight_g, search_space
from common import dish_id, normalize
from diet_filters import FILTERS, allows
from goal_fit import load_models, predict
from pair import food
from pick import plate_result, portion_options

GOALS = ('cut', 'budget')


def build_f_experiment(menu, cache, config, *, top_k=5):
    if type(top_k) is not int or top_k < 1:raise ValueError('top_k must be a positive integer')
    missing = [d['name'] for d in menu['dishes'] if normalize(d['name']) not in cache]
    foods = [food(d, cache) for d in menu['dishes']] if menu['state']=='open' and not missing else []
    options = [portion_options(i, i, config, paired=True) for i in foods]
    stats = search_space(options);too_large=stats['portion_combinations']>MAX_PORTION_COMBINATIONS
    models = load_models()
    profiles = ['all', 'vegan', *FILTERS]
    pools = {g+'_'+p:[] for g in GOALS for p in profiles}
    stats.update(valid_candidates=0, accepted={g:0 for g in GOALS})
    for p in ([] if too_large else exhaustive_candidates(options,config)):
        if non_soup_weight_g(p)>900:continue
        stats['valid_candidates']+=1
        eligible_profiles=['all']
        if all(i.get('is_vegan') is True for i in p['items']):eligible_profiles.append('vegan')
        eligible_profiles += [profile for profile in FILTERS if all(allows(i,profile) for i in p['items'])]
        for goal in GOALS:
            score=predict(p,goal,models)
            if not score['eligible']:continue
            stats['accepted'][goal]+=1
            scored={**p,'score':score}
            for profile in eligible_profiles:pools[goal+'_'+profile].append(scored)
    variants={}
    for key, pool in pools.items():
        pool.sort(key=lambda p:(-p['score']['total'],p['price_cents'],tuple(sorted((dish_id(i),i['count']) for i in p['items']))))
        seen=set();selected=[]
        for p in pool:
            identities=tuple(sorted(dish_id(i) for i in p['items']))
            if identities in seen:continue
            seen.add(identities)
            result=plate_result(p)
            result['total'].update(non_soup_weight_g=non_soup_weight_g(p),soup_weight_g=p['weight_g']-non_soup_weight_g(p))
            result.update(picked_by='goal_fit_v2',reason=None)
            selected.append(result)
            if len(selected)==top_k:break
        state='ready' if selected else menu['state'] if menu['state']!='open' else 'unavailable'
        variants[key]={'state':state,'plates':selected,'message':'' if selected else
                       'F is waiting for nutrition estimates.' if missing else 'This menu exceeds the exhaustive search limit.' if too_large else
                       'No combination passes the experimental goal-fit model for these filters. Try another method.'}
    return {'method':'learned_goal_fit_v2','dataset_id':models['source_dataset'],'max_dishes':4,
            'max_non_soup_weight_g':900,'stats':stats,'variants':variants}


def attach_f_experiment(payload,menu,cache,config, *, ranking=None):
    if payload.get('campus','arcisstr')!='arcisstr':return payload
    ranking = ranking if ranking is not None else build_f_experiment(menu,cache,config)
    shortlist = {**ranking,'variants':{key:{**v,'plates':v['plates'][:5]} for key,v in ranking['variants'].items()}}
    return {**payload,'experiments':{**payload.get('experiments',{}),'combination_f':shortlist}}
