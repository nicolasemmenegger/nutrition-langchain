#!/usr/bin/env python3
"""
Database Models for Medical Chat Application
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import json

db = SQLAlchemy()


class User(db.Model):
    """User model for authentication and user management"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<User {self.username}>'

class Ingredient(db.Model):
    """Ingredient model for storing ingredients"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    calories = db.Column(db.Float, nullable=False)
    protein = db.Column(db.Float, nullable=False)
    carbs = db.Column(db.Float, nullable=False)
    fat = db.Column(db.Float, nullable=False)
    unit_weight = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Ingredient {self.name}>'

class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    ingredients = db.Column(db.JSON, nullable=False)
    meal_type = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Meal {self.name}>'

class MealNutrition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meal_id = db.Column(db.Integer, db.ForeignKey('meal.id'), nullable=False)
    calories = db.Column(db.Float, nullable=False)
    protein = db.Column(db.Float, nullable=False)
    carbs = db.Column(db.Float, nullable=False)
    fat = db.Column(db.Float, nullable=False)

class IngredientUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __repr__(self):
        return f'<IngredientUsage {self.ingredient_id} {self.meal_id} {self.quantity}>'

class ChatHistory(db.Model):
    """Model for storing chat history"""
    __tablename__ = 'chat_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)
    message_metadata = db.Column(db.Text)  # JSON string for additional data
    category = db.Column(db.String(50))  # Category of the request
    
    def __repr__(self):
        return f"<ChatHistory {self.id}: {self.user_id} - {self.role}>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metadata': json.loads(self.message_metadata) if self.message_metadata else None,
            'category': self.category
        }
    
    @classmethod
    def get_user_history(cls, user_id, limit=10):
        """Get chat history for a user"""
        return cls.query.filter_by(user_id=user_id)\
            .order_by(cls.timestamp.desc())\
            .limit(limit)\
            .all()
    
    @classmethod
    def save_message(cls, user_id, role, content, metadata=None, category=None):
        """Save a chat message"""
        message = cls(
            user_id=user_id,
            role=role,
            content=content,
            message_metadata=json.dumps(metadata) if metadata else None,
            category=category
        )
        db.session.add(message)
        db.session.commit()
        return message

    @classmethod
    def clear_user_history(cls, user_id):
        """Delete all chat messages for a user"""
        cls.query.filter_by(user_id=str(user_id)).delete()
        db.session.commit()