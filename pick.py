"""Build coherent one/two-dish lunches, diverse alternatives, and optional extras."""
import argparse
import itertools
import math
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from common import ROOT, load_config, normalize, read_json, today, week_dates, write_json
from judge import choose_variants
from pair import food, load_pairing, pair_score, stands_alone

GOALS = ("bulk", "cut", "budget")
SCHEMA_VERSION = 2


def price_cents(price, grams):
    euros = Decimal(str(price["base_eur"])) + Decimal(str(price["per_100g_eur"])) * Decimal(str(grams)) / 100
    return int((euros * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def scoop_size(dish, config):
    size = config["portions"]["station_scoop_g"].get(dish["station"], config["portions"]["default_scoop_g"])
    if type(size) not in (int, float) or not math.isfinite(size) or size <= 0:
        raise ValueError("Scoop sizes must be finite positive grams")
    return size


def diet(item, config):
    if item.get("is_vegan") is True:
        return "vegan"
    if item.get("is_vegetarian") is True or "f" in item.get("markers", []):
        return "vegetarian"
    p = config["prices"]
    if item["station"] == "Fisch" or re.search(p["fish_name_pattern"], item["name"]) or "FISH" in item.get("api_labels", []):
        return "fish"
    if (set(item.get("markers", [])) & set(p["meat_markers"]) or item["station"] in {"Fleisch", "Grill"}
            or re.search(p["meat_name_pattern"], item["name"])):
        return "meat"
    # Unknown dietary status (including unconfirmed broth) never implies meatless.
    return "meat"


def portion_options(dish, tag, config, paired=False):
    item = {**dish, **tag, "standing": dish.get("standing") is True}
    if item["standing"]:
        item.update(role="side", is_per_piece=False, piece_weight_g=None)
    lo, hi = item["typical_portion_g"]["min"], item["typical_portion_g"]["max"]
    limit = min(hi, config["portions"]["max_plate_g"])
    size = scoop_size(item, config)
    if item["is_per_piece"]:
        portions = [(1, item["piece_weight_g"], "piece")] if item["piece_weight_g"] <= limit else []
    else:
        first = 1 if paired else max(1, math.ceil(lo / size))
        portions = [(n, n * size, "scoop") for n in range(first, min(3, math.floor(limit / size)) + 1)]
    options = []
    for count, grams, unit in portions:
        options.append({**item, "count": count, "unit": unit, "weight_g": grams,
                        "price_cents": price_cents(item["price"], grams), "diet": diet(item, config),
                        **{n: item[f"{n}_per_100g"] * grams / 100 for n in ("kcal", "protein", "carbs", "fat")}})
    return options


def valid_plate(items, config, pairing=None):
    pairing = pairing or {}
    if not 1 <= len(items) <= 2 or len({normalize(i["name"]) for i in items}) != len(items):
        return False
    if any((i["role"] != "main" and not i.get("standing")) or i["texture"] == "liquid" for i in items):
        return False
    if sum(i.get("standing", False) for i in items) > 1 or all(i.get("standing") for i in items):
        return False
    if sum(i["is_per_piece"] for i in items) > 1 or sum(i["weight_g"] for i in items) > config["portions"]["max_plate_g"]:
        return False
    for i in items:
        if i["is_per_piece"]:
            if i["count"] != 1 or i["unit"] != "piece" or i["weight_g"] != i["piece_weight_g"]:
                return False
        elif (i["unit"] != "scoop" or type(i["count"]) is not int or not 1 <= i["count"] <= 3
              or i["weight_g"] != i["count"] * scoop_size(i, config)):
            return False
        if i["weight_g"] > i["typical_portion_g"]["max"]:
            return False
    if len(items) == 1:
        return stands_alone(items[0], pairing) and items[0]["weight_g"] >= items[0]["typical_portion_g"]["min"]
    return all(i["station"] != "Pizza" for i in items) and pair_score(*items, pairing) >= config["pairing"]["min_score"]


def ordered_items(items):
    return sorted(items, key=lambda i: (not i["is_per_piece"], -i["weight_g"], normalize(i["name"])))


def plate(items):
    return {"items": ordered_items(items), "price_cents": sum(i["price_cents"] for i in items),
            "weight_g": sum(i["weight_g"] for i in items),
            **{n: sum(i[n] for i in items) for n in ("kcal", "protein", "carbs", "fat")}}


def candidates(dishes, cache, config, vegan=False, pairing=None):
    items = [food(d, cache) for d in dishes if not vegan or d.get("is_vegan") is True]
    items = [i for i in items if (i["role"] == "main" or i["standing"]) and i["texture"] != "liquid"]
    for item in items:
        for option in portion_options(item, item, config):
            if valid_plate([option], config, pairing):
                yield plate([option])
    for a, b in itertools.combinations(items, 2):
        if a["station"] == "Pizza" or b["station"] == "Pizza" or pair_score(a, b, pairing or {}) < config["pairing"]["min_score"]:
            continue
        for combo in itertools.product(portion_options(a, a, config, paired=True), portion_options(b, b, config, paired=True)):
            if valid_plate(combo, config, pairing):
                yield plate(combo)


def top_plates(plates, goal, config, top_k=8, relax_protein=False):
    g = config["goals"]
    floor = g[f"{goal}_min_protein_g"]
    valid = [p for p in plates if (relax_protein or p["protein"] >= floor)
             and (goal == "bulk" or p["kcal"] >= g[f"{goal}_min_kcal"])]
    if goal == "bulk":
        rank = lambda p: (-(p["kcal"] + g["bulk_protein_weight"] * p["protein"]), p["price_cents"], p["weight_g"])
    elif goal == "cut":
        rank = lambda p: (-p["protein"] / max(p["kcal"], 1), p["price_cents"], p["weight_g"])
    elif goal == "budget":
        rank = lambda p: (p["price_cents"], -p["protein"], p["weight_g"])
    else:
        raise ValueError(f"Unknown goal: {goal}")
    seen, result = set(), []
    for p in sorted(valid, key=rank):
        dish_set = tuple(sorted(normalize(i["name"]) for i in p["items"]))
        if dish_set not in seen:
            seen.add(dish_set)
            result.append(p)
            if len(result) >= top_k:
                break
    return result


def choose(plates, goal, config, relax_protein=False):
    ranked = top_plates(plates, goal, config, 1, relax_protein)
    return ranked[0] if ranked else None


def rank_variant(plates, goal, vegan, config):
    k = config["llm"]["top_k"]
    if type(k) is not int or k < 1:
        raise ValueError("llm.top_k must be a positive integer")
    ranked = top_plates(plates, goal, config, k)
    relaxed, note = False, None
    if vegan and not ranked:
        ranked = top_plates(plates, goal, config, k, True)
        relaxed = True
        note = f"No vegan lunch reaches {config['goals'][f'{goal}_min_protein_g']:g}g protein today; the protein target is relaxed."
    return ranked, relaxed, note


def serving(item):
    return f"{item['count']} {item['unit']}{'s' if item['count'] != 1 else ''}"


def short_name(name):
    name = re.sub(r"\s*\(1\s*Stück\)", "", name, flags=re.I)
    return re.split(r"\s+(?:mit|auf|aus|in|an)\s+", name, maxsplit=1, flags=re.I)[0].strip()


def plate_result(value, goal=None, vegan=None, config=None):
    items = []
    for i in value["items"]:
        items.append({k: i[k] for k in ("name", "name_en", "station", "role", "texture", "count", "unit", "weight_g",
                                        "price_cents", "is_vegan", "markers", "allergens", "additives", "standing", "diet")}
                     | {"serving": serving(i), "price_source": i["price"]["source"], "kcal": round(i["kcal"], 2), "protein_g": round(i["protein"], 2)})
    total = {"price_cents": value["price_cents"], "price_eur": value["price_cents"] / 100, "weight_g": value["weight_g"],
             "kcal": round(value["kcal"], 2), **{f"{n}_g": round(value[n], 2) for n in ("protein", "carbs", "fat")}}
    return {"title": " + ".join(short_name(i["name"]) for i in value["items"]), "reason": None, "picked_by": "rules",
            "items": items, "total": total, "has_estimated_prices": any(i["price_source"] == "config" for i in items)}


def extras(dishes, cache, config):
    all_extras = []
    for d in dishes:
        item = food(d, cache)
        if (item["role"] not in {"soup", "dessert"} and item["texture"] != "liquid") or item["standing"]:
            continue
        options = portion_options(item, item, config)
        if options:
            i = options[0]
            all_extras.append({k: i[k] for k in ("name", "name_en", "station", "weight_g", "price_cents", "is_vegan", "diet")}
                              | {"serving": serving(i), "kcal": round(i["kcal"], 2), "protein_g": round(i["protein"], 2), "price_source": i["price"]["source"]})
    return {"all": all_extras, "vegan": [i for i in all_extras if i["is_vegan"] is True]}


def judge_payload(ranked, config):
    result = {}
    for key, values in ranked.items():
        result[key] = []
        for index, value in enumerate(values):
            p = plate_result(value)
            result[key].append({"id": f"c{index}", "dishes": [{k: i[k] for k in ("name", "name_en", "station", "serving")} for i in p["items"]],
                                "totals": {k: p["total"][k] for k in ("price_eur", "kcal", "protein_g")}})
    return result


def build_today(menu, cache, config, allow_missing=False, *, pairing=None, no_llm=False, api_key=None, judge_caller=None, judge_cache_path=None):
    missing = [d["name"] for d in menu["dishes"] if normalize(d["name"]) not in cache]
    if missing and not allow_missing:
        raise ValueError(f"{len(missing)} dishes need tagging; run tag.py first. Refusing to pick from a partial menu.")
    result = {k: menu[k] for k in ("date", "mensa", "state", "source", "source_url", "fetched_at", "warnings")}
    result.update(schema_version=SCHEMA_VERSION, menu_count=len(menu["dishes"]), goals=config["goals"],
                  max_plate_g=config["portions"]["max_plate_g"], default_scoop_g=config["portions"]["default_scoop_g"],
                  nutrition_note="Nutrition values are estimates.", variants={}, extras={"all": [], "vegan": []})
    if missing:
        result.update(state="unavailable", reason="Today's menu is here. Plate recommendations are waiting for nutrition estimates.", missing_tags=missing)
    ranked = {}
    if result["state"] == "open":
        result["extras"] = extras(menu["dishes"], cache, config)
    for vegan in (False, True):
        values = list(candidates(menu["dishes"], cache, config, vegan, pairing)) if result["state"] == "open" else []
        for goal in GOALS:
            key = f"{goal}_{'vegan' if vegan else 'all'}"
            pool, relaxed, note = rank_variant(values, goal, vegan, config) if result["state"] == "open" else ([], False, None)
            ranked[key] = pool
            state = ("ready" if pool else "unavailable") if result["state"] == "open" else result["state"]
            result["variants"][key] = {"state": state, "goal": goal, "vegan": vegan, "relaxed": relaxed, "note": note,
                                       "plates": [plate_result(p) for p in pool[:3]]}
            if not pool:
                result["variants"][key]["message"] = result.get("reason") or ("No menu is published for this date." if state == "closed" else "No lunch meets this goal's remaining requirements today.")
    if not no_llm and config["llm"]["enabled"]:
        choices = choose_variants(judge_payload(ranked, config), config["gemini_model"], menu["date"],
                                  api_key=api_key, caller=judge_caller, cache_path=judge_cache_path)
        for key, selection in choices.items():
            plates = []
            for index, choice in enumerate(selection):
                selected = plate_result(ranked[key][int(choice["id"][1:])])
                selected.update(title=choice["title"], reason=choice.get("reason") if index == 0 else None, picked_by="llm")
                plates.append(selected)
            result["variants"][key]["plates"] = plates
    return result


def build_week(reference, menus, cache, config, **options):
    days = {}
    for name, menu in sorted(menus.items()):
        days[name] = build_today(menu, cache, config, **options)
        days[name]["generated_on"] = reference.isoformat()
    names = sorted(days)
    index = {"schema_version": SCHEMA_VERSION, "generated_on": reference.isoformat(),
             "week_start": names[0], "valid_through": names[-1], "lunch_cutoff": "14:30",
             "days": [{"date": name, "state": days[name]["state"], "file": f"data/days/{name}.json"} for name in names]}
    return days, index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--menu", type=Path, default=ROOT / "data/menu.json")
    parser.add_argument("--week", action="store_true")
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--cache", type=Path, default=ROOT / "data/dish_cache.json")
    parser.add_argument("--pairing-cache", type=Path, default=ROOT / "data/pairing_cache.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/today.json")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--allow-missing-tags", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    reference = args.date or today(config)
    tags = read_json(args.cache, {})
    options = {"pairing": load_pairing(args.pairing_cache), "no_llm": args.no_llm, "judge_cache_path": ROOT / "data/judge_cache.json"}
    if args.week:
        menus = {day.isoformat(): read_json(ROOT / "data/menus" / f"{day.isoformat()}.json") for day in week_dates(reference)}
        days, index = build_week(reference, menus, tags, config, **options)
        for name, data in days.items():
            write_json(ROOT / "data/days" / f"{name}.json", data)
        write_json(ROOT / "data/week.json", index)
        result = days.get(reference.isoformat()) or build_today(read_json(args.menu), tags, config, **options)
    else:
        result = build_today(read_json(args.menu), tags, config, args.allow_missing_tags, **options)
    write_json(args.output, result)
    for key, variant in result["variants"].items():
        for p in variant["plates"]:
            t = p["total"]
            print(f"{key}: {p['title']} → €{t['price_eur']:.2f} · ~{round(t['kcal'])} kcal · ~{round(t['protein_g'])}g protein")
        if not variant["plates"]:
            print(f"{key}: {variant['message']}")


if __name__ == "__main__":
    main()
