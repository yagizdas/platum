import copy

import pytest

from common import normalize
from pair import food, pair_key, pair_score, stands_alone
from pick import build_today, candidates, choose, diet, plate_result, portion_options, price_cents, top_plates, valid_plate


def menu(dishes):
    return {"schema_version": 1, "date": "2026-11-02", "mensa": "Mensa Arcisstraße", "state": "open",
            "source": "official", "source_url": "https://example.org", "fetched_at": "2026-11-02T07:30:00Z", "warnings": [], "dishes": dishes}


def test_golden_lunches(config, fixture_menu, pairing):
    m, tags = fixture_menu
    result = build_today(m, tags, config, pairing=pairing, no_llm=True)
    bulk = result["variants"]["bulk_all"]["plates"][0]
    assert [i["name"].split(" (")[0] for i in bulk["items"]] == ["Seelachsfilet", "Asia-Reisbällchen auf Teriyakigemüse"]
    assert bulk["items"][1]["count"] == 3
    assert bulk["total"]["price_cents"] == 690
    assert bulk["total"]["kcal"] == 780
    assert bulk["total"]["protein_g"] == 42.15
    cut = result["variants"]["cut_all"]["plates"]
    assert [p["items"][1]["name"] for p in cut] == ["Asia-Reisbällchen auf Teriyakigemüse", "Reis", "Kartoffelsalat"]
    assert all(p["items"][0]["name"].startswith("Seelachs") and p["items"][1]["count"] == 2 for p in cut)
    budget = result["variants"]["budget_all"]["plates"]
    sets = [{i["name"] for i in p["items"]} for p in budget]
    assert any(any(n.startswith("Käsekrainer") for n in s) and "Graupen-Gemüse-Eintopf" in s for s in sets)
    assert any(any(n.startswith("Käsekrainer") for n in s) and "Kartoffelsalat" in s for s in sets)
    vegan = result["variants"]["bulk_vegan"]
    assert vegan["relaxed"] and vegan["note"]
    assert {i["name"] for i in vegan["plates"][0]["items"]} == {"Gemüsecurry aus Blumenkohl und Broccoli", "Asia-Reisbällchen auf Teriyakigemüse"}
    assert result["schema_version"] == 2
    for v in result["variants"].values():
        for p in v["plates"]:
            assert all(i["role"] not in {"soup", "dessert"} and i["texture"] != "liquid" for i in p["items"])
            assert p["total"]["price_cents"] == sum(i["price_cents"] for i in p["items"])
            assert p["total"]["weight_g"] <= 650


def test_every_candidate_meets_rules(config, fixture_menu, pairing):
    m, tags = fixture_menu
    values = list(candidates(m["dishes"], tags, config, pairing=pairing))
    assert values
    for p in values:
        items = p["items"]
        assert valid_plate(items, config, pairing)
        assert len(items) in (1, 2) and len({i["name"] for i in items}) == len(items)
        assert not any(i["role"] in {"soup", "dessert"} or i["texture"] == "liquid" for i in items)
        assert sum(i["is_per_piece"] for i in items) <= 1
        if len(items) == 1:
            assert stands_alone(items[0], pairing)
            assert not items[0]["standing"]
        else:
            assert all(i["station"] != "Pizza" for i in items)
            assert pair_score(*items, pairing) >= config["pairing"]["min_score"]
        assert p["weight_g"] <= config["portions"]["max_plate_g"]


def test_pool_has_one_portioning_per_lunch(config, fixture_menu, pairing):
    m, tags = fixture_menu
    values = list(candidates(m["dishes"], tags, config, pairing=pairing))
    for goal in ("bulk", "cut", "budget"):
        pool = top_plates(values, goal, config)
        sets = [tuple(sorted(i["name"] for i in p["items"])) for p in pool]
        assert len(pool) <= 8 and len(sets) == len(set(sets))
        assert choose(values, goal, config) == pool[0]
        if goal == "bulk":
            scores = [p["kcal"] + config["goals"]["bulk_protein_weight"] * p["protein"] for p in pool]
            assert scores == sorted(scores, reverse=True)
        if goal == "cut":
            ratios = [p["protein"] / p["kcal"] for p in pool]
            assert ratios == sorted(ratios, reverse=True)


def test_invalid_single_pairs_and_pizza(config, fixture_menu, pairing):
    m, tags = fixture_menu
    values = {d["name"]: food(d, tags) for d in m["dishes"]}
    fish = next(i for i in values.values() if i["name"].startswith("Seelachs"))
    pinsa = next(i for i in values.values() if i["station"] == "Pizza")
    rice = values["Reis"]
    f = portion_options(fish, fish, config)[0]
    p = portion_options(pinsa, pinsa, config)[0]
    r = portion_options(rice, rice, config)[0]
    assert not valid_plate([f], config, pairing)
    assert not valid_plate([r], config, pairing)
    assert not valid_plate([f, p], config, pairing)
    assert not valid_plate([f, f], config, pairing)
    assert not valid_plate([f, r, r], config, pairing)
    bad = copy.deepcopy(pairing); bad["pairs"][pair_key(f, r)]["score"] = 1
    assert not valid_plate([f, r], config, bad)
    assert not valid_plate([f, {**r, "count": 4, "weight_g": 600}], config, pairing)
    assert not valid_plate([f, {**r, "is_per_piece": True}], config, pairing)


def test_paired_portions_ignore_minimum_but_not_max(config, make_dish):
    d, t = make_dish(min_g=250, max_g=400)
    assert [i["count"] for i in portion_options(d, t, config)] == [2]
    assert [i["count"] for i in portion_options(d, t, config, paired=True)] == [1, 2]
    config["portions"]["station_scoop_g"]["Wok"] = 100
    assert [i["weight_g"] for i in portion_options(d, t, config, paired=True)] == [100, 200, 300]
    config["portions"]["station_scoop_g"]["Wok"] = 0
    with pytest.raises(ValueError, match="Scoop"):
        portion_options(d, t, config)


def test_no_price_cap(config, make_dish):
    d, t = make_dish("Expensive pasta", protein=20, base=20, rate=5)
    values = list(candidates([d], {normalize(d["name"]): t}, config))
    config["goals"]["bulk_max_eur"] = 7 # even an obsolete config field cannot reinstate a cap
    assert all(choose(values, g, config)["price_cents"] > 700 for g in ("bulk", "cut", "budget"))


def test_vegan_relaxation_applies_to_all_three_goals(config, fixture_menu, pairing):
    m, tags = fixture_menu
    for goal in ("bulk", "cut", "budget"):
        config["goals"][goal + "_min_protein_g"] = 1000
    result = build_today(m, tags, config, pairing=pairing)
    for goal in ("bulk", "cut", "budget"):
        v = result["variants"][goal + "_vegan"]
        assert v["relaxed"] and v["note"] and v["plates"]
        assert all(i["is_vegan"] is True for p in v["plates"] for i in p["items"])
        if goal != "bulk":
            assert all(p["total"]["kcal"] >= config["goals"][goal + "_min_kcal"] for p in v["plates"])
        assert not result["variants"][goal + "_all"]["plates"]


def test_extras_are_separate_and_vegan_filtered(config, fixture_menu, pairing):
    m, tags = fixture_menu
    result = build_today(m, tags, config, pairing=pairing)
    assert len(result["extras"]["all"]) == 4 and result["extras"]["vegan"] == []
    for extra in result["extras"]["all"]:
        assert {"name", "name_en", "station", "serving", "weight_g", "price_cents", "kcal", "protein_g", "is_vegan", "diet"} <= set(extra)
    m = copy.deepcopy(m)
    dessert = next(d for d in m["dishes"] if d["name"].startswith("Vanillecreme"))
    dessert["is_vegan"] = True
    assert build_today(m, tags, config, pairing=pairing)["extras"]["vegan"][0]["name"] == dessert["name"]


def test_standing_overrides_model_role_and_piece(config, make_dish):
    d, t = make_dish("Rice", role="main", piece=True, piece_g=150)
    d["standing"] = True
    item = food(d, {normalize(d["name"]): t})
    assert item["role"] == "side" and item["is_per_piece"] is False
    assert not stands_alone(item, {"dishes": {normalize(d["name"]): {"stands_alone": True}}})
    assert not list(candidates([d], {normalize(d["name"]): t}, config))


def test_diet_is_code_derived_and_conservative(config, make_dish):
    d, t = make_dish("Veganer Fisch", vegan=True)
    assert diet(d, config) == "vegan"
    d.update(is_vegan=False, is_vegetarian=True)
    assert diet(d, config) == "vegetarian"
    d.update(name="Seelachsfilet", is_vegetarian=False)
    assert diet(d, config) == "fish"
    d.update(name="Käsekrainer")
    assert diet(d, config) == "meat"


def test_closed_missing_cache_and_fewer_than_three(config, make_dish):
    m = menu([]); m["state"] = "closed"
    result = build_today(m, {}, config)
    assert result["extras"] == {"all": [], "vegan": []}
    assert all(v["state"] == "closed" and not v["plates"] for v in result["variants"].values())
    d, t = make_dish("Pasta", protein=20)
    with pytest.raises(ValueError, match="need tagging"):
        build_today(menu([d]), {}, config)
    assert build_today(menu([d]), {}, config, allow_missing=True)["state"] == "unavailable"
    result = build_today(menu([d]), {normalize(d["name"]): t}, config)
    assert all(len(v["plates"]) == 1 for v in result["variants"].values())
    d["is_vegan"] = None
    assert list(candidates([d], {normalize(d["name"]): t}, config, vegan=True)) == []


def test_price_rounding_and_piece_portion(config, make_dish):
    assert price_cents({"base_eur": 1, "per_100g_eur": .9}, 300) == 370
    assert price_cents({"base_eur": 0, "per_100g_eur": .33}, 150) == 50
    assert price_cents({"base_eur": 5, "per_100g_eur": 0}, 310) == 500
    d, t = make_dish(piece=True, piece_g=180, min_g=150, max_g=250, base=1.5)
    item = portion_options(d, t, config)[0]
    assert item["count"] == 1 and item["unit"] == "piece" and item["price_cents"] == 312
