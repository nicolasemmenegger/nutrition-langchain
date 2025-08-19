from models import Ingredient, Meal, MealNutrition, IngredientUsage, db
from typing import List, Optional, Tuple
from fuzzywuzzy import fuzz, process
from PIL import Image
import io
import base64
from sqlalchemy import select
from dataclasses import dataclass
import re
from datetime import date, timedelta
import json

@dataclass
class ParsedItem:
    ingredient_name: str
    grams: float
    ingredient_id: Optional[int] = None
    new_ingredient: Optional[dict] = None  # if LLM created a nutrition card

def calculate_meal_nutrition(ingredients_ids, ingredient_weights):
    """
    Calculate the nutrition of a meal based on the ingredients and their weights.
    """
    # Fetch in bulk, then map by id to preserve correspondence with weights
    try:
        ids_int = [int(x) for x in ingredients_ids]
    except Exception:
        ids_int = []

    ingredients = Ingredient.query.filter(Ingredient.id.in_(ids_int)).all() if ids_int else []
    ingredient_by_id = {ing.id: ing for ing in ingredients}

    calories = 0.0
    protein = 0.0
    carbs = 0.0
    fat = 0.0
    for ing_id, weight in zip(ids_int, ingredient_weights):
        ing = ingredient_by_id.get(int(ing_id))
        if not ing:
            continue
        w = float(weight) or 0.0
        unit = float(ing.unit_weight) or 100.0
        calories += float(ing.calories) * w / unit
        protein += float(ing.protein) * w / unit
        carbs += float(ing.carbs) * w / unit
        fat += float(ing.fat) * w / unit
    return calories, protein, carbs, fat

def get_meals_for_date(date, user_id):
    """Get meals for a given date"""
    meals = Meal.query.filter_by(user_id=user_id, date=date).all()
    for meal in meals:
        meal_nutrition = MealNutrition.query.filter_by(meal_id=meal.id).first()
        if meal_nutrition:
            meal.calories = round(float(meal_nutrition.calories or 0), 2)
            meal.protein = round(float(meal_nutrition.protein or 0), 2)
            meal.carbs = round(float(meal_nutrition.carbs or 0), 2)
            meal.fat = round(float(meal_nutrition.fat or 0), 2)
        else:
            meal.calories = 0.0
            meal.protein = 0.0
            meal.carbs = 0.0
            meal.fat = 0.0
    # group by meal type, prepopulate known types for template safety
    meals_grouped = {
        "breakfast": {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0},
        "lunch": {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0},
        "dinner": {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0},
        "snack": {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0},
        "total": {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0},
    }
    for meal in meals:
        if meal.meal_type not in meals_grouped:
            meals_grouped[meal.meal_type] = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
        meals_grouped[meal.meal_type]["calories"] += float(meal.calories or 0.0)
        meals_grouped[meal.meal_type]["protein"] += float(meal.protein or 0.0)
        meals_grouped[meal.meal_type]["carbs"] += float(meal.carbs or 0.0)
        meals_grouped[meal.meal_type]["fat"] += float(meal.fat or 0.0)
    # Compute totals only from actual meal_type keys, excluding 'total'
    types = [k for k in meals_grouped.keys() if k != "total"]
    meals_grouped["total"]["calories"] = round(sum(meals_grouped[t]["calories"] for t in types), 2)
    meals_grouped["total"]["protein"] = round(sum(meals_grouped[t]["protein"] for t in types), 2)
    meals_grouped["total"]["carbs"] = round(sum(meals_grouped[t]["carbs"] for t in types), 2)
    meals_grouped["total"]["fat"] = round(sum(meals_grouped[t]["fat"] for t in types), 2)

    print(meals_grouped)
    return meals_grouped

def _png_base64(file_storage) -> str:
    """Convert uploaded image (any format) to base64 PNG data URL for OpenAI."""
    img = Image.open(file_storage.stream).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"

def _load_ingredient_index() -> Tuple[List[str], List[int]]:
    """Return parallel arrays of names and ids for fuzzy match."""
    rows = db.session.execute(select(Ingredient.id, Ingredient.name)).all()
    ids, names = zip(*[(r.id, r.name) for r in rows]) if rows else ([], [])
    return list(names), list(ids)

_STOP = {"fresh","organic","raw","cooked","dry","dried","unsalted","salted",
         "low-fat","lowfat","reduced-fat","lean","skinless","boneless","plain",
         # common qualifiers that shouldn't block matching
         "firm","extra-firm","silken","soft","extra"}
_WORD = re.compile(r"[A-Za-z0-9]+")

def _norm(s: str) -> str:
    s = (s or "").lower().replace("’", "'").strip()
    toks = [t for t in _WORD.findall(s) if t not in _STOP]
    return " ".join(toks)

def _token_set(s: str) -> set:
    return set(_norm(s).split())

def _len_ratio(a: str, b: str) -> float:
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return float("inf")
    return max(la, lb) / min(la, lb)

def _short(s: str) -> bool:
    return len(s) <= 3  # very short names are risky

def _combined(q: str, cand: str) -> float:
    # Blend a few scorers for robustness
    return 0.45*fuzz.WRatio(q, cand) + 0.45*fuzz.token_set_ratio(q, cand) + 0.10*fuzz.partial_ratio(q, cand)

def _fuzzy_match(name: str, names: List[str], ids: List[int], cutoff: int = 90) -> Optional[int]:
    """Return ingredient_id if a safe fuzzy match; else None."""
    if not names:
        return None

    qn = _norm(name)
    if not qn:
        return None

    # Pre-filter by token overlap & length sanity
    q_tokens = _token_set(qn)
    prelim = []
    for i, cand in enumerate(names):
        cn = _norm(cand)
        if not cn:
            continue
        # require at least 1 common token
        cand_tokens = _token_set(cn)
        if not (q_tokens & cand_tokens):
            continue
        # avoid big length mismatches unless query tokens are contained in candidate tokens
        lr = _len_ratio(qn, cn)
        if not (q_tokens <= cand_tokens) and lr > 3.0:
            continue
        prelim.append((i, cand, cn))

    if not prelim:
        return None

    # If query tokens are a subset of candidate tokens, prefer those directly
    subset = []
    for i, raw, cn in prelim:
        if q_tokens <= _token_set(cn):
            subset.append((i, raw, cn))
    if subset:
        best_score = -1.0
        best_idx = subset[0][0]
        for i, raw, cn in subset:
            s = _combined(qn, cn)
            if s > best_score:
                best_score = s
                best_idx = i
        return ids[best_idx]

    # Score prelim candidates; keep top-k
    scored = []
    for i, raw, cn in prelim:
        s = _combined(qn, cn)
        scored.append((s, i, raw, cn))
    scored.sort(reverse=True, key=lambda x: x[0])
    best_score, best_idx, best_raw, best_norm = scored[0]

    # Extra guard: ultra-short winners must be near-perfect
    if _short(best_norm) and best_score < 98:
        return None

    if best_score >= cutoff:
        return ids[best_idx]
    return None


def get_daily_nutrition_history(user_id: int, start_date: date, end_date: date):
    """Return a list of daily totals for calories and macros between start_date and end_date (inclusive).

    The result is a list of dicts sorted by date with keys: date, calories, protein, carbs, fat.
    Missing days are filled with zeros so charts can render continuous ranges.
    """
    # Aggregate per-day totals from Meal + MealNutrition
    rows = (
        db.session.query(
            Meal.date,
            db.func.sum(MealNutrition.calories).label("calories"),
            db.func.sum(MealNutrition.protein).label("protein"),
            db.func.sum(MealNutrition.carbs).label("carbs"),
            db.func.sum(MealNutrition.fat).label("fat"),
        )
        .join(MealNutrition, MealNutrition.meal_id == Meal.id)
        .filter(
            Meal.user_id == user_id,
            Meal.date >= start_date,
            Meal.date <= end_date,
        )
        .group_by(Meal.date)
        .order_by(Meal.date)
        .all()
    )

    # Map existing rows by date for quick lookup
    totals_by_date = {r[0]: {
        "calories": float(r[1] or 0),
        "protein": float(r[2] or 0),
        "carbs": float(r[3] or 0),
        "fat": float(r[4] or 0),
    } for r in rows}

    # Fill the full range
    results = []
    day = start_date
    while day <= end_date:
        values = totals_by_date.get(day, {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0})
        results.append({
            "date": day.isoformat(),
            "calories": round(values["calories"], 2),
            "protein": round(values["protein"], 2),
            "carbs": round(values["carbs"], 2),
            "fat": round(values["fat"], 2),
        })
        day += timedelta(days=1)

    return results


def get_user_favorite_meal(user_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None):
    """Return the user's most frequently logged meal name and count.

    If no meals exist, returns None. Optional date range can be provided.
    """
    q = (
        db.session.query(
            Meal.name.label("name"),
            db.func.count(Meal.id).label("count"),
        )
        .filter(Meal.user_id == user_id)
    )
    if start_date is not None:
        q = q.filter(Meal.date >= start_date)
    if end_date is not None:
        q = q.filter(Meal.date <= end_date)
    row = q.group_by(Meal.name).order_by(db.func.count(Meal.id).desc()).first()
    if not row:
        return None
    return {"name": row.name, "count": int(row.count)}


def get_ingredient_cloud_data(user_id: int, start_date: Optional[date], end_date: Optional[date], top_n: int = 50, _allow_fallback: bool = True):
    """Compute ingredient usage totals (grams) for a user's meals in a date range.

    Returns a list of dicts: { text: ingredient_name, weight: grams } sorted by weight desc.
    """
    q = Meal.query.filter_by(user_id=user_id)
    if start_date is not None:
        q = q.filter(Meal.date >= start_date)
    if end_date is not None:
        q = q.filter(Meal.date <= end_date)
    meals = q.all()

    totals_by_id = {}
    totals_by_free_name = {}
    for meal in meals:
        items = meal.ingredients
        # JSON column may contain stringified JSON; normalize
        try:
            if isinstance(items, str):
                items = json.loads(items)
        except Exception:
            items = []
        if not isinstance(items, list):
            continue
        for it in items:
            ing_id = it.get("ingredient_id")
            grams = float(it.get("weight") or it.get("grams") or 0) or 0.0
            if grams <= 0:
                continue
            if ing_id:
                totals_by_id[ing_id] = totals_by_id.get(ing_id, 0.0) + grams
            else:
                name = it.get("ingredient_name") or it.get("name")
                if name:
                    totals_by_free_name[name] = totals_by_free_name.get(name, 0.0) + grams

    # Normalize id keys to ints for reliable lookups
    id_totals_int = {}
    for k, v in totals_by_id.items():
        try:
            ik = int(k)
        except Exception:
            continue
        id_totals_int[ik] = id_totals_int.get(ik, 0.0) + float(v)

    ing_ids = list(id_totals_int.keys())
    ingredients = Ingredient.query.filter(Ingredient.id.in_(ing_ids)).all() if ing_ids else []
    id_to_name = {ing.id: ing.name for ing in ingredients}

    rows = []
    # From id totals
    for i, w in id_totals_int.items():
        nm = id_to_name.get(i)
        if nm:
            rows.append({"text": nm, "weight": round(w, 2)})
    # From free-name totals
    for nm, w in totals_by_free_name.items():
        rows.append({"text": nm, "weight": round(w, 2)})
    rows.sort(key=lambda r: r["weight"], reverse=True)

    # Fallback 1: if the requested window yields nothing, try all-time once
    if not rows and _allow_fallback and (start_date is not None or end_date is not None):
        return get_ingredient_cloud_data(user_id, None, None, top_n, _allow_fallback=False)

    # Fallback 2: if still nothing, derive from IngredientUsage totals (lifetime)
    if not rows:
        usages = IngredientUsage.query.filter_by(user_id=user_id).all()
        if usages:
            id_to_qty = {}
            for u in usages:
                try:
                    id_to_qty[int(u.ingredient_id)] = id_to_qty.get(int(u.ingredient_id), 0.0) + float(u.quantity or 0)
                except Exception:
                    continue
            if id_to_qty:
                ing_ids = list(id_to_qty.keys())
                ingredients = Ingredient.query.filter(Ingredient.id.in_(ing_ids)).all()
                name_by_id = {ing.id: ing.name for ing in ingredients}
                rows = [
                    {"text": name_by_id.get(i, str(i)), "weight": round(w, 2)}
                    for i, w in id_to_qty.items() if name_by_id.get(i)
                ]
                rows.sort(key=lambda r: r["weight"], reverse=True)
                return rows[:top_n]

    return rows[:top_n]
