from typing import Dict, Any, List, Optional, Literal
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import Tool, StructuredTool
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field
import base64
from PIL import Image
import io
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
            import re
            
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


class OrchestratorAgent:
    """Main orchestrator agent that coordinates interactions"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0.7
        )
        
        self.nutrition_agent = NutritionAgent(api_key)
        
        # Memory for conversation context
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        self.system_prompt = """You are an intelligent orchestrator for a nutrition tracking application.
        Your role is to:
        1. Understand user requests about food and nutrition
        2. Coordinate with specialized agents when needed
        3. Maintain conversation context
        4. Provide helpful, friendly responses
        
        You have access to a nutrition analysis agent that can:
        - Estimate calories from text descriptions
        - Analyze food images
        - Provide detailed nutritional breakdowns
        
        Guide users through their nutrition journey with empathy and expertise."""
        
        # Create tools for the orchestrator
        self.tools = [
            StructuredTool.from_function(
                func=self._analyze_nutrition,
                name="analyze_nutrition",
                description="Analyze nutritional content of food from text or image. Use when user asks about calories, nutrition, or provides food descriptions/images.",
                args_schema=self._create_nutrition_schema()
            ),
            StructuredTool.from_function(
                func=self._get_nutrition_advice,
                name="get_nutrition_advice",
                description="Get general nutrition advice and recommendations. Use for questions about healthy eating, meal planning, or dietary guidance."
            )
        ]
        
        # Create the agent prompt using ChatPromptTemplate for OpenAI functions
        self.agent_prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # Create the OpenAI functions agent (more reliable than ReAct)
        self.agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.agent_prompt
        )
        
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=3,
            return_intermediate_steps=False
        )
    
    def _create_nutrition_schema(self):
        """Create a schema for the nutrition analysis tool"""
        class NutritionAnalysisSchema(BaseModel):
            text: Optional[str] = Field(default=None, description="Text description of the food")
            image_data: Optional[str] = Field(default=None, description="Base64 encoded image data")
        return NutritionAnalysisSchema
    
    def _analyze_nutrition(self, text: Optional[str] = None, image_data: Optional[str] = None) -> str:
        """Tool function to analyze nutrition"""
        result = self.nutrition_agent.analyze(text=text, image_data=image_data)
        
        if "error" in result:
            return f"Unable to analyze: {result['error']}"
        
        response = f"""Nutritional Analysis:
        
        Food: {result.get('food_item', 'Unknown')}
        Estimated Calories: {result.get('calories', 0)} kcal
        Protein: {result.get('protein_g', 0)}g
        Carbohydrates: {result.get('carbs_g', 0)}g
        Fat: {result.get('fat_g', 0)}g
        Serving Size: {result.get('serving_size', 'Unknown')}
        Confidence: {result.get('confidence', 'Unknown')}
        
        {result.get('detailed_analysis', '')}"""
        
        return response
    
    def _get_nutrition_advice(self, topic: str) -> str:
        """Tool function to provide nutrition advice"""
        messages = [
            SystemMessage(content="You are a nutrition expert. Provide helpful, evidence-based advice."),
            HumanMessage(content=f"Provide advice about: {topic}")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def process_message(
        self,
        message: str,
        image_data: Optional[str] = None,
        session_id: str = "default"
    ) -> Dict[str, Any]:
        """Process a user message with optional image"""
        try:
            # If image is provided, directly use nutrition analysis
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
                
                # Save to memory
                self.memory.save_context(
                    {"input": f"{message} [with image]"},
                    {"output": response_text}
                )
                
                return {
                    "success": True,
                    "message": response_text,
                    "nutrition_data": analysis,
                    "session_id": session_id
                }
            
            # For text-only messages, use the agent executor
            result = self.agent_executor.invoke({"input": message})
            
            return {
                "success": True,
                "message": result.get("output", ""),
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
        self.memory.clear()
        return {"success": True, "message": f"Memory cleared for session {session_id}"}
    
    def get_conversation_history(self, session_id: str = "default") -> List[Dict[str, str]]:
        """Get conversation history"""
        messages = self.memory.chat_memory.messages
        history = []
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                history.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                history.append({"role": "assistant", "content": msg.content})
        
        return history