"""Rescore the saved batch's exact dates, with no source fetches or model calls."""
from datetime import date

from campuses import CAMPUS_IDS, campus_config, campus_data
from common import ROOT, load_config, read_json, write_json
from pick import build_week


def rescore(root=ROOT, campus="arcisstr"):
    data = campus_data(root, campus)
    index = read_json(data / 'week.json')
    reference = date.fromisoformat(index['week_start'])
    menus = {row['date']: read_json(data / 'menus' / f"{row['date']}.json") for row in index['days']}
    days, updated = build_week(reference, menus, read_json(root / 'data/dish_cache.json', {}), campus_config(load_config(), campus),
                               no_llm=True, proposals_dir=data / 'proposals',
                               judge_cache_path=data / 'title_cache.json')
    for day, payload in days.items():
        write_json(data / 'days' / f'{day}.json', payload)
    write_json(data / 'week.json', updated)
    write_json(data / 'today.json', days[index['week_start']])


if __name__ == '__main__':
    for campus in CAMPUS_IDS:
        if (campus_data(ROOT, campus) / "week.json").exists():
            rescore(campus=campus)
