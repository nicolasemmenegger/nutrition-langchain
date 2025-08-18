from typing import Dict, Any, Literal, Tuple
from openai import OpenAI
from .base import BaseAgent, ChatMessage
import json

class CoordinatorAgent(BaseAgent):
    """Coordinator agent that manages conversation flow and routes to appropriate agents"""
    
    CATEGORIES = ["analyze_meal", "coaching", "web_search", "recipe_generation", "conversation", "clarification"]
    
    def __init__(self, openai_api_key: str):
        super().__init__("coordinator", openai_api_key)
        self.client = OpenAI(api_key=openai_api_key)
    
    def classify_and_respond(self, user_input: str, chat_history: list[ChatMessage] = None, has_image: bool = False) -> Tuple[str, str]:
        """Classify request and generate appropriate conversational response"""
        
        # If there's an image, always analyze it immediately
        if has_image:
            response_html = "<p style='color: red; font-weight: bold;'>[COORDINATOR]</p>"
            response_html += "<p>I see you've uploaded an image. Let me analyze the food items in it for you...</p>"
            return "analyze_meal", response_html
        
        # Build messages with recent chat history as actual turns
        history_messages = []
        if chat_history:
            # Use the most recent few messages to preserve context
            for msg in chat_history[-6:]:
                history_messages.append({
                    "role": msg.role,
                    "content": msg.content[:1000]
                })

        messages = [
            {"role": "system", "content": """
                You are a nutrition assistant coordinator. Your job is to:
                1. Understand what the user wants
                2. Classify their request into the appropriate category
                3. Provide a conversational response that guides them
                
                Categories:
                - analyze_meal: User clearly wants to log food with enough detail (e.g., "I had 2 eggs and toast") OR provides an image
                - web_search: User mentions specific branded/restaurant food items
                - coaching: User wants dietary advice or meal balance suggestions
                - recipe_generation: User wants recipe suggestions
                - conversation: General chat, greetings, or off-topic
                - clarification: User's intent is clear but needs more details (e.g., "I had breakfast" without specifics)

                IMPORTANT: Look at the conversation history. If you previously asked for clarification about something:
                - If the user provides the requested details, classify based on the original intent + new details
                - For example: If you asked "What did you have for breakfast?" and they say "eggs and toast", classify as analyze_meal
                - If you asked "What kind of recipe?" and they say "pasta", classify as recipe_generation

                Return a JSON object with:
                {
                    "category": "one of the categories above",
                    "response": "Your conversational response to the user",
                    "follow_up": "Optional follow-up question if needed"
                }
                
                For meal logging (analyze_meal), your response should:
                - Acknowledge what they're logging
                - Let them know you'll analyze it
                - Mention they can review and edit in the side panel
                
                For clarification, your response should:
                - Ask for specific details needed
                - Be friendly and encouraging
                - Give examples of what information would help
                
                Formatting Instructions:
                - You CANNOT use emoji's
                - You should keep responses fairly short, and not provide too many pointers at once. Focus on what seems most important.
                - Talk like a human. Don't include titles or subtitles. Just output some text, as I would when I text a friend.
            """}
        ] + history_messages + [
            {"role": "user", "content": user_input}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            category = result.get("category", "conversation")
            
            # Build the response HTML with debug label
            response_html = f"<p style='color: red; font-weight: bold;'>[COORDINATOR]</p>"
            response_html += f"<p>{result.get('response', '')}</p>"
            if result.get('follow_up'):
                response_html += f"<p><em>{result['follow_up']}</em></p>"
            
            # Validate category
            if category not in self.CATEGORIES:
                category = "conversation"
            
            return category, response_html
            
        except Exception as e:
            print(f"Error in classification: {e}")
            return "conversation", "<p style='color: red; font-weight: bold;'>[COORDINATOR ERROR]</p><p>I'm here to help with your nutrition needs. Could you tell me more about what you'd like to do?</p>"
    
    def generate_follow_up(self, category: str, analysis_result: Dict[str, Any] = None) -> str:
        """Generate follow-up questions based on the analysis results"""
        
        debug_label = f"<p style='color: red; font-weight: bold;'>[COORDINATOR FOLLOW-UP]</p>"
        
        if category == "analyze_meal" and analysis_result:
            items = analysis_result.get("items", [])
            if items:
                item_names = [item["ingredient_name"] for item in items[:3]]
                return debug_label + f"""
                <p>I've identified these ingredients from your meal: <strong>{', '.join(item_names)}</strong>{' and more' if len(items) > 3 else ''}.</p>
                <p>Please check the panel on the right to review and adjust portions. Does everything look correct, or would you like to make any changes?</p>
                """
            else:
                return debug_label + "<p>I couldn't identify specific ingredients. Could you provide more details about what you ate?</p>"
        
        elif category == "recipe_generation":
            return debug_label + "<p>I've generated a recipe suggestion for you! Check the panel on the right for ingredients and instructions. Would you like to log this as a meal or save it for later?</p>"
        
        elif category == "web_search":
            return debug_label + "<p>I've found the nutrition information for that item. You can review it in the panel and log it if you'd like.</p>"
        
        return ""
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process state and determine routing"""
        user_input = state.get("user_input", "")
        user_id = state.get("user_id", "default")
        image_data = state.get("image_data")
        
        # Retrieve chat history
        chat_history = self.get_chat_history(user_id)
        
        # Classify and generate response
        category, coordinator_response = self.classify_and_respond(user_input, chat_history, has_image=bool(image_data))
        
        # Save user message to history (immediately after classification)
        user_message = ChatMessage(
            role="user",
            content=user_input,
            metadata={"category": category}
        )
        self.save_chat_message(user_id, user_message)
        
        # Always save the coordinator's response to ensure continuity across agent calls
        coordinator_message = ChatMessage(
            role="assistant",
            content=coordinator_response,
            metadata={"type": "coordinator", "category": category}
        )
        self.save_chat_message(user_id, coordinator_message)
        
        # If it's conversation or clarification, handle it directly without routing
        if category in ["conversation", "clarification"]:
            state["category"] = category
            state["response"] = {
                "reply_html": coordinator_response,
                "items": []
            }
            
            # Save coordinator's response to history with intent tracking
            metadata = {"type": category}
            
            # If asking for clarification, store what we're clarifying about
            if category == "clarification":
                # Try to determine the underlying intent from the response
                if "breakfast" in user_input.lower() or "lunch" in user_input.lower() or "dinner" in user_input.lower() or "ate" in user_input.lower() or "had" in user_input.lower():
                    metadata["clarifying_about"] = "meal_logging"
                elif "recipe" in user_input.lower() or "cook" in user_input.lower() or "make" in user_input.lower():
                    metadata["clarifying_about"] = "recipe"
                elif "advice" in user_input.lower() or "healthy" in user_input.lower() or "diet" in user_input.lower():
                    metadata["clarifying_about"] = "coaching"
            
            assistant_message = ChatMessage(
                role="assistant",
                content=coordinator_response,
                metadata=metadata
            )
            self.save_chat_message(user_id, assistant_message)
        else:
            # For other categories, store the coordinator's initial response
            state["category"] = category
            state["coordinator_response"] = coordinator_response
            # Refresh chat history to include the just-saved user+coordinator messages
            state["chat_history"] = self.get_chat_history(user_id)
        
        return state