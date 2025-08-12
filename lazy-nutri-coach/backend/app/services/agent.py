from typing import List, Dict, Optional
from ..db import models
from ..config import settings
from .rag import search
from .openai_client import client, has_openai

ADVICE_SYS = (
    "You are a careful nutrition coach. Use evidence-based guidance. "
    "Tailor suggestions to the user's history and stated goals. "
    "Return concise, practical steps and meal patterns. Avoid medical claims."
)

RECIPE_SYS = (
    "You are a helpful recipe generator. Respect dietary constraints and ingredients. "
    "Return 2-3 options with ingredients and steps. Keep total time realistic."
)

def _history_macros(logs: List[models.FoodLog]) -> Dict[str, float]:
    c = p = cb = f = 0.0
    for log in logs:
        for it in log.items_json:
            c += it.get("calories", 0)
            p += it.get("protein", 0)
            cb += it.get("carbs", 0)
            f += it.get("fat", 0)
    return {"calories": round(c,1), "protein": round(p,1), "carbs": round(cb,1), "fat": round(f,1)}

def generate_advice(user: models.User, logs: List[models.FoodLog], goals: Optional[models.Goal], focus: Optional[str], horizon_days: int) -> str:
    hist = _history_macros(logs)
    kb_snips = search("nutrition coaching " + (focus or ""))
    context = "\n\n".join([d["text"][:600] for d in kb_snips])
    goal_text = f"Goals: {getattr(goals, 'calories_target', 2000)} kcal, P {getattr(goals, 'protein_target',120)}g, C {getattr(goals, 'carbs_target',250)}g, F {getattr(goals, 'fat_target',70)}g."
    user_text = f"History last {horizon_days}d macros: {hist}. " + goal_text

    if has_openai():
        c = client()
        messages = [
            {"role":"system", "content": ADVICE_SYS},
            {"role":"user", "content": f"Context from KB (not authoritative):\n{context}\n\n{user_text}. Focus: {focus or 'general'}\nReturn a short numbered plan (<=8 bullets) with concrete examples."}
        ]
        resp = c.chat.completions.create(model=settings.openai_model or "gpt-4o-mini", messages=messages, temperature=0.4)
        return resp.choices[0].message.content.strip()
    else:
        # local template fallback
        bullets = [
            "Prioritize lean protein at each meal (e.g., eggs, Greek yogurt, chicken, tofu).",
            "Anchor meals with produce; aim for 1–2 fistfuls of veggies or fruit per meal.",
            "Keep convenient options on hand (pre-cut veg, canned beans, rotisserie chicken).",
            "Pre-commit 1–2 quick dinners that fit targets (e.g., 500 kcal, 30g protein).",
            "Hydrate: ~8–10 cups/day; include a glass with each meal.",
        ]
        if focus and "protein" in focus.lower():
            bullets.insert(0, "Add 20–40g protein to breakfast (Greek yogurt bowl, protein oats, tofu scramble).")
        return "\n".join([f"{i+1}. {b}" for i,b in enumerate(bullets[:7])])

def generate_recipes(dietary: Optional[str], target_calories: Optional[int], time_limit_min: Optional[int], available: Optional[List[str]]):
    prompt = f"Dietary: {dietary or 'none'}; Target kcal: {target_calories or 'flexible'}; Time <= {time_limit_min or 30} min; Have: {', '.join(available or []) or 'pantry staples'}."
    kb_snips = search("healthy quick recipes " + (dietary or ""))
    context = "\n\n".join([d["text"][:600] for d in kb_snips])

    if has_openai():
        c = client()
        messages = [
            {"role":"system", "content": RECIPE_SYS},
            {"role":"user", "content": f"{prompt}\nUse context for inspiration only:\n{context}\nReturn JSON with recipes:[{{name, est_kcal, time_min, ingredients[], steps[]}}]."}
        ]
        resp = c.chat.completions.create(model=settings.openai_model or "gpt-4o-mini", messages=messages, response_format={"type":"json_object"}, temperature=0.5)
        import json
        try:
            data = json.loads(resp.choices[0].message.content)
            return data.get("recipes", [])
        except Exception:
            pass

    # fallback: simple templated recipes
    base = [
        {
            "name": "High-Protein Greek Yogurt Bowl",
            "est_kcal": target_calories or 450,
            "time_min": 5,
            "ingredients": ["Greek yogurt", "berries", "honey", "granola"],
            "steps": ["Add yogurt to bowl", "Top with berries", "Drizzle honey", "Add granola"],
        },
        {
            "name": "Fast Chickpea Salad",
            "est_kcal": target_calories or 500,
            "time_min": 10,
            "ingredients": ["Canned chickpeas", "cucumber", "tomato", "olive oil", "lemon", "salt"],
            "steps": ["Rinse chickpeas", "Chop veg", "Dress with oil + lemon", "Season to taste"],
        },
    ]
    # filter by available
    if available:
        keep = []
        for r in base:
            if all(any(a.lower() in ing.lower() for ing in r["ingredients"]) for a in available):
                keep.append(r)
        if keep:
            base = keep
    return base[:3]
