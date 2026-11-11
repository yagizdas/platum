import math

import pytest

from scoring import h, score_plate


@pytest.mark.parametrize("x,up,down,expected", [(10, 1, 3, 10), (-10, 1, 3, -30),
    (0, .5, 3, 0), (10, 0, 2, 0), (-10, 0, 2, -20)])
def test_asymmetric_linear(x, up, down, expected):
    assert h(x, up, down) == expected


@pytest.mark.parametrize("goal,terms,total", [
    ("cut", {"price": -1, "price_over_budget": 0, "protein_density": 1.5, "protein_value": .375, "protein": .2, "energy": 0}, 1.075),
    ("budget", {"price": -2, "price_over_budget": 0, "energy_value": .6, "energy": 1 / 30, "protein": 3.2 / 15}, -1.1533),
])
def test_hand_computed_formulas(config, goal, terms, total):
    score = score_plate({"price_cents": 400, "kcal": 600, "protein": 36}, goal, config)
    assert score["total"] == total
    assert {k: v for k, v in score.items() if k != "total"} == pytest.approx(terms)


@pytest.mark.parametrize("goal,total", [("cut", -3.4583), ("budget", -4.9)])
def test_soft_deficits(config, goal, total):
    assert score_plate({"price_cents": 200, "kcal": 300, "protein": 10}, goal, config)["total"] == total


def test_cut_penalizes_energy_above_pivot(config):
    score = score_plate({"price_cents": 400, "kcal": 800, "protein": 40}, "cut", config)
    assert score["energy"] == -1
    assert score["total"] == 0


@pytest.mark.parametrize("goal,base_per_euro", [("cut", .25), ("budget", .5)])
def test_price_penalty_is_continuous_and_steeper_above_seven_euros(config, goal, base_per_euro):
    penalties = []
    for cents in (600, 700, 701, 800):
        terms = score_plate({"price_cents": cents, "kcal": 900, "protein": 60}, goal, config)
        assert terms["price_over_budget"] == pytest.approx(-max(0, cents / 100 - 7))
        penalties.append(terms["price"] + terms["price_over_budget"])
    assert penalties[1] - penalties[0] == pytest.approx(-base_per_euro)
    assert penalties[2] - penalties[1] == pytest.approx(-.01 * (base_per_euro + 1))
    assert penalties[3] - penalties[1] == pytest.approx(-(base_per_euro + 1))


@pytest.mark.parametrize("alternative", [
    {"price_cents": 350, "kcal": 600, "protein": 30},
    {"price_cents": 400, "kcal": 650, "protein": 35},
])
def test_bulk_prefers_substantial_protein_over_cheap_energy_or_small_value_plate(config, alternative):
    preferred = {"price_cents": 650, "kcal": 950, "protein": 60}
    assert score_plate(preferred, "bulk", config)["total"] > score_plate(alternative, "bulk", config)["total"]


def test_learned_bulk_score_is_sum_of_model_feature_terms(config):
    p = {"price_cents": 400, "kcal": 600, "protein": 36}
    score = score_plate(p, "bulk", config)
    weights = {feature["name"]: feature for feature in config["scoring"]["bulk"]["learned_model"]["features"]}
    assert score["kcal"] == pytest.approx(weights["kcal"]["weight"] * 6)
    assert score["protein"] == pytest.approx(weights["protein"]["weight"] * 3.6)
    assert score["price"] == pytest.approx(weights["price"]["weight"] * 4)
    assert score["total"] == round(score["kcal"] + score["protein"] + score["price"], 4)


@pytest.mark.parametrize("goal", ["bulk", "cut", "budget"])
def test_zero_price_and_energy_are_finite(config, goal):
    assert all(math.isfinite(x) for x in score_plate({"price_cents": 0, "kcal": 0, "protein": 0}, goal, config).values())
