import copy
import json
from datetime import date
from unittest.mock import Mock

from common import week_dates, read_json
from pick import build_week
from proposals import fallback_proposals
from scrape import scrape_week
from conftest import FIXTURES


def test_week_dates_include_following_workweek_and_iso_boundary():
    dates = week_dates(date(2026, 11, 7))
    assert len(dates) == 10
    assert dates[0] == date(2026, 11, 2) and dates[-1] == date(2026, 11, 13)
    assert all(d.weekday() < 5 for d in dates)
    assert week_dates(date(2027, 1, 1))[0].isocalendar().year == 2026


def test_week_scrape_fetches_each_source_once(config):
    html = (FIXTURES / "arcisstr.html").read_text()
    api = (FIXTURES / "eat-api-2026-45.json").read_text()
    calls = []
    def fetcher(url):
        calls.append(url)
        return html if url == config["official_url"] else api if "/45.json" in url else '{"days":[]}'
    menus = scrape_week(date(2026, 11, 2), config, fetcher=fetcher)
    assert len(menus) == 10 and len(calls) == 3
    assert calls.count(config["official_url"]) == 1
    assert all(any(d.get("standing") for d in m["dishes"]) for m in menus.values() if m["state"] == "open")


def test_week_closed_day_has_no_standing_sides(config):
    html = (FIXTURES / "arcisstr.html").read_text().replace("03.11.2026", "02.11.2026")
    api = json.loads((FIXTURES / "eat-api-2026-45.json").read_text())
    menus = scrape_week(date(2026, 11, 2), config, html, {(2026, 45): api, (2026, 46): {"days": []}})
    assert menus["2026-11-03"]["state"] == "closed"
    assert menus["2026-11-03"]["dishes"] == []


def test_week_output_and_judge_calls_remain_per_date(config, fixture_menu, pairing, tmp_path):
    config["llm"]["enabled"] = True
    menu, tags = fixture_menu
    menus = {}
    for day in week_dates(date(2026, 11, 2)):
        m = copy.deepcopy(menu);m["date"] = day.isoformat();menus[m["date"]] = m
    menus["2026-11-04"].update(state="closed", dishes=[])
    def respond(pools, *args):
        return {key: [{"id": p["id"], "title": "A coherent lunch", "reason": "A satisfying pairing."}
                      for p in values] for key, values in pools.items() if values}
    caller = Mock(side_effect=respond)
    args = dict(pairing=pairing, api_key="test", judge_caller=caller, judge_cache_path=tmp_path / "judge.json",
                proposal_caller=lambda items, *a, **kw: {"combos": fallback_proposals(items)}, proposals_dir=tmp_path / "proposals")
    days, index = build_week(date(2026, 11, 2), menus, tags, config, **args)
    assert caller.call_count == 9
    build_week(date(2026, 11, 2), menus, tags, config, **args)
    assert caller.call_count == 9
    assert len(read_json(tmp_path / "judge.json")) == 9
    assert index["week_start"] == "2026-11-02" and index["valid_through"] == "2026-11-13"
    assert index["lunch_cutoff"] == "14:30"
    for row in index["days"]:
        assert row["file"] == "data/days/" + row["date"] + ".json"
        assert days[row["date"]]["date"] == row["date"]
        assert days[row["date"]]["schema_version"] == 2
        assert days[row["date"]]["generated_on"] == "2026-11-02"
    assert days["2026-11-04"]["extras"] == {"all": [], "vegan": []}


def test_single_failing_tag_in_ten_day_window_keeps_all_other_plates(config, fixture_menu):
    from common import normalize
    menu, tags = fixture_menu
    menus = {}
    for day in week_dates(date(2026, 11, 6)):
        menus[day.isoformat()] = {**copy.deepcopy(menu), "date": day.isoformat()}
    broken = copy.deepcopy(menu["dishes"][0]);broken["name"] = "Unrepairable model response"
    menus["2026-11-06"]["dishes"].insert(0, broken)
    days, index = build_week(date(2026, 11, 6), menus, tags, config, no_llm=True)
    assert len(days) == len(index["days"]) == 10
    assert all(day["variants"]["bulk_all"]["plates"] for day in days.values())
    assert days["2026-11-06"]["missing_tags"] == [broken["name"]]
    assert days["2026-11-06"]["warnings"]
    assert normalize(broken["name"]) not in tags


def test_missing_menu_file_is_isolated_to_one_day(config, fixture_menu):
    menu, tags = fixture_menu
    menus = {day.isoformat(): {**copy.deepcopy(menu), "date": day.isoformat()}
             for day in week_dates(date(2026, 11, 6))}
    menus["2026-11-06"] = None
    days, index = build_week(date(2026, 11, 6), menus, tags, config, no_llm=True)
    assert days["2026-11-06"]["state"] == "unavailable"
    assert days["2026-11-06"]["warnings"]
    assert all(day["variants"]["bulk_all"]["plates"] for name, day in days.items() if name != "2026-11-06")
