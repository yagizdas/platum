import json
from datetime import date

import pytest

from scrape import MenuParseError, api_dishes, api_price, enrich_prices, parse_official, scrape
from conftest import FIXTURES

DAY = date(2026, 11, 2)


@pytest.fixture
def html():
    return (FIXTURES / "arcisstr.html").read_text()


@pytest.fixture
def api():
    return json.loads((FIXTURES / "eat-api-2026-45.json").read_text())


def test_real_html_has_all_twelve_today_only(html, api):
    dishes = parse_official(html, DAY)
    assert len(dishes) == 12
    assert len(api_dishes(api, DAY)) == 6
    assert dishes[0]["name"] == "Vegane Maultaschen mit Zwiebelmarmelade"
    assert dishes[-1]["name"] == "Cappuccinocreme"
    assert not any("Knöpfle" in d["name"] for d in dishes)
    assert {d["station"] for d in dishes} >= {"Pasta", "Pizza", "Grill", "Wok", "Studitopf", "Fisch", "Vegan", "Dessert (Glas)"}
    assert dishes[5]["station"] == "Unspecified" # blank soup station doesn't inherit Studitopf
    assert dishes[10]["station"] == "Dessert (Glas)"


def test_markers_allergens_additives_and_unknown(html):
    dishes = parse_official(html, DAY)
    assert dishes[0]["is_vegan"] is True
    assert dishes[0]["markers"] == ["v"]
    assert dishes[1]["is_vegetarian"] and not dishes[1]["is_vegan"]
    assert dishes[2]["markers"] == ["R", "S"]
    assert dishes[2]["additives"] == ["2", "3", "8"]
    assert dishes[2]["allergens"] == ["Mi", "Sf"]
    assert dishes[5]["is_vegan"] is False
    assert dishes[7]["allergens"] == ["Fi"]
    changed = html.replace('data-essen-fleischlos="2"', 'data-essen-fleischlos="0"').replace('class="vegan"', 'class="unknown"')
    assert parse_official(changed, DAY)[0]["is_vegan"] is False # name alone never implies vegan


def test_prices_official_superset_is_preserved(html, api, config):
    result = scrape(DAY, config, html, api)
    d = result["dishes"]
    assert result["source"] == "official" and len(d) == 14
    assert d[0]["price"] == {"base_eur": 0., "per_100g_eur": .9, "source": "eat-api"}
    assert d[1]["price"] == {"base_eur": 5., "per_100g_eur": 0, "source": "config"}
    assert d[2]["price"]["base_eur"] == 1.
    assert d[4]["price"]["per_100g_eur"] == .33
    assert d[7]["price"]["base_eur"] == 1.5


def test_no_fuzzy_recipe_match(html, config):
    d = parse_official(html, DAY)
    api = [{"name": d[0]["name"] + " mit Käse", "prices": {"students": {"base_price": 99, "price_per_unit": 0, "unit": ""}}}]
    enrich_prices(d, api, config)
    assert d[0]["price"]["source"] == "config"


def test_no_menu_is_closed_and_api_does_not_override(html, api, config):
    assert parse_official(html, date(2026, 11, 8)) == []
    changed = html.replace("02.11.2026", "01.11.2026")
    result = scrape(DAY, config, changed, api)
    assert result["state"] == "closed" and result["dishes"] == []
    assert scrape(date(2026, 12, 25), config, html, api)["state"] == "closed"


def test_unavailable_official_uses_labeled_api_fallback(api, config):
    result = scrape(DAY, config, "<h1>maintenance</h1>", api)
    assert result["state"] == "open" and result["source"] == "eat-api"
    assert len(result["dishes"]) == 8 and result["warnings"]
    assert result["dishes"][0]["is_vegan"] is True


def test_both_sources_failing_does_not_fake_closed(config):
    def failed(url):
        raise OSError("network offline")
    with pytest.raises(RuntimeError, match="Both menu sources failed"):
        scrape(DAY, config, fetcher=failed)
    with pytest.raises(MenuParseError):
        parse_official("<html>changed</html>", DAY)
    with pytest.raises(MenuParseError, match="dated headers"):
        parse_official('<div id="c-schedule"><div class="c-schedule__item">changed</div></div>', DAY)


def test_missing_api_uses_config_prices(html, config):
    def failed(url):
        raise OSError("network offline")
    result = scrape(DAY, config, html=html, fetcher=failed)
    assert len(result["dishes"]) == 14
    assert all(d["price"]["source"] == "config" for d in result["dishes"])
    assert result["dishes"][4]["price"]["per_100g_eur"] == .33


@pytest.mark.parametrize("unit,rate,expected", [("100g", .9, .9), ("kg", 9, .9), ("g", .009, .9)])
def test_api_weight_units(unit, rate, expected):
    assert api_price({"base_price": 1, "price_per_unit": rate, "unit": unit})["per_100g_eur"] == pytest.approx(expected)


def test_api_unknown_unit_uses_fallback():
    assert api_price({"base_price": 0, "price_per_unit": 1, "unit": "unknown"}) is None
    assert api_price({"base_price": 5, "price_per_unit": 0, "unit": ""})["base_eur"] == 5
    assert api_price({"base_price": 0, "price_per_unit": 2, "unit": "Stück"})["base_eur"] == 2


def test_iso_week_uses_iso_year(html, config):
    urls = []
    def capture(url):
        urls.append(url)
        return '{"days": []}'
    scrape(date(2027, 1, 1), config, html=html, fetcher=capture)
    assert urls == [config["eat_api_url"].format(year=2026, week=53)]


def test_standing_sides_only_on_open_days_and_use_config(html, api, config):
    from common import normalize
    opened = scrape(DAY, config, html, api)
    sides = [d for d in opened["dishes"] if d.get("standing")]
    assert {d["name"] for d in sides} == {"Reis", "Kartoffelsalat"}
    assert next(d for d in sides if d["name"] == "Reis")["is_vegan"] is True
    assert next(d for d in sides if d["name"] == "Kartoffelsalat")["is_vegan"] is False
    assert all(d["price"]["source"] == "config" and d["price"]["per_100g_eur"] == .9 for d in sides)
    assert not scrape(date(2026, 11, 8), config, html, api)["dishes"]
    config["standing_sides"][0]["is_vegan"] = False
    sides = [d for d in scrape(DAY, config, html, api)["dishes"] if d.get("standing")]
    assert all(d["is_vegan"] is False for d in sides)


@pytest.mark.parametrize("state,dishes", [("closed", []), ("open", [])])
def test_past_menu_history_is_not_overwritten(tmp_path, config, state, dishes):
    from common import read_json, write_json
    from scrape import save_menu
    path = tmp_path / "2026-11-02.json"
    original = {"date": "2026-11-02", "state": "open", "dishes": [{"name": "Recorded lunch"}]}
    write_json(path, original)
    before = path.read_bytes()
    assert save_menu(path, {**original, "state": state, "dishes": dishes}, date(2026, 11, 6)) == original
    assert path.read_bytes() == before
    # A current closure remains authoritative.
    save_menu(path, {**original, "state": "closed", "dishes": []}, date(2026, 11, 2))
    assert read_json(path)["state"] == "closed"
