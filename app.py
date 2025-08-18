#!/usr/bin/env python3
"""
Medical Chat Application - Main Application File
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import db
from config import config
from api import api_bp
from views import views_bp
import os
from initialize_ingredients import add_ingredients_to_db


def create_app(config_name=None):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Determine configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    app.config.from_object(config[config_name])
    
    # Set secret key for sessions
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Initialize extensions
    db.init_app(app)
    
    # Register blueprints
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    # Create database tables
    with app.app_context():
        db.create_all()
        add_ingredients_to_db()
    return app


# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 