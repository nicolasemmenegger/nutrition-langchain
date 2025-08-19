from typing import Dict, Any, Literal, Tuple
from openai import OpenAI
from .base import BaseAgent, ChatMessage
import json
import os
from datetime import datetime
import re

class CoordinatorAgent(BaseAgent):
    """Coordinator agent that classifies requests and checks if they're specific enough"""
    
    CATEGORIES = ["analyze_meal", "recipe_generation", "web_search", "coaching", "conversation"]
    
    def __init__(self, openai_api_key: str):
        super().__init__("coordinator", openai_api_key)
        self.client = OpenAI(api_key=openai_api_key)
    
    def classify_request(self, user_input: str, chat_history: list[ChatMessage] = None, has_image: bool = False) -> Tuple[str, bool]:
        """
        Classify request and determine if it's specific enough to delegate
        Returns: (category, is_specific_enough)
        """
        
        # If there's an image, it's specific enough for analysis
        if has_image:
            return "analyze_meal", True
        
        # Build messages with recent chat history
        history_messages = []
        if chat_history:
            tag_re = re.compile(r"<[^>]+>")
            for msg in chat_history[-8:]:
                cleaned = tag_re.sub("", (msg.content or ""))[:10000]
                msg_dict = {
                    "role": msg.role,
                    "content": cleaned
                }
                # Add name for assistant messages
                if msg.role == "assistant" and msg.name:
                    msg_dict["name"] = msg.name
                history_messages.append(msg_dict)
        
        messages = [
            {"role": "system", "content": """
                You are a request classifier for a nutrition assistant. Your job is to:
                1. Classify the user's request into the appropriate category
                2. Determine if the request is specific enough to delegate to a specialized agent
                
                Categories:
                - analyze_meal: User wants to log specific food items with quantities (e.g., "I had 2 eggs and toast", "150g of chicken breast")
                - web_search: User mentions specific branded/restaurant food items that need lookup
                - coaching: User wants specific dietary advice or meal balance suggestions
                - recipe_generation: User wants a specific recipe suggestion
                - conversation: General chat, greetings, or requests that need clarification
                
                A request is SPECIFIC ENOUGH when:
                - For analyze_meal: Food items AND quantities are mentioned (e.g., "2 eggs", "a bowl of rice", "150g chicken")
                - For recipe_generation: A clear type of dish or cuisine is mentioned (e.g., "pasta recipe", "healthy breakfast", "Thai curry")
                - For web_search: A specific brand or restaurant item is mentioned (e.g., "McDonald's Big Mac", "Starbucks latte")
                - For coaching: A specific nutrition question or goal is stated (e.g., "how to increase protein", "is this meal balanced")
                
                A request needs CONVERSATION when:
                - It's too vague (e.g., "I had breakfast", "I want something healthy", "help me eat better")
                - Missing critical details (e.g., "just eggs" without quantity, "a recipe" without type)
                - It's a greeting or general chat
                
                Look at the conversation history to understand context. If the user is providing details in response to a previous question, consider the full context.
                
                Return a JSON object with:
                {
                    "category": "one of the categories above",
                    "is_specific": true/false (whether it's specific enough to delegate),
                    "reasoning": "brief explanation of your decision"
                }
            """},
        ] + list(reversed(history_messages)) + [
            {"role": "user", "content": user_input}
        ]
        
        try:
            # Log the request
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"logs/coordinator_{timestamp}.log"
            os.makedirs("logs", exist_ok=True)
            with open(log_filename, 'w') as f:
                f.write(json.dumps(messages, indent=2))
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Log the response
            response_log_filename = f"logs/coordinator_response_{timestamp}.log"
            with open(response_log_filename, 'w') as f:
                f.write(json.dumps({
                    "response": result,
                    "model": "gpt-4o-mini",
                    "timestamp": timestamp
                }, indent=2))
            
            category = result.get("category", "conversation")
            is_specific = result.get("is_specific", False)
            
            # Validate category
            if category not in self.CATEGORIES:
                category = "conversation"
                is_specific = False
            
            # If not specific enough, route to conversation
            if not is_specific:
                category = "conversation"
            
            print(f"Coordinator: category={category}, specific={is_specific}, reasoning={result.get('reasoning', '')}")
            
            return category, is_specific
            
        except Exception as e:
            print(f"Error in classification: {e}")
            return "conversation", False
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process state and determine routing"""
        user_input = state.get("user_input", "")
        user_id = state.get("user_id", "default")
        image_data = state.get("image_data")
        
        # Retrieve chat history
        chat_history = self.get_chat_history(user_id)
        
        # Classify and check specificity
        category, is_specific = self.classify_request(user_input, chat_history, has_image=bool(image_data))
        
        # Update state
        state["category"] = category
        state["is_specific"] = is_specific
        state["chat_history"] = chat_history
        
        print(f"Coordinator routing to: {category}")
        
        return state