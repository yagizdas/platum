import copy

import pytest

from common import normalize
from pair import food, pair_key, pair_score, stands_alone
from pick import build_today, candidates, choose, diet, plate_result, portion_options, price_cents, top_plates, valid_plate


def menu(dishes):
    return {"schema_version": 1, "date": "2026-11-02", "mensa": "Mensa Arcisstraße", "state": "open",
            "source": "official", "source_url": "https://example.org", "fetched_at": "2026-11-02T07:30:00Z", "warnings": [], "dishes": dishes}


@pytest.mark.parametrize("fixed_caps", [False, True], ids=["original-model-limits", "configured-caps"])
def test_golden_lunches(config, fixture_menu, pairing, fixed_caps):
    if not fixed_caps:
        config["portions"]["max_scoop_g_by_role"] = {} # preserve the original v2 prototype replay
    m, tags = fixture_menu
    result = build_today(m, tags, config, pairing=pairing, no_llm=True)
    bulk = result["variants"]["bulk_all"]["plates"][0]
    assert [i["name"].split(" (")[0] for i in bulk["items"]] == ["Seelachsfilet", "Asia-Reisbällchen auf Teriyakigemüse"]
    assert bulk["items"][1]["count"] == 3
    assert bulk["total"]["price_cents"] == 690
    assert bulk["total"]["kcal"] == 780
    assert bulk["total"]["protein_g"] == 42.15
    cut = result["variants"]["cut_all"]["plates"]
    expected_sides = (["Gemüsecurry aus Blumenkohl und Broccoli", "Asia-Reisbällchen auf Teriyakigemüse", "Reis"]
                      if fixed_caps else ["Asia-Reisbällchen auf Teriyakigemüse", "Reis", "Kartoffelsalat"])
    assert [p["items"][1]["name"] for p in cut] == expected_sides
    assert all(p["items"][0]["name"].startswith("Seelachs") for p in cut)
    assert [p["items"][1]["count"] for p in cut] == ([3, 2, 2] if fixed_caps else [2, 2, 2])
    budget = result["variants"]["budget_all"]["plates"]
    sets = [{i["name"] for i in p["items"]} for p in budget]
    assert any(any(n.startswith("Käsekrainer") for n in s) and "Graupen-Gemüse-Eintopf" in s for s in sets)
    assert any(any(n.startswith("Käsekrainer") for n in s) and "Kartoffelsalat" in s for s in sets)
    vegan = result["variants"]["bulk_vegan"]
    assert vegan["relaxed"] and vegan["note"]
    expected_vegan = ({"Vegane Maultaschen mit Zwiebelmarmelade"} if fixed_caps else
                      {"Gemüsecurry aus Blumenkohl und Broccoli", "Asia-Reisbällchen auf Teriyakigemüse"})
    assert {i["name"] for i in vegan["plates"][0]["items"]} == expected_vegan
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
    potato = values["Kartoffelsalat"]
    k = portion_options(potato, potato, config)[0]
    bad["pairs"][pair_key(r, k)] = {"score": 3}
    bad["pairs"][pair_key(f, p)] = {"score": 3}
    assert not valid_plate([r, k], config, bad) # model scores cannot create a main-less plate
    assert not valid_plate([f, p], config, bad) # model scores cannot override the pizza ban


def test_paired_portions_ignore_minimum_but_not_max(config, make_dish):
    config["portions"]["max_scoop_g_by_role"] = {} # exercise the cached range without an override
    d, t = make_dish(min_g=250, max_g=400)
    assert [i["count"] for i in portion_options(d, t, config)] == [2]
    assert [i["count"] for i in portion_options(d, t, config, paired=True)] == [1, 2]
    config["portions"]["station_scoop_g"]["Wok"] = 100
    assert [i["weight_g"] for i in portion_options(d, t, config, paired=True)] == [100, 200, 300]
    config["portions"]["station_scoop_g"]["Wok"] = 0
    with pytest.raises(ValueError, match="Scoop"):
        portion_options(d, t, config)


def test_fixed_scoop_caps_replace_cached_maxima(config, make_dish):
    d, t = make_dish(max_g=250)
    before = copy.deepcopy(t)
    assert [i["weight_g"] for i in portion_options(d, t, config)] == [150, 300, 450]
    d, side_tag = make_dish("Rice", role="side", max_g=250)
    assert [i["weight_g"] for i in portion_options(d, side_tag, config)] == [150, 300]
    assert t == before # cached estimates are not rewritten
    config["portions"]["max_scoop_g_by_role"]["side"] = 150
    assert [i["weight_g"] for i in portion_options(d, side_tag, config)] == [150]


def test_fixed_caps_keep_piece_weights_and_unconfigured_roles(config, make_dish):
    d, t = make_dish("Pinsa", station="Pizza", piece=True, piece_g=250, max_g=300)
    options = portion_options(d, t, config)
    assert [(i["count"], i["weight_g"], i["unit"]) for i in options] == [(1, 250, "piece")]
    d, t = make_dish("Soup", role="soup", texture="liquid", max_g=250)
    assert [i["weight_g"] for i in portion_options(d, t, config)] == [150]


@pytest.mark.parametrize("maximum", [0, -1, True, "300", float("inf"), float("nan")])
def test_invalid_configured_scoop_caps(config, make_dish, maximum):
    config["portions"]["max_scoop_g_by_role"]["main"] = maximum
    d, t = make_dish()
    with pytest.raises(ValueError, match="Portion caps"):
        portion_options(d, t, config)


def test_friday_fish_can_reach_goals_with_two_scoops_of_rice(config, make_dish):
    fish, fish_tag = make_dish("Fish fillet", station="Fisch", vegan=False,
                             piece=True, piece_g=140, min_g=120, max_g=160,
                             kcal=115, protein=18.5)
    rice, rice_tag = make_dish("Rice", role="side", max_g=250, kcal=130, protein=2.7)
    tags = {normalize(fish["name"]): fish_tag, normalize(rice["name"]): rice_tag}
    values = list(candidates([fish, rice], tags, config))
    for goal in ("bulk", "cut", "budget"):
        value = choose(values, goal, config)
        assert value is not None and valid_plate(value["items"], config)
        assert value["items"][0]["weight_g"] == 140
        assert value["items"][1]["count"] == 2
        assert value["kcal"] == 551
        assert value["protein"] == 34
    # Both dishes individually fit, but the whole-plate cap still rejects 750g.
    a, at = make_dish("Main A")
    b, bt = make_dish("Main B")
    a = portion_options(a, at, config)[-1]
    b = portion_options(b, bt, config)[1]
    pairing = {"pairs": {pair_key(a, b): {"score": 3}}}
    assert not valid_plate([a, b], config, pairing)


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


def test_liquid_main_is_an_extra_not_a_plate(config, make_dish):
    d, t = make_dish("Substantial soup", role="main", texture="liquid")
    result = build_today(menu([d]), {normalize(d["name"]): t}, config)
    assert len(result["extras"]["all"]) == 1
    assert not any(v["plates"] for v in result["variants"].values())


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
