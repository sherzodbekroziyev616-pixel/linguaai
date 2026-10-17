import os
from pathlib import Path

from sqlalchemy.engine import make_url
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

APP_NAME = os.getenv('APP_NAME', 'LinguaAI')
APP_ENV = os.getenv('ENVIRONMENT', os.getenv('APP_ENV', 'development'))
JWT_SECRET_KEY = os.getenv('SECRET_KEY', os.getenv('JWT_SECRET_KEY', 'dev-secret-key'))
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', '1440'))
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}",
)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
elif DATABASE_URL.startswith('sqlite'):
    database_url = make_url(DATABASE_URL)
    database_path = database_url.database
    if database_path and database_path != ':memory:':
        if not os.path.isabs(database_path):
            database_path = os.path.abspath(os.path.join(BASE_DIR, database_path))
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        DATABASE_URL = database_url.set(database=database_path).render_as_string(hide_password=False)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv('FRONTEND_ORIGIN', os.getenv('CORS_ORIGINS', 'http://localhost:5173')).split(',')
    if origin.strip()
]
CORS_ORIGIN_REGEX = r'^https?://([a-z0-9-]+\.)?(onrender\.com|vercel\.app)$'
