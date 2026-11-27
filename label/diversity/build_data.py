"""Create a frozen human-labeling pilot; no model calls or ranking changes."""
import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bulk_experiment import exhaustive_candidates, search_space, MAX_PORTION_COMBINATIONS, non_soup_weight_g
from common import load_config, normalize, read_json
from diversity_features import FEATURE_VERSION, GOALS, pair_features
from label.v2.build_data import serialize
from pair import food
from pick import portion_options
from scoring import score_plate

STRATEGIES = ('core_swap', 'side_change', 'component_change', 'portion_change', 'rank_neighbors', 'explore')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]


def matches(strategy, a, b, f):
    ids_a, ids_b = {i['id'] for i in a['items']}, {i['id'] for i in b['items']}
    if strategy == 'core_swap':
        return f['core_identity_overlap'] < 1 and f['accompaniment_identity_overlap'] == 1 and not f['accompaniment_both_absent']
    if strategy == 'side_change':return f['core_identity_overlap'] == 1 and ids_a != ids_b
    if strategy == 'component_change':return ids_a < ids_b or ids_b < ids_a
    if strategy == 'portion_change':return ids_a == ids_b and a['id'] != b['id']
    return True


def build(source, config, count=100, seed=20261127):
    rng = random.Random(seed)
    cache = read_json(source / 'data/dish_cache.json', {})
    contexts, skipped = [], []
    for path in sorted((source / 'data/menus').glob('*.json')):
        menu = read_json(path)
        if menu.get('state') != 'open' or menu.get('campus', 'arcisstr') != 'arcisstr':continue
        if any(normalize(d['name']) not in cache for d in menu['dishes']):
            skipped.append({'date': menu['date'], 'reason': 'missing nutrition'});continue
        foods = [food(d, cache) for d in menu['dishes']]
        options = [portion_options(i, i, config, paired=True) for i in foods]
        if search_space(options)['portion_combinations'] > MAX_PORTION_COMBINATIONS:
            skipped.append({'date': menu['date'], 'reason': 'search too large'});continue
        raw = [p for p in exhaustive_candidates(options, config) if non_soup_weight_g(p) <= 900]
        for goal in GOALS:
            eligible = [p for p in raw if all(p[k] >= v for k, v in config.get('plate_minimums', {}).get(goal, {}).items())
                        and all(p[k] <= v for k, v in config.get('plate_maximums', {}).get(goal, {}).items())]
            if len(eligible) < 2:continue
            # Retain many portion/dish-set variations and the actual top-ranked cases.
            chosen = rng.sample(eligible, min(180, len(eligible)))
            chosen += sorted(eligible, key=lambda p: -score_plate(p, goal, config)['total'])[:35]
            plates = {}
            for p in chosen:
                value = serialize(p, config);value.pop('baseline_score')
                value['id'] = digest(value)
                plates[value['id']] = value
            values = list(plates.values())
            ranked = sorted(values, key=lambda p: -score_plate({'price_cents': round(p['price'] * 100),
                                    'kcal': p['kcal'], 'protein': p['protein']}, goal, config)['total'])[:20]
            contexts.append({'date': menu['date'], 'goal': goal, 'plates': plates, 'ranked': ranked})
    if not contexts:raise ValueError('No complete eligible menu contexts')
    by_goal = {g: [c for c in contexts if c['goal'] == g] for g in GOALS}
    if any(not v for v in by_goal.values()):raise ValueError('Every goal needs an eligible context')
    seen, pairs, used = set(), [], {}
    for index in range(count):
        goal, requested = GOALS[index % 3], STRATEGIES[(index // 3) % len(STRATEGIES)]
        candidates = list(by_goal[goal]);rng.shuffle(candidates)
        selected = None
        for context in candidates:
            values = list(context['plates'].values())
            combinations = list(itertools.combinations(context['ranked'] if requested == 'rank_neighbors' else values, 2))
            rng.shuffle(combinations)
            for a, b in combinations:
                key = (context['date'], goal, *sorted([a['id'], b['id']]))
                if key in seen:continue
                f = pair_features(a, b, goal)
                if matches(requested, a, b, f):selected = context, a, b, f, key;break
            if selected:break
        if not selected:raise ValueError(f'No unused {requested} pair for {goal}')
        context, a, b, features, key = selected
        seen.add(key)
        if rng.random() < .5:a, b = b, a
        used[a['id']] = a;used[b['id']] = b
        pairs.append({'id': digest(key), 'date': context['date'], 'goal': goal, 'a': a['id'], 'b': b['id'],
                      'strategy': requested, 'features': features})
    rng.shuffle(pairs)
    result = {'schema_version': 1, 'experiment': 'plate-diversity-v1', 'feature_version': FEATURE_VERSION,
              'campus': 'arcisstr', 'seed': seed, 'plates': list(used.values()), 'pairs': pairs,
              'summary': {'comparisons': len(pairs), 'dates': len({p['date'] for p in pairs}),
                          'goals': dict(Counter(p['goal'] for p in pairs)),
                          'strategies': dict(Counter(p['strategy'] for p in pairs)), 'skipped_days': skipped}}
    result['dataset_id'] = digest(result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('data.json'))
    parser.add_argument('--count', type=int, default=100)
    args = parser.parse_args()
    if args.count < 1:parser.error('Count must be positive')
    result = build(args.source_root, load_config(), args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
    print(json.dumps({'dataset_id': result['dataset_id'], **result['summary']}, indent=2))
