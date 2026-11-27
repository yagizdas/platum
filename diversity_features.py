"""Symmetric pair measurements for future learned alternative usefulness."""
from combination_d import component_group

FEATURE_VERSION = 1
GOALS = ('bulk', 'cut', 'budget')


def groups(plate):
    result = {'core': {}, 'accompaniment': {}}
    for i in plate['items']:
        group = result[component_group(i)]
        group[i['id']] = group.get(i['id'], 0) + i['weight_g']
    return result


def overlap(a, b):
    total = sum(a.values()) + sum(b.values())
    # Missing groups are flagged separately; absence supplies no similarity bonus.
    return 2 * sum(min(v, b.get(k, 0)) for k, v in a.items()) / total if total else 0


def pair_features(a, b, goal):
    if goal not in GOALS:
        raise ValueError('Unknown goal')
    left, right = groups(a), groups(b)
    result = {f'goal_{g}': int(g == goal) for g in GOALS}
    total_weight = a['weight_g'] + b['weight_g']
    for group in left:
        x, y = left[group], right[group]
        result.update({f'{group}_identity_overlap': overlap(dict.fromkeys(x, 1), dict.fromkeys(y, 1)),
                       f'{group}_gram_overlap': overlap(x, y),
                       f'{group}_both_absent': int(not x and not y),
                       f'{group}_one_absent': int(bool(x) != bool(y)),
                       f'{group}_count_min': min(len(x), len(y)),
                       f'{group}_count_max': max(len(x), len(y)),
                       f'{group}_changed_fraction': (sum(v for k, v in x.items() if k not in y)
                           + sum(v for k, v in y.items() if k not in x)) / total_weight if total_weight else 0})
    for key in ('weight_g', 'dish_count'):
        result[f'{key}_min'] = min(a[key], b[key])
        result[f'{key}_max'] = max(a[key], b[key])
    for key in ('price', 'kcal', 'protein', 'fat_g', 'carbs_g', 'fat_energy_pct'):
        result[f'{key}_difference'] = abs(a[key] - b[key])
    return {key: round(value, 8) for key, value in result.items()}
