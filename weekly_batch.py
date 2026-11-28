"""Prepare weekly campus batches and refresh changed recipes in the current week."""
import argparse
import hashlib
import json
import sys
from datetime import date, timedelta

from campuses import CAMPUS_IDS, campus_config, campus_data
from common import ROOT, load_config, normalize, read_json, today, week_dates, write_json
from judge import api_key_value
from pair import food
from pick import build_week
from proposals import daily_proposals, fallback_proposals
from scrape import scrape_week, save_menu
from tag import tag_menu
from recommendations import apply_recommendations, EMPTY_PROPOSALS


def next_monday(day):
    return day + timedelta(days=7 - day.weekday())


def batch_ready(root, monday, campus="arcisstr", *, policy=None):
    data = campus_data(root, campus)
    marker = read_json(data / 'batches' / f'{monday}.json', {})
    expected = [day.isoformat() for day in week_dates(monday, 1)]
    index = read_json(data / 'week.json', {})
    return (marker.get('complete') is True and marker.get('dates') == expected
            and index.get('campus', 'arcisstr') == campus
            and [row['date'] for row in index.get('days', [])] == expected
            and (not policy or all(read_json(data / 'days' / f'{day}.json', {}).get('recommendation_policy') == policy for day in expected))
            and all(read_json(data / 'days' / f'{day}.json', {}).get('date') == day
                    and read_json(data / 'days' / f'{day}.json', {}).get('campus', 'arcisstr') == campus for day in expected))


def menu_signature(menu):
    # Ignore fetch timestamps and source order; recipe, diet, price and service changes matter.
    dishes = sorted(menu.get('dishes', []), key=lambda item: normalize(item['name']))
    return hashlib.sha256(json.dumps(dishes, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def run_batch(monday, config, *, root=ROOT, scraper=scrape_week, tagger=tag_menu, builder=build_week,
              proposer=daily_proposals, refresh=False):
    campus = config.get("campus", "arcisstr")
    data = campus_data(root, campus)
    if not refresh and batch_ready(root, monday, campus, policy=config.get('recommendations')):
        print(f'{monday}: complete batch already saved; no source fetches or model calls.')
        return True
    dates = [day.isoformat() for day in week_dates(monday, 1)]
    cache_path = root / 'data/dish_cache.json'
    proposals_dir = data / 'proposals'
    errors = []
    try:
        menus = scraper(monday, config, weeks=1)
    except (OSError, RuntimeError, ValueError) as exc:
        write_json(data / 'batches' / f'{monday}.json',
                   {'complete': False, 'dates': dates, 'errors': [str(exc)]})
        return False
    prior_menus = {day: read_json(data / 'menus' / f'{day}.json') for day in dates}
    # The rolling source drops past dates. Refresh must preserve their archived menus.
    for day, menu in menus.items():
        if day < today(config).isoformat() and not menu.get('dishes') and prior_menus.get(day):
            menus[day] = prior_menus[day]
    # An unpublished future week must not replace the current batch with five closed days.
    if (not any(menu.get('state') == 'open' and menu.get('dishes') for menu in menus.values())
            and not all(menu.get('published') is True for menu in menus.values())):
        errors.append('Next week has no published open menus yet; retaining the existing public batch.')
    for day in dates:
        menu = menus.get(day)
        if not menu:
            errors.append(f'{day}: missing menu')
            continue
        if menu.get('state') == 'unavailable':
            errors.append(f'{day}: menu prices or source unavailable')
        if menu.get('published') is False:
            errors.append(f'{day}: source has not published this date yet')
        save_menu(data / 'menus' / f'{day}.json', menu, today(config))
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
        if config.get('recommendations'):
            continue  # Fixed exhaustive methods need nutrition tags, not LLM meal proposals.
        foods = [food(item, tags) for item in menu['dishes']]
        for goal in ('bulk', 'cut', 'budget'):
            for diet in ('all', 'vegan'):
                variant = goal + '_' + diet
                eligible = [item for item in foods if diet == 'all' or item.get('is_vegan') is True]
                if not fallback_proposals(eligible):
                    continue
                path = proposals_dir / day / f'{variant}.json'
                previous = read_json(path, {})
                signature = menu_signature(menu)
                # Seed legacy caches from the menu they were actually generated from.
                # Keep that signature on failed refreshes so the next run retries.
                if previous and 'menu_signature' not in previous:
                    previous['menu_signature'] = menu_signature(prior_menus.get(day) or menu)
                    write_json(path, previous)
                needs_refresh = bool(previous) and (previous.get('source') != 'llm'
                                                     or previous.get('menu_signature') != signature)
                proposer(day, foods, config, variant, cache_dir=proposals_dir, refresh=needs_refresh)
                current = read_json(path, {})
                if current.get('source') != 'llm' or (needs_refresh and current == previous):
                    errors.append(f'{day}/{variant}: model proposals incomplete or stale')
                else:
                    current['menu_signature'] = signature
                    write_json(path, current)
    if not errors:
        days, index = builder(monday, menus, tags, config,
                              proposals_dir=proposals_dir, judge_cache_path=data / 'title_cache.json',
                              **({'no_llm': True, 'proposals': EMPTY_PROPOSALS} if config.get('recommendations') else {}))
        if config.get('recommendations'):
            days = {day:apply_recommendations(payload, menus[day], tags, config) for day,payload in days.items()}
        if any(day['state'] == 'unavailable' or day.get('missing_tags') for day in days.values()):
            errors.append('Some dated plates could not be generated.')
        else:
            for day, payload in days.items():
                write_json(data / 'days' / f'{day}.json', payload)
            write_json(data / 'menu.json', menus[dates[0]])
            write_json(data / 'today.json', days[dates[0]])
            write_json(data / 'week.json', index)
    write_json(data / 'batches' / f'{monday}.json',
               {'complete': not errors, 'dates': dates, 'errors': errors})
    for error in errors:
        print(error, file=sys.stderr)
    return not errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campus', choices=(*CAMPUS_IDS, 'all'), default='all')
    targets = parser.add_mutually_exclusive_group()
    targets.add_argument('--date', type=date.fromisoformat, help='Batch Monday; defaults to next Monday in Berlin')
    targets.add_argument('--current-week', action='store_true', help='Refresh the current Monday-Friday batch')
    parser.add_argument('--refresh', action='store_true', help='Fetch updated menus even when the saved batch is complete')
    args = parser.parse_args()
    config = load_config()
    current = today(config)
    monday = (current - timedelta(days=current.weekday())) if args.current_week else (args.date or next_monday(current))
    if monday.weekday() != 0:
        parser.error('--date must be a Monday')
    succeeded = []
    for campus in CAMPUS_IDS if args.campus == 'all' else (args.campus,):
        try:
            succeeded.append(run_batch(monday, campus_config(config, campus), refresh=args.refresh))
        except Exception as exc:
            print(f'{campus}: batch failed ({type(exc).__name__}); continuing other campus.', file=sys.stderr)
            succeeded.append(False)
    return 0 if all(succeeded) else 1


if __name__ == '__main__':
    sys.exit(main())
