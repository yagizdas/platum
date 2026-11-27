"""Staging G: F's accepted goal-fit ranking, diversified by the existing MMR selector."""
from combination_e import build_e_experiment


def build_g_experiment(ranking):
    if ranking['method'] != 'learned_goal_fit_v2' or any(
            p['score'].get('eligible') is not True
            for v in ranking['variants'].values() for p in v['plates']):
        raise ValueError('G requires accepted candidates from F’s goal-fit ranking')
    selected, audit = build_e_experiment(ranking, candidate_prefix='g', picked_by='goal_fit_mmr_v2')
    provenance = {'method': 'goal_fit_mmr_v2', 'base_method': ranking['method'],
                  'dataset_id': ranking['dataset_id'], 'max_dishes': ranking['max_dishes'],
                  'max_non_soup_weight_g': ranking['max_non_soup_weight_g'],
                  'acceptability_filter': 'goal_fit_v2'}
    return {**selected, **provenance}, {**audit, 'settings': {**audit['settings'], **provenance}}


def attach_g_experiment(payload, ranking):
    if payload.get('campus', 'arcisstr') != 'arcisstr':return payload, None
    g, audit = build_g_experiment(ranking)
    return {**payload, 'experiments': {**payload.get('experiments', {}), 'combination_g': g}}, audit
