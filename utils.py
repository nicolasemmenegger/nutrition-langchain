from models import Ingredient, Meal, MealNutrition, db
from typing import List, Optional, Tuple
from fuzzywuzzy import fuzz, process
from PIL import Image
import io
import base64
from sqlalchemy import select
from dataclasses import dataclass
import re

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
    ingredients = Ingredient.query.filter(Ingredient.id.in_(ingredients_ids)).all()
    calories = 0
    protein = 0
    carbs = 0
    fat = 0
    for ingredient, weight in zip(ingredients, ingredient_weights):
        calories += float(ingredient.calories) * float(weight) / float(ingredient.unit_weight)
        protein += float(ingredient.protein) * float(weight) / float(ingredient.unit_weight)
        carbs += float(ingredient.carbs) * float(weight) / float(ingredient.unit_weight)
        fat += float(ingredient.fat) * float(weight) / float(ingredient.unit_weight)
    return calories, protein, carbs, fat

def get_meals_for_date(date, user_id):
    """Get meals for a given date"""
    meals = Meal.query.filter_by(user_id=user_id, date=date).all()
    for meal in meals:
        meal_nutrition = MealNutrition.query.filter_by(meal_id=meal.id).first()
        meal.calories = round(meal_nutrition.calories, 2)
        meal.protein = round(meal_nutrition.protein, 2)
        meal.carbs = round(meal_nutrition.carbs, 2)
        meal.fat = round(meal_nutrition.fat, 2)
    # group by meal name
    meals_grouped = {"total": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}}
    for meal in meals:
        if meal.meal_type not in meals_grouped:
            meals_grouped[meal.meal_type] = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
        meals_grouped[meal.meal_type]["calories"] += meal.calories
        meals_grouped[meal.meal_type]["protein"] += meal.protein
        meals_grouped[meal.meal_type]["carbs"] += meal.carbs
        meals_grouped[meal.meal_type]["fat"] += meal.fat
    meals_grouped["total"]["calories"] = sum(meal["calories"] for meal in meals_grouped.values())
    meals_grouped["total"]["protein"] = sum(meal["protein"] for meal in meals_grouped.values())
    meals_grouped["total"]["carbs"] = sum(meal["carbs"] for meal in meals_grouped.values())
    meals_grouped["total"]["fat"] = sum(meal["fat"] for meal in meals_grouped.values())

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
