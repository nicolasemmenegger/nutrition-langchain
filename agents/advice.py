from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
from openai import OpenAI
from .base import BaseAgent
from models import db, Meal, MealNutrition, DailyAdvice
from utils import get_ingredient_cloud_data
import os
import json


class AdviceAgent(BaseAgent):
    """Generates 'Tip of the Day' based on the user's recent nutrition history."""

    def __init__(self, openai_api_key: str):
        super().__init__("advice", openai_api_key)
        self.client = OpenAI(api_key=openai_api_key)

    def _gather_history(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days - 1)
        rows = (
            db.session.query(
                Meal.date,
                db.func.sum(MealNutrition.calories).label("calories"),
                db.func.sum(MealNutrition.protein).label("protein"),
                db.func.sum(MealNutrition.carbs).label("carbs"),
                db.func.sum(MealNutrition.fat).label("fat"),
            )
            .join(MealNutrition, MealNutrition.meal_id == Meal.id)
            .filter(
                Meal.user_id == user_id,
                Meal.date >= start_date,
                Meal.date <= end_date,
            )
            .group_by(Meal.date)
            .order_by(Meal.date)
            .all()
        )
        history = [
            {
                "date": r[0].isoformat(),
                "calories": float(r[1] or 0),
                "protein": float(r[2] or 0),
                "carbs": float(r[3] or 0),
                "fat": float(r[4] or 0),
            }
            for r in rows
        ]
        # Include most used ingredients by grams
        try:
            top_ingredients = get_ingredient_cloud_data(user_id, start_date, end_date, top_n=20)
        except Exception:
            top_ingredients = []
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days,
            "history": history,
            "top_ingredients": top_ingredients,
        }

    def _get_previous_tips(self, user_id: int, limit: int = 5) -> List[str]:
        rows = (
            DailyAdvice.query
            .filter_by(user_id=user_id)
            .order_by(DailyAdvice.date.desc())
            .limit(limit)
            .all()
        )
        return [r.advice for r in rows if r and r.advice]

    def _get_tip_for_date(self, user_id: int, target_date: date) -> Optional[str]:
        row = DailyAdvice.query.filter_by(user_id=user_id, date=target_date).first()
        return row.advice if row else None

    def generate_tip(self, user_id: int, target_date: Optional[date] = None) -> str:
        context = self._gather_history(user_id)
        system_prompt = (
            "You are a certified nutrition coach. Given a user's last 30 days of macro intake (ignore the 0 calories days; those indicate missing logs), "
            "and their most-used ingredients, provide one actionable Tip of the Day to improve dietary habits. "
            "Focus on practical, personalized advice grounded in macro trends and ingredient patterns (e.g., suggest swapping/refining frequent items). "
            "Respond in 1-2 paragraphs, friendly and professional. Do not start with 'tip of the day'."
        )
        previous_tips = self._get_previous_tips(user_id, limit=5)
        avoid = previous_tips[:]
        if target_date is not None:
            existing = self._get_tip_for_date(user_id, target_date)
            if existing:
                avoid.append(existing)
        payload = {**context, "previous_tips": avoid, "target_date": (target_date.isoformat() if target_date else None), "nonce": datetime.utcnow().isoformat()}
        try:
            # Log input
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            os.makedirs("logs", exist_ok=True)
            with open(f"logs/advice_{ts}.log", "w") as f:
                f.write(json.dumps(payload, indent=2))

            resp = self.client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps({
                        "history": context.get("history", []),
                        "top_ingredients": context.get("top_ingredients", []),
                        "note": "Do not repeat or restate any of the previous_tips; provide a different, fresh angle.",
                        "previous_tips": avoid,
                        "target_date": payload.get("target_date"),
                        "nonce": payload.get("nonce")
                    })},
                ],
                temperature=1.0,
            )
            tip = resp.choices[0].message.content.strip()
            return tip
        except Exception as e:
            # Fallback generic tip
            return "Aim for balanced meals with adequate protein, fiber, and healthy fats, and be consistent across the week."

    def upsert_tip_for_date(self, user_id: int, target_date: date) -> DailyAdvice:
        tip = self.generate_tip(user_id, target_date)
        row = DailyAdvice.query.filter_by(user_id=user_id, date=target_date).first()
        if row:
            row.advice = tip
            row.updated_at = datetime.utcnow()
            db.session.commit()
            return row
        row = DailyAdvice(user_id=user_id, date=target_date, advice=tip)
        db.session.add(row)
        db.session.commit()
        return row

    # Satisfy BaseAgent abstract interface; not used in workflow routing
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return state
