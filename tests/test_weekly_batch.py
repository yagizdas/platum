import copy
from datetime import date
from unittest.mock import Mock
import pytest

from common import read_json, week_dates, write_json
from proposals import fallback_proposals
from weekly_batch import batch_ready, next_monday, run_batch


@pytest.fixture(autouse=True)
def legacy_proposal_config(config):
    """These regression cases exercise the archived LLM-proposal batch workflow."""
    config.pop('recommendations', None)


def batch_fixture(root, fixture_menu):
    menu, tags = fixture_menu
    monday = date(2026, 11, 30)
    menus = {day.isoformat(): {**copy.deepcopy(menu), 'date': day.isoformat(), 'published': True}
             for day in week_dates(monday, 1)}
    write_json(root / 'data/dish_cache.json', tags)
    def proposer(day, foods, config, variant, *, cache_dir, refresh=False):
        path = cache_dir / day / f'{variant}.json'
        if not path.exists() or refresh:
            eligible = [item for item in foods if variant.endswith('_all') or item.get('is_vegan') is True]
            write_json(path, {'source': 'llm', 'combos': fallback_proposals(eligible)})
    return monday, menus, Mock(side_effect=proposer)


def test_weekend_target_is_the_coming_monday_across_month_and_year():
    assert next_monday(date(2026, 11, 28)) == date(2026, 11, 30)
    assert next_monday(date(2026, 11, 29)) == date(2026, 11, 30)
    assert next_monday(date(2026, 12, 27)) == date(2026, 12, 28)
    assert next_monday(date(2027, 1, 2)) == date(2027, 1, 4)


def test_successful_saturday_skips_all_fetches_and_model_calls_on_sunday(tmp_path, config, fixture_menu):
    monday, menus, proposer = batch_fixture(tmp_path, fixture_menu)
    scraper = Mock(return_value=menus)
    tagger = Mock()
    assert run_batch(monday, config, root=tmp_path, scraper=scraper, tagger=tagger, proposer=proposer)
    scraper.assert_called_once_with(monday, config, weeks=1)
    assert len(read_json(tmp_path / 'data/week.json')['days']) == 5
    assert batch_ready(tmp_path, monday)
    assert run_batch(monday, config, root=tmp_path, scraper=Mock(side_effect=AssertionError('Fetched again')),
                     tagger=Mock(side_effect=AssertionError('Tagged again')), proposer=Mock(side_effect=AssertionError('Called again')))


def test_missing_source_date_preserves_public_batch_and_sunday_can_retry(tmp_path, config, fixture_menu):
    monday, menus, proposer = batch_fixture(tmp_path, fixture_menu)
    old = {'week_start': '2026-11-23', 'days': []}
    write_json(tmp_path / 'data/week.json', old)
    menus['2026-12-04']['published'] = False
    assert not run_batch(monday, config, root=tmp_path, scraper=Mock(return_value=menus), tagger=Mock(), proposer=proposer)
    assert read_json(tmp_path / 'data/week.json') == old
    assert not batch_ready(tmp_path, monday)
    menus['2026-12-04']['published'] = True
    assert run_batch(monday, config, root=tmp_path, scraper=Mock(return_value=menus), tagger=Mock(), proposer=proposer)
    assert read_json(tmp_path / 'data/week.json')['valid_through'] == '2026-12-04'


def test_unpublished_empty_week_cannot_replace_current_menus(tmp_path, config, fixture_menu):
    monday, menus, proposer = batch_fixture(tmp_path, fixture_menu)
    for menu in menus.values():
        menu.update(state='closed', dishes=[], published=False)
    write_json(tmp_path / 'data/week.json', {'week_start': '2026-11-23'})
    assert not run_batch(monday, config, root=tmp_path, scraper=Mock(return_value=menus), tagger=Mock(), proposer=proposer)
    assert read_json(tmp_path / 'data/week.json')['week_start'] == '2026-11-23'
    proposer.assert_not_called()


def test_failed_proposal_retried_but_good_caches_not_refreshed(tmp_path, config, fixture_menu):
    monday, menus, proposer = batch_fixture(tmp_path, fixture_menu)
    first = tmp_path / 'data/proposals/2026-11-30'
    write_json(first / 'bulk_all.json', {'source': 'fallback', 'combos': []})
    write_json(first / 'cut_all.json', {'source': 'llm', 'combos': []})
    assert run_batch(monday, config, root=tmp_path, scraper=Mock(return_value=menus), tagger=Mock(), proposer=proposer)
    by_variant = {call.args[3]: call.kwargs['refresh'] for call in proposer.call_args_list if call.args[0] == '2026-11-30'}
    assert by_variant['bulk_all'] is True
    assert by_variant['cut_all'] is False


def test_source_failure_keeps_prior_public_data(tmp_path, config):
    write_json(tmp_path / 'data/week.json', {'week_start': '2026-11-23'})
    assert not run_batch(date(2026, 11, 30), config, root=tmp_path,
                         scraper=Mock(side_effect=RuntimeError('Unavailable')), tagger=Mock())
    assert read_json(tmp_path / 'data/week.json')['week_start'] == '2026-11-23'


def test_rescore_uses_saved_batch_dates_without_fetches_or_models(tmp_path, fixture_menu, monkeypatch):
    import rescore_cached
    menu, tags = fixture_menu
    dates = ['2026-11-30', '2026-12-01', '2026-12-02', '2026-12-03', '2026-12-04']
    write_json(tmp_path / 'data/week.json', {'week_start': dates[0], 'days': [{'date': day} for day in dates]})
    write_json(tmp_path / 'data/dish_cache.json', tags)
    for day in dates:
        write_json(tmp_path / 'data/menus' / f'{day}.json', {**menu, 'date': day})
    builder = Mock(return_value=({day: {'date': day} for day in dates}, {'week_start': dates[0]}))
    monkeypatch.setattr(rescore_cached, 'build_week', builder)
    rescore_cached.rescore(tmp_path)
    args, kwargs = builder.call_args
    assert args[0] == date(2026, 11, 30)
    assert list(args[1]) == dates
    assert kwargs['no_llm'] is True


def test_explicitly_published_holiday_week_is_valid_without_model_proposals(tmp_path, config, fixture_menu):
    monday, menus, proposer = batch_fixture(tmp_path, fixture_menu)
    for menu in menus.values():
        menu.update(state='closed', dishes=[], published=True)
    assert run_batch(monday, config, root=tmp_path, scraper=Mock(return_value=menus), tagger=Mock(), proposer=proposer)
    assert batch_ready(tmp_path, monday)
    proposer.assert_not_called()
    assert all(row['state'] == 'closed' for row in read_json(tmp_path / 'data/week.json')['days'])


def test_refresh_updates_only_changed_days_and_retries_a_stale_proposal_cache(tmp_path, config, fixture_menu):
    monday, menus, proposer = batch_fixture(tmp_path, fixture_menu)
    assert run_batch(monday, config, root=tmp_path, scraper=Mock(return_value=menus), tagger=Mock(), proposer=proposer)
    original_public = read_json(tmp_path / 'data/week.json')
    changed = copy.deepcopy(menus)
    first = str(monday)
    changed[first]['dishes'][0]['is_vegan'] = not changed[first]['dishes'][0]['is_vegan']
    # The adapter preserving the prior cache after a failed model refresh must not
    # allow a stale batch to be marked complete or overwrite the public batch.
    assert not run_batch(monday, config, root=tmp_path, scraper=Mock(return_value=changed),
                         tagger=Mock(), proposer=Mock(), refresh=True)
    assert read_json(tmp_path / 'data/week.json') == original_public
    proposer.reset_mock()
    assert run_batch(monday, config, root=tmp_path, scraper=Mock(return_value=changed),
                     tagger=Mock(), proposer=proposer, refresh=True)
    assert all(call.kwargs['refresh'] is (call.args[0] == first) for call in proposer.call_args_list)
    proposer.reset_mock()
    assert run_batch(monday, config, root=tmp_path, scraper=Mock(return_value=changed),
                     tagger=Mock(), proposer=proposer, refresh=True)
    assert all(call.kwargs['refresh'] is False for call in proposer.call_args_list)


def test_refresh_keeps_archived_dates_that_have_rolled_off_official_source(tmp_path, config, fixture_menu, monkeypatch):
    import weekly_batch
    monday, menus, proposer = batch_fixture(tmp_path, fixture_menu)
    assert run_batch(monday, config, root=tmp_path, scraper=Mock(return_value=menus), tagger=Mock(), proposer=proposer)
    monkeypatch.setattr(weekly_batch, 'today', lambda cfg: date(2026, 12, 2))
    archived = read_json(tmp_path / 'data/menus' / f'{monday}.json')
    fresh = copy.deepcopy(menus)
    fresh[str(monday)].update(state='closed', dishes=[], published=False)
    assert run_batch(monday, config, root=tmp_path, scraper=Mock(return_value=fresh),
                     tagger=Mock(), proposer=proposer, refresh=True)
    assert read_json(tmp_path / 'data/menus' / f'{monday}.json') == archived
    assert read_json(tmp_path / 'data/days' / f'{monday}.json')['state'] == 'open'
