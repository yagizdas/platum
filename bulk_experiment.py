"""Staging A/B comparison: exhaustive Arcisstraße Bulk candidates, no model calls."""
import argparse
import itertools
import math
from pathlib import Path
from time import perf_counter

from common import ROOT, load_config, normalize, read_json, write_json
from diet_filters import FILTERS, allows
from pair import food
from pick import plate, plate_result, portion_options, top_plates, valid_plate

MAX_ITEMS = 4
MAX_PORTION_COMBINATIONS = 200_000


def search_space(options):
    """Count distinct dish sets and all portion assignments without enumerating them."""
    coefficients = [1] + [0] * MAX_ITEMS
    for choices in options:
        for size in range(MAX_ITEMS, 0, -1):
            coefficients[size] += coefficients[size - 1] * len(choices)
    count = len(options)
    return {'dish_count': count,
            'dish_sets': sum(math.comb(count, k) for k in range(1, min(MAX_ITEMS, count) + 1)),
            'portion_combinations': sum(coefficients[1:])}


def exhaustive_candidates(options, config):
    for size in range(1, min(MAX_ITEMS, len(options)) + 1):
        for dishes in itertools.combinations(options, size):
            for items in itertools.product(*dishes):
                if valid_plate(items, config, max_items=MAX_ITEMS):
                    yield plate(items)


def build_experiment(menu, cache, config, *, max_combinations=MAX_PORTION_COMBINATIONS):
    started = perf_counter()
    missing = [dish['name'] for dish in menu['dishes'] if normalize(dish['name']) not in cache]
    foods = [food(dish, cache) for dish in menu['dishes']] if menu['state'] == 'open' and not missing else []
    options = [portion_options(item, item, config, paired=True) for item in foods]
    stats = search_space(options)
    too_large = stats['portion_combinations'] > max_combinations
    values = list(exhaustive_candidates(options, config)) if not too_large else []
    stats['valid_candidates'] = len(values)
    profiles = {'all': lambda p: True,
                'vegan': lambda p: all(item.get('is_vegan') is True for item in p['items'])}
    profiles.update({profile: lambda p, profile=profile: all(allows(item, profile) for item in p['items'])
                     for profile in FILTERS})
    variants = {}
    for profile, eligible in profiles.items():
        pool = top_plates((value for value in values if eligible(value)), 'bulk', config,
                          distinct_dish_sets=True)
        state = 'ready' if pool else ('unavailable' if menu['state'] == 'open' else menu['state'])
        variants['bulk_' + profile] = {
            'state': state, 'plates': [plate_result(value) for value in pool],
            'message': ('This comparison is waiting for nutrition estimates.' if missing else 'This menu is too large for the exhaustive comparison.' if too_large
                        else 'No exhaustive-search plate fits these filters and Bulk limits.')}
    stats['elapsed_ms'] = round((perf_counter() - started) * 1000, 1)
    return {'method': 'exhaustive', 'max_dishes': MAX_ITEMS, 'stats': stats, 'variants': variants}


def attach_experiment(payload, menu, cache, config):
    """Only add B; preserve every baseline field and recommendation."""
    if payload.get('campus', config.get('campus', 'arcisstr')) != 'arcisstr':
        return payload
    return {**payload, 'experiments': {**payload.get('experiments', {}),
                                      'bulk_ab': build_experiment(menu, cache, config)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--output-root', type=Path, default=ROOT)
    args = parser.parse_args()
    source, output = args.source_root / 'data', args.output_root / 'data'
    index = read_json(source / 'week.json')
    cache, config = read_json(source / 'dish_cache.json'), load_config()
    for row in index['days']:
        day = row['date']
        payload = attach_experiment(read_json(source / 'days' / f'{day}.json'),
                                    read_json(source / 'menus' / f'{day}.json'), cache, config)
        write_json(output / 'days' / f'{day}.json', payload)
        if day == index['week_start']:
            write_json(output / 'today.json', payload)
        print(day, payload['experiments']['bulk_ab']['stats'], flush=True)
    write_json(output / 'week.json', index)


if __name__ == '__main__':
    main()
