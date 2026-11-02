import pytest

from common import normalize
from pick import build_today, candidates, choose, plate_result, portion_options, price_cents, top_plates, valid_plate


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
            if item["role"] == "main_side":
                assert item["count"] == 1 and item["unit"] == "scoop"
                assert not tag["is_per_piece"] and item["texture"] != "liquid"
            else:
                assert tag["typical_portion_g"]["min"] <= item["weight_g"] <= tag["typical_portion_g"]["max"]
            assert item["weight_g"] == item["count"] * 150


def test_bulk_budget_and_optimizer_ranking(config, make_dish):
    entries = [make_dish("Tofu", protein=12), make_dish("Expensive steak", vegan=False, protein=30, base=7),
               make_dish("Pudding", role="dessert", protein=4, kcal=300, max_g=150)]
    plates = list(candidates([d for d, t in entries], {normalize(d["name"]): t for d, t in entries}, config))
    bulk = choose(plates, "bulk", config)
    valid = [p for p in plates if p["price_cents"] <= 700 and p["protein"] >= 30]
    assert bulk["price_cents"] <= 700
    assert (bulk["kcal"], bulk["protein"]) == max((p["kcal"], p["protein"]) for p in valid)
    cut = choose(plates, "cut", config)
    assert cut["protein"] >= 25 and cut["kcal"] >= 400
    assert cut["protein"] / cut["kcal"] == max(p["protein"] / p["kcal"] for p in plates if p["protein"] >= 25 and p["kcal"] >= 400)
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


def test_real_fixture_bulk_is_filling_and_cut_is_a_lunch(config, fixture_menu):
    m, cache = fixture_menu
    result = build_today(m, cache, config)
    bulk, cut, budget = (result["variants"][key] for key in ("bulk_all", "cut_all", "budget_all"))
    assert bulk["total"]["kcal"] >= budget["total"]["kcal"]
    assert bulk["total"]["protein_g"] >= config["goals"]["bulk_min_protein_g"]
    assert bulk["total"]["price_eur"] <= config["goals"]["bulk_max_eur"]
    assert cut["total"]["kcal"] >= config["goals"]["cut_min_kcal"]
    assert cut["total"]["protein_g"] >= config["goals"]["cut_min_protein_g"]
    assert any(i["role"] == "main_side" for i in bulk["items"])
    assert result["variants"]["bulk_vegan"]["summary"] != result["variants"]["budget_vegan"]["summary"]


def test_secondary_main_is_exactly_one_non_piece_non_liquid_scoop(config, make_dish):
    d, t = make_dish("Protein", piece=True, piece_g=150)
    primary = portion_options(d, t, config)[0]
    d, t = make_dish("Curry", min_g=250, max_g=400)
    secondary = portion_options(d, t, config, secondary=True)[0]
    assert secondary["weight_g"] == 150 and secondary["role"] == "main_side"
    assert valid_plate([primary, secondary], config)
    assert valid_plate([primary, {**secondary, "role": "main"}], config)
    for invalid in ({"count": 2, "weight_g": 300}, {"unit": "piece", "is_per_piece": True},
                    {"texture": "liquid"}, {"weight_g": 100}):
        assert not valid_plate([primary, {**secondary, **invalid}], config)
    assert not valid_plate([primary, secondary, {**secondary, "name": "Other curry"}], config)
    assert not valid_plate([primary, {**secondary, "role": "main"}, {**secondary, "name": "Third main", "role": "main"}], config)
    assert not valid_plate([secondary], config)


def test_secondary_station_scoop_and_duplicate_dishes(config, make_dish):
    config["portions"]["station_scoop_g"]["Wok"] = 100
    d, t = make_dish("Curry", min_g=250)
    secondary = portion_options(d, t, config, secondary=True)[0]
    primary = portion_options(d, t, config)[0]
    assert secondary["weight_g"] == 100
    assert not valid_plate([primary, secondary], config) # same recipe cannot be ordered twice as two roles
    d2, t2 = make_dish("Tofu")
    plates = list(candidates([d, d2], {normalize(d["name"]): t, normalize(d2["name"]): t2}, config))
    signatures = [tuple(sorted((i["name"], i["weight_g"]) for i in p["items"])) for p in plates]
    assert len(signatures) == len(set(signatures))


def test_vegan_protein_relaxation_preserves_other_constraints(config, fixture_menu):
    m, cache = fixture_menu
    result = build_today(m, cache, config)
    for goal in ("bulk", "cut"):
        v = result["variants"][goal + "_vegan"]
        assert v["state"] == "ready" and v["relaxed"] is True and v["note"]
        assert "No vegan plate reaches" in v["note"]
        assert all(i["is_vegan"] is True for i in v["items"])
        assert v["total"]["weight_g"] <= config["portions"]["max_plate_g"]
        if goal == "bulk":
            assert v["total"]["price_eur"] <= config["goals"]["bulk_max_eur"]
        else:
            assert v["total"]["kcal"] >= config["goals"]["cut_min_kcal"]
    assert result["variants"]["bulk_all"]["relaxed"] is False
    assert result["variants"]["budget_vegan"]["relaxed"] is False


def test_top_k_order_and_choose_agree(config):
    plates = [{"kcal": 600, "protein": 31, "price_cents": 500, "weight_g": 300},
              {"kcal": 700, "protein": 30, "price_cents": 600, "weight_g": 400},
              {"kcal": 400, "protein": 40, "price_cents": 400, "weight_g": 300},
              {"kcal": 399, "protein": 45, "price_cents": 350, "weight_g": 300}]
    assert top_plates(plates, "bulk", config, 2) == [plates[1], plates[0]]
    assert choose(plates, "bulk", config) is plates[1]
    assert choose(plates, "cut", config) is plates[2]
    assert choose(plates, "budget", config) is plates[0]
