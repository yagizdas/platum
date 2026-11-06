"""Models propose trays; deterministic equations choose portions and five diverse plates."""
import argparse
import itertools
import math
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from common import ROOT, dish_id, load_config, normalize, read_json, today, week_dates, write_json
from judge import choose_variants
from pair import food, load_pairing
from proposals import daily_proposals, fallback_proposals, validate_proposals
from scoring import score_plate

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


def portion_max_g(item, config):
    """Configured scoop caps replace model maxima; piece weights keep their range."""
    maximum = item["typical_portion_g"]["max"]
    if not item["is_per_piece"]:
        role = "side" if item.get("standing") else item["role"]
        maximum = config["portions"].get("max_scoop_g_by_role", {}).get(role, maximum)
    if type(maximum) not in (int, float) or not math.isfinite(maximum) or maximum <= 0:
        raise ValueError("Portion caps must be finite positive grams")
    return maximum


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
    lo, hi = item["typical_portion_g"]["min"], portion_max_g(item, config)
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
    if not 1 <= len(items) <= 3 or len({dish_id(i) for i in items}) != len(items):
        return False
    if sum(i["role"] == "soup" for i in items) > 1 or all(i["role"] == "dessert" for i in items):
        return False
    if all(i.get("standing") for i in items):
        return False
    if sum(i["weight_g"] for i in items) > config["portions"]["max_plate_g"]:
        return False
    for i in items:
        if i["is_per_piece"]:
            if i["count"] != 1 or i["unit"] != "piece" or i["weight_g"] != i["piece_weight_g"]:
                return False
        elif (i["unit"] != "scoop" or type(i["count"]) is not int or not 1 <= i["count"] <= 3
              or i["weight_g"] != i["count"] * scoop_size(i, config)):
            return False
        if i["weight_g"] > portion_max_g(i, config):
            return False
    return True


def ordered_items(items):
    return sorted(items, key=lambda i: (i["role"] != "main" or i.get("standing"), not i["is_per_piece"], -i["weight_g"], dish_id(i)))


def plate(items):
    return {"items": ordered_items(items), "price_cents": sum(i["price_cents"] for i in items),
            "weight_g": sum(i["weight_g"] for i in items),
            **{n: sum(i[n] for i in items) for n in ("kcal", "protein", "carbs", "fat")}}


def candidates(dishes, cache, config, vegan=False, pairing=None, proposals=None):
    items = [food(d, cache) for d in dishes if not vegan or d.get("is_vegan") is True]
    by_id = {dish_id(i): i for i in items}
    combos = fallback_proposals(items) if proposals is None else validate_proposals({"combos": proposals}, items, vegan=vegan)
    for ids in combos:
        options = [portion_options(by_id[key], by_id[key], config, paired=True) for key in ids]
        for combo in itertools.product(*options):
            if valid_plate(combo, config, pairing):
                yield plate(combo)


def top_plates(plates, goal, config, top_k=5, relax_protein=False):
    if goal not in GOALS:
        raise ValueError(f"Unknown goal: {goal}")
    scored = [{**p, "score": score_plate(p, goal, config)} for p in plates]
    def rank(p):
        return (-p["score"]["total"], p["price_cents"], tuple(sorted(dish_id(i) for i in p["items"])),
                tuple(sorted((dish_id(i), i["count"]) for i in p["items"])))
    seen_mains, result = set(), []
    for p in sorted(scored, key=rank):
        mains = {dish_id(i) for i in p["items"] if i["role"] == "main" and not i.get("standing")}
        mains = mains or {dish_id(p["items"][0])}
        if mains & seen_mains:
            continue
        seen_mains.update(mains)
        result.append(p)
        if len(result) >= top_k:
            break
    return result


def choose(plates, goal, config, relax_protein=False):
    ranked = top_plates(plates, goal, config, 1, relax_protein)
    return ranked[0] if ranked else None


def rank_variant(plates, goal, vegan, config):
    return top_plates(plates, goal, config), False, None


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
                     | {"id": dish_id(i), "serving": serving(i), "price_source": i["price"]["source"], "kcal": round(i["kcal"], 2), "protein_g": round(i["protein"], 2)})
    total = {"price_cents": value["price_cents"], "price_eur": value["price_cents"] / 100, "weight_g": value["weight_g"],
             "kcal": round(value["kcal"], 2), **{f"{n}_g": round(value[n], 2) for n in ("protein", "carbs", "fat")}}
    return {"title": " + ".join(re.split(r"\s+(?:with|on|served|in|made from)\s+", re.sub(r"\s*\([^)]*\)", "", i["name_en"]), maxsplit=1, flags=re.I)[0].strip() for i in value["items"]), "reason": None, "picked_by": "rules",
            "items": items, "total": total, "score": value.get("score"),
            "has_estimated_prices": any(i["price_source"] == "config" for i in items)}


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


def build_today(menu, cache, config, allow_missing=False, *, pairing=None, no_llm=False, api_key=None,
                judge_caller=None, judge_cache_path=None, proposal_caller=None, proposals_dir=None, proposals=None):
    missing = [d["name"] for d in menu["dishes"] if normalize(d["name"]) not in cache]
    if missing and not allow_missing:
        raise ValueError(f"{len(missing)} dishes need tagging; run tag.py first. Refusing to pick from a partial menu.")
    result = {k: menu[k] for k in ("date", "mensa", "state", "source", "source_url", "fetched_at", "warnings")}
    result.update(schema_version=SCHEMA_VERSION, menu_count=len(menu["dishes"]), scoring=config["scoring"],
                  max_plate_g=config["portions"]["max_plate_g"], default_scoop_g=config["portions"]["default_scoop_g"],
                  nutrition_note="Nutrition values are estimates.", variants={}, extras={"all": [], "vegan": []})
    if missing:
        result["warnings"] = [*result["warnings"], f"{len(missing)} untagged dish(es) omitted from plate recommendations."]
        result["missing_tags"] = missing
        menu = {**menu, "dishes": [d for d in menu["dishes"] if normalize(d["name"]) in cache]}
        if not menu["dishes"]:
            result.update(state="unavailable", reason="Today's menu is here. Plate recommendations are waiting for nutrition estimates.")
    ranked = {}
    if result["state"] == "open":
        result["extras"] = extras(menu["dishes"], cache, config)
    foods = [food(d, cache) for d in menu["dishes"]] if result["state"] == "open" else []
    keys = [f"{goal}_{dietary}" for dietary in ("all", "vegan") for goal in GOALS]
    def propose(key):
        if proposals is not None and key in proposals:
            return proposals[key]
        return daily_proposals(menu["date"], foods, config, key, cache_dir=proposals_dir,
                               api_key=api_key, caller=proposal_caller, no_llm=no_llm)
    if foods:
        # Independent variant caches allow concurrent calls, with deterministic collection order.
        with ThreadPoolExecutor(max_workers=6) as executor:
            proposal_sets = dict(zip(keys, executor.map(propose, keys)))
    else:
        proposal_sets = {key: [] for key in keys}
    for vegan in (False, True):
        for goal in GOALS:
            key = f"{goal}_{'vegan' if vegan else 'all'}"
            combos = proposal_sets[key]
            values = list(candidates(menu["dishes"], cache, config, vegan, pairing, proposals=combos)) if foods else []
            pool, relaxed, note = rank_variant(values, goal, vegan, config) if result["state"] == "open" else ([], False, None)
            ranked[key] = pool
            state = ("ready" if pool else "unavailable") if result["state"] == "open" else result["state"]
            result["variants"][key] = {"state": state, "goal": goal, "vegan": vegan, "relaxed": relaxed, "note": note,
                                       "plates": [plate_result(p) for p in pool]}
            if not pool:
                result["variants"][key]["message"] = result.get("reason") or ("No menu is published for this date." if state == "closed" else "No plate fits this goal today.")
    if not no_llm and config["llm"]["enabled"]:
        choices = choose_variants(judge_payload(ranked, config), config["gemini_model"], menu["date"],
                                  api_key=api_key, caller=judge_caller, cache_path=judge_cache_path)
        for key, selection in choices.items():
            # Apply copy by ID to the already selected plates. Response order cannot select/reorder.
            copy_by_id = {choice["id"]: choice for choice in selection}
            for index, selected in enumerate(result["variants"][key]["plates"]):
                choice = copy_by_id.get(f"c{index}")
                if choice:
                    selected.update(title=choice["title"], reason=choice["reason"])
    return result


def build_week(reference, menus, cache, config, **options):
    options.setdefault("allow_missing", True)
    days = {}
    for name, menu in sorted(menus.items()):
        try:
            days[name] = build_today(menu, cache, config, **options)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            print(f"{name}: plate generation unavailable ({type(exc).__name__}); continuing other days.", file=sys.stderr)
            fallback = {"date": name, "mensa": "Mensa Arcisstraße", "state": "unavailable",
                        "source": "unavailable", "source_url": config["official_url"], "fetched_at": None,
                        "warnings": ["Plate generation failed for this date; other dates remain available."], "dishes": []}
            days[name] = build_today(fallback, cache, config, no_llm=True)
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
    options = {"pairing": load_pairing(args.pairing_cache), "no_llm": args.no_llm,
               "judge_cache_path": ROOT / "data/title_cache.json", "proposals_dir": ROOT / "data/proposals"}
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
