from flask import Blueprint, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from utils import _png_base64, _load_ingredient_index, _fuzzy_match, ParsedItem, _norm
from prompts import STRUCTURE_SPEC, NUTRITION_CARD_SPEC
import json
from typing import List
from dataclasses import asdict
from openai import OpenAI
from dotenv import load_dotenv
import os
from models import Ingredient, db
from sqlalchemy import func

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY_COMMON_EXPERIENCE"))
OPENAI_MODEL_PARSER = "gpt-4o-mini"
OPENAI_MODEL_NUTRITION = "gpt-4o-mini"

api_bp = Blueprint('api', __name__)

limiter = Limiter(
    get_remote_address,
    default_limits=["10 per minute"]
)

@limiter.limit("1 per minute")
@api_bp.route("/ai_chat", methods=["POST"])
def ai_chat():
    """
    Accepts: form-data { message?: str, image?: file, thread_id?: str }
    Returns: { reply_html, items: [{ingredient_id|None, ingredient_name, grams, new_ingredient?}] }
    """
    user_text = (request.form.get("message") or "").strip()
    file = request.files.get("image")

    if not user_text and not file:
        return jsonify({"reply_html": "<p>Please send a message or a photo.</p>", "items": []})

    # Build chat messages (text + optional image) for GPT-4o
    user_content = []
    if user_text:
        user_content.append({"type": "text", "text": user_text})
    if file:
        # Data URL for local file
        data_url = _png_base64(file)
        user_content.append({"type": "image_url", "image_url": {"url": data_url}})


    messages = [
        {"role": "system", "content": [
            {"type": "text", "text": "You are a nutrition parser that extracts ingredients and weights."},
            {"type": "text", "text": STRUCTURE_SPEC}
        ]},
        {"role": "user", "content": user_content},
    ]

    # Ask model to return strict JSON (use response_format)
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL_PARSER,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
    except Exception as e:
        # Fallback: plain text error
        return jsonify({"reply_html": f"<p>Parser error: {e}</p>", "items": []}), 500

    # Parse LLM JSON
    try:
        parsed = json.loads(raw)
        assistant_html = parsed.get("assistant_html") or "<p>Parsed.</p>"
        raw_items = parsed.get("items") or []
    except Exception:
        assistant_html = "<p>Parsed, but the response wasn't valid JSON. Please adjust and resend.</p>"
        raw_items = []

    # Fuzzy map to DB, collect unknowns
    names, ids = _load_ingredient_index()
    items: List[ParsedItem] = []
    unknown_names = []

    for it in raw_items:
        name = (it.get("ingredient_name") or "").strip()
        grams = float(it.get("grams") or 0)
        if not name or grams <= 0:
            continue
        ingredient_id = _fuzzy_match(name, names, ids, cutoff=88)
        if ingredient_id is None:
            unknown_names.append(name)
        items.append(ParsedItem(ingredient_name=name, grams=grams, ingredient_id=ingredient_id))

    # For new ingredients, ask LLM for 100g nutrition card
    new_cards = {}
    if unknown_names:
        print(f"AI needs to create nutrition cards for: {unknown_names}")
        nutri_system = f"You create compact nutrition cards.\n{NUTRITION_CARD_SPEC}"
        # One-shot per unknown (keeps it simple; you could batch with a single prompt too)
        for uname in unknown_names:
            try:
                nr = client.chat.completions.create(
                    model=OPENAI_MODEL_NUTRITION,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": [{"type": "text", "text": nutri_system}]},
                        {"role": "user", "content": [{"type": "text", "text": f"Create card for: {uname}"}]},
                    ],
                )
                card = json.loads(nr.choices[0].message.content)
                print(f"AI generated nutrition card for {uname}: {card}")
                # basic sanity
                if "per_100g" in card and all(k in card["per_100g"] for k in ("calories", "protein", "carbs", "fat")):
                    new_cards[uname] = card
                    print(f"✅ Valid nutrition card for {uname}")
                else:
                    print(f"❌ Invalid nutrition card for {uname} - missing required fields")
            except Exception as e:
                print(f"❌ Failed to get nutrition card for {uname}: {e}")
                # ignore individual failures
                pass

    created_ids = {}  # normalized name -> id
    created_rows = []

    try:
        # Stage inserts with flush (one transaction)
        for uname, card in new_cards.items():
            per = (card.get("per_100g") or {})
            try:
                cal = float(per["calories"]); pro = float(per["protein"])
                carb = float(per["carbs"]);   fat = float(per["fat"])
            except Exception as e:
                print(f"Failed to parse nutrition values for {uname}: {e}")
                continue

            key = _norm(uname)

            # case-insensitive de-dupe
            existing = (
                db.session.query(Ingredient)
                .filter(func.lower(Ingredient.name) == uname.lower())
                .first()
            )
            if existing:
                print(f"Ingredient {uname} already exists with ID {existing.id}")
                created_ids[key] = existing.id
                created_rows.append(existing)
                continue

            print(f"Creating new ingredient: {uname} - cal:{cal}, pro:{pro}, carb:{carb}, fat:{fat}")
            ing = Ingredient(
                name=uname,
                calories=cal,      # adjust field names if your model uses calories_100g, etc.
                protein=pro,
                carbs=carb,
                fat=fat,
                unit_weight=100,   # remove if your model doesn't have this column
            )
            db.session.add(ing)
            db.session.flush()     # <-- assigns ing.id without committing
            created_ids[key] = ing.id
            created_rows.append(ing)
            print(f"Successfully created ingredient {uname} with ID {ing.id}")

        db.session.commit()         # one commit
        print(f"Committed {len(created_rows)} new ingredients to database")
    except Exception as e:
        db.session.rollback()
        print("Create-commit failed:", repr(e))
        print(f"Error details: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

    db.session.expire_all()

    # --- Build response items using created_ids (no fragile re-query) ---
    all_ingredients = Ingredient.query.all()

    out = []
    for it in items:
        d = {
            "ingredient_name": it.ingredient_name,
            "grams": it.grams
        }
        if it.ingredient_id is not None:
            d["ingredient_id"] = it.ingredient_id
        else:
            # prefer the ID we just created
            new_id = created_ids.get(_norm(it.ingredient_name))
            if new_id is None:
                # last-resort lookup, with guard
                rec = Ingredient.query.filter(func.lower(Ingredient.name) == it.ingredient_name.lower()).first()
                new_id = rec.id if rec else None
            d["ingredient_id"] = new_id
        out.append(d)

    return jsonify({"reply_html": assistant_html, "items": out, "ingredients": [{"id": ingredient.id, "name": ingredient.name} for ingredient in all_ingredients]})