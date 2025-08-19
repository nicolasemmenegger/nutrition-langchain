from typing import TypedDict, Optional, Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from .coordinator import CoordinatorAgent
from .analyzer import AnalyzerAgent
from .web_search import WebSearchAgent
from .recipe import RecipeGenerationAgent
from .coaching import CoachingAgent
from .conversation import ConversationAgent
import os

class State(TypedDict):
    """State definition for the workflow"""
    user_input: str
    user_id: str
    image_data: Optional[str]
    category: Optional[str]
    is_specific: Optional[bool]
    chat_history: Optional[list]
    response: Optional[Dict[str, Any]]
    error: Optional[str]
    previous_action: Optional[str]  # Track what action was just completed
    side_panel_data: Optional[Dict[str, Any]]  # Data for the side panel (meal items, recipe, etc.)

def create_nutrition_workflow(openai_api_key: str = None):
    """Create and configure the LangGraph workflow"""
    
    if not openai_api_key:
        openai_api_key = os.getenv("OPENAI_API_KEY_COMMON_EXPERIENCE")
    
    # Initialize agents
    coordinator = CoordinatorAgent(openai_api_key)
    analyzer = AnalyzerAgent(openai_api_key)
    web_search = WebSearchAgent(openai_api_key)
    recipe_gen = RecipeGenerationAgent(openai_api_key)
    coaching = CoachingAgent(openai_api_key)
    conversation = ConversationAgent(openai_api_key)
    
    # Create the graph
    workflow = StateGraph(State)
    
    # Define node functions
    def coordinate(state: State) -> State:
        """Coordinator node - classifies and checks specificity"""
        try:
            return coordinator.process(state)
        except Exception as e:
            state["error"] = f"Coordinator error: {str(e)}"
            state["category"] = "conversation"
            return state
    
    def analyze_meal(state: State) -> State:
        """Meal analyzer node"""
        try:
            result_state = analyzer.process(state)
            # Mark that we just completed analysis for the conversation agent
            result_state["previous_action"] = "analyze_meal"
            return result_state
        except Exception as e:
            state["error"] = f"Analyzer error: {str(e)}"
            state["response"] = {
                "reply_html": f"<p>I encountered an error analyzing your meal. Please try again.</p>",
                "items": []
            }
            state["previous_action"] = "analyze_meal_error"
            return state
    
    def search_web(state: State) -> State:
        """Web search node"""
        try:
            result_state = web_search.process(state)
            result_state["previous_action"] = "web_search"
            return result_state
        except Exception as e:
            state["error"] = f"Web search error: {str(e)}"
            state["response"] = {
                "reply_html": f"<p>I couldn't find nutrition information for that item. Please try describing it differently.</p>",
                "items": []
            }
            state["previous_action"] = "web_search_error"
            return state
    
    def generate_recipe(state: State) -> State:
        """Recipe generation node"""
        try:
            result_state = recipe_gen.process(state)
            # Mark that we just completed recipe generation for the conversation agent
            result_state["previous_action"] = "recipe_generation"
            return result_state
        except Exception as e:
            state["error"] = f"Recipe generation error: {str(e)}"
            state["response"] = {
                "reply_html": f"<p>I couldn't generate a recipe right now. Please try again.</p>",
                "items": []
            }
            state["previous_action"] = "recipe_generation_error"
            return state
    
    def provide_coaching(state: State) -> State:
        """Coaching node"""
        try:
            result_state = coaching.process(state)
            result_state["previous_action"] = "coaching"
            return result_state
        except Exception as e:
            state["error"] = f"Coaching error: {str(e)}"
            state["response"] = {
                "reply_html": f"<p>I couldn't provide coaching advice right now. Please try again.</p>",
                "coaching_data": {}
            }
            state["previous_action"] = "coaching_error"
            return state
    
    def handle_conversation(state: State) -> State:
        """Conversation node - handles clarifications and general chat"""
        try:
            # Just process normally - the conversation agent will see the chat history
            # and respond appropriately based on context
            return conversation.process(state)
        except Exception as e:
            state["error"] = f"Conversation error: {str(e)}"
            state["response"] = {
                "reply_html": f"<p>I'm having trouble understanding. Could you please rephrase that?</p>",
                "items": []
            }
            return state
    
    # Add nodes to the graph
    workflow.add_node("coordinator", coordinate)
    workflow.add_node("analyzer", analyze_meal)
    workflow.add_node("web_search", search_web)
    workflow.add_node("recipe_generation", generate_recipe)
    workflow.add_node("coaching", provide_coaching)
    workflow.add_node("conversation", handle_conversation)
    
    # Define routing logic
    def route_from_coordinator(state: State) -> str:
        """Route based on coordinator's classification"""
        category = state.get("category", "conversation")
        
        # Map categories to node names
        routing_map = {
            "analyze_meal": "analyzer",
            "web_search": "web_search",
            "recipe_generation": "recipe_generation",
            "coaching": "coaching",
            "conversation": "conversation"
        }
        
        return routing_map.get(category, "conversation")
    
    # Add edges
    workflow.add_edge(START, "coordinator")
    workflow.add_conditional_edges(
        "coordinator",
        route_from_coordinator,
        {
            "analyzer": "analyzer",
            "web_search": "web_search",
            "recipe_generation": "recipe_generation",
            "coaching": "coaching",
            "conversation": "conversation"
        }
    )
    
    # Analyzer and Recipe Generation route to conversation for follow-up
    workflow.add_edge("analyzer", "conversation")
    workflow.add_edge("recipe_generation", "conversation")
    
    # These still go to END as they're typically final
    workflow.add_edge("web_search", END)
    workflow.add_edge("coaching", END)
    workflow.add_edge("conversation", END)
    
    # Compile the graph
    return workflow.compile()


class NutritionAssistant:
    """Wrapper class for backward compatibility with the API"""
    
    def __init__(self, openai_api_key: str = None):
        """Initialize the nutrition assistant with the workflow"""
        self.workflow = create_nutrition_workflow(openai_api_key)
    
    def process_request(self, user_input: str, user_id: str = "default", image_data: str = None) -> Dict[str, Any]:
        """Process a user request through the workflow"""
        try:
            # Create initial state
            state = {
                "user_input": user_input,
                "user_id": user_id,
                "image_data": image_data,
                "category": None,
                "is_specific": None,
                "chat_history": None,
                "response": None,
                "error": None,
                "previous_action": None,
                "side_panel_data": None
            }
            
            # Run the workflow
            result = self.workflow.invoke(state)
            
            # Extract the response
            if result.get("response"):
                response = {
                    "success": True,
                    "category": result.get("category"),  # Include the category
                    "reply_html": result["response"].get("reply_html", ""),
                    "items": result["response"].get("items", []),
                    "ingredients": result["response"].get("ingredients", []),
                    "recipe": result["response"].get("recipe"),
                    "coaching_data": result["response"].get("coaching_data"),
                    "nutrition_data": result["response"].get("nutrition_data")
                }
                
                # Include side_panel_data if present
                if result.get("side_panel_data"):
                    response["side_panel_data"] = result["side_panel_data"]
                
                return response
            else:
                return {
                    "success": False,
                    "reply_html": "<p>I couldn't process your request. Please try again.</p>",
                    "error": result.get("error", "Unknown error")
                }
                
        except Exception as e:
            print(f"Error in NutritionAssistant.process_request: {e}")
            return {
                "success": False,
                "reply_html": "<p>An error occurred while processing your request.</p>",
                "error": str(e)
            }