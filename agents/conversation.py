from typing import Dict, Any, List
from openai import OpenAI
from .base import BaseAgent, ChatMessage
import json
import os
from datetime import datetime
import re

MAX_NUM_MESSAGES_CONVERSATION = 10

class ConversationAgent(BaseAgent):
    """Agent for handling general conversation and clarification requests"""
    
    def __init__(self, openai_api_key: str):
        super().__init__("conversation", openai_api_key)
        self.client = OpenAI(api_key=openai_api_key)
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process conversation or clarification request"""
        
        user_input = state.get("user_input", "")
        user_id = state.get("user_id", "default")
        chat_history = state.get("chat_history", [])
        category = state.get("category", "conversation")
        previous_action = state.get("previous_action")
        assistant_response = state.get("assistant_response")
        
        # If there's an assistant response from a specialized agent, save it
        # Otherwise, save the user message (direct from coordinator)
        if assistant_response:
            # Coming from analyzer/recipe - save their assistant response
            print(f"Conversation agent received assistant_response from {assistant_response.get('name')}, content length: {len(assistant_response.get('content', ''))}")
            self.save_chat_message(
                user_id,
                ChatMessage(
                    role="assistant",
                    content=assistant_response.get("content", ""),
                    metadata=assistant_response.get("metadata", {}),
                    category=category,
                    name=assistant_response.get("name", "")
                )
            )
        else:
            # Coming directly from coordinator - save user message
            print(f"Conversation agent saving user message: '{user_input[:50]}...'")
            self.save_chat_message(
                user_id,
                ChatMessage(
                    role="user",
                    content=user_input,
                    metadata={"category": category, "has_image": bool(state.get("image_data"))},
                    category=category
                )
            )
        
        # Get fresh chat history that includes the just-saved message
        chat_history = self.get_chat_history(user_id, limit=MAX_NUM_MESSAGES_CONVERSATION)
        
        # Build messages with recent chat history
        history_messages = []
        if chat_history:
            # Use the most recent messages to preserve context
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
        
        messages = [
            {"role": "system", "content": """
                You are a friendly nutrition assistant. Your role is to:
                1. Engage in natural conversation about nutrition and food. If the user asks you about your opinion on a meal, recipe or specific diet, give it concise tips grounded in common nutritional knowledge.
                2. Ask clarifying questions when users are vague about their meals (e.g. ask about specific instantiations of a dish)
                3. Refer the user to the side bar when the last message came from an assistant
                
                The last message you are getting is going to be either:
                - a user message (in which case you should engage in conversation and potentially ask for clarification)
                - an assistant message (in which case you should refer to the side bar, and ask if the user requires a modification)
                
                When users mention food without enough detail, ask for:
                - Specific ingredients and items, or instantiations of a dish (i.e. "did you have this with chicken or beef"?)
                
                In case asking clarifications (Important: look at context history) goes on for too long, you can ask something like "Would you like me to come up with a best guess?"
                                
                Keep responses conversational and friendly. Don't use emojis.
                Be concise but helpful. Focus on one questions at a time.
                
                When you see that a meal was just analyzed (from meal_analyzer) or a recipe was generated (from recipe_generator), 
                provide appropriate follow-up based on the context (see above for instructions). You can see this from the chat history.
                
                Examples of good follow-ups:
                - "I want something healthy" → "I'd be happy to help! What kind of dish would you like to eat?"
                - After meal analysis → "I've logged your meal. You can review the details in the side panel. Do you we need to modify anything?"
                - After recipe generation → "Here's your recipe! Check the side panel for the full details. Would you like to save this or try something different?"
            """},
        ] + list(reversed(history_messages))
        
        # No need to add user input - it's already in the chat history we just fetched
        
        try:
            # Log the request
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"logs/conversation_{timestamp}.log"
            os.makedirs("logs", exist_ok=True)
            with open(log_filename, 'w') as f:
                f.write(json.dumps(messages, indent=2))
            
            response = self.client.chat.completions.create(
                model="gpt-4o-realtime-preview",
                messages=messages,
                temperature=0.7,
            )
            
            response_text = response.choices[0].message.content
            
            # Log the response
            response_log_filename = f"logs/conversation_response_{timestamp}.log"
            with open(response_log_filename, 'w') as f:
                f.write(json.dumps({
                    "response": response_text,
                    "model": "gpt-4o-mini",
                    "timestamp": timestamp
                }, indent=2))
            
            # Format response without debug label
            response_html = f"<p>{response_text}</p>"
            
            # Save assistant message with name
            self.save_chat_message(
                user_id,
                ChatMessage(
                    role="assistant",
                    content=response_html,
                    metadata={"type": "conversation", "category": category},
                    category=category,
                    name="conversation"
                )
            )
            
            # Update state
            state["response"] = {
                "reply_html": response_html,
                "items": []
            }
            state["chat_history"] = self.get_chat_history(user_id)
            
            # Preserve side_panel_data if it exists (from analyzer or recipe generator)
            # The side_panel_data will remain in state for the frontend to use
            
            return state
            
        except Exception as e:
            print(f"Error in conversation: {e}")
            error_response = "<p>I'm here to help with your nutrition needs. Could you tell me more about what you'd like to do?</p>"
            
            state["response"] = {
                "reply_html": error_response,
                "items": []
            }
            return state