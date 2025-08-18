from flask import Blueprint, request, jsonify, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from utils import _png_base64
from agents.workflow import NutritionAssistant
from models import db, Meal, MealNutrition, Ingredient
from datetime import datetime
from dotenv import load_dotenv
import os
import uuid
import json

load_dotenv()

# Initialize the nutrition assistant with LangGraph workflow
nutrition_assistant = NutritionAssistant(
    openai_api_key=os.getenv("OPENAI_API_KEY_COMMON_EXPERIENCE")
)

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
        elif result.get("category") == "web_search" and result.get("nutrition_data"):
            response["nutrition_data"] = result["nutrition_data"]
        
        # Include all ingredients for frontend
        if result.get("ingredients"):
            response["ingredients"] = result["ingredients"]
        
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

@api_bp.route("/log_meal", methods=["POST"])
def log_meal():
    """
    Log a meal with ingredients
    Accepts: JSON { items: [{ingredient_name, grams, ingredient_id?}], notes?, timestamp? }
    """
    data = request.json
    items = data.get('items', [])
    notes = data.get('notes', '')
    timestamp = data.get('timestamp', datetime.utcnow().isoformat())
    
    # Get user session ID
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    user_id = session['user_id']
    
    try:
        # Create meal record
        meal = Meal(
            date=datetime.fromisoformat(timestamp).date(),
            user_id=1,  # TODO: Use actual user ID when auth is implemented
            name=notes or 'Meal',
            ingredients=json.dumps(items),
            meal_type='meal'  # TODO: Determine meal type based on time
        )
        db.session.add(meal)
        db.session.flush()
        
        # Calculate nutrition totals
        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        
        for item in items:
            if item.get('ingredient_id'):
                ingredient = Ingredient.query.get(item['ingredient_id'])
                if ingredient:
                    # Calculate nutrition based on grams
                    factor = item['grams'] / 100.0  # Ingredients are per 100g
                    total_calories += ingredient.calories * factor
                    total_protein += ingredient.protein * factor
                    total_carbs += ingredient.carbs * factor
                    total_fat += ingredient.fat * factor
        
        # Create nutrition record
        nutrition = MealNutrition(
            meal_id=meal.id,
            calories=total_calories,
            protein=total_protein,
            carbs=total_carbs,
            fat=total_fat
        )
        db.session.add(nutrition)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "meal_id": meal.id,
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