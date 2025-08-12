from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..auth.auth import get_db, get_current_user
from ..db import models
from typing import Dict, List

router = APIRouter(prefix="/progress", tags=["progress"])

@router.get("/daily_macros")
def daily_macros(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    logs = db.query(models.FoodLog).filter(models.FoodLog.user_id == user.id).all()
    by_day = {}
    for l in logs:
        day = l.timestamp.date().isoformat()
        if day not in by_day:
            by_day[day] = {"calories":0.0, "protein":0.0, "carbs":0.0, "fat":0.0}
        for it in l.items_json:
            by_day[day]["calories"] += it.get("calories",0)
            by_day[day]["protein"] += it.get("protein",0)
            by_day[day]["carbs"] += it.get("carbs",0)
            by_day[day]["fat"] += it.get("fat",0)
    # to sorted list
    out = [{"day": d, **{k: round(v,1) for k,v in m.items()}} for d,m in sorted(by_day.items())]
    return {"days": out}
