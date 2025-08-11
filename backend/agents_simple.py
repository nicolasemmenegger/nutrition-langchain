from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field
import re
import json


class NutritionEstimate(BaseModel):
    """Model for nutrition estimation results"""
    food_item: str = Field(description="Name of the food item")
    calories: int = Field(description="Estimated calories")
    protein_g: float = Field(description="Protein in grams")
    carbs_g: float = Field(description="Carbohydrates in grams")
    fat_g: float = Field(description="Fat in grams")
    serving_size: str = Field(description="Estimated serving size")
    confidence: str = Field(description="Confidence level: high, medium, or low")


class CalorieEstimationTool:
    """Tool for estimating calories and nutrition from text or images"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.nutrition_prompt = """You are a nutrition expert specializing in food analysis and calorie estimation.
        
        Analyze the provided food description or image and estimate:
        1. Total calories
        2. Macronutrients (protein, carbs, fat in grams)
        3. Serving size
        4. Confidence level of your estimate
        
        Base your estimates on standard nutritional databases and common serving sizes.
        Be as accurate as possible while acknowledging uncertainty when appropriate.
        
        If an image is provided, analyze visual cues like:
        - Portion size relative to visible objects
        - Food type and preparation method
        - Visible ingredients
        
        Return a structured analysis with your best estimates."""
    
    def estimate_from_text(self, food_description: str) -> Dict[str, Any]:
        """Estimate nutrition from text description"""
        messages = [
            SystemMessage(content=self.nutrition_prompt),
            HumanMessage(content=f"Analyze this food: {food_description}")
        ]
        
        response = self.llm.invoke(messages)
        return self._parse_nutrition_response(response.content, food_description)
    
    def estimate_from_image(self, image_data: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Estimate nutrition from image with optional text description"""
        content = []
        
        if description:
            content.append({"type": "text", "text": f"Analyze this food: {description}"})
        else:
            content.append({"type": "text", "text": "Analyze the food in this image:"})
        
        content.append({
            "type": "image_url",
            "image_url": {"url": image_data}
        })
        
        messages = [
            SystemMessage(content=self.nutrition_prompt),
            HumanMessage(content=content)
        ]
        
        response = self.llm.invoke(messages)
        return self._parse_nutrition_response(response.content, description or "food from image")
    
    def _parse_nutrition_response(self, response_text: str, food_item: str) -> Dict[str, Any]:
        """Parse the LLM response into structured nutrition data"""
        try:
            # Try to extract numbers from the response
            
            # Extract calories
            calorie_match = re.search(r'(\d+)\s*(?:calories?|kcal)', response_text.lower())
            calories = int(calorie_match.group(1)) if calorie_match else 0
            
            # Extract protein
            protein_match = re.search(r'protein[:\s]+(\d+(?:\.\d+)?)\s*g', response_text.lower())
            protein = float(protein_match.group(1)) if protein_match else 0.0
            
            # Extract carbs
            carbs_match = re.search(r'carb(?:ohydrate)?s?[:\s]+(\d+(?:\.\d+)?)\s*g', response_text.lower())
            carbs = float(carbs_match.group(1)) if carbs_match else 0.0
            
            # Extract fat
            fat_match = re.search(r'fat[:\s]+(\d+(?:\.\d+)?)\s*g', response_text.lower())
            fat = float(fat_match.group(1)) if fat_match else 0.0
            
            # Determine confidence
            confidence = "medium"
            if "approximately" in response_text.lower() or "estimate" in response_text.lower():
                confidence = "medium"
            if "uncertain" in response_text.lower() or "unclear" in response_text.lower():
                confidence = "low"
            if "confident" in response_text.lower() or "accurate" in response_text.lower():
                confidence = "high"
            
            return {
                "food_item": food_item,
                "calories": calories,
                "protein_g": protein,
                "carbs_g": carbs,
                "fat_g": fat,
                "serving_size": "1 serving",
                "confidence": confidence,
                "raw_analysis": response_text
            }
        except Exception as e:
            return {
                "food_item": food_item,
                "calories": 0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
                "serving_size": "unknown",
                "confidence": "low",
                "error": str(e),
                "raw_analysis": response_text
            }


class NutritionAgent:
    """Specialized agent for nutrition analysis and calorie estimation"""
    
    def __init__(self, api_key: str):
        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0.3
        )
        
        self.vision_llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0.3
        )
        
        self.calorie_tool = CalorieEstimationTool(self.vision_llm)
        
        self.system_prompt = """You are a professional nutritionist and dietitian AI assistant.
        Your primary role is to help users understand the nutritional content of their meals,
        especially focusing on calorie estimation and macronutrient breakdown.
        
        When analyzing food:
        1. Provide detailed calorie estimates
        2. Break down macronutrients (protein, carbs, fat)
        3. Suggest portion sizes if unclear
        4. Explain your reasoning
        5. Acknowledge uncertainty when appropriate
        6. Provide health insights when relevant
        
        Be supportive, encouraging, and educational in your responses."""
    
    def analyze(self, text: Optional[str] = None, image_data: Optional[str] = None) -> Dict[str, Any]:
        """Analyze food from text and/or image"""
        if image_data:
            result = self.calorie_tool.estimate_from_image(image_data, text)
        elif text:
            result = self.calorie_tool.estimate_from_text(text)
        else:
            return {"error": "No input provided for analysis"}
        
        # Generate a comprehensive response
        analysis_prompt = f"""Based on this nutrition analysis:
        Food: {result.get('food_item', 'Unknown')}
        Calories: {result.get('calories', 0)}
        Protein: {result.get('protein_g', 0)}g
        Carbs: {result.get('carbs_g', 0)}g
        Fat: {result.get('fat_g', 0)}g
        Confidence: {result.get('confidence', 'low')}
        
        Provide a helpful, conversational response about this food's nutritional value,
        portion recommendations, and any health insights."""
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=analysis_prompt)
        ]
        
        response = self.llm.invoke(messages)
        
        result["detailed_analysis"] = response.content
        return result


class SimpleOrchestratorAgent:
    """Simplified orchestrator agent without complex agent chains"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0.7
        )
        
        self.nutrition_agent = NutritionAgent(api_key)
        
        # Store conversation history per session
        self.conversations: Dict[str, List[Dict[str, str]]] = {}
        
        self.system_prompt = """You are an intelligent nutrition coach and assistant.
        Your role is to help users track their food intake, understand nutrition, and make healthy choices.
        
        When users mention specific foods or upload images:
        - Analyze the nutritional content
        - Provide calorie and macro estimates
        - Give helpful dietary advice
        
        Be friendly, supportive, and educational in your responses.
        Always maintain context from the conversation history."""
    
    def _should_analyze_nutrition(self, message: str) -> bool:
        """Determine if the message requires nutrition analysis"""
        food_keywords = ['ate', 'eating', 'had', 'meal', 'food', 'breakfast', 'lunch', 'dinner',
                        'snack', 'drink', 'calories', 'nutrition', 'protein', 'carbs', 'analyze']
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in food_keywords)
    
    def process_message(
        self,
        message: str,
        image_data: Optional[str] = None,
        session_id: str = "default"
    ) -> Dict[str, Any]:
        """Process a user message with optional image"""
        try:
            # Initialize conversation for new sessions
            if session_id not in self.conversations:
                self.conversations[session_id] = []
            
            # If image is provided, always use nutrition analysis
            if image_data:
                analysis = self.nutrition_agent.analyze(text=message, image_data=image_data)
                
                # Format response
                response_text = f"""I've analyzed your food image:

**{analysis.get('food_item', 'Food Item')}**
- Estimated Calories: {analysis.get('calories', 0)} kcal
- Protein: {analysis.get('protein_g', 0)}g
- Carbohydrates: {analysis.get('carbs_g', 0)}g
- Fat: {analysis.get('fat_g', 0)}g
- Serving Size: {analysis.get('serving_size', 'Unknown')}
- Analysis Confidence: {analysis.get('confidence', 'Unknown')}

{analysis.get('detailed_analysis', '')}"""
                
                # Save to conversation history
                self.conversations[session_id].append({"role": "user", "content": f"{message} [with image]"})
                self.conversations[session_id].append({"role": "assistant", "content": response_text})
                
                # Keep conversation manageable
                if len(self.conversations[session_id]) > 20:
                    self.conversations[session_id] = self.conversations[session_id][-20:]
                
                return {
                    "success": True,
                    "message": response_text,
                    "nutrition_data": analysis,
                    "session_id": session_id
                }
            
            # For text-only messages, check if nutrition analysis is needed
            if self._should_analyze_nutrition(message):
                # Extract food description and analyze
                analysis = self.nutrition_agent.analyze(text=message)
                
                if analysis.get('calories', 0) > 0:  # If we got meaningful nutrition data
                    response_text = f"""{analysis.get('detailed_analysis', '')}

**Nutritional Breakdown:**
- Calories: {analysis.get('calories', 0)} kcal
- Protein: {analysis.get('protein_g', 0)}g
- Carbohydrates: {analysis.get('carbs_g', 0)}g
- Fat: {analysis.get('fat_g', 0)}g"""
                    
                    # Save to history
                    self.conversations[session_id].append({"role": "user", "content": message})
                    self.conversations[session_id].append({"role": "assistant", "content": response_text})
                    
                    return {
                        "success": True,
                        "message": response_text,
                        "nutrition_data": analysis,
                        "session_id": session_id
                    }
            
            # For general conversation, use the LLM with conversation history
            messages = [SystemMessage(content=self.system_prompt)]
            
            # Add conversation history
            for msg in self.conversations[session_id][-10:]:  # Last 10 messages for context
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(AIMessage(content=msg["content"]))
            
            # Add current message
            messages.append(HumanMessage(content=message))
            
            # Get response
            response = self.llm.invoke(messages)
            response_text = response.content
            
            # Save to history
            self.conversations[session_id].append({"role": "user", "content": message})
            self.conversations[session_id].append({"role": "assistant", "content": response_text})
            
            # Keep conversation manageable
            if len(self.conversations[session_id]) > 20:
                self.conversations[session_id] = self.conversations[session_id][-20:]
            
            return {
                "success": True,
                "message": response_text,
                "session_id": session_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing message: {str(e)}",
                "session_id": session_id
            }
    
    def clear_memory(self, session_id: str = "default"):
        """Clear conversation memory for a session"""
        if session_id in self.conversations:
            self.conversations[session_id] = []
        return {"success": True, "message": f"Memory cleared for session {session_id}"}
    
    def get_conversation_history(self, session_id: str = "default") -> List[Dict[str, str]]:
        """Get conversation history"""
        return self.conversations.get(session_id, [])