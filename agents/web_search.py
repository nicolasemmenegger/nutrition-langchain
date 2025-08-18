from typing import Dict, Any
from openai import OpenAI
from .base import BaseAgent, ChatMessage
import json
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

class WebSearchAgent(BaseAgent):
    """Agent for searching nutritional information of known food items online"""
    
    def __init__(self, openai_api_key: str):
        super().__init__("web_search", openai_api_key)
        self.client = OpenAI(api_key=openai_api_key)
        
        # Initialize DuckDuckGo search
        wrapper = DuckDuckGoSearchAPIWrapper(max_results=3)
        self.search = DuckDuckGoSearchRun(api_wrapper=wrapper)
    
    def search_nutrition_info(self, food_item: str) -> str:
        """Search for nutritional information online"""
        
        search_query = f"{food_item} nutrition facts calories protein carbs fat per 100g"
        
        try:
            results = self.search.run(search_query)
            return results
        except Exception as e:
            print(f"Error searching for {food_item}: {e}")
            return f"Could not find nutrition information for {food_item}"
    
    def extract_nutrition_from_search(self, food_item: str, search_results: str) -> Dict[str, Any]:
        """Use GPT to extract structured nutrition data from search results"""
        
        messages = [
            {"role": "system", "content": """
                You are a nutrition data extractor. From the search results provided, 
                extract nutritional information and return it in JSON format.
                
                Return a JSON object with:
                {
                    "found": true/false,
                    "food_name": "exact food item name",
                    "per_100g": {
                        "calories": number,
                        "protein": number (in grams),
                        "carbs": number (in grams),
                        "fat": number (in grams)
                    },
                    "serving_size": "standard serving size if mentioned",
                    "source": "where the data came from",
                    "confidence": "high/medium/low"
                }
                
                If nutrition data cannot be reliably extracted, set "found" to false.
            """},
            {"role": "user", "content": f"""
                Food item: {food_item}
                
                Search results:
                {search_results}
                
                Extract the nutritional information for this food item.
            """}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Error extracting nutrition data: {e}")
            return {
                "found": False,
                "error": str(e)
            }
    
    def format_response(self, nutrition_data: Dict[str, Any]) -> str:
        """Format nutrition data into HTML response"""
        
        debug_label = "<p style='color: red; font-weight: bold;'>[WEB SEARCH]</p>"
        
        if not nutrition_data.get("found", False):
            return debug_label + "<p>Could not find reliable nutrition information for this item. Please try describing the ingredients instead.</p>"
        
        food_name = nutrition_data.get("food_name", "Unknown")
        per_100g = nutrition_data.get("per_100g", {})
        serving = nutrition_data.get("serving_size", "Not specified")
        confidence = nutrition_data.get("confidence", "unknown")
        
        html = debug_label + f"""
        <div class="nutrition-info">
            <h3>{food_name}</h3>
            <p><strong>Per 100g:</strong></p>
            <ul>
                <li>Calories: {per_100g.get('calories', 'N/A')} kcal</li>
                <li>Protein: {per_100g.get('protein', 'N/A')}g</li>
                <li>Carbohydrates: {per_100g.get('carbs', 'N/A')}g</li>
                <li>Fat: {per_100g.get('fat', 'N/A')}g</li>
            </ul>
            <p><small>Standard serving: {serving}</small></p>
            <p><small>Data confidence: {confidence}</small></p>
        </div>
        """
        
        return html
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process web search request for nutrition information"""
        
        user_input = state.get("user_input", "")
        user_id = state.get("user_id", "default")
        
        # Extract food item from user input
        food_item = self.extract_food_item(user_input)
        
        # Search for nutrition information
        search_results = self.search_nutrition_info(food_item)
        
        # Extract structured data from search results
        nutrition_data = self.extract_nutrition_from_search(food_item, search_results)
        
        # Format response
        response_html = self.format_response(nutrition_data)
        
        # If found, create items for tracking
        items = []
        if nutrition_data.get("found") and nutrition_data.get("per_100g"):
            items.append({
                "ingredient_name": nutrition_data.get("food_name"),
                "grams": 100,  # Default to 100g
                "nutrition": nutrition_data.get("per_100g")
            })
        
        # Save to chat history
        assistant_message = ChatMessage(
            role="assistant",
            content=response_html,
            metadata={"nutrition_data": nutrition_data}
        )
        self.save_chat_message(user_id, assistant_message)
        
        # Update state
        state["response"] = {
            "reply_html": response_html,
            "items": items,
            "nutrition_data": nutrition_data
        }
        
        return state
    
    def extract_food_item(self, user_input: str) -> str:
        """Extract the food item name from user input"""
        
        messages = [
            {"role": "system", "content": "Extract the main food item or product name from the user's message. Return only the food item name, nothing else."},
            {"role": "user", "content": user_input}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,
                max_tokens=50
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error extracting food item: {e}")
            # Fallback to using the entire input
            return user_input