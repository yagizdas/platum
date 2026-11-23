"""Prepare only the coming Monday-Friday batch; retry unfinished work on Sunday."""
import argparse
import sys
from datetime import date, timedelta

from common import ROOT, load_config, normalize, read_json, today, week_dates, write_json
from judge import api_key_value
from pair import food
from pick import build_week
from proposals import daily_proposals, fallback_proposals
from scrape import scrape_week
from tag import tag_menu


def next_monday(day):
    return day + timedelta(days=7 - day.weekday())


def batch_ready(root, monday):
    marker = read_json(root / 'data/batches' / f'{monday}.json', {})
    expected = [day.isoformat() for day in week_dates(monday, 1)]
    index = read_json(root / 'data/week.json', {})
    return (marker.get('complete') is True and marker.get('dates') == expected
            and [row['date'] for row in index.get('days', [])] == expected
            and all(read_json(root / 'data/days' / f'{day}.json', {}).get('date') == day for day in expected))


def run_batch(monday, config, *, root=ROOT, scraper=scrape_week, tagger=tag_menu, builder=build_week,
              proposer=daily_proposals):
    if batch_ready(root, monday):
        print(f'{monday}: complete batch already saved; no source fetches or model calls.')
        return True
    dates = [day.isoformat() for day in week_dates(monday, 1)]
    cache_path = root / 'data/dish_cache.json'
    proposals_dir = root / 'data/proposals'
    errors = []
    try:
        menus = scraper(monday, config, weeks=1)
    except (OSError, RuntimeError, ValueError) as exc:
        write_json(root / 'data/batches' / f'{monday}.json',
                   {'complete': False, 'dates': dates, 'errors': [str(exc)]})
        return False
    # An unpublished future week must not replace the current batch with five closed days.
    if (not any(menu.get('state') == 'open' and menu.get('dishes') for menu in menus.values())
            and not all(menu.get('published') is True for menu in menus.values())):
        errors.append('Next week has no published open menus yet; retaining the existing public batch.')
    for day in dates:
        menu = menus.get(day)
        if not menu:
            errors.append(f'{day}: missing menu')
            continue
        if menu.get('published') is False:
            errors.append(f'{day}: source has not published this date yet')
        write_json(root / 'data/menus' / f'{day}.json', menu)
        try:
            failures = []
            tagger(menu, cache_path, config['gemini_model'], api_key_value(), failures=failures)
            errors.extend(f'{day}: {failure["name"]} needs tagging' for failure in failures)
        except (RuntimeError, ValueError, OSError) as exc:
            errors.append(f'{day}: {exc}')
    tags = read_json(cache_path, {})
    for day, menu in menus.items():
        if menu.get('state') != 'open':
            continue
        if any(normalize(item['name']) not in tags for item in menu['dishes']):
            errors.append(f'{day}: incomplete nutrition cache')
            continue
        foods = [food(item, tags) for item in menu['dishes']]
        for goal in ('bulk', 'cut', 'budget'):
            for diet in ('all', 'vegan'):
                variant = goal + '_' + diet
                eligible = [item for item in foods if diet == 'all' or item.get('is_vegan') is True]
                if not fallback_proposals(eligible):
                    continue
                path = proposals_dir / day / f'{variant}.json'
                previous = read_json(path, {})
                # Failed caches are retried on the backup run; successful calls are reused.
                proposer(day, foods, config, variant, cache_dir=proposals_dir,
                         refresh=bool(previous) and previous.get('source') != 'llm')
                if read_json(path, {}).get('source') != 'llm':
                    errors.append(f'{day}/{variant}: model proposals incomplete')
    if not errors:
        days, index = builder(monday, menus, tags, config,
                              proposals_dir=proposals_dir, judge_cache_path=root / 'data/title_cache.json')
        if any(day['state'] == 'unavailable' or day.get('missing_tags') for day in days.values()):
            errors.append('Some dated plates could not be generated.')
        else:
            for day, payload in days.items():
                write_json(root / 'data/days' / f'{day}.json', payload)
            write_json(root / 'data/menu.json', menus[dates[0]])
            write_json(root / 'data/today.json', days[dates[0]])
            write_json(root / 'data/week.json', index)
    write_json(root / 'data/batches' / f'{monday}.json',
               {'complete': not errors, 'dates': dates, 'errors': errors})
    for error in errors:
        print(error, file=sys.stderr)
    return not errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', type=date.fromisoformat, help='Batch Monday; defaults to next Monday in Berlin')
    args = parser.parse_args()
    config = load_config()
    monday = args.date or next_monday(today(config))
    if monday.weekday() != 0:
        parser.error('--date must be a Monday')
    return 0 if run_batch(monday, config) else 1


if __name__ == '__main__':
    sys.exit(main())
