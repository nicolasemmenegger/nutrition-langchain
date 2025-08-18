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
            import re
            tag_re = re.compile(r"<[^>]+>")
            for msg in chat_history[-8:]:
                # Strip HTML tags to reduce noise for the classifier
                cleaned = tag_re.sub("", (msg.content or ""))[:10000]
                history_messages.append({
                    "role": msg.role,
                    "content": cleaned
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
    
    def _last_clarification_about(self, chat_history: list[ChatMessage]) -> tuple[str | None, str | None, dict | None]:
        """Return (about, prior_user_message, assistant_metadata) if the last assistant message was a clarification; else (None, None, None)."""
        if not chat_history:
            return None, None, None
        prior_user_text = None
        for i in range(len(chat_history) - 1, -1, -1):
            msg = chat_history[i]
            if msg.role == "assistant" and msg.category == "clarification":
                about = None
                if msg.metadata and isinstance(msg.metadata, dict):
                    about = msg.metadata.get("clarifying_about")
                # find the nearest previous user message
                for j in range(i - 1, -1, -1):
                    if chat_history[j].role == "user":
                        prior_user_text = chat_history[j].content or ""
                        break
                return about, prior_user_text, (msg.metadata or {})
        return None, None, None
    
    def _is_negative_reply(self, text: str) -> bool:
        t = (text or "").strip().lower()
        return t in {"no", "nope", "nah", "nothing else", "just that", "that's it", "only"}
    
    def _extract_item_from_text(self, text: str) -> str | None:
        """Extract the main food item from a sentence. Robust to prefixes like 'hi,'."""
        if not text:
            return None
        raw = (text or "").strip()
        s = raw.lower()
        # Prefer extracting after explicit meal verbs
        keys = ["i had ", "i ate ", "had ", "ate "]
        pos = min((s.find(k) for k in keys if k in s), default=-1)
        if pos != -1:
            # Pick the key actually present at that position
            key = next(k for k in keys if s.find(k) == pos)
            frag = raw[pos + len(key):]
        else:
            # No verb found; fallback to the right side of a comma if it contains a meal verb
            if "," in s:
                left, right = raw.split(",", 1)
                if any(k in right.lower() for k in keys):
                    s = right.lower()
                    # find again with keys in right part
                    pos = min((s.find(k) for k in keys if k in s), default=-1)
                    if pos != -1:
                        key = next(k for k in keys if s.find(k) == pos)
                        frag = right[pos + len(key):]
                    else:
                        frag = right
                else:
                    frag = right
            else:
                frag = raw
        # Trim at common delimiters that usually start adjuncts
        lowers = frag.lower()
        for cut in [" with ", " and ", ",", ";", " for ", ". "]:
            idx = lowers.find(cut)
            if idx != -1:
                frag = frag[:idx]
                lowers = frag.lower()
        # Token cleanup
        toks = [t for t in frag.strip().split() if t.isalpha()]
        if not toks:
            return None
        # Prefer up to first 4 tokens
        return " ".join(toks[:4])

    def _extract_grams(self, text: str) -> float | None:
        """Extract a gram amount from user input (e.g., '150', '150g', '150 grams')."""
        import re
        if not text:
            return None
        s = text.strip().lower()
        # patterns: 150, 150g, 150 g, 150grams, 150 grams, 1 block (~300 g)
        m = re.search(r"(\d+(?:\.\d+)?)\s*(g|grams)?\b", s)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return None
        return None

    def _find_recent_meal_item(self, chat_history: list[ChatMessage]) -> str | None:
        """Scan recent user messages for a likely meal item and extract it."""
        if not chat_history:
            return None
        for msg in reversed(chat_history):
            if msg.role != "user":
                continue
            text = (msg.content or "").lower()
            # ignore trivial greetings like 'hi'/'hello'
            if text.strip() in {"hi", "hello", "hey", "yo", "sup"}:
                continue
            if any(k in text for k in ["i had ", "had ", "i ate ", "ate ", "breakfast", "lunch", "dinner"]):
                item = self._extract_item_from_text(msg.content or "")
                if item:
                    return item
        return None
    
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
        
        # Heuristic: if last assistant message was a clarification about meal logging
        # and the user responds with a short negative (e.g., "no"), keep the thread
        about, prior_user_text, last_meta = self._last_clarification_about(chat_history)
        if about == "meal_logging" and self._is_negative_reply(user_input):
            # Prefer explicit item stored in previous clarification metadata
            last_item = None
            if last_meta and isinstance(last_meta, dict):
                last_item = last_meta.get("clarifying_item")
            item = last_item or self._find_recent_meal_item(chat_history) or "that"
            response_html = (
                "<p style='color: red; font-weight: bold;'>[COORDINATOR]</p>"
                f"<p>Got it — just {item}. Approximately how much did you have in grams?</p>"
                "<p><em>For example: 150 g, 1 block (~300 g), or a rough estimate.</em></p>"
            )
            # Save current user message
            self.save_chat_message(user_id, ChatMessage(role="user", content=user_input, metadata={"category": "clarification"}, category="clarification"))
            # Save assistant follow-up
            self.save_chat_message(
                user_id,
                ChatMessage(
                    role="assistant",
                    content=response_html,
                    metadata={
                        "type": "coordinator",
                        "category": "clarification",
                        "clarifying_about": "meal_logging",
                        "clarifying_item": item,
                    },
                    category="clarification",
                ),
            )
            # Update state and return without calling classifier
            state["category"] = "clarification"
            state["response"] = {"reply_html": response_html, "items": []}
            state["chat_history"] = self.get_chat_history(user_id)
            return state

        # Heuristic: if last was clarification about meal logging and the user provides a quantity
        # assume it's the weight for the previously mentioned item and proceed to analyze_meal.
        if about == "meal_logging":
            grams = self._extract_grams(user_input)
            if grams is not None and grams > 0:
                # Prefer the explicit item captured in the last clarification metadata
                last_item = None
                if last_meta and isinstance(last_meta, dict):
                    last_item = last_meta.get("clarifying_item")
                item = last_item or self._find_recent_meal_item(chat_history) or "item"
                canonical = f"{item} {grams} g"
                ack_html = (
                    "<p style='color: red; font-weight: bold;'>[COORDINATOR]</p>"
                    f"<p>Thanks! Logging {canonical}. I'll analyze it for you now.</p>"
                )
                # Save user message with intended category
                self.save_chat_message(user_id, ChatMessage(role="user", content=user_input, metadata={"category": "analyze_meal"}, category="analyze_meal"))
                # Update state to route to analyzer; do not save assistant here to avoid duplicate saves
                state["user_input"] = canonical
                state["category"] = "analyze_meal"
                state["coordinator_response"] = ack_html
                state["chat_history"] = self.get_chat_history(user_id)
                return state

        # Fallback heuristic: if user says "no" and we recently saw a meal-like user message,
        # ask for grams even if the last assistant turn didn't get tagged as clarification.
        if about is None and self._is_negative_reply(user_input):
            recent_item = self._find_recent_meal_item(chat_history)
            if recent_item:
                response_html = (
                    "<p style='color: red; font-weight: bold;'>[COORDINATOR]</p>"
                    f"<p>Got it — just {recent_item}. Approximately how much did you have in grams?</p>"
                    "<p><em>For example: 150 g, 1 block (~300 g), or a rough estimate.</em></p>"
                )
                # Save current user message
                self.save_chat_message(user_id, ChatMessage(role="user", content=user_input, metadata={"category": "clarification"}, category="clarification"))
                # Save assistant follow-up with clarifying context
                self.save_chat_message(
                    user_id,
                    ChatMessage(
                        role="assistant",
                        content=response_html,
                        metadata={
                            "type": "coordinator",
                            "category": "clarification",
                            "clarifying_about": "meal_logging",
                            "clarifying_item": recent_item,
                        },
                        category="clarification",
                    ),
                )
                state["category"] = "clarification"
                state["response"] = {"reply_html": response_html, "items": []}
                state["chat_history"] = self.get_chat_history(user_id)
                return state

        # Fallback heuristic: if user provides grams and there's a recent meal-like message,
        # proceed to analyze that specific item.
        if about is None:
            grams = self._extract_grams(user_input)
            if grams is not None and grams > 0:
                recent_item = self._find_recent_meal_item(chat_history)
                if recent_item:
                    canonical = f"{recent_item} {grams} g"
                    ack_html = (
                        "<p style='color: red; font-weight: bold;'>[COORDINATOR]</p>"
                        f"<p>Thanks! Logging {canonical}. I'll analyze it for you now.</p>"
                    )
                    self.save_chat_message(user_id, ChatMessage(role="user", content=user_input, metadata={"category": "analyze_meal"}, category="analyze_meal"))
                    state["user_input"] = canonical
                    state["category"] = "analyze_meal"
                    state["coordinator_response"] = ack_html
                    state["chat_history"] = self.get_chat_history(user_id)
                    return state
        
        # Classify and generate response
        category, coordinator_response = self.classify_and_respond(user_input, chat_history, has_image=bool(image_data))
        
        # Save user message to history (immediately after classification)
        user_message = ChatMessage(
            role="user",
            content=user_input,
            metadata={"category": category},
            category=category
        )
        self.save_chat_message(user_id, user_message)
        
        # Prepare metadata for coordinator response (single save, no duplicates)
        coordinator_metadata = {"type": "coordinator", "category": category}
        
        # If it's conversation or clarification, handle it directly without routing
        if category in ["conversation", "clarification"]:
            state["category"] = category
            state["response"] = {
                "reply_html": coordinator_response,
                "items": []
            }
            
            # If asking for clarification, store what we're clarifying about
            if category == "clarification":
                lower_in = user_input.lower()
                if any(k in lower_in for k in ["breakfast", "lunch", "dinner", "ate", "had", "i had", "i ate"]):
                    coordinator_metadata["clarifying_about"] = "meal_logging"
                    # capture the item being discussed for continuity
                    item_guess = self._extract_item_from_text(user_input)
                    if item_guess:
                        coordinator_metadata["clarifying_item"] = item_guess
                elif any(k in lower_in for k in ["recipe", "cook", "make"]):
                    coordinator_metadata["clarifying_about"] = "recipe"
                elif any(k in lower_in for k in ["advice", "healthy", "diet"]):
                    coordinator_metadata["clarifying_about"] = "coaching"

            # Save the coordinator's response once with enriched metadata
            coordinator_message = ChatMessage(
                role="assistant",
                content=coordinator_response,
                metadata=coordinator_metadata,
                category=category
            )
            self.save_chat_message(user_id, coordinator_message)

            # Refresh chat history for completeness
            state["chat_history"] = self.get_chat_history(user_id)
        else:
            # For other categories, store the coordinator's initial response
            state["category"] = category
            state["coordinator_response"] = coordinator_response
            # Refresh chat history to include the just-saved user+coordinator messages
            state["chat_history"] = self.get_chat_history(user_id)
        
        return state