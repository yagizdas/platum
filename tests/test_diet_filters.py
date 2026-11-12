import pytest
from diet_filters import allows, meat_types
from pick import build_today
from common import read_json
from conftest import FIXTURES


@pytest.mark.parametrize('name,markers,species', [
    ('Pork with beef', ['S', 'R'], ['beef', 'pork']),
    ('Turkey steak', ['G'], ['poultry']),
    ('Breaded veal', ['K'], ['beef']),
    ('Unspecified sausage', [], ['unknown']),
])
def test_species_labels(name, markers, species):
    assert meat_types({'name': name, 'markers': markers}) == species


def test_vegetarian_filter_and_unknown_meat():
    assert allows({'diet': 'vegetarian'}, 'vegetarian')
    assert not allows({'diet': 'fish'}, 'vegetarian')
    assert not allows({'diet': 'meat'}, 'no_pork')
    assert not allows({'markers': ['R', 'S']}, 'no_beef')
    assert allows({'markers': ['G']}, 'no_pork_beef')


def test_filtered_rankings_keep_diet_rules_and_original_goals(config, fixture_menu):
    menu, tags = fixture_menu
    result = build_today(menu, tags, config, no_llm=True, proposals=read_json(FIXTURES / 'proposals-v4.json'))
    assert len(result['variants']) == 6
    assert len(result['filtered_variants']) == 12
    for key, variant in result['filtered_variants'].items():
        goal, profile = key.split('_', 1)
        for plate in variant['plates']:
            assert all(allows(item, profile) for item in plate['items'])
            if goal == 'bulk':
                assert plate['total']['kcal'] <= 1500
            else:
                assert plate['total']['kcal'] >= 300
                assert plate['total']['protein_g'] >= 20
