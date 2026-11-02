from pathlib import Path

import pytest

from common import load_config

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def make_dish():
    """Synthetic estimates, deliberately separate from the production tag cache."""
    def make(name="Test main", station="Wok", vegan=True, role="main", texture="dry",
             kcal=200, protein=10, min_g=150, max_g=450, piece=False, piece_g=None,
             base=0, rate=.9):
        dish = {"name": name, "station": station, "is_vegan": vegan, "is_vegetarian": vegan,
                "markers": ["v"] if vegan else [], "allergens": [], "additives": [],
                "price": {"base_eur": base, "per_100g_eur": rate, "source": "config"}}
        tag = {"name_en": name, "role": role, "texture": texture, "kcal_per_100g": kcal,
               "protein_per_100g": protein, "carbs_per_100g": 15, "fat_per_100g": 5,
               "typical_portion_g": {"min": min_g, "max": max_g}, "is_per_piece": piece,
               "piece_weight_g": piece_g}
        return dish, tag
    return make
