from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=150)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class RegisterV1Request(BaseModel):
    nickname: str = Field(..., min_length=2, max_length=80)
    password: str = Field(..., min_length=6, max_length=72)
    confirm_password: str = Field(..., min_length=6, max_length=72)

    @model_validator(mode='after')
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError('Parollar mos kelmadi.')
        self.nickname = self.nickname.strip()
        if len(self.nickname) < 2:
            raise ValueError('Taxallus kamida 2 ta belgidan iborat bo‘lishi kerak.')
        return self


class LoginV1Request(BaseModel):
    nickname: str = Field(..., min_length=2, max_length=80)
    password: str = Field(..., min_length=1, max_length=72)


class ResetPasswordRequest(BaseModel):
    nickname: str = Field(..., min_length=2, max_length=80)
    recovery_code: str = Field(..., min_length=13, max_length=13)
    new_password: str = Field(..., min_length=6, max_length=72)
    confirm_password: str = Field(..., min_length=6, max_length=72)

    @model_validator(mode='after')
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError('Parollar mos kelmadi.')
        self.nickname = self.nickname.strip()
        return self


class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    created_at: datetime


class UserV1Read(BaseModel):
    id: int
    nickname: str
    is_active: bool
    created_at: datetime


class AuthV1Response(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: UserV1Read


class RecoveryCodeResponse(BaseModel):
    recovery_code: str
    access_token: str
    token_type: str = 'bearer'
    user: UserV1Read


class PasswordResetResponse(BaseModel):
    recovery_code: str


class TranslationCreate(BaseModel):
    source_text: str = Field(..., min_length=1, max_length=5000)
    source_lang: str
    target_lang: str
    translated_text: str = Field(..., min_length=1, max_length=5000)


class TranslationRead(BaseModel):
    id: int
    user_id: int
    source_text: str
    source_lang: str
    target_lang: str
    translated_text: str
    created_at: datetime


class FavoriteCreate(BaseModel):
    translation_id: int


class UserSettingsUpdate(BaseModel):
    theme: Literal['light', 'dark'] = 'light'
    source_lang: Literal['uz', 'en', 'ko', 'tr'] = 'uz'
    target_lang: Literal['uz', 'en', 'ko', 'tr'] = 'en'
    translation_style: Literal['Oddiy', 'Rasmiy', 'Professional'] = 'Oddiy'


class UserSettingsRead(UserSettingsUpdate):
    updated_at: datetime | None = None


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class AIChatResponse(BaseModel):
    reply: str


class TranslationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    source_lang: str
    target_lang: str


class TranslationResponse(BaseModel):
    text: str
    source_lang: str
    target_lang: str
    translated_text: str


class TranslationV1Request(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    source_lang: Literal['auto', 'uz', 'en', 'ko', 'tr'] = 'auto'
    target_lang: Literal['uz', 'en', 'ko', 'tr']
    style: Literal['Oddiy', 'Rasmiy', 'Professional'] = 'Oddiy'


class TranslationV1Response(BaseModel):
    text: str
    source_lang: Literal['uz', 'en', 'ko', 'tr']
    target_lang: Literal['uz', 'en', 'ko', 'tr']
    translated_text: str
    style: Literal['Oddiy', 'Rasmiy', 'Professional']


class TranslationExplainRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    translated_text: str = Field(..., min_length=1, max_length=5000)
    source_lang: Literal['auto', 'uz', 'en', 'ko', 'tr'] = 'auto'
    target_lang: Literal['uz', 'en', 'ko', 'tr']
    style: Literal['Oddiy', 'Rasmiy', 'Professional'] = 'Oddiy'
    analysis_mode: Literal[
        "So'zma-so'z va Grammatik tahlil",
        '3 xil uslubda taqqoslash (Oddiy / Rasmiy / Professional)',
        "Talaffuz va O'qilishi (Transkripsiya)",
        'Sinonimlar va Muqobil iboralar',
        'Erkin savol-javob',
    ] | None = None
    question: str | None = Field(default=None, max_length=2000)


class TranslationExplainResponse(BaseModel):
    explanation: str
    source_lang: Literal['uz', 'en', 'ko', 'tr']
    target_lang: Literal['uz', 'en', 'ko', 'tr']
