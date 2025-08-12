from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from ..auth.auth import get_db, get_current_user
from ..db import models
from ..models.schemas import (
    FoodItem,
    FoodLogIn,
    FoodLogOut,
    FoodSearchOut,
    ParsedItemsOut,
    TextChatIn,
    TextChatOut,
)
from ..services import nutrition, vision
from ..config import settings
import os, base64, json
from typing import List, Optional
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/foods", tags=["foods"])

def _calc_items(items_spec: List[dict]) -> List[dict]:
    out = []
    for it in items_spec:
        name = it.get("name", "").strip()
        # support unit-based inputs
        if it.get("unit") and it.get("amount") is not None:
            g = nutrition.convert_to_grams(name, float(it.get("amount")), it.get("unit"))
            grams = float(g or 0)
        else:
            grams = float(it.get("grams", 0))
        computed = nutrition.compute_from_grams(name, grams)
        if not computed:
            # unknown; keep grams, zero macros
            computed = {"name": name, "grams": grams, "calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
        out.append(computed)
    return out

@router.post("/log", response_model=FoodLogOut)
def log_food(payload: FoodLogIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    items = _calc_items([it.model_dump() for it in payload.items])
    ts = payload.timestamp or datetime.now(timezone.utc)
    entry = models.FoodLog(user_id=user.id, items_json=items, source=payload.source, meal_type=payload.meal_type, timestamp=ts)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "items": items, "source": entry.source, "timestamp": entry.timestamp, "meal_type": entry.meal_type}

@router.post("/parse_text_draft", response_model=ParsedItemsOut)
def parse_text_draft(text: str = Form(...), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    Use OpenAI (if configured) to parse free-text into items with estimated grams.
    Does NOT persist a log entry; returns computed items so the client can confirm/edit.
    """
    try:
        items = vision.llm_parse_text(text)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    computed = _calc_items(items)
    return {"items": computed}

@router.post("/parse_text", response_model=FoodLogOut)
def parse_text(text: str = Form(...), meal_type: Optional[str] = Form(None), timestamp: Optional[str] = Form(None), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    Backwards-compatible endpoint that parses and immediately logs. Optional meal_type/timestamp supported.
    Prefer using /parse_text_draft on the client followed by /foods/log after confirmation.
    """
    try:
        items = vision.llm_parse_text(text)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    items = _calc_items(items)
    ts = None
    if timestamp:
        try:
            ts = datetime.fromisoformat(timestamp)
        except Exception:
            try:
                # Handle trailing Z
                ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except Exception:
                ts = None
    entry = models.FoodLog(
        user_id=user.id,
        items_json=items,
        source="text",
        meal_type=meal_type or "unspecified",
        timestamp=ts or datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "items": items, "source": entry.source, "timestamp": entry.timestamp, "meal_type": entry.meal_type}

@router.post("/parse_image", response_model=FoodLogOut)
def parse_image(file: UploadFile = File(...), hint: str = Form(None), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="Image parsing requires OpenAI API key")
    os.makedirs(settings.uploads_dir, exist_ok=True)
    saved = os.path.join(settings.uploads_dir, file.filename)
    with open(saved, "wb") as f:
        f.write(file.file.read())
    with open(saved, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    items = vision.llm_parse_image(b64, hint_text=hint)
    items = _calc_items(items)
    entry = models.FoodLog(user_id=user.id, items_json=items, source="image")
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "items": items, "source": entry.source, "timestamp": entry.timestamp, "meal_type": entry.meal_type}

@router.post("/text_chat", response_model=TextChatOut)
def text_chat(payload: TextChatIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    Conduct a chat with the model. If the model returns structured items JSON, we consider it ready to log; otherwise, we return assistant_text for another turn.
    The client can send multiple turns until confirmation.
    """
    # Convert to model message format
    messages = [{"role": m.role, "content": m.content} for m in payload.messages]
    try:
        assistant_text, raw_items = vision.llm_text_chat(messages)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    computed_items = _calc_items(raw_items) if raw_items else []
    if computed_items:
        # We consider this confirmed if the last user message contained an explicit confirmation, else ask confirm
        last_user = next((m for m in reversed(payload.messages) if m.role == 'user'), None)
        confirmed = bool(last_user and any(x in last_user.content.lower() for x in ["yes", "confirm", "looks right", "ok"]))
        if confirmed:
            ts = payload.timestamp or datetime.now(timezone.utc)
            entry = models.FoodLog(
                user_id=user.id,
                items_json=computed_items,
                source="text",
                meal_type=payload.meal_type or "unspecified",
                timestamp=ts,
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)
            return TextChatOut(
                assistant_text=assistant_text,
                items=computed_items, needs_confirmation=False, logged=True,
                log={"id": entry.id, "items": computed_items, "source": entry.source, "timestamp": entry.timestamp, "meal_type": entry.meal_type}
            )
        else:
            return TextChatOut(assistant_text=assistant_text, items=computed_items, needs_confirmation=True, logged=False, log=None)
    else:
        # No items yet, another clarification turn
        return TextChatOut(assistant_text=assistant_text, items=[], needs_confirmation=True, logged=False, log=None)

@router.get("/history", response_model=List[FoodLogOut])
def history(
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    q = db.query(models.FoodLog).filter(models.FoodLog.user_id == user.id)
    if start:
        q = q.filter(models.FoodLog.timestamp >= start)
    if end:
        q = q.filter(models.FoodLog.timestamp < end)
    logs = q.order_by(models.FoodLog.timestamp.desc()).limit(500).all()
    out = []
    for e in logs:
        out.append({"id": e.id, "items": e.items_json, "source": e.source, "timestamp": e.timestamp, "meal_type": e.meal_type})
    return out

@router.delete("/log/{log_id}")
def delete_log(log_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    e = db.get(models.FoodLog, log_id)
    if not e or e.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(e)
    db.commit()
    return {"ok": True}

@router.get("/search", response_model=List[FoodSearchOut])
def search_foods(q: str, limit: int = 10):
    ql = q.strip().lower()
    rows = []
    for row in nutrition.load_foods():
        if ql in row["name"].lower():
            rows.append({
                "name": row["name"],
                "calories": row["calories"],
                "protein": row["protein"],
                "carbs": row["carbs"],
                "fat": row["fat"],
                "grams": 100.0,
            })
            if len(rows) >= limit:
                break
    return rows

@router.get("/units")
def get_units(name: str):
    return nutrition.allowed_units(name)
