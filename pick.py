"""Brute-force scoop portions and precompute the six goal/diet variants."""
import argparse
import itertools
import math
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from common import ROOT, load_config, normalize, read_json, write_json
from judge import choose_variants
from tag import validate_tag

GOALS = ("bulk", "cut", "budget")
ROLES = ("main", "side", "soup", "dessert")


def price_cents(price, grams):
    euros = Decimal(str(price["base_eur"])) + Decimal(str(price["per_100g_eur"])) * Decimal(str(grams)) / 100
    return int((euros * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def scoop_size(dish, config):
    scoop = config["portions"]["station_scoop_g"].get(dish["station"], config["portions"]["default_scoop_g"])
    if type(scoop) not in (int, float) or not math.isfinite(scoop) or scoop <= 0:
        raise ValueError("Scoop sizes must be finite positive grams")
    return scoop


def portion_options(dish, tag, config, secondary=False):
    lo, hi = tag["typical_portion_g"]["min"], tag["typical_portion_g"]["max"]
    limit = min(hi, config["portions"]["max_plate_g"])
    scoop = scoop_size(dish, config)
    if secondary:
        if tag["role"] != "main" or tag["is_per_piece"] or tag["texture"] == "liquid":
            return []
        # A side scoop is smaller than a full main's usual minimum portion.
        portions = [(1, scoop, "scoop")] if scoop <= limit else []
    elif tag["is_per_piece"]:
        portions = [(1, tag["piece_weight_g"], "piece")] if lo <= tag["piece_weight_g"] <= limit else []
    else:
        portions = [(count, count * scoop, "scoop") for count in range(max(1, math.ceil(lo / scoop)), math.floor(limit / scoop) + 1)]
    result = []
    for count, grams, unit in portions:
        item = {**dish, **tag, "role": "main_side" if secondary else tag["role"], "count": count, "unit": unit, "weight_g": grams,
                "price_cents": price_cents(dish["price"], grams)}
        for nutrient in ("kcal", "protein", "carbs", "fat"):
            item[nutrient] = tag[f"{nutrient}_per_100g"] * grams / 100
        result.append(item)
    return result


def valid_plate(items, config):
    roles = [item["role"] for item in items]
    mains = [item for item in items if item["role"] == "main"]
    secondary = [item for item in items if item["role"] == "main_side"]
    # Also accept unmarked input with two mains: the second must satisfy side rules.
    if len(mains) == 2 and not secondary:
        mains, secondary = mains[:1], mains[1:]
    if (len(mains) != 1 or len(secondary) > 1
            or any(roles.count(role) > 1 for role in ("side", "soup", "dessert"))
            or any(role not in ROLES + ("main_side",) for role in roles)):
        return False
    if secondary:
        item = secondary[0]
        if (item["count"] != 1 or item["unit"] != "scoop" or item.get("is_per_piece", False)
                or item["texture"] == "liquid" or item["weight_g"] != scoop_size(item, config)):
            return False
    names = [normalize(item["name"]) for item in items]
    return (len(names) == len(set(names))
            and sum(item["texture"] == "liquid" for item in items) <= 1
            and sum(item["weight_g"] for item in items) <= config["portions"]["max_plate_g"])


def candidates(dishes, cache, config, vegan=False):
    groups = {role: [] for role in ROLES}
    secondary = []
    for dish in dishes:
        if vegan and dish["is_vegan"] is not True:
            continue
        tag = validate_tag(cache[normalize(dish["name"])])
        groups[tag["role"]].extend(portion_options(dish, tag, config))
        secondary.extend(portion_options(dish, tag, config, secondary=True))
    seen = set()
    for combo in itertools.product(groups["main"], [None] + secondary, [None] + groups["side"], [None] + groups["soup"], [None] + groups["dessert"]):
        items = [item for item in combo if item is not None]
        if valid_plate(items, config):
            signature = tuple(sorted((normalize(i["name"]), i["weight_g"], i["unit"]) for i in items))
            if signature in seen:
                continue
            seen.add(signature)
            yield {"items": items, "price_cents": sum(item["price_cents"] for item in items),
                   "weight_g": sum(item["weight_g"] for item in items),
                   **{key: sum(item[key] for item in items) for key in ("kcal", "protein", "carbs", "fat")}}


def top_plates(plates, goal, config, top_k=10, relax_protein=False):
    """Filter and rank candidates entirely in code; no judge can bypass these rules."""
    g = config["goals"]
    if goal == "bulk":
        valid = [p for p in plates if p["price_cents"] <= round(g["bulk_max_eur"] * 100)
                 and (relax_protein or p["protein"] >= g["bulk_min_protein_g"])]
        key = lambda p: (-p["kcal"], -p["protein"], p["price_cents"], p["weight_g"])
    elif goal == "cut":
        valid = [p for p in plates if p["kcal"] >= g["cut_min_kcal"] and p["kcal"] > 0
                 and (relax_protein or p["protein"] >= g["cut_min_protein_g"])]
        key = lambda p: (-p["protein"] / p["kcal"], p["price_cents"], p["weight_g"])
    elif goal == "budget":
        valid = [p for p in plates if p["kcal"] >= g["budget_min_kcal"]]
        key = lambda p: (p["price_cents"], -p["protein"], p["weight_g"])
    else:
        raise ValueError(f"Unknown goal: {goal}")
    return sorted(valid, key=key)[:top_k]


def choose(plates, goal, config, relax_protein=False):
    ranked = top_plates(plates, goal, config, top_k=1, relax_protein=relax_protein)
    return ranked[0] if ranked else None


def rank_variant(plates, goal, vegan, config):
    top_k = config.get("llm", {}).get("top_k", 10)
    if type(top_k) is not int or not 1 <= top_k <= 10:
        raise ValueError("llm.top_k must be an integer from 1 to 10")
    ranked = top_plates(plates, goal, config, top_k)
    relaxed, note = False, None
    if vegan and not ranked and goal in {"bulk", "cut"}:
        ranked = top_plates(plates, goal, config, top_k, relax_protein=True)
        relaxed = True
        floor = config["goals"][f"{goal}_min_protein_g"]
        ending = "showing a filling lunch with that target relaxed." if ranked else "no plate meets the remaining requirements."
        note = f"No vegan plate reaches {floor:g}g protein today; {ending}"
    return ranked, relaxed, note


def serving(item):
    return f"{item['count']} {item['unit']}{'s' if item['count'] != 1 else ''}"


def plate_result(plate, goal, vegan, config):
    if plate is None:
        message = {"bulk": f"No valid plate reaches {config['goals']['bulk_min_protein_g']:g}g protein within €{config['goals']['bulk_max_eur']:.2f}.",
                  "cut": f"No valid plate reaches {config['goals']['cut_min_kcal']:g} kcal and {config['goals']['cut_min_protein_g']:g}g protein.",
                  "budget": f"No valid plate reaches {config['goals']['budget_min_kcal']:g} kcal."}[goal]
        return {"state": "unavailable", "goal": goal, "vegan": vegan,
                "message": ("Vegan: " if vegan else "") + message, "reason": None, "picked_by": "rules"}
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
            "has_estimated_prices": any(item["price_source"] == "config" for item in items), "summary": summary,
            "reason": None, "picked_by": "rules"}


def judge_payload(ranked, config):
    """Supply only names, portions and the same rounded totals used by plate_result."""
    payload = {}
    for key, plates in ranked.items():
        goal, diet = key.split("_")
        payload[key] = []
        for index, plate in enumerate(plates):
            total = plate_result(plate, goal, diet == "vegan", config)["total"]
            payload[key].append({"id": f"c{index}", "dishes": [
                {"name_de": i["name"], "name_en": i["name_en"], "station": i["station"], "serving": serving(i)}
                for i in plate["items"]], "totals": {key: total[key] for key in ("price_eur", "kcal", "protein_g")}})
    return payload


def build_today(menu, cache, config, allow_missing=False, *, no_llm=False, api_key=None, judge_caller=None, judge_cache_path=None):
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
    ranked = {}
    for vegan in (False, True):
        plates = list(candidates(menu["dishes"], cache, config, vegan)) if menu["state"] == "open" and not missing else []
        for goal in GOALS:
            variant_key = f"{goal}_{'vegan' if vegan else 'all'}"
            if result["state"] in {"closed", "unavailable"}:
                result["variants"][variant_key] = {"state": result["state"], "goal": goal, "vegan": vegan,
                    "message": result.get("reason", "No menu is published for this date. Check the official menu before heading over."),
                    "reason": None, "picked_by": "rules", "relaxed": False, "note": None}
            else:
                selected, relaxed, note = rank_variant(plates, goal, vegan, config)
                ranked[variant_key] = selected
                result["variants"][variant_key] = plate_result(selected[0] if selected else None, goal, vegan, config)
                result["variants"][variant_key].update(relaxed=relaxed, note=note)
    if not no_llm and config.get("llm", {}).get("enabled", False) and ranked:
        choices = choose_variants(judge_payload(ranked, config), config["gemini_model"], menu["date"],
                                  api_key=api_key, caller=judge_caller, cache_path=judge_cache_path)
        for key, choice in choices.items():
            goal, diet = key.split("_")
            variant = result["variants"][key]
            # Resolve the ID into the original code candidate, never LLM-supplied values.
            selected = ranked[key][int(choice["id"][1:])]
            result["variants"][key] = plate_result(selected, goal, diet == "vegan", config)
            result["variants"][key].update(reason=choice["reason"], picked_by="llm", relaxed=variant["relaxed"], note=variant["note"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--menu", type=Path, default=ROOT / "data/menu.json")
    parser.add_argument("--cache", type=Path, default=ROOT / "data/dish_cache.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/today.json")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--allow-missing-tags", action="store_true", help="Publish an honest unavailable state for first-run setup")
    parser.add_argument("--no-llm", action="store_true", help="Use the rule-based top plate without a judge call")
    args = parser.parse_args()
    menu = read_json(args.menu)
    if menu is None:
        raise ValueError("Run scrape.py first")
    result = build_today(menu, read_json(args.cache, {}), load_config(args.config), args.allow_missing_tags,
                         no_llm=args.no_llm, judge_cache_path=ROOT / "data/judge_cache.json")
    write_json(args.output, result)
    print(f"{result['date']}: {result['state']}")
    for key, plate in result["variants"].items():
        print(f"{key}: {plate.get('summary', plate.get('message'))}")


if __name__ == "__main__":
    main()
