"""Brute-force scoop portions and precompute the six goal/diet variants."""
import argparse
import itertools
import math
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from common import ROOT, load_config, normalize, read_json, write_json
from tag import validate_tag

GOALS = ("bulk", "cut", "budget")
ROLES = ("main", "side", "soup", "dessert")


def price_cents(price, grams):
    euros = Decimal(str(price["base_eur"])) + Decimal(str(price["per_100g_eur"])) * Decimal(str(grams)) / 100
    return int((euros * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def portion_options(dish, tag, config):
    lo, hi = tag["typical_portion_g"]["min"], tag["typical_portion_g"]["max"]
    limit = min(hi, config["portions"]["max_plate_g"])
    scoop = config["portions"]["station_scoop_g"].get(dish["station"], config["portions"]["default_scoop_g"])
    if not isinstance(scoop, (int, float)) or not math.isfinite(scoop) or scoop <= 0:
        raise ValueError("Scoop sizes must be finite positive grams")
    if tag["is_per_piece"]:
        portions = [(1, tag["piece_weight_g"], "piece")] if lo <= tag["piece_weight_g"] <= limit else []
    else:
        portions = [(count, count * scoop, "scoop") for count in range(max(1, math.ceil(lo / scoop)), math.floor(limit / scoop) + 1)]
    result = []
    for count, grams, unit in portions:
        item = {**dish, **tag, "count": count, "unit": unit, "weight_g": grams,
                "price_cents": price_cents(dish["price"], grams)}
        for nutrient in ("kcal", "protein", "carbs", "fat"):
            item[nutrient] = tag[f"{nutrient}_per_100g"] * grams / 100
        result.append(item)
    return result


def valid_plate(items, config):
    roles = [item["role"] for item in items]
    return (roles.count("main") == 1 and all(roles.count(role) <= 1 for role in ROLES)
            and all(role in ROLES for role in roles)
            and sum(item["texture"] == "liquid" for item in items) <= 1
            and sum(item["weight_g"] for item in items) <= config["portions"]["max_plate_g"])


def candidates(dishes, cache, config, vegan=False):
    groups = {role: [] for role in ROLES}
    for dish in dishes:
        if vegan and dish["is_vegan"] is not True:
            continue
        tag = validate_tag(cache[normalize(dish["name"])])
        groups[tag["role"]].extend(portion_options(dish, tag, config))
    for combo in itertools.product(groups["main"], [None] + groups["side"], [None] + groups["soup"], [None] + groups["dessert"]):
        items = [item for item in combo if item is not None]
        if valid_plate(items, config):
            yield {"items": items, "price_cents": sum(item["price_cents"] for item in items),
                   "weight_g": sum(item["weight_g"] for item in items),
                   **{key: sum(item[key] for item in items) for key in ("kcal", "protein", "carbs", "fat")}}


def choose(plates, goal, config):
    g = config["goals"]
    if goal == "bulk":
        valid = [p for p in plates if p["price_cents"] <= round(g["bulk_max_eur"] * 100)]
        key = lambda p: (-p["protein"], -p["kcal"], p["price_cents"], p["weight_g"])
    elif goal == "cut":
        valid = [p for p in plates if p["protein"] >= g["cut_min_protein_g"]]
        key = lambda p: (p["kcal"], p["price_cents"], -p["protein"], p["weight_g"])
    elif goal == "budget":
        valid = [p for p in plates if p["kcal"] >= g["budget_min_kcal"]]
        key = lambda p: (p["price_cents"], -p["protein"], p["kcal"], p["weight_g"])
    else:
        raise ValueError(f"Unknown goal: {goal}")
    return min(valid, key=key) if valid else None


def serving(item):
    return f"{item['count']} {item['unit']}{'s' if item['count'] != 1 else ''}"


def plate_result(plate, goal, vegan, config):
    if plate is None:
        reason = {"bulk": f"No valid plate fits the €{config['goals']['bulk_max_eur']:.2f} limit.",
                  "cut": f"No valid plate reaches {config['goals']['cut_min_protein_g']:g}g protein.",
                  "budget": f"No valid plate reaches {config['goals']['budget_min_kcal']:g} kcal."}[goal]
        return {"state": "unavailable", "goal": goal, "vegan": vegan,
                "reason": ("Vegan: " if vegan else "") + reason}
    items = []
    for item in plate["items"]:
        items.append({key: item[key] for key in ("name", "name_en", "station", "role", "texture", "count", "unit",
                     "weight_g", "price_cents", "is_vegan", "markers", "allergens", "additives")}
                     | {"price_source": item["price"]["source"], "serving": serving(item),
                        "kcal": round(item["kcal"], 2), "protein_g": round(item["protein"], 2)})
    total = {"price_cents": plate["price_cents"], "price_eur": plate["price_cents"] / 100,
             "weight_g": plate["weight_g"], "kcal": round(plate["kcal"], 2),
             **{f"{key}_g": round(plate[key], 2) for key in ("protein", "carbs", "fat")}}
    summary = " + ".join(f"{item['serving']} {item['name']}" for item in items)
    summary += f" → €{total['price_eur']:.2f} · ~{round(total['kcal'])} kcal · ~{round(total['protein_g'])}g protein"
    return {"state": "ready", "goal": goal, "vegan": vegan, "items": items, "total": total,
            "has_estimated_prices": any(item["price_source"] == "config" for item in items), "summary": summary}


def build_today(menu, cache, config, allow_missing=False):
    missing = [dish["name"] for dish in menu["dishes"] if normalize(dish["name"]) not in cache]
    if missing and not allow_missing:
        raise ValueError(f"{len(missing)} dishes need tagging; run tag.py first. Refusing to pick from a partial menu.")
    result = {key: menu[key] for key in ("schema_version", "date", "mensa", "state", "source", "source_url", "fetched_at", "warnings")}
    result["menu_count"] = len(menu["dishes"])
    result["goals"] = config["goals"]
    result["max_plate_g"] = config["portions"]["max_plate_g"]
    result["default_scoop_g"] = config["portions"]["default_scoop_g"]
    result["nutrition_note"] = "Nutrition values are estimates."
    result["variants"] = {}
    if missing:
        result["state"] = "unavailable"
        result["reason"] = "Today's menu is here. Plate recommendations are waiting for nutrition estimates."
        result["missing_tags"] = missing
    for vegan in (False, True):
        plates = list(candidates(menu["dishes"], cache, config, vegan)) if menu["state"] == "open" and not missing else []
        for goal in GOALS:
            variant_key = f"{goal}_{'vegan' if vegan else 'all'}"
            if result["state"] in {"closed", "unavailable"}:
                result["variants"][variant_key] = {"state": result["state"], "goal": goal, "vegan": vegan,
                    "reason": result.get("reason", "No menu is published for this date. Check the official menu before heading over.")}
            else:
                result["variants"][variant_key] = plate_result(choose(plates, goal, config), goal, vegan, config)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--menu", type=Path, default=ROOT / "data/menu.json")
    parser.add_argument("--cache", type=Path, default=ROOT / "data/dish_cache.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/today.json")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--allow-missing-tags", action="store_true", help="Publish an honest unavailable state for first-run setup")
    args = parser.parse_args()
    menu = read_json(args.menu)
    if menu is None:
        raise ValueError("Run scrape.py first")
    result = build_today(menu, read_json(args.cache, {}), load_config(args.config), args.allow_missing_tags)
    write_json(args.output, result)
    print(f"{result['date']}: {result['state']}")
    for key, plate in result["variants"].items():
        print(f"{key}: {plate.get('summary', plate.get('reason'))}")


if __name__ == "__main__":
    main()
