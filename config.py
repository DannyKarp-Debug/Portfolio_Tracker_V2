"""
Application configuration loaded from environment variables.
Uses python-dotenv to read a .env file when present.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Central configuration object for the Flask application."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///portfolio.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
