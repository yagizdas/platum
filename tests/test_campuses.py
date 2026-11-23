import copy
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from campuses import campus_config, campus_data
from common import normalize, read_json, write_json
from pair import food
from pick import candidates, plate_result
from proposals import fallback_proposals
from scrape import scrape, parse_official
from weekly_batch import run_batch, batch_ready

FIXTURES = Path(__file__).parent / 'fixtures'


def garching(config):
    return campus_config(config, 'garching')


def real_menu(config, day=date(2026, 11, 23)):
    return scrape(day, garching(config), html=(FIXTURES / 'garching-2026-11-23.html').read_text(),
                  api_payload=read_json(FIXTURES / 'garching-prices-2026-48.json'))


def test_garching_real_official_markup_controls_names_stations_and_diet(config):
    menu = real_menu(config)
    assert menu['mensa'] == 'Mensa Garching' and menu['campus'] == 'garching'
    assert menu['source'] == 'official'
    assert len(menu['dishes']) == 8
    soup = next(d for d in menu['dishes'] if d['name'] == 'Linsensuppe mit Gemüse')
    assert soup['station'] == 'Tagessupe, Brot, Obst'
    assert soup['is_vegan'] is True
    assert 'Sl' in soup['allergens']
    assert not any(d.get('standing') for d in menu['dishes'])
    sausage = next(d for d in menu['dishes'] if d['station'] == 'Grill')
    assert sausage['price']['base_eur'] == .5  # actual Garching feed, not the Arcisstraße meat default
    assert sausage['markers'] == ['R', 'S']


def test_api_cannot_override_official_garching_diet_or_invent_dishes(config):
    html = (FIXTURES / 'garching-2026-11-23.html').read_text()
    api = read_json(FIXTURES / 'garching-prices-2026-48.json')
    first = api['days'][0]['dishes'][0]
    first['labels'] = ['MEAT']
    api['days'][0]['dishes'].append({**first, 'name': 'Invented API-only main'})
    menu = scrape(date(2026, 11, 23), garching(config), html=html, api_payload=api)
    dish = next(d for d in menu['dishes'] if d['name'] == first['name'])
    assert dish['is_vegan'] is True
    assert not any(d['name'] == 'Invented API-only main' for d in menu['dishes'])


def test_garching_never_copies_standing_sides_or_guesses_unmatched_prices(config):
    menu = scrape(date(2026, 11, 23), garching(config), html=(FIXTURES / 'garching-2026-11-23.html').read_text(), api_payload={'days': []})
    assert menu['state'] == 'unavailable'  # not a false closed day or Arcisstraße fallback prices
    assert menu['dishes'] == []
    assert menu['warnings']
    assert config['standing_sides']  # profile creation did not mutate Arcisstraße


def test_official_closed_day_is_not_reopened_by_api(config):
    menu = real_menu(config, date(2026, 11, 28))
    assert menu['state'] == 'closed' and not menu['dishes']


def test_shared_tag_keeps_campus_local_service_metadata(config, fixture_menu):
    menu, tags = fixture_menu
    dish = {**menu['dishes'][0], 'station': 'Tagessupe, Brot, Obst', 'name': 'Linsensuppe mit Gemüse',
            'campus': 'garching', 'counter_policy': 'published_stations'}
    tags = {normalize(dish['name']): tags[normalize(menu['dishes'][0]['name'])]}
    result = food(dish, tags)
    assert result['role'] == 'soup'
    assert result['counters'] == ['Tagessupe, Brot, Obst']
    assert result['campus'] == 'garching'
    assert tags[normalize(dish['name'])]['role'] != 'soup'  # shared estimate is immutable


def test_garching_combinations_use_published_stations_not_arcis_floorplan(config, fixture_menu):
    menu, tags = fixture_menu
    dishes = copy.deepcopy(menu['dishes'])
    for i, dish in enumerate(dishes):
        dish.update(campus='garching', counter_policy='published_stations', station='Grill' if i % 2 else 'Wok')
    cfg = garching(config)
    foods = [food(d, tags) for d in dishes]
    trays = list(candidates(dishes, tags, cfg, proposals=fallback_proposals(foods)))
    assert trays
    result = plate_result(trays[0])
    assert result['counter'] is None
    assert result['stations']
    assert not any('Warm' in station for station in result['stations'])


def test_campus_paths_and_config_are_separate_but_cache_is_shared(tmp_path, config):
    assert campus_data(tmp_path, 'arcisstr') == tmp_path / 'data'
    assert campus_data(tmp_path, 'garching') == tmp_path / 'data/campuses/garching'
    assert garching(config)['lunch_cutoff'] == '14:15'
    with pytest.raises(ValueError):
        campus_config(config, '../escape')
    with pytest.raises(ValueError):
        campus_data(tmp_path, 'unrecognized')


def test_garching_batch_has_its_own_checkpoint_and_does_not_overwrite_arcis(tmp_path, config, fixture_menu):
    menu, tags = fixture_menu
    write_json(tmp_path / 'data/dish_cache.json', tags)
    original = {'week_start': '2026-11-02', 'days': []}
    write_json(tmp_path / 'data/week.json', original)
    menus = {}
    from common import week_dates
    for day in week_dates(date(2026, 11, 30), 1):
        value = copy.deepcopy(menu)
        value.update(date=str(day), campus='garching', mensa='Mensa Garching', published=True)
        for dish in value['dishes']:
            dish.update(campus='garching', counter_policy='published_stations')
        menus[str(day)] = value
    def proposer(day, foods, cfg, variant, *, cache_dir, refresh):
        eligible = [i for i in foods if variant.endswith('_all') or i.get('is_vegan')]
        write_json(cache_dir / day / f'{variant}.json', {'source': 'llm', 'combos': fallback_proposals(eligible)})
    assert run_batch(date(2026, 11, 30), garching(config), root=tmp_path, scraper=Mock(return_value=menus), tagger=Mock(), proposer=proposer)
    assert read_json(tmp_path / 'data/week.json') == original
    assert read_json(tmp_path / 'data/campuses/garching/week.json')['campus'] == 'garching'
    assert batch_ready(tmp_path, date(2026, 11, 30), 'garching')
    assert not batch_ready(tmp_path, date(2026, 11, 30), 'arcisstr')

def test_proposal_validation_does_not_apply_arcis_counter_map_to_garching(config, fixture_menu):
    from common import dish_id
    from proposals import validate_proposals
    menu, tags = fixture_menu
    dishes = copy.deepcopy(menu['dishes'])[:2]
    for dish, station in zip(dishes, ['Grill', 'Wok']):
        dish.update(station=station, counter_policy='published_stations', campus='garching')
    items = [food(d, tags) for d in dishes]
    for item in items:
        item['role'] = 'main'
    combo = [dish_id(item) for item in items]
    assert validate_proposals({'combos': [combo]}, items) == [sorted(combo)]
