"""Portable goal-fit trees for the isolated staging F experiment. No ML dependency."""
import math
import struct
from functools import lru_cache

from common import ROOT, read_json

FEATURES = ('kcal', 'protein', 'price', 'fat_g', 'carbs_g', 'weight_g', 'dish_count',
            'fat_energy_pct', 'protein_energy_pct', 'soup_weight_g', 'dessert_weight_g', 'side_weight_g')
MODEL_PATH = ROOT / 'data/models/goal-fit-v2.json'


def features(p):
    raw = 'price_cents' in p
    kcal, protein = round(p['kcal'], 2), round(p['protein'], 2)
    fat = round(p['fat'] if raw else p['fat_g'], 2)
    values = [kcal, protein, p['price_cents']/100 if raw else p['price'], fat,
              round(p['carbs'] if raw else p['carbs_g'], 2), p['weight_g'], len(p['items']),
              round(900*fat/kcal, 3) if kcal else 0, round(400*protein/kcal, 3) if kcal else 0]
    values += [sum(i['weight_g'] for i in p['items'] if i['role'] == role) for role in ('soup', 'dessert', 'side')]
    if not all(math.isfinite(v) for v in values):raise ValueError('Nonfinite goal-fit input')
    # Match scikit-learn's tree input precision exactly.
    return [struct.unpack('f', struct.pack('f', v))[0] for v in values]


@lru_cache(maxsize=1)
def load_models():
    result = read_json(MODEL_PATH)
    if result['features'] != list(FEATURES) or result['schema_version'] != 1:
        raise ValueError('Incompatible goal-fit model')
    return result


def tree_value(tree, values):
    node = 0
    while tree['left'][node] != -1:
        node = tree['left'][node] if values[tree['feature'][node]] <= tree['threshold'][node] else tree['right'][node]
    return tree['value'][node]


def predict_ensemble(model, values):
    return model['intercept'] + model['learning_rate'] * sum(tree_value(t, values) for t in model['trees'])


def predict(p, goal, models=None):
    model = (models or load_models())['goals'][goal]
    values = features(p)
    logit = predict_ensemble(model['acceptability'], values)
    probability = 1/(1+math.exp(-max(-40, min(40, logit))))
    utility = predict_ensemble(model['preference'], values)
    return {'total': round(utility, 8), 'acceptability': round(probability, 8),
            'eligible': probability >= model['acceptability_threshold']}
