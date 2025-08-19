from typing import Dict, Any, List
from openai import OpenAI
from .base import BaseAgent, ChatMessage
import json
import os
from datetime import datetime


MAX_NUM_MESSAGES_RECIPE_GENERATOR = 3

class RecipeGenerationAgent(BaseAgent):
    """Agent for generating healthy recipe suggestions"""
    
    def __init__(self, openai_api_key: str):
        super().__init__("recipe_generation", openai_api_key)
        self.client = OpenAI(api_key=openai_api_key)
    
    def analyze_dietary_preferences(self, chat_history: List[ChatMessage]) -> Dict[str, Any]:
        """Analyze chat history to understand dietary preferences"""
        
        preferences = {
            "restrictions": [],
            "preferred_cuisines": [],
            "common_ingredients": [],
            "meal_types": []
        }
        
        if not chat_history:
            return preferences
        
        # Analyze recent history for patterns
        recent_meals = []
        for msg in chat_history[-20:]:  # Last 20 messages
            if msg.metadata and "items" in msg.metadata:
                items = msg.metadata["items"]
                for item in items:
                    if "ingredient_name" in item:
                        recent_meals.append(item["ingredient_name"])
        
        preferences["common_ingredients"] = list(set(recent_meals))[:10]
        
        return preferences
    
    def generate_recipe(self, user_request: str, preferences: Dict[str, Any], nutritional_goals: Dict[str, Any] = None, chat_history: List[ChatMessage] = None) -> Dict[str, Any]:
        """Generate a recipe based on user request and preferences"""
        
        # Build messages with recent chat history as actual turns
        history_messages = []
        if chat_history:
            # Use the most recent few messages to preserve context
            import re
            tag_re = re.compile(r"<[^>]+>")
            for msg in chat_history:
                # Strip HTML tags to reduce noise
                cleaned = tag_re.sub("", (msg.content or ""))[:10000]
                msg_dict = {
                    "role": msg.role,
                    "content": cleaned
                }
                # Add name for assistant messages
                if msg.role == "assistant" and msg.name:
                    msg_dict["name"] = msg.name
                history_messages.append(msg_dict)
        
        # Build context from preferences
        context_parts = []
        if preferences.get("common_ingredients"):
            context_parts.append(f"User commonly eats: {', '.join(preferences['common_ingredients'][:5])}")
        if preferences.get("restrictions"):
            context_parts.append(f"Dietary restrictions: {', '.join(preferences['restrictions'])}")
        if nutritional_goals:
            context_parts.append(f"Nutritional goals: {json.dumps(nutritional_goals)}")
        
        context = "\n".join(context_parts) if context_parts else "No specific preferences identified."
        
        messages = [
            {"role": "system", "content": f"""
                You are a professional nutritionist and chef who creates healthy, balanced recipes.
                
                User context:
                {context}
                
                IMPORTANT: The user has made a specific request. You MUST generate a recipe that directly addresses their request.
                
                Generate a recipe that:
                1. MATCHES the user's specific request
                2. Is nutritionally balanced
                3. Is easy to prepare (under 45 minutes)
                4. Uses readily available ingredients
                5. Includes detailed nutritional information
                
                Return a JSON object with:
                {{
                    "recipe_name": "name of the dish",
                    "description": "brief description",
                    "prep_time": "minutes",
                    "cook_time": "minutes",
                    "servings": number,
                    "ingredients": [
                        {{"name": "ingredient", "amount": "quantity with unit", "grams": estimated_grams}}
                    ],
                    "instructions": ["step 1", "step 2", ...],
                    "nutrition_per_serving": {{
                        "calories": number,
                        "protein": number,
                        "carbs": number,
                        "fat": number,
                        "fiber": number
                    }},
                    "tags": ["healthy", "quick", etc],
                    "tips": "cooking tips or variations"
                }}
            """},
        ] + list(reversed(history_messages)) + [
            {"role": "user", "content": f"Generate a recipe for: {user_request}\n\nREMEMBER: The recipe MUST match this specific request."}
        ]
        
        try:
            # Log the request to a timestamped file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"logs/recipe_generation_{timestamp}.log"
            os.makedirs("logs", exist_ok=True)
            with open(log_filename, 'w') as f:
                f.write(json.dumps(messages, indent=2))

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            
            recipe_result = json.loads(response.choices[0].message.content)
            
            # Log the response to a timestamped file
            response_log_filename = f"logs/recipe_generation_response_{timestamp}.log"
            with open(response_log_filename, 'w') as f:
                f.write(json.dumps({
                    "response": recipe_result,
                    "model": "gpt-4o-mini",
                    "timestamp": timestamp
                }, indent=2))
            
            return recipe_result
            
        except Exception as e:
            print(f"Error generating recipe: {e}")
            return {
                "error": str(e),
                "recipe_name": "Recipe Generation Failed"
            }
    
    def format_recipe_plain_text(self, recipe: Dict[str, Any]) -> str:
        """Format recipe into plain text for chat history"""
        
        if "error" in recipe:
            return "Sorry, I couldn't generate a recipe right now. Please try again."
        
        lines = []
        lines.append(f"Here's a recipe for {recipe.get('recipe_name', 'your requested dish')}:")
        lines.append(f"{recipe.get('description', '')}")
        lines.append("")
        lines.append(f"Prep time: {recipe.get('prep_time', 'N/A')} minutes")
        lines.append(f"Cook time: {recipe.get('cook_time', 'N/A')} minutes")
        lines.append(f"Servings: {recipe.get('servings', 'N/A')}")
        lines.append("")
        lines.append("Ingredients:")
        for ing in recipe.get("ingredients", []):
            lines.append(f"- {ing['amount']} {ing['name']}")
        lines.append("")
        lines.append("Instructions:")
        for i, step in enumerate(recipe.get("instructions", []), 1):
            lines.append(f"{i}. {step}")
        lines.append("")
        
        nutrition = recipe.get("nutrition_per_serving", {})
        if nutrition:
            lines.append("Nutrition per serving:")
            lines.append(f"- Calories: {nutrition.get('calories', 'N/A')}")
            lines.append(f"- Protein: {nutrition.get('protein', 'N/A')}g")
            lines.append(f"- Carbs: {nutrition.get('carbs', 'N/A')}g")
            lines.append(f"- Fat: {nutrition.get('fat', 'N/A')}g")
            lines.append(f"- Fiber: {nutrition.get('fiber', 'N/A')}g")
        
        if recipe.get("tips"):
            lines.append("")
            lines.append(f"Tips: {recipe.get('tips')}")
        
        return "\n".join(lines)
    
    def format_recipe_response(self, recipe: Dict[str, Any]) -> str:
        """Format recipe into HTML response"""
        
        debug_label = "<p style='color: red; font-weight: bold;'>[RECIPE GENERATION]</p>"
        
        if "error" in recipe:
            return debug_label + f"<p>Sorry, I couldn't generate a recipe right now. Please try again.</p>"
        
        ingredients_html = "\n".join([
            f"<li>{ing['amount']} {ing['name']}</li>"
            for ing in recipe.get("ingredients", [])
        ])
        
        instructions_html = "\n".join([
            f"<li>{step}</li>"
            for step in recipe.get("instructions", [])
        ])
        
        nutrition = recipe.get("nutrition_per_serving", {})
        tags = ", ".join(recipe.get("tags", []))
        
        html = debug_label + f"""
        <div class="recipe-card">
            <h2>{recipe.get('recipe_name', 'Unnamed Recipe')}</h2>
            <p class="description">{recipe.get('description', '')}</p>
            
            <div class="recipe-meta">
                <span>⏱️ Prep: {recipe.get('prep_time', 'N/A')} min</span>
                <span>🍳 Cook: {recipe.get('cook_time', 'N/A')} min</span>
                <span>🍽️ Servings: {recipe.get('servings', 'N/A')}</span>
            </div>
            
            <h3>Ingredients:</h3>
            <ul class="ingredients-list">
                {ingredients_html}
            </ul>
            
            <h3>Instructions:</h3>
            <ol class="instructions-list">
                {instructions_html}
            </ol>
            
            <h3>Nutrition per serving:</h3>
            <div class="nutrition-info">
                <span>Calories: {nutrition.get('calories', 'N/A')}</span>
                <span>Protein: {nutrition.get('protein', 'N/A')}g</span>
                <span>Carbs: {nutrition.get('carbs', 'N/A')}g</span>
                <span>Fat: {nutrition.get('fat', 'N/A')}g</span>
                <span>Fiber: {nutrition.get('fiber', 'N/A')}g</span>
            </div>
            
            {f'<p class="tips"><strong>Tips:</strong> {recipe.get("tips", "")}</p>' if recipe.get("tips") else ''}
            
            <p class="tags"><small>Tags: {tags}</small></p>
        </div>
        """
        
        return html
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process recipe generation request"""
        
        user_input = state.get("user_input", "")
        user_id = state.get("user_id", "default")

        print(f"Recipe agent processing request: '{user_input}'")
        
        # Save the user message - the conversation agent won't save it since we'll pass an assistant_response
        print(f"Recipe agent saving user message to chat history")
        self.save_chat_message(
            user_id,
            ChatMessage(
                role="user",
                content=user_input,
                metadata={"category": "recipe_generation"},
                category="recipe_generation"
            )
        )
        print(f"Recipe agent successfully saved user message")
        
        # Get fresh chat history that includes the just-saved user message
        chat_history = self.get_chat_history(user_id, limit=MAX_NUM_MESSAGES_RECIPE_GENERATOR)
        
        # Analyze dietary preferences from history
        preferences = self.analyze_dietary_preferences(chat_history)
        
        # Generate recipe with updated chat history
        recipe = self.generate_recipe(user_input, preferences, chat_history=chat_history)
        
        # Create a plain text version for chat history
        plain_text_response = self.format_recipe_plain_text(recipe)
        
        # Extract items for tracking (ingredients from recipe)
        items = []
        if "ingredients" in recipe:
            for ing in recipe["ingredients"]:
                if "grams" in ing:
                    items.append({
                        "ingredient_name": ing["name"],
                        "grams": ing["grams"]
                    })
        
        # Don't save message here - pass it to conversation agent through state
        state["assistant_response"] = {
            "content": plain_text_response,
            "metadata": {"type": "recipe_generation", "recipe": recipe},
            "name": "recipe_generator"
        }
        print(f"Recipe generator setting assistant_response with content length: {len(plain_text_response)}")
        
        # Update state - don't include HTML in response for chat window
        state["response"] = {
            "reply_html": "",  # Empty HTML for chat window
            "items": items,
            "recipe": recipe
        }
        state["chat_history"] = self.get_chat_history(user_id)
        
        # Set side panel data for recipe display
        if recipe and "error" not in recipe:
            state["side_panel_data"] = {
                "type": "recipe",
                "recipe": recipe,
                "items": items  # Include items for potential meal logging
            }
        
        return state