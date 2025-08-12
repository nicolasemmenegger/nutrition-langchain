from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
from sqlalchemy import Integer, String, Float, ForeignKey, DateTime, Text, JSON, func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    display_name: Mapped[str] = mapped_column(String, default="User")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    logs: Mapped[list["FoodLog"]] = relationship(back_populates="user")

class FoodLog(Base):
    __tablename__ = "food_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    items_json: Mapped[dict] = mapped_column(JSON)  # [{name, grams, calories, protein, carbs, fat}]
    source: Mapped[str] = mapped_column(String, default="manual")  # manual|text|image
    meal_type: Mapped[str] = mapped_column(String, default="unspecified")  # breakfast|lunch|snacks|dinner

    user: Mapped["User"] = relationship(back_populates="logs")

class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    calories_target: Mapped[float] = mapped_column(Float, default=2000.0)
    protein_target: Mapped[float] = mapped_column(Float, default=120.0)
    carbs_target: Mapped[float] = mapped_column(Float, default=250.0)
    fat_target: Mapped[float] = mapped_column(Float, default=70.0)

class Advice(Base):
    __tablename__ = "advice"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    text: Mapped[str] = mapped_column(Text)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
