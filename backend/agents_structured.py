from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field
import json


class NutritionData(BaseModel):
    """Structured nutrition data model"""
    food_item: str = Field(description="Name or description of the food item")
    calories: int = Field(description="Total calories (kcal)")
    protein_g: float = Field(description="Protein in grams")
    carbs_g: float = Field(description="Carbohydrates in grams")
    fat_g: float = Field(description="Fat in grams")
    fiber_g: Optional[float] = Field(default=0, description="Fiber in grams")
    sugar_g: Optional[float] = Field(default=0, description="Sugar in grams")
    sodium_mg: Optional[int] = Field(default=0, description="Sodium in milligrams")
    serving_size: str = Field(description="Serving size description")
    serving_count: float = Field(default=1.0, description="Number of servings")
    confidence_level: str = Field(description="Confidence level: high, medium, or low")
    notes: Optional[str] = Field(default="", description="Additional notes or assumptions")


class NutritionExtractor:
    """Extract structured nutrition data from food descriptions and images"""
    
    def __init__(self, api_key: str):
        # Use JSON mode for structured output
        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0.2,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
        
        self.vision_llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0.2
        )
        
        self.extraction_prompt = """You are a professional nutritionist. Analyze the food and provide accurate nutritional information.

You MUST respond with a valid JSON object containing these exact fields:
{
    "food_item": "descriptive name of the food",
    "calories": <integer>,
    "protein_g": <float>,
    "carbs_g": <float>,
    "fat_g": <float>,
    "fiber_g": <float>,
    "sugar_g": <float>,
    "sodium_mg": <integer>,
    "serving_size": "description like '1 cup' or '100g' or '1 medium bowl'",
    "serving_count": <float>,
    "confidence_level": "high|medium|low",
    "notes": "any assumptions or important notes"
}

Base your estimates on:
- USDA nutritional databases
- Standard portion sizes
- Common preparation methods
- Visible ingredients and cooking methods

For images, analyze:
- Portion size relative to plate/bowl/utensils
- Color and texture indicating cooking method
- Visible ingredients and garnishes
- Overall volume estimation

Be as accurate as possible. If uncertain, use "medium" or "low" confidence and explain in notes."""
    
    def extract_from_text(self, description: str) -> Dict[str, Any]:
        """Extract nutrition data from text description"""
        prompt = f"{self.extraction_prompt}\n\nAnalyze this food and provide nutritional data:\n{description}"
        
        messages = [
            SystemMessage(content="You are a nutrition analysis system. Always respond with valid JSON."),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            data = json.loads(response.content)
            
            # Validate and ensure all fields exist
            return self._validate_nutrition_data(data)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return self._create_fallback_data(description)
        except Exception as e:
            return self._create_fallback_data(description, str(e))
    
    def extract_from_image(self, image_data: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Extract nutrition data from image with optional description"""
        content = [
            {"type": "text", "text": self.extraction_prompt},
            {"type": "text", "text": f"Additional context: {description}" if description else "Analyze this food image:"},
            {"type": "image_url", "image_url": {"url": image_data}}
        ]
        
        messages = [
            SystemMessage(content="You are a nutrition analysis system. Analyze the image and respond with valid JSON containing nutritional data."),
            HumanMessage(content=content)
        ]
        
        try:
            response = self.vision_llm.invoke(messages)
            
            # Extract JSON from response (it might be wrapped in markdown)
            content = response.content
            
            # Try to find JSON in the response
            import re
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # Try parsing the whole content
                data = json.loads(content)
            
            return self._validate_nutrition_data(data)
        except Exception as e:
            return self._create_fallback_data(description or "food from image", str(e))
    
    def _validate_nutrition_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and ensure all required fields exist"""
        defaults = {
            "food_item": "Unknown food",
            "calories": 0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
            "sugar_g": 0.0,
            "sodium_mg": 0,
            "serving_size": "1 serving",
            "serving_count": 1.0,
            "confidence_level": "low",
            "notes": ""
        }
        
        # Merge with defaults to ensure all fields exist
        validated = {**defaults, **data}
        
        # Ensure correct types
        validated["calories"] = int(validated["calories"])
        validated["protein_g"] = float(validated["protein_g"])
        validated["carbs_g"] = float(validated["carbs_g"])
        validated["fat_g"] = float(validated["fat_g"])
        validated["fiber_g"] = float(validated.get("fiber_g", 0))
        validated["sugar_g"] = float(validated.get("sugar_g", 0))
        validated["sodium_mg"] = int(validated.get("sodium_mg", 0))
        validated["serving_count"] = float(validated.get("serving_count", 1))
        
        return validated
    
    def _create_fallback_data(self, food_item: str, error: str = "") -> Dict[str, Any]:
        """Create fallback data when extraction fails"""
        return {
            "food_item": food_item,
            "calories": 0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
            "sugar_g": 0.0,
            "sodium_mg": 0,
            "serving_size": "unknown",
            "serving_count": 1.0,
            "confidence_level": "low",
            "notes": f"Unable to extract nutrition data. {error}"
        }


class NutritionCoach:
    """Provides personalized nutrition advice based on extracted data"""
    
    def __init__(self, api_key: str):
        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0.7
        )
        
        self.coach_prompt = """You are a friendly, knowledgeable nutrition coach.
        Based on the nutritional data provided, give helpful insights about:
        - Whether this is a balanced meal
        - Health benefits and concerns
        - Portion size appropriateness
        - Suggestions for improvement
        - How it fits into daily nutritional goals
        
        Be encouraging, educational, and practical. Keep responses concise but informative."""
    
    def generate_advice(self, nutrition_data: Dict[str, Any]) -> str:
        """Generate personalized nutrition advice"""
        data_summary = f"""
        Food: {nutrition_data['food_item']}
        Calories: {nutrition_data['calories']} kcal
        Protein: {nutrition_data['protein_g']}g
        Carbs: {nutrition_data['carbs_g']}g
        Fat: {nutrition_data['fat_g']}g
        Fiber: {nutrition_data.get('fiber_g', 0)}g
        Serving: {nutrition_data['serving_size']}
        """
        
        messages = [
            SystemMessage(content=self.coach_prompt),
            HumanMessage(content=f"Provide nutrition coaching for this food:\n{data_summary}")
        ]
        
        response = self.llm.invoke(messages)
        return response.content


class StructuredOrchestratorAgent:
    """Orchestrator using structured data extraction"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        
        # Initialize components
        self.extractor = NutritionExtractor(api_key)
        self.coach = NutritionCoach(api_key)
        
        # General conversation LLM
        self.conversation_llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0.7
        )
        
        # Store conversation history
        self.conversations: Dict[str, List[Dict[str, str]]] = {}
        
        self.system_prompt = """You are a helpful nutrition assistant and coach.
        Help users understand their food choices, track nutrition, and make healthier decisions.
        Be friendly, supportive, and educational."""
    
    def _is_food_related(self, message: str) -> bool:
        """Check if message is food/nutrition related"""
        food_indicators = [
            'ate', 'eating', 'eat', 'had', 'having', 'meal', 'food', 'breakfast',
            'lunch', 'dinner', 'snack', 'drink', 'beverage', 'calories', 'nutrition',
            'protein', 'carbs', 'fat', 'analyze', 'what is in', 'how many calories',
            'healthy', 'diet', 'portion', 'serving'
        ]
        
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in food_indicators)
    
    def process_message(
        self,
        message: str,
        image_data: Optional[str] = None,
        session_id: str = "default"
    ) -> Dict[str, Any]:
        """Process user message and return response"""
        try:
            # Initialize conversation history
            if session_id not in self.conversations:
                self.conversations[session_id] = []
            
            # Always analyze if image is provided
            if image_data:
                # Extract nutrition data
                nutrition_data = self.extractor.extract_from_image(image_data, message)
                
                # Generate coaching advice
                advice = self.coach.generate_advice(nutrition_data)
                
                # Format complete response
                response_text = f"""I've analyzed your food image:

📊 **{nutrition_data['food_item']}**

**Nutritional Information:**
• Calories: {nutrition_data['calories']} kcal
• Protein: {nutrition_data['protein_g']}g
• Carbohydrates: {nutrition_data['carbs_g']}g
• Fat: {nutrition_data['fat_g']}g
• Fiber: {nutrition_data.get('fiber_g', 0)}g
• Serving: {nutrition_data['serving_size']}

**Analysis Confidence:** {nutrition_data['confidence_level']}

{advice}"""
                
                if nutrition_data.get('notes'):
                    response_text += f"\n\n💡 *Note: {nutrition_data['notes']}*"
                
                # Save to history
                self.conversations[session_id].append({
                    "role": "user",
                    "content": f"{message} [with image]"
                })
                self.conversations[session_id].append({
                    "role": "assistant",
                    "content": response_text
                })
                
                return {
                    "success": True,
                    "message": response_text,
                    "nutrition_data": nutrition_data,
                    "session_id": session_id
                }
            
            # Check if text message is food-related
            elif self._is_food_related(message):
                # Extract nutrition data from text
                nutrition_data = self.extractor.extract_from_text(message)
                
                if nutrition_data['calories'] > 0:  # Valid nutrition data extracted
                    # Generate coaching advice
                    advice = self.coach.generate_advice(nutrition_data)
                    
                    # Format response
                    response_text = f"""Based on your description:

📊 **{nutrition_data['food_item']}**

**Estimated Nutrition:**
• Calories: {nutrition_data['calories']} kcal
• Protein: {nutrition_data['protein_g']}g
• Carbohydrates: {nutrition_data['carbs_g']}g
• Fat: {nutrition_data['fat_g']}g
• Serving: {nutrition_data['serving_size']}

{advice}"""
                    
                    if nutrition_data['confidence_level'] != 'high':
                        response_text += f"\n\n*Confidence: {nutrition_data['confidence_level']} - For more accurate analysis, consider providing an image.*"
                    
                    # Save to history
                    self.conversations[session_id].append({"role": "user", "content": message})
                    self.conversations[session_id].append({"role": "assistant", "content": response_text})
                    
                    return {
                        "success": True,
                        "message": response_text,
                        "nutrition_data": nutrition_data,
                        "session_id": session_id
                    }
            
            # Handle general conversation
            messages = [SystemMessage(content=self.system_prompt)]
            
            # Add recent conversation history
            for msg in self.conversations[session_id][-6:]:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(AIMessage(content=msg["content"]))
            
            messages.append(HumanMessage(content=message))
            
            response = self.conversation_llm.invoke(messages)
            response_text = response.content
            
            # Save to history
            self.conversations[session_id].append({"role": "user", "content": message})
            self.conversations[session_id].append({"role": "assistant", "content": response_text})
            
            # Limit conversation history
            if len(self.conversations[session_id]) > 20:
                self.conversations[session_id] = self.conversations[session_id][-20:]
            
            return {
                "success": True,
                "message": response_text,
                "session_id": session_id
            }
            
        except Exception as e:
            print(f"Error in process_message: {str(e)}")
            return {
                "success": False,
                "message": f"I encountered an error processing your request. Please try again or rephrase your message.",
                "error": str(e),
                "session_id": session_id
            }
    
    def clear_memory(self, session_id: str = "default"):
        """Clear conversation memory"""
        if session_id in self.conversations:
            self.conversations[session_id] = []
        return {"success": True, "message": f"Conversation cleared for session {session_id}"}
    
    def get_conversation_history(self, session_id: str = "default") -> List[Dict[str, str]]:
        """Get conversation history"""
        return self.conversations.get(session_id, [])