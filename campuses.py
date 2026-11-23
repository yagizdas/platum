"""Campus-specific sources and policies; dish nutrition remains shared."""
from copy import deepcopy
from pathlib import Path

CAMPUS_IDS = ('arcisstr', 'garching')


def campus_config(config, campus='arcisstr'):
    if campus not in CAMPUS_IDS:
        raise ValueError(f'Unknown campus: {campus}')
    result = deepcopy(config)
    result.update(campus=campus, mensa='Mensa Arcisstraße' if campus == 'arcisstr' else 'Mensa Garching',
                  lunch_cutoff='14:30' if campus == 'arcisstr' else '14:15')
    if campus == 'garching':
        result.update(official_url='https://www.studierendenwerk-muenchen-oberbayern.de/gastronomie/speiseplan/speiseplan_422_-de.html',
                      eat_api_url='https://tum-dev.github.io/eat-api/mensa-garching/{year}/{week:02d}.json',
                      standing_sides=[], counter_policy='published_stations', require_matched_prices=True)
        for goal, instruction in result['proposals']['instructions'].items():
            result['proposals']['instructions'][goal] = instruction + ' At Mensa Garching use only supplied, published components. No standing sides are assumed; station labels are menu categories, not a verified shared-counter layout.'
    return result


def campus_data(root, campus='arcisstr'):
    if campus not in CAMPUS_IDS:
        raise ValueError(f'Unknown campus: {campus}')
    return Path(root) / 'data' if campus == 'arcisstr' else Path(root) / 'data/campuses' / campus
