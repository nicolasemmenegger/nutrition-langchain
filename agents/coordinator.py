from typing import Dict, Any, Literal, Tuple
from openai import OpenAI
from .base import BaseAgent, ChatMessage
import json
import os
from datetime import datetime
import re

MAX_NUM_MESSAGES_COORDINATOR = 10

class CoordinatorAgent(BaseAgent):
    """Coordinator agent that classifies requests and checks if they're specific enough"""
    
    CATEGORIES = ["analyze_meal", "recipe_generation", "web_search", "coaching", "conversation"]
    
    def __init__(self, openai_api_key: str):
        super().__init__("coordinator", openai_api_key)
        self.client = OpenAI(api_key=openai_api_key)
    
    def classify_request(self, user_input: str, chat_history: list[ChatMessage] = None, has_image: bool = False) -> str:
        """
        Classify request into appropriate category
        Returns: category
        """
        
        # If there's an image, route to meal analysis
        if has_image:
            return "analyze_meal"
        
        # Build messages with recent chat history
        history_messages = []
        if chat_history:
            tag_re = re.compile(r"<[^>]+>")
            for msg in chat_history:
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
                You are a request classifier for a nutrition assistant. Your job is to classify the user's request into the appropriate category. You should use the full context that is being passed to you.
                Conversation messages come either from the user, or from an assistant. The assistants that write to the chat history are a conversational agent, a recipe generation agent, 
                and a meal logging agent. Your goal is to determine which agent gets the current request. Use the full conversation history.

                Categories:
                - analyze_meal: User wants to log food items with sufficient precision (e.g., "I had eggs and toast", "150g of chicken breast")
                - recipe_generation: User wants a recipe suggestion and provides some minimal context. ("What could I eat for breakfast")
                    * At least some context should be specified  (e.g. whether it's lunch or dinner or breakfast or whether a specific ingredient is present: "I need to use this tofu")
                - coaching: User wants some general advice (e.g. "How could I improve my diet")
                - conversation: General chat, greetings, meal logging requests that need some clarification and recipe generation requests that need some clarification ("Hi" or "I ate pasta today" or "Help me find what to eat" all warrant some follow-ups, so conversation is appropriate)

                Pointers:
                - If there is no prior context in the messages, and the request is vague, defer to conversation. For instance if the user says "I had pasta" and no follow-ups have been asked, conversation is correct.
                - Recency bias:
                    * if the chat history is most recently about recipe generation, you should be biased towards recipe_generation
                    * if the chat history is most recently about recipe logging, you should be biased towards analyze_meal
                - However, do not defer to conversation too many times in a row, so check the history before deferring to conversation
                - Important: If the user declines to clarify ("no"), go with analyze_meal or recipe_generation based on previous context!

                Return a JSON object with:
                {
                    "category": "one of the categories above",
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
            
            # Validate category
            if category not in self.CATEGORIES:
                category = "conversation"
            
            print(f"Coordinator: category={category}, reasoning={result.get('reasoning', '')}")
            
            return category
            
        except Exception as e:
            print(f"Error in classification: {e}")
            return "conversation", False
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process state and determine routing"""
        user_input = state.get("user_input", "")
        user_id = state.get("user_id", "default")
        image_data = state.get("image_data")
        
        # Retrieve chat history
        chat_history = self.get_chat_history(user_id, limit=MAX_NUM_MESSAGES_COORDINATOR) # you can set a limit here
        
        # Classify request
        category = self.classify_request(user_input, chat_history, has_image=bool(image_data))
        
        # Update state
        state["category"] = category
        state["chat_history"] = chat_history
        
        print(f"Coordinator routing to: {category}")
        
        return state