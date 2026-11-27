"""Staging E: MMR selection using a simple corrected overlap measure."""
from copy import deepcopy
import math

from combination_d import SCAN_K, PICK_K, component_weights, dice

BALANCES = {'quality': {'label': 'Quality first', 'lambda': .8},
            'balanced': {'label': 'Balanced', 'lambda': .5},
            'variety': {'label': 'More variety', 'lambda': .35}}
DEFAULT_BALANCE = 'balanced'
QUALITY_TRANSFORM = '1 - (best_score - candidate_score) / max(1, best_score - pool_worst_score)'


def similarity(a, b):
    left, right = component_weights(a), component_weights(b)
    total, active_weight, parts = 0., 0., {}
    for group, weight in [('core', .8), ('accompaniment', .2)]:
        if left[group] or right[group]:
            parts[group] = dice(left[group], right[group])
            total += weight * parts[group];active_weight += weight
        else:
            parts[group] = None
    # Empty groups supply no agreement; weights normalize over groups present
    # on at least one plate. Identical nonempty plates still have similarity 1.
    return {**parts, 'total': total / active_weight if active_weight else 0.}


def quality(score, best, scale=1.):
    if not math.isfinite(score) or not math.isfinite(best) or not math.isfinite(scale) or scale < 1 or score > best:
        raise ValueError('Expected finite preference scores at or below the best score')
    return max(0., 1 - (best - score) / scale)


def select_mmr(plates, weight):
    if not math.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError('MMR lambda must be between zero and one')
    pool = plates[:SCAN_K]
    if not pool:return [], []
    best = max(p['score']['total'] for p in pool)
    scale = max(1., best - min(p['score']['total'] for p in pool))
    qualities = [quality(p['score']['total'], best, scale) for p in pool]
    selected, chosen, steps = [], set(), []
    for slot in range(min(PICK_K, len(pool))):
        evaluated = []
        for i, p in enumerate(pool):
            if i in chosen:continue
            matches = [(similarity(p, pool[j]), j + 1) for j in selected]
            closest = max(matches, key=lambda x: x[0]['total']) if matches else None
            max_sim = closest[0]['total'] if closest else 0.
            terms = {'quality': qualities[i], 'quality_scale': scale, 'quality_term': weight * qualities[i],
                     'max_similarity': max_sim, 'redundancy_penalty': (1 - weight) * max_sim,
                     'closest_selected_rank': closest[1] if closest else None,
                     'similarity_components': closest[0] if closest else None}
            evaluated.append({'preference_rank': i + 1,
                              'value': terms['quality_term'] - terms['redundancy_penalty'], **terms})
        # Source ranks already use the scorer's stable price/identity tie-breaks.
        evaluated.sort(key=lambda e: (-e['value'], -e['quality'], e['preference_rank']))
        winner = next(e for e in evaluated if e['preference_rank'] == 1) if slot == 0 else evaluated[0]
        rank = winner['preference_rank'];chosen.add(rank - 1);selected.append(rank - 1)
        steps.append({'pick': slot + 1, **winner, 'closest_competitors': evaluated[:5]})
    results = []
    for slot, (index, step) in enumerate(zip(selected, steps), 1):
        p = deepcopy(pool[index])
        mmr = {k: v for k, v in step.items() if k != 'closest_competitors'}
        p.update(picked_by='mmr', preference_rank=index + 1, candidate_id=f'e{index + 1:03}',
                 mmr={'lambda': weight, **mmr}, reason='Highest-ranked eligible combination.' if slot == 1 else
                 f"MMR choice {slot}; original preference rank #{index + 1}. "
                 f"{step['max_similarity']:.0%} similarity to its closest earlier pick; similarity is a soft penalty.")
        results.append(p)
    return results, steps


def build_e_experiment(ranking):
    balances = {name: {**setting, 'variants': {}} for name, setting in BALANCES.items()}
    audit_variants = {}
    for key, ranked in ranking['variants'].items():
        pool = ranked['plates'][:SCAN_K]
        audit_variants[key] = {'candidates': [{**p, 'candidate_id': f'e{i:03}', 'preference_rank': i}
                                             for i, p in enumerate(pool, 1)], 'balances': {}}
        for name, setting in BALANCES.items():
            plates, steps = select_mmr(pool, setting['lambda'])
            v = {'state': 'ready' if plates else ranked['state'], 'plates': plates, 'pool_count': len(pool),
                 'message': (f'Only {len(pool)} eligible dish combinations are available.' if plates and len(pool) < PICK_K
                             else '' if plates else ranked.get('message', 'No eligible combinations.'))}
            balances[name]['variants'][key] = v
            audit_variants[key]['balances'][name] = {'state': v['state'], 'message': v['message'],
                'selections': [{'candidate_id': p['candidate_id'], 'preference_rank': p['preference_rank'],
                                'reason': p['reason'], 'mmr': p['mmr']} for p in plates], 'steps': steps}
    settings = {'method': 'mmr_simple_overlap', 'default_balance': DEFAULT_BALANCE, 'scan_k': SCAN_K,
                'pick_k': PICK_K, 'quality_transform': QUALITY_TRANSFORM,
                'similarity': 'weighted_dice_present_groups_only', 'substantial_g': 150,
                'core_weight': .8, 'accompaniment_weight': .2}
    return {**settings, 'balances': balances}, {'settings': {**settings, 'balances': BALANCES}, 'variants': audit_variants}


def attach_e_experiment(payload, ranking):
    if payload.get('campus', 'arcisstr') != 'arcisstr':return payload, None
    e, audit = build_e_experiment(ranking)
    return {**payload, 'experiments': {**payload.get('experiments', {}), 'combination_e': e}}, audit
