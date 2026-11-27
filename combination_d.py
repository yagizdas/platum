"""Deterministic diversity selection after preference ranking; no model calls."""
from copy import deepcopy

from common import normalize

SCAN_K = 100
PICK_K = 5
CORE_WEIGHT = .8
SIMILARITY_THRESHOLD = .65
SUBSTANTIAL_G = 150
SETTINGS = {'scan_k': SCAN_K, 'pick_k': PICK_K, 'core_weight': CORE_WEIGHT,
            'accompaniment_weight': 1 - CORE_WEIGHT,
            'similarity_threshold': SIMILARITY_THRESHOLD, 'substantial_g': SUBSTANTIAL_G}


def component_group(item):
    # Standing rice/potato salad remain accompaniments even if an old tag says main.
    # Complete pasta dishes, stews and vegetarian entrees retain their cached main role.
    return 'core' if item['role'] == 'main' and not item.get('standing') else 'accompaniment'


def component_weights(plate):
    groups = {'core': {}, 'accompaniment': {}}
    for item in plate['items']:
        key = item.get('id') or normalize(item['name'])
        group = groups[component_group(item)]
        # One normal scoop is a full presence. Extra scoops don't create novelty;
        # tiny additions contribute only in proportion to their size.
        group[key] = min(1., group.get(key, 0) + max(0, item['weight_g']) / SUBSTANTIAL_G)
    return groups


def dice(a, b):
    denominator = sum(a.values()) + sum(b.values())
    return 2 * sum(min(value, b.get(key, 0)) for key, value in a.items()) / denominator if denominator else 1.


def similarity(a, b):
    left, right = component_weights(a), component_weights(b)
    core = dice(left['core'], right['core'])
    accompaniment = dice(left['accompaniment'], right['accompaniment'])
    return {'core': core, 'accompaniment': accompaniment,
            'total': CORE_WEIGHT * core + (1 - CORE_WEIGHT) * accompaniment}


def select_distinct(plates):
    selected, walked = [], []
    for rank, candidate in enumerate(plates[:SCAN_K], 1):
        matches = [(similarity(candidate, p), p['preference_rank']) for p in selected]
        nearest = max(matches, key=lambda value: value[0]['total']) if matches else None
        duplicate = nearest is not None and nearest[0]['total'] >= SIMILARITY_THRESHOLD - 1e-12
        comparison = {'closest_selected_rank': nearest[1] if nearest else None,
                      'similarity': nearest[0] if nearest else None}
        walked.append({'preference_rank': rank, 'title': candidate['title'],
                       'score': candidate['score']['total'],
                       'decision': 'skipped' if duplicate else 'selected', **comparison})
        if duplicate:
            continue
        result = deepcopy(candidate)
        result.update(picked_by='diversity_filter', preference_rank=rank, candidate_id=f'd{rank:03}',
                      diversity={**comparison, 'components': [
                          {'id': i.get('id'), 'name': i.get('name_en') or i['name'],
                           'group': component_group(i), 'presence': min(1., i['weight_g'] / SUBSTANTIAL_G)}
                          for i in candidate['items']]})
        result['reason'] = ('Highest-ranked eligible combination.' if not nearest else
                            f"Preference rank #{rank}; {nearest[0]['total']:.0%} similarity to its closest earlier pick "
                            f"(#{nearest[1]}), below the 65% cutoff.")
        selected.append(result)
        if len(selected) == PICK_K:
            break
    return selected, walked


def build_d_experiment(ranking):
    variants, audits = {}, {}
    for key, ranked in ranking['variants'].items():
        pool = ranked['plates'][:SCAN_K]
        selected, walked = select_distinct(pool)
        message = (f'Only {len(selected)} distinct options survived the 65% similarity cutoff '
                   f'in the top {len(pool)} eligible combinations.' if selected and len(selected) < PICK_K
                   else '' if selected else ranked.get('message', 'No eligible combinations.'))
        variants[key] = {'state': 'ready' if selected else ranked['state'], 'plates': selected,
                         'message': message, 'pool_count': len(pool), 'scanned_count': len(walked)}
        audits[key] = {**variants[key], 'walk': walked}
    return {'method': 'deterministic_diversity', **SETTINGS, 'variants': variants}, {
        'settings': SETTINGS, 'variants': audits}


def attach_d_experiment(payload, ranking):
    if payload.get('campus', 'arcisstr') != 'arcisstr':
        return payload, None
    d, audit = build_d_experiment(ranking)
    return {**payload, 'experiments': {**payload.get('experiments', {}), 'combination_d': d}}, audit
