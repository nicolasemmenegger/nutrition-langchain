from typing import Dict, Any, List
from openai import OpenAI
from .base import BaseAgent, ChatMessage
import json
from datetime import datetime, timedelta

class CoachingAgent(BaseAgent):
    """Agent that provides nutritional coaching based on user's eating history"""
    
    def __init__(self, openai_api_key: str):
        super().__init__("coaching", openai_api_key)
        self.client = OpenAI(api_key=openai_api_key)
    
    def analyze_nutritional_history(self, chat_history: List[ChatMessage]) -> Dict[str, Any]:
        """Analyze user's nutritional history from chat messages"""
        
        analysis = {
            "total_meals": 0,
            "daily_averages": {
                "calories": 0,
                "protein": 0,
                "carbs": 0,
                "fat": 0
            },
            "meal_patterns": [],
            "frequently_consumed": [],
            "nutritional_gaps": [],
            "time_period": "last 7 days"
        }
        
        if not chat_history:
            return analysis
        
        # Collect all meals from history
        meals_data = []
        for msg in chat_history:
            if msg.metadata and "items" in msg.metadata:
                meals_data.append({
                    "timestamp": msg.timestamp,
                    "items": msg.metadata["items"]
                })
        
        analysis["total_meals"] = len(meals_data)
        
        # Calculate nutritional totals (simplified - would need actual ingredient lookups)
        if meals_data:
            # This is a simplified version - in production, you'd look up actual nutrition values
            analysis["meal_patterns"] = self.identify_meal_patterns(meals_data)
            analysis["frequently_consumed"] = self.get_frequent_foods(meals_data)
        
        return analysis
    
    def identify_meal_patterns(self, meals_data: List[Dict]) -> List[str]:
        """Identify patterns in meal consumption"""
        patterns = []
        
        # Check meal timing
        meal_times = [meal["timestamp"].hour for meal in meals_data if meal.get("timestamp")]
        if meal_times:
            avg_time = sum(meal_times) / len(meal_times)
            if avg_time < 10:
                patterns.append("Early morning eater")
            elif avg_time > 20:
                patterns.append("Late night eating")
        
        # Check meal frequency
        if len(meals_data) > 0:
            days_span = (meals_data[-1]["timestamp"] - meals_data[0]["timestamp"]).days + 1
            meals_per_day = len(meals_data) / max(days_span, 1)
            
            if meals_per_day < 2:
                patterns.append("Infrequent meals")
            elif meals_per_day > 5:
                patterns.append("Frequent snacking")
        
        return patterns
    
    def get_frequent_foods(self, meals_data: List[Dict]) -> List[str]:
        """Get frequently consumed foods"""
        food_counts = {}
        
        for meal in meals_data:
            for item in meal.get("items", []):
                food_name = item.get("ingredient_name", "")
                if food_name:
                    food_counts[food_name] = food_counts.get(food_name, 0) + 1
        
        # Sort by frequency and return top 5
        sorted_foods = sorted(food_counts.items(), key=lambda x: x[1], reverse=True)
        return [food for food, count in sorted_foods[:5]]
    
    def generate_coaching_advice(self, user_request: str, nutritional_history: Dict[str, Any]) -> Dict[str, Any]:
        """Generate personalized coaching advice"""
        
        history_context = json.dumps(nutritional_history, indent=2, default=str)
        
        messages = [
            {"role": "system", "content": f"""
                You are a professional nutritionist and health coach providing personalized dietary advice.
                
                User's nutritional history:
                {history_context}
                
                Provide actionable, encouraging advice that:
                1. Acknowledges positive habits
                2. Identifies areas for improvement
                3. Suggests specific, achievable changes
                4. Provides meal balance recommendations
                5. Considers the user's eating patterns
                
                Return a JSON object with:
                {{
                    "summary": "brief overview of nutritional status",
                    "strengths": ["positive habit 1", "positive habit 2"],
                    "improvements": [
                        {{"area": "protein intake", "suggestion": "specific advice", "priority": "high/medium/low"}}
                    ],
                    "meal_suggestions": [
                        {{"meal_type": "breakfast/lunch/dinner/snack", "suggestion": "specific meal idea"}}
                    ],
                    "weekly_goals": ["goal 1", "goal 2"],
                    "tips": ["practical tip 1", "practical tip 2"],
                    "motivation": "encouraging message"
                }}
            """},
            {"role": "user", "content": user_request}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.6,
                response_format={"type": "json_object"},
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Error generating coaching advice: {e}")
            return {
                "error": str(e),
                "summary": "Unable to generate coaching advice at this time."
            }
    
    def format_coaching_response(self, advice: Dict[str, Any], history: Dict[str, Any]) -> str:
        """Format coaching advice into HTML response"""
        
        debug_label = "<p style='color: red; font-weight: bold;'>[COACHING]</p>"
        
        if "error" in advice:
            return debug_label + "<p>I'm having trouble generating personalized advice right now. Please try again later.</p>"
        
        strengths_html = "\n".join([f"<li>✅ {s}</li>" for s in advice.get("strengths", [])])
        
        improvements_html = "\n".join([
            f"<li><strong>{imp['area']}:</strong> {imp['suggestion']} "
            f"<span class='priority-{imp['priority']}'>[{imp['priority']} priority]</span></li>"
            for imp in advice.get("improvements", [])
        ])
        
        meal_suggestions_html = "\n".join([
            f"<li><strong>{meal['meal_type'].capitalize()}:</strong> {meal['suggestion']}</li>"
            for meal in advice.get("meal_suggestions", [])
        ])

        
        goals_html = "\n".join([f"<li>🎯 {goal}</li>" for goal in advice.get("weekly_goals", [])])
        tips_html = "\n".join([f"<li>💡 {tip}</li>" for tip in advice.get("tips", [])])
        
        html = debug_label + f"""
        <div class="coaching-advice">
            <h2>Your Personalized Nutrition Coaching</h2>
            
            <div class="summary">
                <p>{advice.get('summary', '')}</p>
            </div>
            
            <div class="history-stats">
                <p>📊 Based on {history.get('total_meals', 0)} meals tracked in the {history.get('time_period', 'recent period')}</p>
            </div>
            
            {f'''<div class="strengths">
                <h3>Your Strengths:</h3>
                <ul>{strengths_html}</ul>
            </div>''' if strengths_html else ''}
            
            {f'''<div class="improvements">
                <h3>Areas for Improvement:</h3>
                <ul>{improvements_html}</ul>
            </div>''' if improvements_html else ''}
            
            {f'''<div class="meal-suggestions">
                <h3>Meal Suggestions for Better Balance:</h3>
                <ul>{meal_suggestions_html}</ul>
            </div>''' if meal_suggestions_html else ''}
            
            {f'''<div class="weekly-goals">
                <h3>Your Weekly Goals:</h3>
                <ul>{goals_html}</ul>
            </div>''' if goals_html else ''}
            
            {f'''<div class="tips">
                <h3>Practical Tips:</h3>
                <ul>{tips_html}</ul>
            </div>''' if tips_html else ''}
            
            <div class="motivation">
                <p><em>{advice.get('motivation', 'Keep up the great work on your nutrition journey!')}</em></p>
            </div>
            
            {f'''<div class="patterns">
                <p><small>Detected patterns: {', '.join(history.get('meal_patterns', []))}</small></p>
            </div>''' if history.get('meal_patterns') else ''}
        </div>
        """
        
        return html
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process coaching request"""
        
        user_input = state.get("user_input", "")
        user_id = state.get("user_id", "default")
        chat_history = state.get("chat_history", [])
        
        # Analyze nutritional history
        nutritional_history = self.analyze_nutritional_history(chat_history)
        
        # Generate coaching advice
        advice = self.generate_coaching_advice(user_input, nutritional_history)
        
        # Format response
        response_html = self.format_coaching_response(advice, nutritional_history)
        
        # Update state
        state["response"] = {
            "reply_html": response_html,
            "coaching_data": {
                "advice": advice,
                "history": nutritional_history
            }
        }
        
        return state