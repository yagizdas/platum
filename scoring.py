"""Fixed, configurable goal equations. No nutrition floors or model decisions."""


def h(x, up, down):
    return (up if x >= 0 else down) * x


def score_plate(plate, goal, config):
    settings = config["scoring"][goal]
    euros, kcal, prot = plate["price_cents"] / 100, plate["kcal"], plate["protein"]
    if "learned_model" in settings:
        model = settings["learned_model"]
        values = {"kcal": kcal, "protein": prot, "price": euros}
        terms = {feature["name"]: feature["weight"] * values[feature["name"]] / feature["scale"]
                 for feature in model["features"]}
        return {**terms, "total": round(sum(terms.values()), 4)}
    # Zero-price or zero-energy dishes have zero density, not infinity/NaN.
    metrics = {"price": euros, "kcal_per_euro": kcal / euros if euros > 0 else 0,
               "protein_per_euro": prot / euros if euros > 0 else 0,
               "protein_per_100kcal": prot / kcal * 100 if kcal > 0 else 0}
    terms = {}
    for name, term in settings.items():
        if "metric" in term:
            terms[name] = term["weight"] * metrics[term["metric"]] / term["normalizer"]
        else:
            value = {"kcal": kcal, "protein": prot, "price": euros}[term["quantity"]]
            delta = (term["pivot"] - value) if term.get("reverse") else (value - term["pivot"])
            terms[name] = h(delta, term["up"], term["down"]) / term["normalizer"]
    return {**terms, "total": round(sum(terms.values()), 4)}
