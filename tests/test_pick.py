import copy

import pytest

from common import dish_id, normalize, read_json
from conftest import FIXTURES
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
    result = build_today(m, tags, config, pairing=pairing, no_llm=True, proposals=read_json(FIXTURES / "proposals-v4.json"))
    expected = {
        "bulk_all": ([('Vegane Maultaschen mit Zwiebelmarmelade', 3), ('Reis', 2)], 675, 29.4867) if fixed_caps else
                    ([('PINSA Funghi mit frischen Champignons', 1), ('Reis', 2)], 770, 27.0205),
        "cut_all": ([('Fleischpflanzerl (Frikadelle)', 1), ('Reis', 1)], 348, -1.7821),
        "budget_all": ([('Käsekrainer (1 Stück)', 1)], 226, .1448),
        "bulk_vegan": ([('Asia-Reisbällchen auf Teriyakigemüse', 3), ('Vegane Maultaschen mit Zwiebelmarmelade', 3)], 810, 34.8506) if fixed_caps else
                      ([('Asia-Reisbällchen auf Teriyakigemüse', 3), ('Vegane Maultaschen mit Zwiebelmarmelade', 2)], 675, 28.0622),
        "cut_vegan": ([('Vegane Maultaschen mit Zwiebelmarmelade', 2), ('Gemüsecurry aus Blumenkohl und Broccoli', 1)], 405, -7.0742),
        "budget_vegan": ([('Graupen-Gemüse-Eintopf', 2), ('Vegane Maultaschen mit Zwiebelmarmelade', 2)], 369, -.3292),
    }
    for key, (items, price, score) in expected.items():
        p = result["variants"][key]["plates"][0]
        assert [(i["name"], i["count"]) for i in p["items"]] == items
        assert p["total"]["price_cents"] == price
        assert p["score"]["total"] == score
    assert result["schema_version"] == 2
    for v in result["variants"].values():
        for p in v["plates"]:
            assert p["total"]["price_cents"] == sum(i["price_cents"] for i in p["items"])
            assert p["total"]["weight_g"] == sum(i["weight_g"] for i in p["items"])


def test_every_candidate_meets_rules(config, fixture_menu, pairing):
    m, tags = fixture_menu
    values = list(candidates(m["dishes"], tags, config, pairing=pairing))
    assert values
    for p in values:
        items = p["items"]
        assert valid_plate(items, config, pairing)
        assert len(items) in (1, 2) and len({i["name"] for i in items}) == len(items)
        assert not any(i["role"] in {"soup", "dessert"} or i["texture"] == "liquid" for i in items)
        if len(items) == 1:
            assert not items[0]["standing"]
        else:
            assert any(i["standing"] for i in items) # deterministic fallback is main + standing side
        assert p["weight_g"] == sum(i["weight_g"] for i in items)


def test_pool_has_one_portioning_per_lunch(config, fixture_menu, pairing):
    m, tags = fixture_menu
    values = list(candidates(m["dishes"], tags, config, pairing=pairing))
    for goal in ("bulk", "cut", "budget"):
        pool = top_plates(values, goal, config)
        sets = [tuple(sorted(i["name"] for i in p["items"])) for p in pool]
        assert len(pool) <= 5 and len(sets) == len(set(sets))
        assert choose(values, goal, config) == pool[0]
        scores = [p["score"]["total"] for p in pool]
        assert scores == sorted(scores, reverse=True)
        mains = [dish_id(i) for p in pool for i in p["items"] if i["role"] == "main" and not i["standing"]]
        assert len(mains) == len(set(mains))


def test_equal_scores_use_price_then_sorted_dish_ids(config, make_dish):
    for feature in config["scoring"]["bulk"]["learned_model"]["features"]:
        feature["weight"] = 0
    dishes, tags = [], {}
    for name, price in [("Main A", 1), ("Main B", 1), ("Main C", 2)]:
        d, t = make_dish(name, base=price, rate=0)
        dishes.append(d);tags[normalize(name)] = t
    values = list(candidates(dishes, tags, config))
    ranked = top_plates(reversed(values), "bulk", config)
    actual = [(p["price_cents"], tuple(sorted(dish_id(i) for i in p["items"]))) for p in ranked]
    assert actual == sorted(actual)
    assert len(ranked) == 3


def test_invalid_single_pairs_and_pizza(config, fixture_menu, pairing):
    m, tags = fixture_menu
    values = {d["name"]: food(d, tags) for d in m["dishes"]}
    fish = next(i for i in values.values() if i["name"].startswith("Seelachs"))
    pinsa = next(i for i in values.values() if i["station"] == "Pizza")
    rice = values["Reis"]
    f = portion_options(fish, fish, config)[0]
    p = portion_options(pinsa, pinsa, config)[0]
    r = portion_options(rice, rice, config)[0]
    assert valid_plate([f], config, pairing) # proposals decide completeness, not old pair scores
    assert not valid_plate([r], config, pairing)
    assert valid_plate([f, p], config, pairing)
    assert not valid_plate([f, f], config, pairing)
    assert not valid_plate([f, r, r], config, pairing)
    bad = copy.deepcopy(pairing); bad["pairs"][pair_key(f, r)]["score"] = 1
    assert valid_plate([f, r], config, bad)
    assert not valid_plate([f, {**r, "count": 4, "weight_g": 600}], config, pairing)
    assert not valid_plate([f, {**r, "is_per_piece": True}], config, pairing)
    potato = values["Kartoffelsalat"]
    k = portion_options(potato, potato, config)[0]
    bad["pairs"][pair_key(r, k)] = {"score": 3}
    bad["pairs"][pair_key(f, p)] = {"score": 3}
    assert not valid_plate([r, k], config, bad) # model scores cannot create a main-less plate
    assert valid_plate([f, p], config, bad)


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


def test_goal_scoring_chooses_rice_portions_for_fixed_fish_serving(config, make_dish):
    fish, fish_tag = make_dish("Fish fillet", station="Fisch", vegan=False,
                             piece=True, piece_g=140, min_g=120, max_g=160,
                             kcal=115, protein=18.5)
    rice, rice_tag = make_dish("Rice", role="side", max_g=250, kcal=130, protein=2.7)
    tags = {normalize(fish["name"]): fish_tag, normalize(rice["name"]): rice_tag}
    values = list(candidates([fish, rice], tags, config))
    # Score each portioning of the same proposed fish + rice tray.
    values = [p for p in values if len(p["items"]) == 2]
    for goal in ("bulk", "cut", "budget"):
        value = choose(values, goal, config)
        assert value is not None and valid_plate(value["items"], config)
        assert value["items"][0]["weight_g"] == 140
        count = 2 if goal == "bulk" else 1
        assert value["items"][1]["count"] == count
        assert value["kcal"] == (551 if goal == "bulk" else 356)
        assert value["protein"] == (34 if goal == "bulk" else 29.95)
def test_candidates_can_exceed_650g_within_individual_portion_limits(config, make_dish):
    a, at = make_dish("Main A")
    b, bt = make_dish("Main B")
    values = list(candidates([a, b], {normalize(a["name"]): at, normalize(b["name"]): bt}, config,
                             proposals=[[dish_id(a), dish_id(b)]]))
    large = [p for p in values if p["weight_g"] > 650]
    assert {p["weight_g"] for p in large} == {750, 900}
    assert all(valid_plate(p["items"], config) for p in large)
    assert choose(values, "bulk", config)["weight_g"] > 650


def test_piece_over_650g_retains_cached_weight(config, make_dish):
    d, t = make_dish("Large pizza", station="Pizza", piece=True,
                     piece_g=700, min_g=650, max_g=750)
    options = portion_options(d, t, config)
    assert [(i["count"], i["weight_g"], i["unit"]) for i in options] == [(1, 700, "piece")]
    assert valid_plate(options, config)


@pytest.mark.parametrize("count", [1, 2, 6])
def test_piece_count_is_one_fixed_serving_with_one_surcharge(config, make_dish, count):
    d, t = make_dish(f"Meatballs ({count} Stück)", piece=True, piece_g=240,
                     min_g=200, max_g=300, base=1, rate=.9)
    values = list(candidates([d], {normalize(d["name"]): t}, config))
    assert len(values) == 1
    p = values[0]
    assert p["items"][0]["count"] == 1
    assert p["items"][0]["unit"] == "piece"
    assert p["weight_g"] == 240
    assert p["price_cents"] == 316
    assert p["kcal"] == 480
    assert p["protein"] == 24


def test_bulk_price_cap_does_not_change_other_goals(config, make_dish):
    d, t = make_dish("Expensive pasta", protein=20, base=10, rate=0)
    values = list(candidates([d], {normalize(d["name"]): t}, config))
    assert choose(values, "bulk", config) is None
    assert all(choose(values, goal, config)["price_cents"] == 1000 for goal in ("cut", "budget"))


def test_vegan_relaxation_applies_to_all_three_goals(config, fixture_menu, pairing):
    m, tags = fixture_menu
    config["goals"] = {goal + "_min_protein_g": 1000 for goal in ("bulk", "cut", "budget")}
    result = build_today(m, tags, config, pairing=pairing)
    for goal in ("bulk", "cut", "budget"):
        v = result["variants"][goal + "_vegan"]
        assert not v["relaxed"] and v["note"] is None and v["plates"]
        assert all(i["is_vegan"] is True for p in v["plates"] for i in p["items"])
        assert result["variants"][goal + "_all"]["plates"] # soft scores have no floors to relax


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
    assert all(v["plates"] for v in result["variants"].values()) # a substantial soup can be a main proposal


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


@pytest.mark.parametrize('goal', ['cut', 'budget'])
def test_meal_minimums_reject_snack_portions_before_ranking(config, make_dish, goal):
    stew, tag = make_dish("Farmer's stew", kcal=85, protein=4.5, min_g=150)
    values = list(candidates([stew], {normalize(stew['name']): tag}, config))
    selected = choose(values, goal, config)
    assert selected['kcal'] == 382.5
    assert selected['protein'] == 20.25
    assert selected['items'][0]['count'] == 3
    assert choose([p for p in values if p['kcal'] < 300 or p['protein'] < 20], goal, config) is None
    # Bulk has no minimum meal requirement.
    assert choose(values[:1], 'bulk', config) is not None


@pytest.mark.parametrize('kcal,protein,qualifies', [(300,20,True),(299.99,20,False),(300,19.99,False)])
@pytest.mark.parametrize('goal', ['cut', 'budget'])
def test_meal_minimum_boundaries(config, make_dish, kcal, protein, qualifies, goal):
    config['portions']['max_scoop_g_by_role']['main'] = 150
    dish, tag = make_dish('Boundary plate', min_g=150, max_g=150, kcal=kcal/1.5, protein=protein/1.5)
    values = list(candidates([dish], {normalize(dish['name']): tag}, config))
    assert bool(choose(values, goal, config)) is qualifies


@pytest.mark.parametrize('kcal,qualifies', [(1400, True), (1500, True), (1500.01, False)])
def test_bulk_calorie_cap_boundaries(config, make_dish, kcal, qualifies):
    dish, tag = make_dish('Fixed lunch', piece=True, piece_g=300, min_g=300, max_g=300,
                          kcal=kcal / 3, protein=10)
    values = list(candidates([dish], {normalize(dish['name']): tag}, config))
    assert bool(choose(values, 'bulk', config)) is qualifies
    assert choose(values, 'cut', config) is not None
    assert choose(values, 'budget', config) is not None


@pytest.mark.parametrize('price,qualifies', [(8.99, True), (9, True), (9.01, False)])
def test_bulk_price_cap_boundaries(config, make_dish, price, qualifies):
    dish, tag = make_dish('Fixed-price lunch', piece=True, piece_g=300, min_g=300, max_g=300,
                          base=price, rate=0, protein=10)
    values = list(candidates([dish], {normalize(dish['name']): tag}, config))
    assert bool(choose(values, 'bulk', config)) is qualifies
    assert choose(values, 'cut', config) is not None
    assert choose(values, 'budget', config) is not None


def test_bulk_price_cap_refills_ranking_with_best_eligible_plates(config, make_dish):
    dishes, tags = [], {}
    for name, price in [('Too expensive', 10), ('Best eligible', 9), ('Next eligible', 8)]:
        dish, tag = make_dish(name, piece=True, piece_g=300, min_g=300, max_g=300,
                              base=price, rate=0, protein=10)
        dishes.append(dish)
        tags[normalize(name)] = tag
    ranked = top_plates(candidates(dishes, tags, config), 'bulk', config)
    assert [plate['price_cents'] for plate in ranked] == [900, 800]


@pytest.mark.parametrize('vegan', [False, True])
def test_bulk_cap_selects_smaller_eligible_portions(config, make_dish, vegan):
    dish, tag = make_dish('Calorie dense main', vegan=vegan, kcal=400, protein=15)
    values = list(candidates([dish], {normalize(dish['name']): tag}, config, vegan=vegan))
    assert any(plate['kcal'] > 1500 for plate in values)
    selected = choose(values, 'bulk', config)
    assert selected['items'][0]['count'] == 2
    assert selected['kcal'] == 1200


def test_bulk_cap_applies_to_the_whole_tray(config, make_dish):
    first, first_tag = make_dish('First main', kcal=200)
    second, second_tag = make_dish('Second main', kcal=200)
    tags = {normalize(first['name']): first_tag, normalize(second['name']): second_tag}
    values = list(candidates([first, second], tags, config,
                             proposals=[[dish_id(first), dish_id(second)]]))
    assert max(plate['kcal'] for plate in values) == 1800
    assert choose(values, 'bulk', config)['kcal'] == 1500
