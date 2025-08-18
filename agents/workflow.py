from typing import TypedDict, Optional, Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from .coordinator import CoordinatorAgent
from .analyzer import AnalyzerAgent
from .web_search import WebSearchAgent
from .recipe import RecipeGenerationAgent
from .coaching import CoachingAgent
import os

class State(TypedDict):
    """State definition for the workflow"""
    user_input: str
    user_id: str
    image_data: Optional[str]
    category: Optional[str]
    coordinator_response: Optional[str]
    chat_history: Optional[list]
    response: Optional[Dict[str, Any]]
    error: Optional[str]

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
    
    # Create the graph
    workflow = StateGraph(State)
    
    # Define node functions
    def coordinate(state: State) -> State:
        """Coordinator node"""
        try:
            return coordinator.process(state)
        except Exception as e:
            state["error"] = f"Coordinator error: {str(e)}"
            return state
    
    def analyze_meal(state: State) -> State:
        """Meal analyzer node"""
        try:
            # Process with analyzer
            state = analyzer.process(state)
            
            # Combine coordinator's response with follow-up
            coordinator_response = state.get("coordinator_response", "")
            follow_up = coordinator.generate_follow_up("analyze_meal", state.get("response"))
            
            if state.get("response"):
                state["response"]["reply_html"] = coordinator_response + follow_up
            
            return state
        except Exception as e:
            state["error"] = f"Analyzer error: {str(e)}"
            state["response"] = {
                "reply_html": state.get("coordinator_response", "") + f"<p>I encountered an error analyzing your meal. Please try again.</p>",
                "items": []
            }
            return state
    
    def search_web(state: State) -> State:
        """Web search node"""
        try:
            state = web_search.process(state)
            
            # Combine coordinator's response with follow-up
            coordinator_response = state.get("coordinator_response", "")
            follow_up = coordinator.generate_follow_up("web_search", state.get("response"))
            
            if state.get("response"):
                state["response"]["reply_html"] = coordinator_response + follow_up
            
            return state
        except Exception as e:
            state["error"] = f"Web search error: {str(e)}"
            state["response"] = {
                "reply_html": state.get("coordinator_response", "") + f"<p>I couldn't find nutrition information for that item. Please try describing it differently.</p>",
                "items": []
            }
            return state
    
    def generate_recipe(state: State) -> State:
        """Recipe generation node"""
        try:
            state = recipe_gen.process(state)
            
            # Combine coordinator's response with follow-up
            coordinator_response = state.get("coordinator_response", "")
            follow_up = coordinator.generate_follow_up("recipe_generation", state.get("response"))
            
            if state.get("response"):
                state["response"]["reply_html"] = coordinator_response + follow_up
            
            return state
        except Exception as e:
            state["error"] = f"Recipe generation error: {str(e)}"
            state["response"] = {
                "reply_html": state.get("coordinator_response", "") + f"<p>I couldn't generate a recipe right now. Please try again.</p>",
                "items": []
            }
            return state
    
    def provide_coaching(state: State) -> State:
        """Coaching node"""
        try:
            state = coaching.process(state)
            
            # For coaching, just prepend the coordinator response
            coordinator_response = state.get("coordinator_response", "")
            
            if state.get("response"):
                state["response"]["reply_html"] = coordinator_response + state["response"]["reply_html"]
            
            return state
        except Exception as e:
            state["error"] = f"Coaching error: {str(e)}"
            state["response"] = {
                "reply_html": state.get("coordinator_response", "") + f"<p>I couldn't provide coaching advice right now. Please try again.</p>",
                "coaching_data": {}
            }
            return state
    
    # Define in_conversation node - just passes through to END for now
    def in_conversation(state: State) -> State:
        """Node for conversation state - response already set by coordinator"""
        # The coordinator has already set the response
        # This node just marks we're in conversation mode
        return state
    
    # Add nodes to the graph
    workflow.add_node("coordinator", coordinate)
    workflow.add_node("analyze_meal", analyze_meal)
    workflow.add_node("web_search", search_web)
    workflow.add_node("recipe_generation", generate_recipe)
    workflow.add_node("coaching", provide_coaching)
    workflow.add_node("in_conversation", in_conversation)
    
    # Define routing logic
    def route_after_coordinator(state: State) -> Literal["analyze_meal", "web_search", "recipe_generation", "coaching", "in_conversation", END]:
        """Route based on category from coordinator"""
        category = state.get("category", "conversation")
        
        # If it's conversation or clarification, stay in conversation mode
        if category in ["conversation", "clarification"]:
            return "in_conversation"
        elif category == "web_search":
            return "web_search"
        elif category == "recipe_generation":
            return "recipe_generation"
        elif category == "coaching":
            return "coaching"
        elif category == "analyze_meal":
            return "analyze_meal"
        else:
            return END
    
    # Add edges
    workflow.add_edge(START, "coordinator")
    workflow.add_conditional_edges(
        "coordinator",
        route_after_coordinator,
        {
            "analyze_meal": "analyze_meal",
            "web_search": "web_search",
            "recipe_generation": "recipe_generation",
            "coaching": "coaching",
            "in_conversation": "in_conversation",
            END: END
        }
    )
    
    # All agent nodes lead to END
    workflow.add_edge("analyze_meal", END)
    workflow.add_edge("web_search", END)
    workflow.add_edge("recipe_generation", END)
    workflow.add_edge("coaching", END)
    
    # In conversation also leads to END (ready for next user input)
    workflow.add_edge("in_conversation", END)
    
    # Compile the graph
    return workflow.compile()

class NutritionAssistant:
    """High-level interface for the nutrition workflow"""
    
    def __init__(self, openai_api_key: str = None):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY_COMMON_EXPERIENCE")
        self.workflow = None
        self._init_workflow()
    
    def _init_workflow(self):
        """Initialize workflow - called within app context"""
        self.workflow = create_nutrition_workflow(self.openai_api_key)
    
    def process_request(self, user_input: str, user_id: str = "default", image_data: str = None) -> Dict[str, Any]:
        """Process a user request through the workflow"""
        
        # Ensure workflow is initialized
        if not self.workflow:
            self._init_workflow()
        
        # Initialize state
        initial_state = {
            "user_input": user_input,
            "user_id": user_id,
            "image_data": image_data,
            "category": None,
            "coordinator_response": None,
            "chat_history": None,
            "response": None,
            "error": None
        }
        
        try:
            # Run the workflow
            result = self.workflow.invoke(initial_state)
            
            # Extract the response
            if result.get("error"):
                return {
                    "success": False,
                    "error": result["error"],
                    "reply_html": f"<p>Error: {result['error']}</p>",
                    "items": []
                }
            
            response = result.get("response", {})
            return {
                "success": True,
                "category": result.get("category"),
                **response
            }
            
        except Exception as e:
            print(f"Workflow error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "reply_html": f"<p>System error: {str(e)}</p>",
                "items": []
            }