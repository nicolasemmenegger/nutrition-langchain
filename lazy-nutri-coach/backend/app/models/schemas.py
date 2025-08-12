from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None

class UserOut(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    class Config:
        from_attributes = True

class FoodItem(BaseModel):
    name: str
    grams: float = Field(..., ge=0)
    calories: float
    protein: float
    carbs: float
    fat: float
    unit: Optional[str] = None
    amount: Optional[float] = None

class FoodLogIn(BaseModel):
    items: List[FoodItem]
    source: Literal["manual", "text", "image"] = "manual"
    meal_type: Literal["breakfast", "lunch", "snacks", "dinner", "unspecified"] = "unspecified"
    timestamp: Optional[datetime] = None

class FoodLogOut(BaseModel):
    id: int
    items: List[FoodItem]
    source: str
    timestamp: datetime
    meal_type: str
    class Config:
        from_attributes = True

class FoodSearchOut(BaseModel):
    name: str
    calories: float
    protein: float
    carbs: float
    fat: float
    grams: float = 100.0

class GoalIn(BaseModel):
    calories_target: float
    protein_target: float
    carbs_target: float
    fat_target: float

class GoalOut(GoalIn):
    user_id: int

class AdviceIn(BaseModel):
    focus: Optional[str] = None  # e.g., "protein", "fiber", "hydration"
    horizon_days: int = 7

class AdviceOut(BaseModel):
    text: str
    created_at: datetime

class RecipeRequest(BaseModel):
    target_calories: Optional[int] = None
    dietary: Optional[str] = None  # e.g., "dairy-free", "vegetarian"
    time_limit_min: Optional[int] = None
    available_ingredients: Optional[List[str]] = None

# Payload returned when parsing text into items without logging yet
class ParsedItemsOut(BaseModel):
    items: List[FoodItem]

# Chat-based text logging
class ChatMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str

class TextChatIn(BaseModel):
    messages: List[ChatMessage]
    meal_type: Literal["breakfast", "lunch", "snacks", "dinner", "unspecified"] | None = None
    timestamp: Optional[datetime] = None

class TextChatOut(BaseModel):
    assistant_text: str
    items: List[FoodItem]
    needs_confirmation: bool
    logged: bool = False
    log: Optional[FoodLogOut] = None
