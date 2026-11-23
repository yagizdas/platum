"""Build the small, static data set used by the preference labeler."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def plate_id(plate):
    return "+".join(sorted(item["id"] for item in plate["items"]))


def visual_item(item):
    """Keep the dish identity fields used by the shared plate artwork."""
    fields = ("name", "name_en", "station", "role", "diet", "is_vegan")
    return {field: item[field] for field in fields if field in item}


def build():
    days = []
    for path in sorted((ROOT / "data" / "days").glob("*.json")):
        source = json.loads(path.read_text())
        goals = {}
        for goal in ("bulk", "cut", "budget"):
            unique = {}
            for name, variant in source.get("variants", {}).items():
                if not name.startswith(goal + "_"):
                    continue
                for plate in variant.get("plates", []):
                    key = plate_id(plate)
                    unique[key] = {
                        "id": key,
                        "title": plate["title"],
                        "dishes": [item.get("name_en") or item["name"] for item in plate["items"]],
                        "items": [visual_item(item) for item in plate["items"]],
                        "kcal": plate["total"]["kcal"],
                        "protein": plate["total"]["protein_g"],
                        "price": plate["total"]["price_eur"],
                        "score": plate["score"]["total"],
                    }
            goals[goal] = sorted(unique.values(), key=lambda plate: plate["score"], reverse=True)
        if any(goals.values()):
            days.append({"date": source["date"], "goals": goals})
    return {"schema_version": 1, "days": days}


if __name__ == "__main__":
    (ROOT / "label" / "data.json").write_text(json.dumps(build(), indent=2) + "\n")
