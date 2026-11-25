"""Build a frozen, reproducible Bulk v2 labeling set from exhaustive candidates."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bulk_experiment import MAX_PORTION_COMBINATIONS, exhaustive_candidates, search_space
from common import dish_id, load_config, normalize, read_json
from diet_filters import meat_types
from pair import food
from pick import plate_result, portion_options
from scoring import score_plate

STRATEGIES = ('dish_count', 'portion_size', 'fat_share', 'meat_share', 'current_top', 'explore')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()[:20]


def features(plate):
    kcal = plate['kcal']
    meat = [i for i in plate['items'] if set(meat_types(i)) - {'unknown', 'fish'}]
    unknown = [i for i in plate['items'] if 'unknown' in meat_types(i)]
    return {'kcal': round(kcal, 2), 'protein': round(plate['protein'], 2),
            'price': plate['price_cents'] / 100, 'fat_g': round(plate['fat'], 2),
            'carbs_g': round(plate['carbs'], 2), 'weight_g': plate['weight_g'],
            'dish_count': len(plate['items']),
            'fat_energy_pct': round(9 * plate['fat'] / kcal * 100, 3) if kcal else 0,
            'protein_energy_pct': round(4 * plate['protein'] / kcal * 100, 3) if kcal else 0,
            'meat_dish_weight_g': sum(i['weight_g'] for i in meat), 'meat_dish_count': len(meat),
            'unknown_diet_weight_g': sum(i['weight_g'] for i in unknown)}


def serialize(plate, config):
    result = plate_result(plate)
    for item, raw in zip(result['items'], plate['items']):
        item.update(fat_g=round(raw['fat'], 2), carbs_g=round(raw['carbs'], 2))
    key = sorted((dish_id(i), i['count'], i['unit'], i['weight_g']) for i in plate['items'])
    return {'id': digest(key), **features(plate), 'items': result['items'],
            'title': result['title'], 'has_estimated_prices': result['has_estimated_prices'],
            'baseline_score': score_plate(plate, 'bulk', config)['total']}


def dish_set(plate):
    return tuple(sorted(i['id'] for i in plate['items']))


def select_pairs(plates, count, rng):
    """Balanced dish-count exploration plus controlled trade-offs; never just top-five picks."""
    counts, sets = defaultdict(list), defaultdict(list)
    for p in plates:
        counts[p['dish_count']].append(p)
        sets[dish_set(p)].append(p)
    available_counts = sorted(counts)
    portion_sets = [v for v in sets.values() if len(v) > 1]
    # Equal weighting of dish counts prevents four-dish sets swamping smaller lunches.
    def explore():
        return rng.choice(counts[rng.choice(available_counts)])
    top = sorted(plates, key=lambda p: (-p['baseline_score'], p['price'], p['id']))[:20]
    seen, result = set(), []
    for index in range(count):
        strategy = STRATEGIES[index % len(STRATEGIES)]
        for _ in range(100):
            a, b = explore(), explore()
            if strategy == 'dish_count' and len(available_counts) > 1:
                ca, cb = rng.sample(available_counts, 2)
                a, b = rng.choice(counts[ca]), rng.choice(counts[cb])
            elif strategy == 'portion_size' and portion_sets:
                group = rng.choice(portion_sets)
                a = rng.choice(group)
                b = max(group, key=lambda p: abs(p['weight_g'] - a['weight_g']))
            elif strategy in ('fat_share', 'meat_share'):
                key = 'fat_energy_pct' if strategy == 'fat_share' else 'meat_dish_weight_g'
                # Match energy and protein where possible so the contrast is useful.
                neighbors = [p for p in plates if abs(p['kcal'] - a['kcal']) <= 250
                             and abs(p['protein'] - a['protein']) <= 20 and p['id'] != a['id']]
                if neighbors:
                    b = max(rng.sample(neighbors, min(80, len(neighbors))), key=lambda p: abs(p[key] - a[key]))
            elif strategy == 'current_top':
                a = rng.choice(top)
            pair_key = tuple(sorted((a['id'], b['id'])))
            if a['id'] == b['id'] or pair_key in seen:
                continue
            seen.add(pair_key)
            if rng.random() < .5:
                a, b = b, a
            result.append({'id': digest(pair_key), 'a': a['id'], 'b': b['id'], 'strategy': strategy})
            break
    return result


def build(source, config, *, pairs_per_day=24, seed=20261125):
    rng, days, skipped = random.Random(seed), [], []
    cache = read_json(source / 'data/dish_cache.json', {})
    for path in sorted((source / 'data/menus').glob('*.json')):
        menu = read_json(path)
        if menu.get('state') != 'open' or menu.get('campus', 'arcisstr') != 'arcisstr':
            continue
        missing = [d['name'] for d in menu['dishes'] if normalize(d['name']) not in cache]
        if missing:
            skipped.append({'date': menu['date'], 'reason': 'missing_nutrition', 'dishes': missing})
            continue
        foods = [food(d, cache) for d in menu['dishes']]
        options = [portion_options(i, i, config, paired=True) for i in foods]
        stats = search_space(options)
        if stats['portion_combinations'] > MAX_PORTION_COMBINATIONS:
            skipped.append({'date': menu['date'], 'reason': 'search_too_large', **stats})
            continue
        # Stratify across size and composition before sampling; no learned-score cutoff is used.
        buckets = defaultdict(list)
        valid_count = 0
        for p in exhaustive_candidates(options, config):
            if any(p[k] < v for k, v in config['plate_minimums']['bulk'].items()) or any(
                    p[k] > v for k, v in config['plate_maximums']['bulk'].items()):
                continue
            valid_count += 1
            f = features(p)
            key = (f['dish_count'], int(f['kcal'] // 250), int(f['fat_energy_pct'] // 10),
                   int(f['weight_g'] // 250), f['meat_dish_count'])
            # The same search-size guard as B bounds the candidate pool.
            bucket = buckets[key]
            bucket.append(p)
        sampled = []
        for bucket in buckets.values():
            sampled.extend(rng.sample(bucket, min(6, len(bucket))))
        # Include a small current-score reference slice without curating the exploration pool.
        raw = [p for bucket in buckets.values() for p in bucket]
        sampled.extend(sorted(raw, key=lambda p: -score_plate(p, 'bulk', config)['total'])[:20])
        unique = {p['id']: p for p in (serialize(value, config) for value in sampled)}
        plates = list(unique.values())
        if len(plates) < 2:
            skipped.append({'date': menu['date'], 'reason': 'too_few_eligible_plates'})
            continue
        pairs = select_pairs(plates, pairs_per_day, rng)
        used = {key for pair in pairs for key in (pair['a'], pair['b'])}
        days.append({'date': menu['date'], 'stats': {**stats, 'eligible_candidates': valid_count,
                     'sampled_candidates': len(plates)},
                     'plates': [p for p in plates if p['id'] in used], 'pairs': pairs})
    if not days:
        raise ValueError('No complete Arcisstraße menus with comparable plates were found')
    queue = [{'date': day['date'], 'pair_id': pair['id']} for day in days for pair in day['pairs']]
    rng.shuffle(queue)
    core = {'schema_version': 2, 'experiment': 'bulk-exhaustive-v2', 'campus': 'arcisstr', 'goal': 'bulk',
            'seed': seed, 'days': days, 'queue': queue}
    core['dataset_id'] = digest(core)
    core['summary'] = {'days': len(days), 'comparisons': len(queue),
                       'eligible_candidates': sum(d['stats']['eligible_candidates'] for d in days),
                       'dish_counts': dict(sorted(Counter(p['dish_count'] for d in days for p in d['plates']).items())),
                       'strategies': dict(Counter(p['strategy'] for d in days for p in d['pairs'])), 'skipped_days': skipped}
    return core


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=ROOT / 'label/v2/data.json')
    parser.add_argument('--pairs-per-day', type=int, default=24)
    parser.add_argument('--seed', type=int, default=20261125)
    args = parser.parse_args()
    if args.pairs_per_day < 1:
        parser.error('--pairs-per-day must be positive')
    data = build(args.source_root, load_config(), pairs_per_day=args.pairs_per_day, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
    print(json.dumps({'dataset_id': data['dataset_id'], **data['summary']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
