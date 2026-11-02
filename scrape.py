"""Fetch today's official Arcisstraße dishes and enrich with student prices."""
import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from common import ROOT, fetch, load_config, normalize, today, write_json


class MenuParseError(ValueError):
    pass


def codes(value):
    return [s.strip() for s in value.strip("() ").split(",") if s.strip()]


def parse_official(html, day):
    """Selectors verified against tests/fixtures/arcisstr.html, fetched 2026-11-02."""
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select("#c-schedule .c-schedule__item")
    if not blocks:
        raise MenuParseError("Official menu structure changed: no daily menu blocks")
    dated_headers = 0
    for block in blocks:
        header = block.select_one(".c-schedule__header")
        match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", header.get_text(" ", strip=True) if header else "")
        if not match:
            continue
        dated_headers += 1
        if datetime.strptime(match[1], "%d.%m.%Y").date() != day:
            continue
        dishes = []
        dessert_section = False
        for item in block.select("li.c-menu-dish-list__item"):
            title = item.select_one(".c-menu-dish__title")
            station = item.select_one(".stwm-artname")
            if not title or not title.get_text(strip=True):
                raise MenuParseError("Official dish has no name")
            raw_station = station.get_text(" ", strip=True) if station else ""
            # Blank stations are real. Only continue the explicit dessert section;
            # never inherit Studitopf onto the unlabeled soup that follows it.
            if raw_station:
                dessert_section = raw_station.startswith("Dessert")
            category = raw_station or ("Dessert (Glas)" if dessert_section else "Unspecified")
            types = codes(item.get("data-essen-typ", ""))
            vegetarian_code = item.get("data-essen-fleischlos")
            vegan = vegetarian_code == "2" or bool(item.select_one(".vegan")) or "v" in types
            vegetarian = vegan or vegetarian_code == "1" or bool(item.select_one(".fleischlos")) or "f" in types
            if vegan:
                types = list(dict.fromkeys(types + ["v"]))
            elif vegetarian:
                types = list(dict.fromkeys(types + ["f"]))
            dishes.append({
                "name": title.get_text(" ", strip=True), "station": category,
                "station_raw": raw_station, "markers": types,
                "allergens": codes(item.get("data-essen-allergene", "")),
                "additives": codes(item.get("data-essen-zusatz", "")),
                "is_vegan": vegan, "is_vegetarian": vegetarian,
                "dietary_source": "official", "source": "official",
            })
        return dishes
    if not dated_headers:
        raise MenuParseError("Official menu structure changed: no dated headers")
    # A valid menu with no block for the requested date means closed/no menu.
    return []


def api_dishes(payload, day):
    if not isinstance(payload, dict) or not isinstance(payload.get("days"), list):
        raise MenuParseError("Invalid eat-api week")
    for entry in payload["days"]:
        if entry.get("date") == day.isoformat():
            if not isinstance(entry.get("dishes"), list):
                raise MenuParseError("Invalid eat-api day")
            return entry["dishes"]
    return []


def api_price(student):
    """Return a common price representation, rejecting unknown billing units."""
    if not isinstance(student, dict):
        return None
    try:
        base = float(student["base_price"])
        rate = float(student.get("price_per_unit") or 0)
        if not (0 <= base < 100 and 0 <= rate < 100):
            return None
        unit = str(student.get("unit") or "").casefold().replace(" ", "")
        if rate == 0 and base > 0:
            return {"base_eur": base, "per_100g_eur": 0, "source": "eat-api"}
        factors = {"100g": 1, "g": 100, "kg": 0.1, "1000g": 0.1}
        if unit in factors:
            return {"base_eur": base, "per_100g_eur": rate * factors[unit], "source": "eat-api"}
        if unit in {"stück", "piece", "st", "portion"}:
            return {"base_eur": base + rate, "per_100g_eur": 0, "source": "eat-api"}
    except (KeyError, TypeError, ValueError):
        pass
    return None


def fallback_price(dish, config):
    p = config["prices"]
    station = dish["station"]
    if station in p["flat_by_station"]:
        return {"base_eur": p["flat_by_station"][station], "per_100g_eur": 0, "source": "config"}
    base = 0
    # Official meatless/vegan markings take precedence over words like Veggie-Schnitzel.
    if not dish["is_vegetarian"]:
        if station == "Fisch" or re.search(p["fish_name_pattern"], dish["name"]):
            base = p["fish_base"]
        elif (station == "Fleisch" or set(dish["markers"]) & set(p["meat_markers"])
              or re.search(p["meat_name_pattern"], dish["name"])):
            base = p["meat_base"]
    return {"base_eur": base, "per_100g_eur": p["station_per_100g"].get(station, p["default_per_100g"]), "source": "config"}


def enrich_prices(dishes, api, config):
    by_name = {}
    for entry in api:
        by_name.setdefault(normalize(entry["name"]), []).append(entry)
    for dish in dishes:
        matches = by_name.get(normalize(dish["name"]), [])
        # Ambiguous matches use category rules; never silently choose a recipe.
        match = matches[0] if len(matches) == 1 else None
        dish["api_labels"] = match.get("labels", []) if match else []
        price = api_price(match.get("prices", {}).get("students")) if match else None
        dish["price"] = price or fallback_price(dish, config)
        # Official unknown means NOT vegan, even when its name sounds vegan.
    return dishes


def from_api(entries):
    dishes = []
    for entry in entries:
        labels = entry.get("labels", [])
        vegan = "VEGAN" in labels
        dishes.append({"name": entry["name"], "station": entry.get("dish_type") or "Unspecified",
                       "station_raw": entry.get("dish_type") or "", "markers": [],
                       "allergens": [], "additives": [], "is_vegan": vegan,
                       "is_vegetarian": vegan or "VEGETARIAN" in labels,
                       "dietary_source": "eat-api", "source": "eat-api"})
    return dishes


def append_standing_sides(dishes, config):
    """Only augment a real open menu; counter staples cannot manufacture an open day."""
    if not dishes:
        return dishes
    names = {normalize(d["name"]) for d in dishes}
    for side in config.get("standing_sides", []):
        if normalize(side["name"]) in names:
            continue
        vegan = side.get("is_vegan") is True
        dishes.append({"name": side["name"], "name_en": side["name_en"], "station": side["station"],
                       "station_raw": side["station"], "standing": True, "is_vegan": vegan,
                       "is_vegetarian": vegan or side.get("is_vegetarian") is True,
                       "markers": ["v"] if vegan else [], "allergens": [], "additives": [],
                       "dietary_source": "config", "source": "config", "api_labels": [],
                       "price_source": "config", "price": {"base_eur": 0,
                       "per_100g_eur": config["prices"]["default_per_100g"], "source": "config"}})
        names.add(normalize(side["name"]))
    return dishes


def scrape(day, config, html=None, api_payload=None, fetcher=fetch):
    warnings = []
    iso = day.isocalendar()
    api_url = config["eat_api_url"].format(year=iso.year, week=iso.week)
    # Fetch the official source first. Transport/parser errors may use eat-api;
    # an official closed day must never be replaced with an API menu.
    official_error = None
    try:
        dishes = parse_official(html if html is not None else fetcher(config["official_url"]), day)
    except (OSError, ValueError) as exc:
        official_error = exc
        dishes = None
        warnings.append("Official menu unavailable; using the smaller eat-api menu.")
    api = []
    try:
        api = api_dishes(api_payload if api_payload is not None else json.loads(fetcher(api_url)), day)
    except (OSError, ValueError, KeyError, TypeError):
        if dishes is None:
            raise RuntimeError("Both menu sources failed; refusing to publish a false closed state") from official_error
        warnings.append("eat-api prices unavailable; using configured student prices.")
    if dishes is None:
        dishes = from_api(api)
    enrich_prices(dishes, api, config)
    append_standing_sides(dishes, config)
    return {"schema_version": 1, "date": day.isoformat(), "mensa": "Mensa Arcisstraße",
            "state": "open" if dishes else "closed", "source": "eat-api" if official_error else "official",
            "source_url": config["official_url"], "price_source_url": api_url,
            "fetched_at": datetime.now(timezone.utc).isoformat(), "warnings": warnings, "dishes": dishes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--html", type=Path, help="Read saved official HTML (offline/replay)")
    parser.add_argument("--api-json", type=Path, help="Read saved eat-api JSON")
    parser.add_argument("--save-html", type=Path, help="Save freshly fetched HTML as a fixture")
    parser.add_argument("--output", type=Path, default=ROOT / "data/menu.json")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    html = args.html.read_text() if args.html else None
    if args.save_html:
        html = fetch(config["official_url"])
        args.save_html.parent.mkdir(parents=True, exist_ok=True)
        args.save_html.write_text(html)
    payload = json.loads(args.api_json.read_text()) if args.api_json else None
    result = scrape(args.date or today(config), config, html, payload)
    write_json(args.output, result)
    print(f"{result['date']}: {result['state']}, {len(result['dishes'])} dishes ({result['source']})")
    for warning in result["warnings"]:
        print(warning, file=sys.stderr)


if __name__ == "__main__":
    main()
