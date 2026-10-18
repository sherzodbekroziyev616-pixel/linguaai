import pytest
from fastapi.testclient import TestClient

from backend.app import models
from backend.app.database import SessionLocal
from backend.app import main as main_module
from backend.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    db = SessionLocal()
    try:
        db.query(models.Favorite).delete()
        db.query(models.UserSettings).delete()
        db.query(models.Translation).delete()
        db.query(models.AIChatMessage).delete()
        db.query(models.RecoveryCodeHistory).delete()
        db.query(models.User).delete()
        db.commit()
    finally:
        db.close()


def test_healthcheck():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_cors_preflight_allows_authorized_frontend_requests():
    response = client.options(
        '/api/v1/auth/login',
        headers={
            'Origin': 'https://linguaai.vercel.app',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'authorization,content-type',
        },
    )

    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == '*'
    assert 'authorization' in response.headers['access-control-allow-headers'].lower()
    assert 'content-type' in response.headers['access-control-allow-headers'].lower()
    assert 'access-control-allow-credentials' not in response.headers


def test_register_and_login():
    payload = {
        'email': 'user@example.com',
        'full_name': 'Test Foydalanuvchi',
        'password': 'secret123',
    }
    response = client.post('/api/auth/register', json=payload)
    assert response.status_code == 200
    login_response = client.post('/api/auth/login', json={'email': payload['email'], 'password': payload['password']})
    assert login_response.status_code == 200
    assert 'access_token' in login_response.json()


def test_v1_registration_and_recovery_code_is_one_time():
    registration = client.post(
        '/api/v1/auth/register',
        json={'nickname': 'gulasal', 'password': 'secret123', 'confirm_password': 'secret123'},
    )
    assert registration.status_code == 200
    first_code = registration.json()['recovery_code']
    assert len(first_code) == 13
    assert first_code.startswith('LNG-')

    reset = client.post(
        '/api/v1/auth/reset-password',
        json={
            'nickname': 'gulasal',
            'recovery_code': first_code,
            'new_password': 'updated123',
            'confirm_password': 'updated123',
        },
    )
    assert reset.status_code == 200
    second_code = reset.json()['recovery_code']
    assert second_code != first_code

    reuse = client.post(
        '/api/v1/auth/reset-password',
        json={
            'nickname': 'gulasal',
            'recovery_code': first_code,
            'new_password': 'thirdpass123',
            'confirm_password': 'thirdpass123',
        },
    )
    assert reuse.status_code == 400

    login = client.post('/api/v1/auth/login', json={'nickname': 'gulasal', 'password': 'updated123'})
    assert login.status_code == 200
    next_reset = client.post(
        '/api/v1/auth/reset-password',
        json={
            'nickname': 'gulasal',
            'recovery_code': second_code,
            'new_password': 'thirdpass123',
            'confirm_password': 'thirdpass123',
        },
    )
    assert next_reset.status_code == 200


def test_v1_registration_rejects_password_mismatch():
    response = client.post(
        '/api/v1/auth/register',
        json={'nickname': 'gulasal', 'password': 'secret123', 'confirm_password': 'different'},
    )
    assert response.status_code == 422


def test_translate_endpoint_uses_translation_service(monkeypatch):
    monkeypatch.setattr(main_module, 'translate_text', lambda text, source, target: 'hello')
    response = client.post('/api/translate', json={'text': 'salom', 'source_lang': 'uz', 'target_lang': 'en'})
    assert response.status_code == 200
    assert response.json()['translated_text'] == 'hello'


def test_v1_translate_supports_auto_detection_and_style(monkeypatch):
    monkeypatch.setattr(
        main_module,
        'translate_translation',
        lambda text, source, target, style: {
            'source_lang': 'uz',
            'target_lang': target,
            'translated_text': 'Hello.',
        },
    )
    response = client.post(
        '/api/v1/translations',
        json={'text': 'Salom.', 'source_lang': 'auto', 'target_lang': 'en', 'style': 'Professional'},
    )
    assert response.status_code == 200
    assert response.json() == {
        'text': 'Salom.',
        'source_lang': 'uz',
        'target_lang': 'en',
        'translated_text': 'Hello.',
        'style': 'Professional',
    }


def test_v1_translation_explanation_is_returned(monkeypatch):
    monkeypatch.setattr(
        main_module,
        'explain_translation',
        lambda text, translated, source, target, style, analysis_mode, question: {
            'source_lang': 'uz',
            'explanation': 'Bu tarjima salomlashuv ma’nosini beradi.',
        },
    )
    response = client.post(
        '/api/v1/translations/explain',
        json={
            'text': 'Salom.',
            'translated_text': 'Hello.',
            'source_lang': 'uz',
            'target_lang': 'en',
            'style': 'Oddiy',
        },
    )
    assert response.status_code == 200
    assert response.json()['explanation'].startswith('Bu tarjima')


def test_v1_translation_uses_google_fallback_for_provider_errors(monkeypatch):
    monkeypatch.setattr(
        main_module,
        'translate_translation',
        lambda text, source, target, style: {
            'source_lang': 'uz',
            'target_lang': target,
            'translated_text': 'Hello!',
        },
    )
    response = client.post(
        '/api/v1/translations',
        json={'text': 'Salom!', 'source_lang': 'auto', 'target_lang': 'en', 'style': 'Oddiy'},
    )
    assert response.status_code == 200
    assert response.json()['translated_text'] == 'Hello!'


def test_history_favorites_settings_and_auth_endpoints_avoid_server_errors():
    registration = client.post(
        '/api/v1/auth/register',
        json={'nickname': 'functional-user', 'password': 'secret123', 'confirm_password': 'secret123'},
    )
    assert registration.status_code == 200
    token = registration.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    user_id = registration.json()['user']['id']

    db = SessionLocal()
    try:
        translation = models.Translation(
            user_id=user_id,
            source_text='Salom',
            source_lang='uz',
            target_lang='en',
            translated_text='Hello',
        )
        db.add(translation)
        db.commit()
        db.refresh(translation)
        translation_id = translation.id
    finally:
        db.close()

    assert client.get('/api/v1/history', headers=headers).status_code == 200
    favorite = client.post('/api/v1/favorites', headers=headers, json={'translation_id': translation_id})
    assert favorite.status_code == 200
    assert client.get('/api/v1/favorites', headers=headers).status_code == 200

    settings = client.get('/api/v1/settings', headers=headers)
    assert settings.status_code == 200
    updated = client.put(
        '/api/v1/settings',
        headers=headers,
        json={'theme': 'dark', 'source_lang': 'uz', 'target_lang': 'tr', 'translation_style': 'Professional'},
    )
    assert updated.status_code == 200
    assert updated.json()['theme'] == 'dark'

    assert client.post('/api/v1/auth/login', json={'nickname': 'functional-user', 'password': 'secret123'}).status_code == 200
    reset = client.post(
        '/api/v1/auth/reset-password',
        json={
            'nickname': 'functional-user',
            'recovery_code': registration.json()['recovery_code'],
            'new_password': 'updated123',
            'confirm_password': 'updated123',
        },
    )
    assert reset.status_code == 200


def test_unexpected_exceptions_return_safe_json():
    from fastapi.testclient import TestClient

    safe_client = TestClient(app, raise_server_exceptions=False)
    previous = main_module.translate_translation

    def fail_translation(*args, **kwargs):
        raise RuntimeError('internal detail must not leak')

    main_module.translate_translation = fail_translation
    try:
        response = safe_client.post(
            '/api/v1/translations',
            json={'text': 'hello', 'source_lang': 'en', 'target_lang': 'uz', 'style': 'Oddiy'},
        )
    finally:
        main_module.translate_translation = previous

    assert response.status_code == 500
    assert response.json() == {"detail": "Serverda kutilmagan holat yuz berdi. Iltimos, qayta urinib ko'ring."}
    assert 'internal detail' not in response.text


def test_frontend_spa_routes_are_served_when_build_exists():
    if not main_module.FRONTEND_INDEX.is_file():
        pytest.skip('Frontend distribution has not been built')

    root_response = client.get('/')
    static_index_response = client.get('/static/index.html')
    deep_link_response = client.get('/assistant')
    unknown_api_response = client.get('/api/v1/not-a-route')

    assert root_response.status_code == 200
    assert 'text/html' in root_response.headers['content-type']
    assert static_index_response.status_code == 200
    assert 'text/html' in static_index_response.headers['content-type']
    assert deep_link_response.status_code == 200
    assert 'text/html' in deep_link_response.headers['content-type']
    assert unknown_api_response.status_code == 404
