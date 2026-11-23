import math

import pytest

from scoring import h, score_plate


@pytest.mark.parametrize("x,up,down,expected", [(10, 1, 3, 10), (-10, 1, 3, -30),
    (0, .5, 3, 0), (10, 0, 2, 0), (-10, 0, 2, -20)])
def test_asymmetric_linear(x, up, down, expected):
    assert h(x, up, down) == expected


def test_learned_cut_prefers_more_protein_and_less_energy(config):
    plate = {"price_cents": 400, "kcal": 600, "protein": 36}
    score = score_plate(plate, "cut", config)["total"]
    assert score_plate({**plate, "protein": 46}, "cut", config)["total"] > score
    assert score_plate({**plate, "kcal": 700}, "cut", config)["total"] < score


def test_learned_budget_penalizes_price_continuously(config):
    scores = []
    for cents in (600, 700, 701, 800):
        terms = score_plate({"price_cents": cents, "kcal": 900, "protein": 60}, "budget", config)
        scores.append(terms["price"])
    assert scores[0] > scores[1] > scores[2] > scores[3]
    assert scores[1] - scores[0] == pytest.approx(scores[3] - scores[1])
    assert scores[2] - scores[1] == pytest.approx(.01 * (scores[1] - scores[0]))


@pytest.mark.parametrize("alternative", [
    {"price_cents": 350, "kcal": 600, "protein": 30},
    {"price_cents": 400, "kcal": 650, "protein": 35},
])
def test_bulk_prefers_substantial_protein_over_cheap_energy_or_small_value_plate(config, alternative):
    preferred = {"price_cents": 650, "kcal": 950, "protein": 60}
    assert score_plate(preferred, "bulk", config)["total"] > score_plate(alternative, "bulk", config)["total"]


@pytest.mark.parametrize("goal", ["bulk", "cut", "budget"])
def test_learned_score_is_sum_of_model_feature_terms(config, goal):
    p = {"price_cents": 400, "kcal": 600, "protein": 36}
    score = score_plate(p, goal, config)
    weights = {feature["name"]: feature for feature in config["scoring"][goal]["learned_model"]["features"]}
    assert score["kcal"] == pytest.approx(weights["kcal"]["weight"] * 6)
    assert score["protein"] == pytest.approx(weights["protein"]["weight"] * 3.6)
    assert score["price"] == pytest.approx(weights["price"]["weight"] * 4)
    assert score["total"] == round(score["kcal"] + score["protein"] + score["price"], 4)


@pytest.mark.parametrize("goal", ["bulk", "cut", "budget"])
def test_zero_price_and_energy_are_finite(config, goal):
    assert all(math.isfinite(x) for x in score_plate({"price_cents": 0, "kcal": 0, "protein": 0}, goal, config).values())
