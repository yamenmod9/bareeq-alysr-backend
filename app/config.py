"""
Application Configuration
Supports both FastAPI and Flask settings
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration"""
    
    # Application
    APP_NAME = "Bareeq Al-Yusr"
    APP_VERSION = "1.0.0"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # Database (Flask-SQLAlchemy)
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", 
        "sqlite:///bareeq_alysr.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.getenv("SQL_ECHO", "False").lower() == "true"
    
    # JWT Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "bareeq-alysr-secret-key-change-in-production")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
    JWT_ACCESS_TOKEN_EXPIRE = timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS)
    
    # Business Rules
    DEFAULT_CREDIT_LIMIT = float(os.getenv("DEFAULT_CREDIT_LIMIT", "5000.0"))  # SAR
    MAX_CREDIT_LIMIT = float(os.getenv("MAX_CREDIT_LIMIT", "50000.0"))  # SAR
    AUTO_APPROVE_LIMIT_CEILING = float(os.getenv("AUTO_APPROVE_LIMIT", "5000.0"))  # SAR
    
    # Commission
    PLATFORM_COMMISSION_RATE = float(os.getenv("COMMISSION_RATE", "0.005"))  # 0.5%
    
    # Purchase Request Expiry
    PURCHASE_REQUEST_EXPIRY_HOURS = int(os.getenv("REQUEST_EXPIRY_HOURS", "24"))
    
    # Default Repayment Period (for single payment)
    DEFAULT_REPAYMENT_DAYS = int(os.getenv("DEFAULT_REPAYMENT_DAYS", "10"))
    
    # Available Repayment Plans (in months)
    REPAYMENT_PLANS = [1, 3, 6, 12, 18, 24]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT", "60"))


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_ECHO = False


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


def get_config():
    """Get configuration based on environment"""
    env = os.getenv("FLASK_ENV", "development")
    configs = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig
    }
    return configs.get(env, DevelopmentConfig)
