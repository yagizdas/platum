"""Rescore the saved batch's exact dates, with no source fetches or model calls."""
from datetime import date

from common import ROOT, load_config, read_json, write_json
from pick import build_week


def rescore(root=ROOT):
    index = read_json(root / 'data/week.json')
    reference = date.fromisoformat(index['week_start'])
    menus = {row['date']: read_json(root / 'data/menus' / f"{row['date']}.json") for row in index['days']}
    days, updated = build_week(reference, menus, read_json(root / 'data/dish_cache.json', {}), load_config(),
                               no_llm=True, proposals_dir=root / 'data/proposals',
                               judge_cache_path=root / 'data/title_cache.json')
    for day, payload in days.items():
        write_json(root / 'data/days' / f'{day}.json', payload)
    write_json(root / 'data/week.json', updated)
    write_json(root / 'data/today.json', days[index['week_start']])


if __name__ == '__main__':
    rescore()
