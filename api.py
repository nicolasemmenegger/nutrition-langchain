from flask import Blueprint, request, jsonify, session, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from utils import _png_base64, calculate_meal_nutrition
from agents.workflow import NutritionAssistant
from agents.advice import AdviceAgent
from models import db, Meal, MealNutrition, Ingredient, IngredientUsage, ChatHistory, SavedRecipe, DailyAdvice
from datetime import datetime
from dotenv import load_dotenv
import os
import threading
import uuid
import json
import io

load_dotenv()

# Initialize the nutrition assistant with LangGraph workflow
nutrition_assistant = NutritionAssistant(
    openai_api_key=os.getenv("OPENAI_API_KEY_COMMON_EXPERIENCE")
)
advice_agent = AdviceAgent(
    openai_api_key=os.getenv("OPENAI_API_KEY_COMMON_EXPERIENCE") or os.getenv("OPENAI_API_KEY")
)

api_bp = Blueprint('api', __name__)

limiter = Limiter(
    get_remote_address,
    default_limits=["10 per minute"]
)

@limiter.limit("30 per minute")
@api_bp.route("/ai_chat", methods=["POST"])
def ai_chat():
    """
    Accepts: form-data { message?: str, image?: file, thread_id?: str }
    Returns: { reply_html, items: [{ingredient_id|None, ingredient_name, grams, new_ingredient?}], category?: str }
    
    Now uses LangGraph workflow with multiple specialized agents
    """
    user_text = (request.form.get("message") or "").strip()
    file = request.files.get("image")
    
    # Get or create user session ID for chat history
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    user_id = session['user_id']
    
    if not user_text and not file:
        return jsonify({"reply_html": "<p>Please send a message or a photo.</p>", "items": []})
    
    # Prepare image data if present
    image_data = None
    if file:
        image_data = _png_base64(file)
    
    try:
        # Process request through the LangGraph workflow
        result = nutrition_assistant.process_request(
            user_input=user_text,
            user_id=user_id,
            image_data=image_data
        )
        
        if not result.get("success"):
            return jsonify({
                "reply_html": result.get("reply_html", "<p>An error occurred processing your request.</p>"),
                "items": [],
                "error": result.get("error")
            }), 500
        
        # Extract response based on category
        response = {
            "reply_html": result.get("reply_html", "<p>Request processed.</p>"),
            "items": result.get("items", []),
            "category": result.get("category")
        }
        
        # Add additional data based on agent type
        if result.get("category") == "recipe_generation" and result.get("recipe"):
            response["recipe"] = result["recipe"]
        elif result.get("category") == "coaching" and result.get("coaching_data"):
            response["coaching_data"] = result["coaching_data"]
        
        # Include all ingredients for frontend
        if result.get("ingredients"):
            response["ingredients"] = result["ingredients"]
        
        # Include side panel data if present
        if result.get("side_panel_data"):
            response["side_panel_data"] = result["side_panel_data"]
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in ai_chat endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "reply_html": f"<p>System error: {str(e)}</p>",
            "items": [],
            "error": str(e)
        }), 500


@api_bp.route("/chat_history", methods=["GET"])
def get_chat_history():
    """Return recent chat history for the current session user."""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    user_id = session['user_id']

    try:
        records = ChatHistory.get_user_history(str(user_id), limit=50)
        # Return as a simple array of {role, content, name}
        messages = []
        for rec in reversed(records):
            msg = {
                "role": rec.role,
                "content": rec.content,
                "category": rec.category,
            }
            # Extract name from metadata if present
            if rec.message_metadata:
                try:
                    metadata = json.loads(rec.message_metadata)
                    if metadata.get("name"):
                        msg["name"] = metadata["name"]
                except:
                    pass
            messages.append(msg)
        return jsonify({"messages": messages})
    except Exception as e:
        return jsonify({"messages": [], "error": str(e)}), 500


@api_bp.route("/chat_history", methods=["DELETE"])
def clear_chat_history():
    """Clear chat history for the current session user."""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    user_id = session['user_id']

    try:
        ChatHistory.clear_user_history(str(user_id))
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/log_meal", methods=["POST"])
def log_meal():
    """
    Log a meal with ingredients
    Accepts: JSON { items: [{ingredient_name, grams, ingredient_id?}], notes?, timestamp? }
    """
    data = request.json
    items = data.get('items', [])
    notes = data.get('notes', '')
    requested_meal_type = (data.get('meal_type') or '').strip().lower()
    timestamp = data.get('timestamp', datetime.utcnow().isoformat())
    specified_date_str = (data.get('date') or '').strip()
    
    # Require an authenticated user (session user_id must be an integer)
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    try:
        user_id = int(session['user_id'])
    except Exception:
        return jsonify({"success": False, "error": "Invalid session user"}), 401
    
    try:
        # Parse timestamp robustly
        try:
            ts = (timestamp or '').strip()
            if ts.endswith('Z'):
                ts = ts.replace('Z', '+00:00')
            dt = datetime.fromisoformat(ts)
        except Exception:
            dt = datetime.utcnow()

        # Use specified date if provided and valid (YYYY-MM-DD), else from timestamp
        if specified_date_str:
            try:
                meal_date = datetime.fromisoformat(specified_date_str).date()
            except Exception:
                try:
                    meal_date = datetime.strptime(specified_date_str, '%Y-%m-%d').date()
                except Exception:
                    meal_date = dt.date()
        else:
            meal_date = dt.date()
        hour = dt.hour
        # Choose based on user selection if valid; otherwise infer from time
        valid_types = {'breakfast','lunch','dinner','snack','other'}
        if requested_meal_type in valid_types:
            meal_type = requested_meal_type
        else:
            if hour < 11:
                meal_type = 'breakfast'
            elif hour < 15:
                meal_type = 'lunch'
            elif hour < 21:
                meal_type = 'dinner'
            else:
                meal_type = 'snack'

        # Resolve ingredient ids and weights
        ingredient_ids = []
        ingredient_weights = []
        stored_items = []
        for item in items:
            grams = float(item.get('grams') or 0) or 0.0
            ing_id = item.get('ingredient_id')
            if not ing_id and item.get('ingredient_name'):
                ing = Ingredient.query.filter(Ingredient.name.ilike(item['ingredient_name'])).first()
                if ing:
                    ing_id = ing.id
            if ing_id:
                ingredient_ids.append(int(ing_id))
                ingredient_weights.append(float(grams))
                stored_items.append({"ingredient_id": int(ing_id), "weight": float(grams)})

        # Determine meal name
        meal_name = (notes or '').strip()
        if not meal_name:
            meal_name = (items[0].get('ingredient_name') if items else 'Meal') or 'Meal'
        if meal_name.lower().startswith('recipe:'):
            meal_name = meal_name.split(':', 1)[1].strip() or meal_name

        # Create meal record
        meal = Meal(
            date=meal_date,
            user_id=user_id,
            name=meal_name,
            ingredients=(stored_items or items),
            meal_type=meal_type
        )
        db.session.add(meal)
        db.session.flush()

        # Compute nutrition totals using the same util as manual entry
        total_calories, total_protein, total_carbs, total_fat = 0.0, 0.0, 0.0, 0.0
        if ingredient_ids and ingredient_weights:
            total_calories, total_protein, total_carbs, total_fat = calculate_meal_nutrition(ingredient_ids, ingredient_weights)
        else:
            # Fallback: if items include per_100g nutrition, compute from that
            for it in items:
                grams = float(it.get('grams') or 0) or 0.0
                n = it.get('nutrition') or it.get('per_100g')
                if not n or grams <= 0:
                    continue
                try:
                    total_calories += float(n.get('calories') or 0) * grams / 100.0
                    total_protein += float(n.get('protein') or 0) * grams / 100.0
                    total_carbs += float(n.get('carbs') or 0) * grams / 100.0
                    total_fat += float(n.get('fat') or 0) * grams / 100.0
                except Exception:
                    continue

        nutrition = MealNutrition(
            meal_id=meal.id,
            calories=total_calories,
            protein=total_protein,
            carbs=total_carbs,
            fat=total_fat
        )
        db.session.add(nutrition)

        # Track ingredient usage
        for ing_id, grams in zip(ingredient_ids, ingredient_weights):
            usage = IngredientUsage.query.filter_by(ingredient_id=ing_id, user_id=user_id).first()
            if usage:
                usage.quantity += grams
            else:
                db.session.add(IngredientUsage(ingredient_id=ing_id, user_id=user_id, quantity=grams))

        db.session.commit()

        return jsonify({
            "success": True,
            "meal_id": meal.id,
            "meal_type": meal_type,
            "meal_name": meal_name,
            "nutrition": {
                "calories": round(total_calories, 1),
                "protein": round(total_protein, 1),
                "carbs": round(total_carbs, 1),
                "fat": round(total_fat, 1)
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error logging meal: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
@api_bp.route('/transcribe_audio', methods=['POST'])
def transcribe_audio():
    """
    Accepts: multipart/form-data with field 'audio' (audio/webm or audio/ogg)
    Uses OpenAI GPT-4o-mini Transcribe to produce text.
    Returns: { text }
    """
    try:
        file = request.files.get('audio')
        if not file:
            return jsonify({"error": "No audio file provided"}), 400

        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY_COMMON_EXPERIENCE') or os.getenv('OPENAI_API_KEY'))

        # Read file content into memory
        audio_bytes = file.read()
        file.seek(0)

        # Create a transient upload for transcription
        # Using the unified audio.transcriptions.create with model 'gpt-4o-mini-transcribe'
        result = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=(file.filename or "audio.webm", io.BytesIO(audio_bytes))
        )

        text = result.text if hasattr(result, 'text') else (result.get('text') if isinstance(result, dict) else None)
        if not text:
            # Some SDKs return {text: ...} directly
            text = getattr(result, 'text', None) or ''

        return jsonify({"text": text or ""})
    except Exception as e:
        print("transcribe_audio error:", str(e))
        return jsonify({"error": str(e)}), 500


@api_bp.route('/recipes', methods=['GET'])
def list_recipes():
    if 'user_id' not in session:
        return jsonify({"recipes": []})
    try:
        user_id = int(session['user_id'])
    except Exception:
        return jsonify({"recipes": []})
    rows = SavedRecipe.query.filter_by(user_id=user_id).order_by(SavedRecipe.created_at.desc()).all()
    def _r(r):
        return {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "ingredients": r.ingredients,
            "instructions": r.instructions,
            "nutrition_per_serving": r.nutrition_per_serving,
            "servings": r.servings,
            "prep_time": r.prep_time,
            "cook_time": r.cook_time,
            "image_url": r.image_url,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
    return jsonify({"recipes": [_r(r) for r in rows]})


@api_bp.route('/recipes', methods=['POST'])
def save_recipe():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    try:
        user_id = int(session['user_id'])
    except Exception:
        return jsonify({"success": False, "error": "Invalid session user"}), 401

    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"success": False, "error": "Missing recipe name"}), 400
    recipe = SavedRecipe(
        user_id=user_id,
        name=name,
        description=data.get('description'),
        ingredients=data.get('ingredients'),
        instructions=data.get('instructions'),
        nutrition_per_serving=data.get('nutrition_per_serving'),
        servings=data.get('servings'),
        prep_time=data.get('prep_time'),
        cook_time=data.get('cook_time'),
        image_url=data.get('image_url')
    )
    db.session.add(recipe)
    db.session.commit()
    # If no image was provided, generate one asynchronously
    try:
        if not data.get('image_url'):
            app = current_app._get_current_object()
            threading.Thread(
                target=_generate_recipe_image_async,
                args=(recipe.id, recipe.name, app),
                daemon=True
            ).start()
    except Exception as _bg_e:
        # Non-fatal; proceed without blocking the response
        print('Failed to start background image generation:', str(_bg_e))
    return jsonify({"success": True, "id": recipe.id})


def _generate_recipe_image_async(recipe_id: int, recipe_name: str, app):
    """Background task to generate a recipe image and update the DB when ready."""
    try:
        from openai import OpenAI
        img_api_key = os.getenv("OPENAI_API_KEY_IMAGE") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY_COMMON_EXPERIENCE")
        if not img_api_key:
            return
        client = OpenAI(api_key=img_api_key)
        prompt = (
            f"Professional food photography of: {recipe_name or 'a healthy dish'}. "
            "Uncropped, full plate in frame with ample margins; do not crop edges. "
            "Top-down or 45-degree angle, natural lighting, vibrant colors, appetizing presentation."
        )
        img = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
            n=1,
        )
        image_url = None
        try:
            if hasattr(img, 'data') and img.data:
                if getattr(img.data[0], 'b64_json', None):
                    image_url = f"data:image/png;base64,{img.data[0].b64_json}"
                elif getattr(img.data[0], 'url', None):
                    image_url = img.data[0].url
        except Exception:
            image_url = None
        if not image_url:
            return
        # Update DB record under application context
        with app.app_context():
            row = SavedRecipe.query.get(int(recipe_id))
            if row and not getattr(row, 'image_url', None):
                row.image_url = image_url
                db.session.commit()
    except Exception as e:
        try:
            print(f"Background recipe image generation failed for {recipe_id}: {e}")
        except Exception:
            pass


@api_bp.route('/advice/today', methods=['GET'])
def get_today_advice():
    if 'user_id' not in session:
        return jsonify({"advice": None})
    try:
        user_id = int(session['user_id'])
    except Exception:
        return jsonify({"advice": None})
    # Optional date query param (YYYY-MM-DD); default: today
    date_str = (request.args.get('date') or '').strip()
    try:
        target_date = datetime.fromisoformat(date_str).date() if date_str else datetime.utcnow().date()
    except Exception:
        target_date = datetime.utcnow().date()
    row = db.session.query(DailyAdvice).filter_by(user_id=user_id, date=target_date).first()
    return jsonify({"advice": row.advice if row else None})


@api_bp.route('/advice/today', methods=['POST'])
def regenerate_today_advice():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    try:
        user_id = int(session['user_id'])
    except Exception:
        return jsonify({"success": False, "error": "Invalid session user"}), 401
    body = request.json or {}
    date_str = (body.get('date') or '').strip()
    try:
        target_date = datetime.fromisoformat(date_str).date() if date_str else datetime.utcnow().date()
    except Exception:
        target_date = datetime.utcnow().date()
    row = advice_agent.upsert_tip_for_date(user_id, target_date)
    return jsonify({"success": True, "advice": row.advice})


@api_bp.route("/compute_nutrition", methods=["POST"])
def compute_nutrition():
    """
    Compute aggregated nutrition for a list of items.
    Accepts JSON: { items: [{ingredient_id?|ingredient_name?, grams}] }
    Returns: { calories, protein, carbs, fat, resolved: n }
    """
    try:
        data = request.json or {}
        items = data.get("items", [])
        if not isinstance(items, list):
            return jsonify({"error": "items must be a list"}), 400

        ingredient_ids = []
        ingredient_weights = []

        for item in items:
            grams = float(item.get("grams") or 0) or 0.0
            if grams <= 0:
                continue
            ing_id = item.get("ingredient_id")
            if not ing_id and item.get("ingredient_name"):
                ing = Ingredient.query.filter(Ingredient.name.ilike(item["ingredient_name"])).first()
                if ing:
                    ing_id = ing.id
            if ing_id:
                ingredient_ids.append(int(ing_id))
                ingredient_weights.append(float(grams))

        calories, protein, carbs, fat = 0.0, 0.0, 0.0, 0.0
        if ingredient_ids and ingredient_weights:
            calories, protein, carbs, fat = calculate_meal_nutrition(ingredient_ids, ingredient_weights)

        return jsonify({
            "calories": round(calories, 2),
            "protein": round(protein, 2),
            "carbs": round(carbs, 2),
            "fat": round(fat, 2),
            "resolved": len(ingredient_ids)
        })
    except Exception as e:
        print("compute_nutrition error:", str(e))
        return jsonify({"error": str(e)}), 500