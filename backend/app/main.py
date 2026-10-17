from __future__ import annotations

import hashlib
import logging
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from . import models
from .auth import create_access_token, get_current_user_id, get_optional_user_id, get_password_hash, verify_password
from .config import APP_NAME, CORS_ORIGINS, CORS_ORIGIN_REGEX
from .database import Base, engine, ensure_schema_columns, get_db
from .schemas import (
    AIChatRequest,
    AIChatResponse,
    AuthV1Response,
    FavoriteCreate,
    LoginV1Request,
    PasswordResetResponse,
    RecoveryCodeResponse,
    RegisterV1Request,
    ResetPasswordRequest,
    Token,
    TranslationCreate,
    TranslationExplainRequest,
    TranslationExplainResponse,
    TranslationRequest,
    TranslationResponse,
    TranslationV1Request,
    TranslationV1Response,
    UserSettingsRead,
    UserSettingsUpdate,
    UserCreate,
    UserLogin,
    UserRead,
)
from .services.translation_service import (
    GeminiServiceError,
    explain_translation,
    translate_text,
    translate_translation,
)

Base.metadata.create_all(bind=engine)
ensure_schema_columns(Base)

app = FastAPI(title=APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ['*'],
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / 'frontend' / 'dist'
FRONTEND_INDEX = FRONTEND_DIST / 'index.html'


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
    logger.error(
        'Database operation failed for %s %s (%s)',
        request.method,
        request.url.path,
        type(error).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={'detail': 'Ma’lumotlar bazasida vaqtinchalik xatolik yuz berdi. Qayta urinib ko‘ring.'},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    logger.error(
        'Unexpected server error for %s %s (%s)',
        request.method,
        request.url.path,
        type(error).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Serverda kutilmagan holat yuz berdi. Iltimos, qayta urinib ko'ring."},
    )


def _commit_or_raise_validation(
    db: Session,
    detail: str = 'So‘rovdagi ma’lumotlar bilan yozib bo‘lmadi.',
) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from error
    except SQLAlchemyError as error:
        db.rollback()
        logger.error('Database write failed (%s)', type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Ma’lumotlarni saqlab bo‘lmadi. Kiritilgan qiymatlarni tekshiring.',
        ) from error


@app.get('/', response_model=None)
def read_root():
    if FRONTEND_INDEX.is_file():
        return FileResponse(FRONTEND_INDEX)
    return {'app': APP_NAME, 'status': 'ok'}


@app.get('/api/health')
def health_check() -> dict:
    return {'status': 'ok'}


def _hash_recovery_code(recovery_code: str) -> str:
    return hashlib.sha256(recovery_code.encode('utf-8')).hexdigest()


def _new_recovery_code(db: Session) -> tuple[str, str]:
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    for _ in range(100):
        code = f"LNG-{''.join(secrets.choice(alphabet) for _ in range(4))}-{''.join(secrets.choice(alphabet) for _ in range(4))}"
        code_hash = _hash_recovery_code(code)
        exists = db.query(models.RecoveryCodeHistory).filter(
            models.RecoveryCodeHistory.recovery_code_hash == code_hash
        ).first()
        if not exists:
            return code, code_hash
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail='Tiklash kodi yaratilmadi. Qayta urinib ko‘ring.',
    )


def _record_recovery_code(db: Session, user: models.User, code_hash: str) -> None:
    user.recovery_code_hash = code_hash
    db.add(models.RecoveryCodeHistory(user_id=user.id, recovery_code_hash=code_hash))


@app.post('/api/v1/auth/register', response_model=RecoveryCodeResponse)
def register_user_v1(payload: RegisterV1Request, db: Session = Depends(get_db)) -> RecoveryCodeResponse:
    nickname = payload.nickname.strip()
    existing = db.query(models.User).filter(
        (models.User.nickname.ilike(nickname))
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Bu taxallus band.')

    user = models.User(
        nickname=nickname,
        email=f'{nickname.casefold()}@nickname.linguaai.local',
        full_name=nickname,
        password_hash=get_password_hash(payload.password),
    )
    try:
        db.add(user)
        db.flush()
        recovery_code, code_hash = _new_recovery_code(db)
        _record_recovery_code(db, user, code_hash)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Bu taxallus band.') from error
    except SQLAlchemyError as error:
        db.rollback()
        logger.error('Registration write failed (%s)', type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Hisob yaratib bo‘lmadi. Kiritilgan ma’lumotlarni tekshiring.',
        ) from error
    _commit_or_raise_validation(db, 'Bu taxallus band.')
    db.refresh(user)
    return {
        'recovery_code': recovery_code,
        'access_token': create_access_token(str(user.id)),
        'token_type': 'bearer',
        'user': user,
    }


@app.post('/api/v1/auth/login', response_model=AuthV1Response)
def login_user_v1(payload: LoginV1Request, db: Session = Depends(get_db)) -> AuthV1Response:
    user = db.query(models.User).filter(models.User.nickname.ilike(payload.nickname.strip())).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Taxallus yoki parol noto‘g‘ri.',
        )
    if not user.nickname:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Bu hisob yangi kirish tizimini qo‘llamaydi.')
    return {
        'access_token': create_access_token(str(user.id)),
        'token_type': 'bearer',
        'user': user,
    }


@app.post('/api/v1/auth/reset-password', response_model=PasswordResetResponse)
def reset_password_v1(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> PasswordResetResponse:
    user = db.query(models.User).filter(models.User.nickname.ilike(payload.nickname.strip())).first()
    supplied_hash = _hash_recovery_code(payload.recovery_code.strip().upper())
    if not user or not user.recovery_code_hash or not secrets.compare_digest(user.recovery_code_hash, supplied_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Taxallus yoki tiklash kodi noto‘g‘ri yoki kod avval ishlatilgan.',
        )

    new_code, new_hash = _new_recovery_code(db)
    try:
        updated = (
            db.query(models.User)
            .filter(
                models.User.id == user.id,
                models.User.recovery_code_hash == supplied_hash,
            )
            .update(
                {
                    models.User.password_hash: get_password_hash(payload.new_password),
                    models.User.recovery_code_hash: new_hash,
                },
                synchronize_session=False,
            )
        )
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception('Password reset update failed')
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Parolni tiklab bo‘lmadi. Qayta urinib ko‘ring.',
        ) from error
    if updated != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Tiklash kodi noto‘g‘ri yoki avval ishlatilgan.',
        )
    db.add(models.RecoveryCodeHistory(user_id=user.id, recovery_code_hash=new_hash))
    _commit_or_raise_validation(db, 'Parolni tiklash ma’lumotlari bilan ziddiyat yuz berdi.')
    return {'recovery_code': new_code}


@app.post('/api/auth/register', response_model=UserRead)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    existing = db.query(models.User).filter(models.User.email == user_data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Bu elektron pochta allaqachon ro\'yxatdan o\'tgan.')

    user = models.User(
        email=user_data.email.lower(),
        full_name=user_data.full_name.strip(),
        password_hash=get_password_hash(user_data.password),
    )
    db.add(user)
    _commit_or_raise_validation(db, 'Bu elektron pochta allaqachon ro‘yxatdan o‘tgan.')
    db.refresh(user)
    return user


@app.post('/api/auth/login', response_model=Token)
def login_user(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = db.query(models.User).filter(models.User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Noto\'g\'ri elektron pochta yoki parol.')

    access_token = create_access_token(str(user.id))
    return {'access_token': access_token, 'token_type': 'bearer'}


@app.get('/api/auth/me', response_model=UserRead)
def get_current_user_profile(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)) -> UserRead:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Foydalanuvchi topilmadi.')
    return user


@app.post('/api/translate', response_model=TranslationResponse)
def translate_text_endpoint(payload: TranslationRequest) -> TranslationResponse:
    translated_text = payload.text if payload.source_lang == payload.target_lang else translate_text(payload.text, payload.source_lang, payload.target_lang)
    return {
        'text': payload.text,
        'source_lang': payload.source_lang,
        'target_lang': payload.target_lang,
        'translated_text': translated_text,
    }


@app.post('/api/v1/translations', response_model=TranslationV1Response)
def create_translation_v1(payload: TranslationV1Request) -> TranslationV1Response:
    try:
        result = translate_translation(
            payload.text,
            payload.source_lang,
            payload.target_lang,
            payload.style,
        )
    except GeminiServiceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return {
        'text': payload.text,
        **result,
        'style': payload.style,
    }


@app.post('/api/v1/translations/explain', response_model=TranslationExplainResponse)
def explain_translation_v1(payload: TranslationExplainRequest) -> TranslationExplainResponse:
    try:
        result = explain_translation(
            payload.text,
            payload.translated_text,
            payload.source_lang,
            payload.target_lang,
            payload.style,
            payload.analysis_mode,
            payload.question,
        )
    except GeminiServiceError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return {
        'explanation': result['explanation'],
        'source_lang': result['source_lang'],
        'target_lang': payload.target_lang,
    }


@app.post('/api/translations', response_model=TranslationResponse)
def create_translation(payload: TranslationCreate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    result = translate_text(payload.source_text, payload.source_lang, payload.target_lang)
    item = models.Translation(
        user_id=user_id,
        source_text=payload.source_text,
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        translated_text=result,
    )
    db.add(item)
    _commit_or_raise_validation(db, 'Tarjima tarixga saqlanmadi.')
    db.refresh(item)
    return {
        'text': payload.source_text,
        'source_lang': payload.source_lang,
        'target_lang': payload.target_lang,
        'translated_text': result,
    }


@app.get('/api/translations', response_model=list[TranslationResponse])
def list_translations(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    items = db.query(models.Translation).filter(models.Translation.user_id == user_id).order_by(models.Translation.id.desc()).all()
    return [
        {
            'text': item.source_text,
            'source_lang': item.source_lang,
            'target_lang': item.target_lang,
            'translated_text': item.translated_text,
        }
        for item in items
    ]


@app.get('/api/v1/history', response_model=list[TranslationResponse])
def list_translation_history_v1(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return list_translations(db, user_id)


@app.get('/api/v1/favorites', response_model=list[TranslationResponse])
def list_favorites_v1(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return list_favorites(db, user_id)


@app.post('/api/v1/favorites', response_model=dict)
def create_favorite_v1(
    payload: FavoriteCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return create_favorite(payload, db, user_id)


def _get_or_create_settings(db: Session, user_id: int) -> models.UserSettings:
    settings = db.query(models.UserSettings).filter(models.UserSettings.user_id == user_id).first()
    if settings:
        return settings
    settings = models.UserSettings(user_id=user_id)
    db.add(settings)
    _commit_or_raise_validation(db, 'Foydalanuvchi sozlamalarini yaratib bo‘lmadi.')
    db.refresh(settings)
    return settings


@app.get('/api/v1/settings', response_model=UserSettingsRead)
def get_user_settings(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return _get_or_create_settings(db, user_id)


@app.put('/api/v1/settings', response_model=UserSettingsRead)
@app.post('/api/v1/settings', response_model=UserSettingsRead)
def update_user_settings(
    payload: UserSettingsUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    settings = _get_or_create_settings(db, user_id)
    settings.theme = payload.theme
    settings.source_lang = payload.source_lang
    settings.target_lang = payload.target_lang
    settings.translation_style = payload.translation_style
    _commit_or_raise_validation(db, 'Sozlamalarni saqlab bo‘lmadi.')
    db.refresh(settings)
    return settings


@app.post('/api/favorites', response_model=dict)
def create_favorite(payload: FavoriteCreate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    existing = db.query(models.Favorite).filter(models.Favorite.user_id == user_id, models.Favorite.translation_id == payload.translation_id).first()
    if existing:
        return {'status': 'exists'}

    favorite = models.Favorite(user_id=user_id, translation_id=payload.translation_id)
    db.add(favorite)
    _commit_or_raise_validation(db, 'Bu tarjimani sevimlilarga qo‘shib bo‘lmadi.')
    return {'status': 'created'}


@app.get('/api/favorites', response_model=list[TranslationResponse])
def list_favorites(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    items = (
        db.query(models.Translation)
        .join(models.Favorite, models.Favorite.translation_id == models.Translation.id)
        .filter(models.Favorite.user_id == user_id)
        .order_by(models.Translation.id.desc())
        .all()
    )
    return [
        {
            'text': item.source_text,
            'source_lang': item.source_lang,
            'target_lang': item.target_lang,
            'translated_text': item.translated_text,
        }
        for item in items
    ]


@app.post('/api/ai/chat', response_model=AIChatResponse)
def ai_chat(payload: AIChatRequest, db: Session = Depends(get_db), user_id: int | None = Depends(get_optional_user_id)):
    reply = translate_text(payload.message, 'en', 'uz')
    if user_id is not None:
        db.add(models.AIChatMessage(user_id=user_id, role='user', content=payload.message))
        db.add(models.AIChatMessage(user_id=user_id, role='assistant', content=reply))
        _commit_or_raise_validation(db, 'AI suhbatini tarixga saqlab bo‘lmadi.')
    return {'reply': reply}


@app.get('/api/ai/history')
def get_ai_history(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    items = db.query(models.AIChatMessage).filter(models.AIChatMessage.user_id == user_id).order_by(models.AIChatMessage.id.desc()).all()
    return {'messages': [{'role': item.role, 'content': item.content} for item in items]}


if (FRONTEND_DIST / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=FRONTEND_DIST / 'assets'), name='frontend-assets')


@app.get('/{full_path:path}', response_model=None, include_in_schema=False)
def serve_frontend(full_path: str):
    if full_path == 'api' or full_path.startswith('api/'):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='API yo‘li topilmadi.')
    if FRONTEND_INDEX.is_file():
        requested_file = (FRONTEND_DIST / full_path).resolve()
        if requested_file.is_relative_to(FRONTEND_DIST.resolve()) and requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(FRONTEND_INDEX)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Sahifa topilmadi.')
