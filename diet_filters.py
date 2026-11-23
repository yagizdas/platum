"""Dietary exclusions derived from menu labels and explicit species names."""
import re

FILTERS = ('no_pork', 'no_beef', 'no_pork_beef', 'vegetarian')


def meat_types(item):
    markers = set(item.get('markers', []))
    if item.get('is_vegan') is True or item.get('is_vegetarian') is True or item.get('diet') in {'vegan', 'vegetarian'} or markers & {'v', 'f'}:
        return []
    labels = set(item.get('api_labels', []))
    name = item.get('name', '') + ' ' + item.get('name_en', '')
    species = set()
    rules = (
        ('pork', {'S'}, {'PORK'}, r'schwein|speck|schinken|bacon|pork|ham\b'),
        ('beef', {'R', 'K'}, {'BEEF', 'VEAL'}, r'rind|kalb|beef|veal'),
        ('poultry', {'G'}, {'POULTRY', 'CHICKEN', 'TURKEY'}, r'hähn|hühn|pute|chicken|turkey|ente|duck'),
        ('lamb', {'L'}, {'LAMB'}, r'lamm|lamb'),
        ('game', {'W'}, {'GAME'}, r'wild|hirsch|venison'),
        ('fish', set(), {'FISH'}, r'fisch|lachs|seelachs|thunfisch|fish|salmon|pollock|tuna'),
    )
    for kind, codes, api_codes, pattern in rules:
        if markers & codes or labels & api_codes or re.search(pattern, name, re.I):
            species.add(kind)
    if item.get('diet') == 'fish' or item.get('station') == 'Fisch':
        species.add('fish')
    return sorted(species or {'unknown'})


def allows(item, profile):
    species = set(meat_types(item))
    if profile == 'vegetarian':
        return not species
    excluded = {'unknown'}
    if profile in {'no_pork', 'no_pork_beef'}:
        excluded.add('pork')
    if profile in {'no_beef', 'no_pork_beef'}:
        excluded.add('beef')
    return not species & excluded
