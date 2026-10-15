import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')

APP_NAME = os.getenv('APP_NAME', 'LinguaAI')
APP_ENV = os.getenv('ENVIRONMENT', os.getenv('APP_ENV', 'development'))
JWT_SECRET_KEY = os.getenv('SECRET_KEY', os.getenv('JWT_SECRET_KEY', 'dev-secret-key'))
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', '1440'))
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./backend/data/linguaai.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv('FRONTEND_ORIGIN', os.getenv('CORS_ORIGINS', 'http://localhost:5173')).split(',')
    if origin.strip()
]
CORS_ORIGIN_REGEX = r'^https?://([a-z0-9-]+\.)?(onrender\.com|vercel\.app)$'
