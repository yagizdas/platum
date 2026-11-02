from pathlib import Path
from datetime import date
import json

import pytest

from common import load_config, read_json
from scrape import scrape

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def config():
    config = load_config()
    # Ordinary picker tests stay deterministic even when a local .env has a real key.
    config["llm"]["enabled"] = False
    return config


@pytest.fixture
def fixture_menu(config):
    return read_json(FIXTURES / "menu-2026-11-02.json"), read_json(FIXTURES / "dish-cache-2026-11-02.json")


@pytest.fixture
def pairing():
    return read_json(FIXTURES / "pairing-2026-11-02.json")


@pytest.fixture
def make_dish():
    """Synthetic estimates, deliberately separate from the production tag cache."""
    def make(name="Test main", station="Wok", vegan=True, role="main", texture="dry",
             kcal=200, protein=10, min_g=150, max_g=450, piece=False, piece_g=None,
             base=0, rate=.9):
        dish = {"name": name, "station": station, "is_vegan": vegan, "is_vegetarian": vegan,
                "markers": ["v"] if vegan else [], "allergens": [], "additives": [], "standing": role == "side",
                "price": {"base_eur": base, "per_100g_eur": rate, "source": "config"}}
        tag = {"name_en": name, "role": role, "texture": texture, "kcal_per_100g": kcal,
               "protein_per_100g": protein, "carbs_per_100g": 15, "fat_per_100g": 5,
               "typical_portion_g": {"min": min_g, "max": max_g}, "is_per_piece": piece,
               "piece_weight_g": piece_g}
        return dish, tag
    return make
