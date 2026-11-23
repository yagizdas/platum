import json

from train_pairwise_score import fit, agrees


def test_training_reproduces_high_leave_one_date_out_accuracy():
    rows = [row for row in json.loads((__import__("pathlib").Path(__file__).parents[1]
            / "data/judgments/bulk-2026-11-11.json").read_text()) if row["winner"] in {"a", "b"}]
    correct = 0
    for date in {row["date"] for row in rows}:
        weights = fit([row for row in rows if row["date"] != date])
        correct += sum(agrees(row, weights) for row in rows if row["date"] == date)
    assert correct / len(rows) > 0.75
