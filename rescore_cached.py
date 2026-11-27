"""Rescore the saved batch's exact dates, with no source fetches or model calls."""
from datetime import date

from campuses import CAMPUS_IDS, campus_config, campus_data
from common import ROOT, load_config, read_json, write_json
from pick import GOALS, build_week
from bulk_experiment import attach_experiment, build_experiment
from combination_c import TOP_K, attach_c_experiment
from combination_d import SCAN_K, attach_d_experiment
from combination_e import attach_e_experiment
from combination_f import attach_f_experiment


def rescore(root=ROOT, campus="arcisstr"):
    data = campus_data(root, campus)
    index = read_json(data / 'week.json')
    reference = date.fromisoformat(index['week_start'])
    menus = {row['date']: read_json(data / 'menus' / f"{row['date']}.json") for row in index['days']}
    days, updated = build_week(reference, menus, read_json(root / 'data/dish_cache.json', {}), campus_config(load_config(), campus),
                               no_llm=True, proposals_dir=data / 'proposals',
                               judge_cache_path=data / 'title_cache.json')
    cache = read_json(root / 'data/dish_cache.json', {})
    config = campus_config(load_config(), campus)
    selection_cache = read_json(root / 'data/selection_c.json', {})
    audit_days = []
    for day, payload in days.items():
        if campus == 'arcisstr' and payload.get('schema_version') == 2:
            ranking = build_experiment(menus[day], cache, config, goals=GOALS, top_k=SCAN_K)
            shortlist = {**ranking, 'variants': {key: {**v, 'plates': v['plates'][:TOP_K]}
                                               for key, v in ranking['variants'].items()}}
            payload = attach_experiment(payload, menus[day], cache, config, ranking=shortlist)
            payload, audit = attach_c_experiment(payload, shortlist, config, selection_cache)
            write_json(root / 'label/c/data' / f'{day}.json', {'date': day, 'campus': campus,
                       'stats': ranking['stats'], **audit})
            payload, d_audit = attach_d_experiment(payload, ranking)
            write_json(root / 'label/d/data' / f'{day}.json', {'date': day, 'campus': campus, **d_audit})
            payload, e_audit = attach_e_experiment(payload, ranking)
            write_json(root / 'label/e/data' / f'{day}.json', {'date': day, 'campus': campus, **e_audit})
            audit_days.append({'date': day, 'file': f'{day}.json'})
            payload = attach_f_experiment(payload, menus[day], cache, config)
        write_json(data / 'days' / f'{day}.json', payload)
    write_json(data / 'week.json', updated)
    write_json(data / 'today.json', read_json(data / 'days' / f"{index['week_start']}.json"))
    if campus == 'arcisstr':
        write_json(root / 'label/c/data/index.json', {'schema_version': 1, 'campus': campus,
                   'top_k': TOP_K, 'days': audit_days})
        write_json(root / 'label/d/data/index.json', {'schema_version': 1, 'campus': campus,
                   'scan_k': SCAN_K, 'days': audit_days})
        write_json(root / 'label/e/data/index.json', {'schema_version': 1, 'campus': campus,
                   'scan_k': SCAN_K, 'days': audit_days})


if __name__ == '__main__':
    for campus in CAMPUS_IDS:
        if (campus_data(ROOT, campus) / "week.json").exists():
            rescore(campus=campus)
