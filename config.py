#!/usr/bin/env python3
"""
Configuration for Medical Chat Application
"""

import os

class Config:
    """Base configuration class"""
    # Flask secret key for sessions and security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///./nutrition.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # OpenAI configuration
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    
    # Development settings
    DEBUG = os.environ.get('FLASK_ENV') == 'development'
    TESTING = False


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    # In production, ensure these are set via environment variables
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
} 