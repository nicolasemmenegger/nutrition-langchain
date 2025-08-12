from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..auth.auth import get_db, get_current_user
from ..db import models
from ..models.schemas import AdviceIn, AdviceOut
from ..services.agent import generate_advice

router = APIRouter(prefix="/advice", tags=["advice"])

@router.post("/generate", response_model=AdviceOut)
def gen_advice(payload: AdviceIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    # Pull last N days logs (simple: all)
    logs = db.query(models.FoodLog).filter(models.FoodLog.user_id == user.id).order_by(models.FoodLog.timestamp.desc()).all()
    goals = db.query(models.Goal).filter(models.Goal.user_id == user.id).first()
    text = generate_advice(user, logs, goals, payload.focus, payload.horizon_days)
    adv = models.Advice(user_id=user.id, text=text, meta_json={"focus": payload.focus, "horizon_days": payload.horizon_days})
    db.add(adv)
    db.commit()
    db.refresh(adv)
    return {"text": adv.text, "created_at": adv.created_at}
