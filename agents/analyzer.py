from typing import Dict, Any, List
from openai import OpenAI
from .base import BaseAgent, ChatMessage
import json
from utils import _png_base64, _load_ingredient_index, _fuzzy_match, ParsedItem, _norm
from prompts import STRUCTURE_SPEC, NUTRITION_CARD_SPEC
from models import Ingredient, db
from sqlalchemy import func

class AnalyzerAgent(BaseAgent):
    """Agent for analyzing meal content from text/images"""
    
    def __init__(self, openai_api_key: str):
        super().__init__("analyzer", openai_api_key)
        self.client = OpenAI(api_key=openai_api_key)
        self.parser_model = "gpt-4o-mini"
        self.nutrition_model = "gpt-4o-mini"
    
    def parse_meal_content(self, user_text: str = None, image_data: str = None) -> Dict[str, Any]:
        """Parse meal content from text and/or image"""
        
        user_content = []
        if user_text:
            user_content.append({"type": "text", "text": user_text})
        if image_data:
            user_content.append({"type": "image_url", "image_url": {"url": image_data}})
        
        messages = [
            {"role": "system", "content": [
                {"type": "text", "text": "You are a nutrition parser that extracts ingredients and weights."},
                {"type": "text", "text": STRUCTURE_SPEC}
            ]},
            {"role": "user", "content": user_content},
        ]
        
        try:
            resp = self.client.chat.completions.create(
                model=self.parser_model,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            parsed_result = json.loads(raw)
            
            # Debug logging
            print(f"Analyzer parsed result: {parsed_result}")
            
            return parsed_result
        except Exception as e:
            print(f"Error parsing meal content: {e}")
            import traceback
            traceback.print_exc()
            return {"reply_html": f"<p>Parser error: {e}</p>", "items": []}
    
    def create_nutrition_card(self, ingredient_name: str) -> Dict[str, Any]:
        """Create nutrition card for unknown ingredient"""
        
        nutri_system = f"You create compact nutrition cards.\n{NUTRITION_CARD_SPEC}"
        
        try:
            resp = self.client.chat.completions.create(
                model=self.nutrition_model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": [{"type": "text", "text": nutri_system}]},
                    {"role": "user", "content": [{"type": "text", "text": f"Create card for: {ingredient_name}"}]},
                ],
            )
            card = json.loads(resp.choices[0].message.content)
            
            # Validate card
            if "per_100g" in card and all(k in card["per_100g"] for k in ("calories", "protein", "carbs", "fat")):
                return card
            else:
                print(f"Invalid nutrition card for {ingredient_name} - missing required fields")
                return None
                
        except Exception as e:
            print(f"Failed to get nutrition card for {ingredient_name}: {e}")
            return None
    
    def process_ingredients(self, raw_items: List[Dict]) -> tuple[List[ParsedItem], List[str]]:
        """Process parsed ingredients and identify unknowns"""
        
        try:
            names, ids = _load_ingredient_index()
        except Exception as e:
            print(f"Error loading ingredient index: {e}")
            names, ids = [], []
        
        items: List[ParsedItem] = []
        unknown_names = []
        
        for it in raw_items:
            name = (it.get("ingredient_name") or "").strip()
            grams = float(it.get("grams") or 0)
            if not name or grams <= 0:
                continue
            
            ingredient_id = None
            if names and ids:
                ingredient_id = _fuzzy_match(name, names, ids, cutoff=95)
            
            if ingredient_id is None:
                unknown_names.append(name)
            
            items.append(ParsedItem(
                ingredient_name=name, 
                grams=grams, 
                ingredient_id=ingredient_id
            ))
        
        return items, unknown_names
    
    def create_new_ingredients(self, unknown_names: List[str]) -> Dict[str, int]:
        """Create new ingredients in database"""
        
        new_cards = {}
        for name in unknown_names:
            card = self.create_nutrition_card(name)
            if card:
                new_cards[name] = card
        
        created_ids = {}
        
        try:
            for uname, card in new_cards.items():
                per = card.get("per_100g", {})
                try:
                    cal = float(per["calories"])
                    pro = float(per["protein"])
                    carb = float(per["carbs"])
                    fat = float(per["fat"])
                except Exception as e:
                    print(f"Failed to parse nutrition values for {uname}: {e}")
                    continue
                
                key = _norm(uname)
                
                # Check if ingredient already exists
                existing = (
                    db.session.query(Ingredient)
                    .filter(func.lower(Ingredient.name) == uname.lower())
                    .first()
                )
                
                if existing:
                    created_ids[key] = existing.id
                    continue
                
                # Create new ingredient
                ing = Ingredient(
                    name=uname,
                    calories=cal,
                    protein=pro,
                    carbs=carb,
                    fat=fat,
                    unit_weight=100,
                )
                db.session.add(ing)
                db.session.flush()
                created_ids[key] = ing.id
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            print(f"Create-commit failed: {e}")
            raise
        
        db.session.expire_all()
        return created_ids
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process meal analysis request"""
        
        user_input = state.get("user_input", "")
        image_data = state.get("image_data")
        user_id = state.get("user_id", "default")
        
        print(f"Analyzer processing: user_input='{user_input[:50]}...', has_image={bool(image_data)}")
        
        # Parse meal content
        parsed = self.parse_meal_content(user_input, image_data)
        # Add debug label to analyzer's response
        assistant_html = "<p style='color: red; font-weight: bold;'>[ANALYZER]</p>" + parsed.get("reply_html", "<p>Parsed.</p>")
        raw_items = parsed.get("items", [])
        
        print(f"Analyzer got {len(raw_items)} raw items from parsing")
        
        # Process ingredients
        items, unknown_names = self.process_ingredients(raw_items)
        
        print(f"Processed into {len(items)} items, {len(unknown_names)} unknown")
        
        # Create new ingredients if needed
        created_ids = {}
        if unknown_names:
            created_ids = self.create_new_ingredients(unknown_names)
        
        # Build response items
        try:
            all_ingredients = Ingredient.query.all()
        except Exception as e:
            print(f"Error querying ingredients: {e}")
            all_ingredients = []
        
        out = []
        
        for it in items:
            d = {
                "ingredient_name": it.ingredient_name,
                "grams": it.grams
            }
            
            if it.ingredient_id is not None:
                d["ingredient_id"] = it.ingredient_id
            else:
                new_id = created_ids.get(_norm(it.ingredient_name))
                if new_id is None:
                    rec = Ingredient.query.filter(
                        func.lower(Ingredient.name) == it.ingredient_name.lower()
                    ).first()
                    new_id = rec.id if rec else None
                d["ingredient_id"] = new_id
            
            out.append(d)
        
        # Update state
        response_data = {
            "reply_html": assistant_html,
            "items": out,
            "ingredients": [{"id": ing.id, "name": ing.name} for ing in all_ingredients]
        }
        
        print(f"Analyzer returning {len(out)} items in response")
        state["response"] = response_data
        
        return state