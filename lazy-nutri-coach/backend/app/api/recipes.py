from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..auth.auth import get_db, get_current_user
from ..db import models
from ..models.schemas import RecipeRequest
from ..services.agent import generate_recipes

router = APIRouter(prefix="/recipes", tags=["recipes"])

@router.post("/generate")
def gen_recipes(payload: RecipeRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    recipes = generate_recipes(payload.dietary, payload.target_calories, payload.time_limit_min, payload.available_ingredients)
    return {"recipes": recipes}
