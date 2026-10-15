import json
from types import SimpleNamespace

import pytest

from backend.app.services import translation_service


def test_vertex_express_sends_user_role_and_parses_content(monkeypatch):
    captured = {}

    def fake_post(url, *, params, json, timeout):
        captured.update(url=url, params=params, body=json, timeout=timeout)
        return SimpleNamespace(
            status_code=200,
            is_error=False,
            json=lambda: {
                'candidates': [{'content': {'parts': [{'text': '{"source_lang":"uz",'}, {'text': '"translated_text":"Hello"}'}]}}],
            },
        )

    monkeypatch.setattr(translation_service, 'GEMINI_API_KEY', 'AQ.test-key')
    monkeypatch.setattr(translation_service, 'GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setattr(translation_service.httpx, 'post', fake_post)

    result = translation_service._generate_content('translate me', json_response=True)

    assert result == '{"source_lang":"uz","translated_text":"Hello"}'
    assert captured['url'].endswith('/gemini-2.5-flash:generateContent')
    assert captured['params'] == {'key': 'AQ.test-key'}
    assert captured['body']['contents'] == [
        {'role': 'user', 'parts': [{'text': 'translate me'}]},
    ]
    assert captured['body']['generationConfig']['responseMimeType'] == 'application/json'


def test_vertex_express_retries_fallback_model_after_404(monkeypatch):
    called_urls = []

    def fake_post(url, **kwargs):
        called_urls.append(url)
        status_code = 404 if len(called_urls) == 1 else 200
        return SimpleNamespace(
            status_code=status_code,
            is_error=status_code >= 400,
            json=lambda: {'candidates': [{'content': {'parts': [{'text': 'fallback response'}]}}]},
        )

    monkeypatch.setattr(translation_service, 'GEMINI_API_KEY', 'AQ.test-key')
    monkeypatch.setattr(translation_service, 'GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setattr(translation_service.httpx, 'post', fake_post)

    assert translation_service._generate_content('prompt') == 'fallback response'
    assert called_urls == [
        f'{translation_service.VERTEX_EXPRESS_ENDPOINT}/gemini-2.5-flash:generateContent',
        f'{translation_service.VERTEX_EXPRESS_ENDPOINT}/gemini-2.0-flash:generateContent',
    ]


def test_vertex_express_does_not_fallback_for_non_404_errors(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(status_code=503, is_error=True)

    monkeypatch.setattr(translation_service, 'GEMINI_API_KEY', 'AQ.test-key')
    monkeypatch.setattr(translation_service, 'GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setattr(translation_service.httpx, 'post', fake_post)

    with pytest.raises(translation_service.GeminiServiceError, match='HTTP 503'):
        translation_service._generate_content('prompt')
    assert len(calls) == 1


def test_vertex_express_reports_project_permission_errors(monkeypatch):
    monkeypatch.setattr(translation_service, 'GEMINI_API_KEY', 'AQ.test-key')
    monkeypatch.setattr(
        translation_service.httpx,
        'post',
        lambda *args, **kwargs: SimpleNamespace(status_code=403, is_error=True),
    )

    with pytest.raises(translation_service.GeminiServiceError, match='Vertex AI API'):
        translation_service._generate_content('prompt')


@pytest.mark.parametrize('status_code', [403, 404, 429, 503])
def test_translation_falls_back_on_google_provider_statuses(monkeypatch, status_code):
    monkeypatch.setattr(
        translation_service,
        '_generate_content',
        lambda *args, **kwargs: (_ for _ in ()).throw(
            translation_service.GeminiServiceError('provider failed', status_code=status_code)
        ),
    )
    monkeypatch.setattr(
        translation_service,
        'google_translate',
        lambda text, source, target: {
            'source_lang': 'uz',
            'target_lang': target,
            'translated_text': 'Hello',
        },
    )

    assert translation_service.translate_translation('Salom', 'auto', 'en')['translated_text'] == 'Hello'


def test_google_translate_sends_language_and_text_parameters(monkeypatch):
    captured = {}

    def fake_get(url, *, params, timeout):
        captured.update(url=url, params=params, timeout=timeout)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: [[['Hel', 'Salom', None], ['lo', ' dunyo', None]], None, 'uz'],
        )

    monkeypatch.setattr(translation_service.httpx, 'get', fake_get)
    result = translation_service.google_translate('Salom', 'auto', 'en')

    assert result == {'source_lang': 'uz', 'target_lang': 'en', 'translated_text': 'Hello'}
    assert captured['url'] == translation_service.GOOGLE_TRANSLATE_ENDPOINT
    assert captured['params'] == {'client': 'gtx', 'sl': 'auto', 'tl': 'en', 'dt': 't', 'q': 'Salom'}


def test_translation_returns_uzbek_status_when_all_providers_fail(monkeypatch):
    def fail_provider(*args, **kwargs):
        raise translation_service.GeminiServiceError('unavailable', status_code=503)

    monkeypatch.setattr(translation_service, '_generate_content', fail_provider)
    monkeypatch.setattr(translation_service, 'google_translate', fail_provider)

    result = translation_service.translate_translation('hello', 'en', 'uz')
    assert result['translated_text'].startswith('Tarjima xizmati vaqtincha ishlamayapti.')
    assert 'hello' in result['translated_text']


def test_google_translate_rejects_malformed_response_without_index_error(monkeypatch):
    monkeypatch.setattr(
        translation_service.httpx,
        'get',
        lambda *args, **kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: None,
        ),
    )

    with pytest.raises(translation_service.GeminiServiceError, match='vaqtincha ishlamayapti'):
        translation_service.google_translate('Salom', 'uz', 'en')


def test_explanation_falls_back_to_uzbek_style_guidance(monkeypatch):
    monkeypatch.setattr(
        translation_service,
        '_generate_content',
        lambda *args, **kwargs: (_ for _ in ()).throw(
            translation_service.GeminiServiceError('provider unavailable', status_code=503)
        ),
    )
    result = translation_service.explain_translation(
        'Salom',
        'Hello',
        'uz',
        'en',
        'Professional',
    )

    assert result['source_lang'] == 'uz'
    assert 'Professional uslub' in result['explanation']
    assert 'Asosiy mazmun' in result['explanation']


def test_uzbek_preprocessing_restores_greeting_and_polite_suffixes():
    normalized = translation_service.normalize_uzbek_text(
        "Assalomu alaykum yaxshimisiz sog'lig'iz yaxshimi"
    )

    assert normalized == "Assalomu alaykum, Yaxshimisiz? Sog'lig'ingiz yaxshimi?"
    assert translation_service.normalize_uzbek_text('ishlariz qalesiz yaxshimis') == "ishlaringiz qalaysiz yaxshimisiz"
    assert translation_service.normalize_uzbek_text('sogligiz') == "sog'lig'ingiz"
    assert translation_service.normalize_uzbek_text('sog' + chr(0x2019) + 'lig' + chr(0x2018) + 'iz') == "sog'lig'ingiz"


def test_translation_fallback_keeps_greeting_and_enforces_turkish_politeness(monkeypatch):
    captured = {}

    def failed_gemini(*args, **kwargs):
        raise translation_service.GeminiServiceError('billing disabled', status_code=403)

    def fake_google(text, source, target):
        captured['text'] = text
        return {
            'source_lang': 'uz',
            'target_lang': target,
            'translated_text': 'Nasılsın? Sağlığın iyi mi?',
        }

    monkeypatch.setattr(translation_service, '_generate_content', failed_gemini)
    monkeypatch.setattr(translation_service, 'google_translate', fake_google)
    result = translation_service.translate_translation(
        "Assalomu alaykum yaxshimisiz sog'lig'iz yaxshimi",
        'auto',
        'tr',
        'Professional',
    )

    assert captured['text'] == "Assalomu alaykum, Yaxshimisiz? Sog'lig'ingiz yaxshimi?"
    assert result['translated_text'] == 'Selamün aleyküm, Nasılsınız? Sağlığınız iyi mi?'


def test_korean_translation_enforces_polite_and_formal_endings():
    polite = translation_service.enforce_polite_translation(
        '잘 지내? 건강해?',
        'yaxshimisiz',
        'uz',
        'ko',
        'Oddiy',
    )
    formal = translation_service.enforce_polite_translation(
        '잘 지내? 건강해?',
        'hello',
        'en',
        'ko',
        'Rasmiy',
    )

    assert polite == '잘 지내요? 건강해요?'
    assert formal == '잘 지내십니까? 건강하십니까?'


def test_fallback_explanation_contains_all_requested_sections(monkeypatch):
    monkeypatch.setattr(
        translation_service,
        '_generate_content',
        lambda *args, **kwargs: (_ for _ in ()).throw(
            translation_service.GeminiServiceError('billing disabled', status_code=403)
        ),
    )
    monkeypatch.setattr(
        translation_service,
        'google_translate',
        lambda text, source, target: {
            'source_lang': 'uz',
            'target_lang': target,
            'translated_text': 'hello' if text == 'salom' else 'hello there',
        },
    )

    result = translation_service.explain_translation(
        'Salom',
        'Hello',
        'uz',
        'ko',
        'Oddiy',
    )
    assert 'Asosiy ma’no va Kontekst' in result['explanation']
    assert 'So‘zma-so‘z tahlil' in result['explanation']
    assert '3 xil uslubdagi variantlar' in result['explanation']
    assert 'Talaffuz va O‘qilishi' in result['explanation']
    assert '- Oddiy:' in result['explanation']
    assert '- Rasmiy:' in result['explanation']
    assert '- Professional:' in result['explanation']


@pytest.mark.parametrize('target_lang', ['uz', 'en', 'ko', 'tr'])
@pytest.mark.parametrize('style', ['Oddiy', 'Rasmiy', 'Professional'])
def test_translation_uses_gemini_response_for_supported_languages_and_styles(monkeypatch, target_lang, style):
    calls = []

    def fake_generate(prompt, *, json_response=False):
        calls.append((prompt, json_response))
        return json.dumps({'source_lang': 'uz', 'translated_text': 'translated'})

    monkeypatch.setattr(translation_service, '_generate_content', fake_generate)
    result = translation_service.translate_translation('Salom', 'auto', target_lang, style)

    assert result == {
        'source_lang': 'uz',
        'target_lang': target_lang,
        'translated_text': 'translated',
    }
    assert calls[0][1] is True
    assert f'Translation style: {style}' in calls[0][0]


def test_explanation_requests_uzbek_and_resolves_auto_language(monkeypatch):
    captured_prompt = ''

    def fake_generate(prompt, *, json_response=False):
        nonlocal captured_prompt
        captured_prompt = prompt
        assert json_response is True
        return json.dumps({'source_lang': 'ko', 'explanation': 'Koreyscha tarjima izohi.'})

    monkeypatch.setattr(translation_service, '_generate_content', fake_generate)
    result = translation_service.explain_translation('안녕', 'Salom', 'auto', 'uz', 'Rasmiy')

    assert result == {'source_lang': 'ko', 'explanation': 'Koreyscha tarjima izohi.'}
    assert 'in Uzbek using Uzbek Latin script' in captured_prompt
    assert 'Translation style: Rasmiy' in captured_prompt
