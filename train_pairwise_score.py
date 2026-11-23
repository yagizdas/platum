"""Fit a reproducible pairwise logistic plate-scoring model."""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FEATURES = (("kcal", 100), ("protein", 10), ("price", 1))


def solve(matrix, vector):
    """Solve a tiny dense linear system with pivoted Gaussian elimination."""
    size = len(vector)
    rows = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda index: abs(rows[index][column]))
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for index in range(column + 1, size):
            ratio = rows[index][column] / rows[column][column]
            for item in range(column, size + 1):
                rows[index][item] -= ratio * rows[column][item]
    result = [0.0] * size
    for index in range(size - 1, -1, -1):
        result[index] = (rows[index][size] - sum(rows[index][item] * result[item]
                         for item in range(index + 1, size))) / rows[index][index]
    return result


def difference(row):
    return [(row["plate_a"][name] - row["plate_b"][name]) / scale for name, scale in FEATURES]


def fit(rows, regularization=0.5):
    """Fit Bradley-Terry weights with Newton-Raphson and no intercept."""
    weights = [0.0] * len(FEATURES)
    for _ in range(100):
        gradient = [-regularization * weight for weight in weights]
        information = [[regularization * (i == j) for j in range(len(FEATURES))]
                       for i in range(len(FEATURES))]
        for row in rows:
            values = difference(row)
            linear = max(-40, min(40, sum(weight * value for weight, value in zip(weights, values))))
            probability = 1 / (1 + math.exp(-linear))
            target = row["winner"] == "a"
            for i, value in enumerate(values):
                gradient[i] += (target - probability) * value
                for j, other in enumerate(values):
                    information[i][j] += probability * (1 - probability) * value * other
        step = solve(information, gradient)
        weights = [weight + change for weight, change in zip(weights, step)]
        if max(map(abs, step)) < 1e-10:
            break
    return weights


def agrees(row, weights):
    return (sum(weight * value for weight, value in zip(weights, difference(row))) > 0) == (row["winner"] == "a")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/judgments/bulk-2026-11-11.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/models/bulk-score.json")
    parser.add_argument("--goal", default="bulk")
    parser.add_argument("--user", help="Optionally train only judgments for one user ID")
    parser.add_argument("--regularization", type=float, default=0.5)
    args = parser.parse_args()
    judgments = json.loads(args.input.read_text())
    rows = [row for row in judgments if row.get("goal") == args.goal and row.get("winner") in {"a", "b"}
            and (args.user is None or row.get("user") == args.user)]
    if not rows:
        raise ValueError("No decisive judgments matched the requested goal and user")

    correct = 0
    dates = sorted({row["date"] for row in rows})
    for held_out in dates:
        weights = fit([row for row in rows if row["date"] != held_out], args.regularization)
        correct += sum(agrees(row, weights) for row in rows if row["date"] == held_out)
    old_correct = sum((row["plate_a"]["score"] > row["plate_b"]["score"]) == (row["winner"] == "a") for row in rows)
    weights = fit(rows, args.regularization)
    model = {"type": "bradley-terry", "goal": args.goal, "intercept": 0,
             "regularization": args.regularization, "training_rows": len(rows),
             "features": [{"name": name, "scale": scale, "weight": round(weight, 12)}
                          for (name, scale), weight in zip(FEATURES, weights)]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(model, indent=2, allow_nan=False) + "\n")
    print(f"Leave-one-date-out accuracy: {correct}/{len(rows)} ({correct / len(rows):.1%})")
    print(f"Old score agreement: {old_correct}/{len(rows)} ({old_correct / len(rows):.1%})")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
