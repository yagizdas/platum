"""Likely Arcisstraße serving counters, derived from online menu categories."""

# Keep this mapping in counter order so the UI gives consistent directions.
# Assignments are a heuristic: the Mensa chef can move dishes on any given day.
COUNTERS_BY_STATION = {
    "Fleisch": ("Warm 1&2",), "Fisch": ("Warm 1&2",), "Beilagen": ("Warm 1&2",),
    "Pasta": ("Warm 1&2", "Pasta"), "Vegetarisch/fleischlos": ("Warm 1&2", "Pasta"),
    "Pizza": ("Pasta",), "Vegan": ("Warm 1&2", "Warm 3/4"),
    "Studitopf": ("Warm 3/4",), "Wok": ("Warm 3/4",), "Grill": ("Grill",),
    "Dessert (Glas)": ("Warm 1&2",), "Süßspeise": ("Warm 1&2",),
    "Unspecified": ("Warm 1&2",),
}


def counters_for(station):
    """Return the editable heuristic assignment for a menu station."""
    return COUNTERS_BY_STATION.get(station, ("Warm 1&2",))


def shared_counters(items):
    """Return counters shared by every dish, preserving display order."""
    if not items:
        return ()
    shared = set(items[0].get("counters", counters_for(items[0]["station"])))
    for item in items[1:]:
        shared &= set(item.get("counters", counters_for(item["station"])))
    return tuple(counter for counter in ("Warm 1&2", "Pasta", "Warm 3/4", "Grill") if counter in shared)
