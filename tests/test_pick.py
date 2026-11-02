import pytest

from common import normalize
from pick import build_today, candidates, choose, plate_result, portion_options, price_cents, valid_plate


def menu(dishes):
    return {"schema_version": 1, "date": "2026-11-02", "mensa": "Mensa Arcisstraße", "state": "open",
            "source": "official", "source_url": "https://example.org", "fetched_at": "2026-11-02T07:30:00Z", "warnings": [], "dishes": dishes}


def test_all_candidates_obey_rules(config, make_dish):
    entries = [make_dish(), make_dish("Liquid main", texture="liquid"),
               make_dish("Rice", role="side", max_g=300), make_dish("Soup", role="soup", texture="liquid", max_g=300),
               make_dish("Custard", role="dessert", texture="liquid", max_g=150)]
    dishes, tags = zip(*entries)
    cache = {normalize(d["name"]): t for d, t in entries}
    plates = list(candidates(dishes, cache, config))
    assert len(plates) > 10
    assert any(len(p["items"]) > 1 for p in plates)
    for plate in plates:
        assert valid_plate(plate["items"], config)
        assert sum(i["texture"] == "liquid" for i in plate["items"]) <= 1
        assert sum(i["role"] == "main" for i in plate["items"]) == 1
        for role in ("side", "soup", "dessert"):
            assert sum(i["role"] == role for i in plate["items"]) <= 1
        assert plate["weight_g"] <= 650
        for item in plate["items"]:
            tag = cache[normalize(item["name"])]
            assert tag["typical_portion_g"]["min"] <= item["weight_g"] <= tag["typical_portion_g"]["max"]
            assert item["weight_g"] == item["count"] * 150


def test_bulk_budget_and_optimizer_ranking(config, make_dish):
    entries = [make_dish("Tofu", protein=12), make_dish("Expensive steak", vegan=False, protein=30, base=7),
               make_dish("Pudding", role="dessert", protein=4, kcal=300, max_g=150)]
    plates = list(candidates([d for d, t in entries], {normalize(d["name"]): t for d, t in entries}, config))
    bulk = choose(plates, "bulk", config)
    valid = [p for p in plates if p["price_cents"] <= 700]
    assert bulk["price_cents"] <= 700
    assert (bulk["protein"], bulk["kcal"]) == max((p["protein"], p["kcal"]) for p in valid)
    cut = choose(plates, "cut", config)
    assert cut["protein"] >= 25 and cut["kcal"] == min(p["kcal"] for p in plates if p["protein"] >= 25)
    budget = choose(plates, "budget", config)
    assert budget["kcal"] >= 550 and budget["price_cents"] == min(p["price_cents"] for p in plates if p["kcal"] >= 550)


def test_bulk_ties_use_kcal(config):
    low = {"protein": 30, "kcal": 500, "price_cents": 500, "weight_g": 300}
    high = {**low, "kcal": 600}
    assert choose([low, high], "bulk", config) == high


def test_all_six_variants_and_vegan_filter(config, make_dish):
    entries = [make_dish("Tofu", protein=12), make_dish("Fish", vegan=False, protein=20),
               make_dish("Rice", role="side", max_g=150)]
    result = build_today(menu([d for d, t in entries]), {normalize(d["name"]): t for d, t in entries}, config)
    assert len(result["variants"]) == 6
    for key, variant in result["variants"].items():
        assert variant["state"] == "ready"
        if key.endswith("_vegan"):
            assert all(item["is_vegan"] is True for item in variant["items"])
        assert variant["total"]["price_cents"] == sum(item["price_cents"] for item in variant["items"])
        assert variant["total"]["weight_g"] == sum(item["weight_g"] for item in variant["items"])
        assert "→ €" in variant["summary"]


def test_unknown_vegan_filtered_and_impossible_goal(config, make_dish):
    d, t = make_dish(protein=1, kcal=10)
    d["is_vegan"] = None
    cache = {normalize(d["name"]): t}
    assert list(candidates([d], cache, config, vegan=True)) == []
    result = build_today(menu([d]), cache, config)
    assert result["variants"]["cut_all"]["state"] == "unavailable"
    assert result["variants"]["budget_all"]["state"] == "unavailable"
    assert result["variants"]["bulk_vegan"]["state"] == "unavailable"


def test_per_piece_and_station_scoop(config, make_dish):
    d, t = make_dish("Fish (1 Stück)", piece=True, piece_g=180, min_g=150, max_g=250, base=1.5)
    options = portion_options(d, t, config)
    assert len(options) == 1 and options[0]["unit"] == "piece" and options[0]["count"] == 1
    assert options[0]["weight_g"] == 180 and options[0]["price_cents"] == 312
    d, t = make_dish(station="Studitopf", min_g=200, max_g=400)
    config["portions"]["station_scoop_g"]["Studitopf"] = 100
    options = portion_options(d, t, config)
    assert [i["weight_g"] for i in options] == [200, 300, 400]
    config["portions"]["station_scoop_g"]["Studitopf"] = 0
    with pytest.raises(ValueError, match="Scoop"):
        portion_options(d, t, config)


def test_price_base_once_and_round_per_dish():
    p = {"base_eur": 1, "per_100g_eur": .9}
    assert price_cents(p, 150) == 235
    assert price_cents(p, 300) == 370
    assert price_cents({"base_eur": 0, "per_100g_eur": .33}, 150) == 50
    assert price_cents({"base_eur": 5, "per_100g_eur": 0}, 400) == 500


def test_empty_closed_missing_cache_and_no_main(config, make_dish):
    m = menu([]); m["state"] = "closed"
    assert all(v["state"] == "closed" for v in build_today(m, {}, config)["variants"].values())
    d, t = make_dish()
    with pytest.raises(ValueError, match="need tagging"):
        build_today(menu([d]), {}, config)
    assert build_today(menu([d]), {}, config, allow_missing=True)["state"] == "unavailable"
    d, t = make_dish(role="side")
    assert list(candidates([d], {normalize(d["name"]): t}, config)) == []


def test_portion_without_whole_scoop_is_unavailable(config, make_dish):
    d, t = make_dish(min_g=200, max_g=250)
    assert portion_options(d, t, config) == []
