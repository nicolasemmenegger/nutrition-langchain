import csv
from typing import List, Dict
from ..config import settings

def load_foods() -> List[Dict]:
    rows = []
    with open(settings.foods_csv, "r") as f:
        r = csv.DictReader(f)
        for row in r:
            # normalize numbers
            for k in ["calories", "protein", "carbs", "fat"]:
                row[k] = float(row[k])
            row["grams"] = 100.0  # per 100g baseline
            # parse optional units column mapping unit -> grams
            units_raw = row.get("units")
            units_map: Dict[str, float] = {"g": 1.0}
            if units_raw:
                units_raw = units_raw.strip()
                if units_raw.startswith("{"):
                    try:
                        import json
                        units_map = {k: float(v) for k, v in json.loads(units_raw).items()}
                    except Exception:
                        units_map = {"g": 1.0}
                else:
                    parts = [p.strip() for p in units_raw.split(";") if p.strip()]
                    for p in parts:
                        if ":" in p:
                            u, g = p.split(":", 1)
                            try:
                                units_map[u.strip()] = float(g)
                            except Exception:
                                pass
            row["units"] = units_map
            rows.append(row)
    return rows

def find_food(name: str) -> Dict | None:
    """Find the best matching food by name.
    Strategy: exact (case-insensitive) -> substring -> fuzzy best ratio.
    """
    name_l = name.strip().lower()
    foods = load_foods()
    # exact
    for row in foods:
        if row["name"].lower() == name_l:
            return row
    # substring
    for row in foods:
        if name_l in row["name"].lower():
            return row
    # fuzzy (difflib)
    try:
        from difflib import SequenceMatcher
        best_row = None
        best_ratio = 0.0
        for row in foods:
            r = SequenceMatcher(None, name_l, row["name"].lower()).ratio()
            if r > best_ratio:
                best_ratio = r
                best_row = row
        if best_ratio >= 0.6:
            return best_row
    except Exception:
        pass
    return None

def compute_from_grams(name: str, grams: float) -> Dict | None:
    base = find_food(name)
    if not base:
        return None
    factor = grams / 100.0
    return {
        "name": base["name"],
        "grams": grams,
        "calories": round(base["calories"] * factor, 1),
        "protein": round(base["protein"] * factor, 1),
        "carbs": round(base["carbs"] * factor, 1),
        "fat": round(base["fat"] * factor, 1),
    }

def allowed_units(name: str) -> Dict[str, float]:
    base = find_food(name)
    if not base:
        return {"g": 1.0}
    return base.get("units", {"g": 1.0})

def convert_to_grams(name: str, amount: float, unit: str) -> float | None:
    units = allowed_units(name)
    if unit not in units:
        return None
    grams_per_unit = units[unit]
    return float(amount) * float(grams_per_unit)
