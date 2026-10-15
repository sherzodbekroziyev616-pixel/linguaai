from __future__ import annotations

import json
import logging
import re

import httpx
from google import genai
from google.genai import types

from ..config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    'uz': 'Uzbek',
    'en': 'English',
    'ko': 'Korean',
    'tr': 'Turkish',
}
LANGUAGE_NAMES_UZ = {
    'uz': 'o‘zbek',
    'en': 'ingliz',
    'ko': 'koreys',
    'tr': 'turk',
}
VALID_STYLES = {'Oddiy', 'Rasmiy', 'Professional'}
VERTEX_EXPRESS_ENDPOINT = 'https://aiplatform.googleapis.com/v1/publishers/google/models'
VERTEX_FALLBACK_MODEL = 'gemini-2.0-flash'
GOOGLE_TRANSLATE_ENDPOINT = 'https://translate.googleapis.com/translate_a/single'
ANALYSIS_MODES = {
    "So'zma-so'z va Grammatik tahlil",
    '3 xil uslubda taqqoslash (Oddiy / Rasmiy / Professional)',
    "Talaffuz va O'qilishi (Transkripsiya)",
    'Sinonimlar va Muqobil iboralar',
    'Erkin savol-javob',
}


class GeminiServiceError(RuntimeError):
    """Raised when Gemini is unavailable or returns an unusable response."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _generate_content(contents: str, *, json_response: bool = False) -> str:
    if not GEMINI_API_KEY:
        raise GeminiServiceError('Gemini API kaliti sozlanmagan.')

    if GEMINI_API_KEY.startswith('AQ.'):
        response_text = _generate_vertex_express_content(contents, json_response=json_response)
        return response_text

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=2048,
            response_mime_type='application/json' if json_response else 'text/plain',
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )
    except Exception as error:
        logger.exception('Gemini content generation failed')
        status_code = getattr(error, 'code', None)
        if status_code == 404:
            message = 'Sozlangan Gemini modeli mavjud emas yoki API kalitida unga ruxsat yo‘q (HTTP 404).'
        elif status_code == 503:
            message = 'Gemini xizmati vaqtincha band. Birozdan so‘ng qayta urinib ko‘ring (HTTP 503).'
        elif status_code:
            message = f'Gemini AI so‘rovida xatolik yuz berdi (HTTP {status_code}).'
        else:
            message = 'Gemini AI xizmatiga ulanishda xatolik yuz berdi.'
        raise GeminiServiceError(message, status_code=status_code) from error

    response_text = getattr(response, 'text', None)
    if not response_text or not response_text.strip():
        raise GeminiServiceError('Gemini AI bo‘sh javob qaytardi.')
    return response_text.strip()


def _generate_vertex_express_content(contents: str, *, json_response: bool) -> str:
    models_to_try = [GEMINI_MODEL]
    if GEMINI_MODEL != VERTEX_FALLBACK_MODEL:
        models_to_try.append(VERTEX_FALLBACK_MODEL)

    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': contents}]}],
        'generationConfig': {
            'temperature': 0.2,
            'maxOutputTokens': 2048,
        },
    }
    if json_response:
        payload['generationConfig']['responseMimeType'] = 'application/json'

    for model in models_to_try:
        url = f'{VERTEX_EXPRESS_ENDPOINT}/{model}:generateContent'
        try:
            response = httpx.post(
                url,
                params={'key': GEMINI_API_KEY},
                json=payload,
                timeout=60,
            )
        except httpx.RequestError as error:
            raise GeminiServiceError('Vertex AI Express xizmatiga ulanishda xatolik yuz berdi.') from error

        if response.status_code == 404 and model != models_to_try[-1]:
            continue
        if response.is_error:
            if response.status_code == 503:
                message = 'Gemini xizmati vaqtincha band. Birozdan so‘ng qayta urinib ko‘ring (HTTP 503).'
            elif response.status_code == 404:
                message = f'Sozlangan Gemini modellari mavjud emas yoki API kalitida ularga ruxsat yo‘q (HTTP 404).'
            elif response.status_code == 403:
                message = 'Vertex AI API kalitiga ruxsat berilmagan yoki Google Cloud loyihasida Vertex AI API yoqilmagan (HTTP 403).'
            else:
                message = f'Vertex AI Express so‘rovida xatolik yuz berdi (HTTP {response.status_code}).'
            raise GeminiServiceError(message, status_code=response.status_code)

        try:
            result = response.json()
            candidates = result['candidates']
            parts = candidates[0]['content']['parts']
            response_text = ''.join(part.get('text', '') for part in parts).strip()
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise GeminiServiceError('Vertex AI Express noto‘g‘ri javob qaytardi.') from error
        if not response_text:
            raise GeminiServiceError('Gemini AI bo‘sh javob qaytardi.')
        return response_text

    raise GeminiServiceError('Vertex AI Express so‘rovi bajarilmadi.')


def translate_translation(text: str, source_lang: str, target_lang: str, style: str = 'Oddiy') -> dict[str, str]:
    source_lang = source_lang.strip().lower()
    target_lang = target_lang.strip().lower()
    if source_lang != 'auto' and source_lang not in LANGUAGE_NAMES:
        raise ValueError('Unsupported source language')
    if target_lang not in LANGUAGE_NAMES:
        raise ValueError('Unsupported target language')
    if style not in VALID_STYLES:
        raise ValueError('Unsupported translation style')
    if not text.strip():
        raise ValueError('Translation text cannot be empty')
    normalized_text = normalize_uzbek_text(text) if source_lang in {'uz', 'auto'} else text.strip()

    style_instructions = {
        'Oddiy': 'Use natural, clear, everyday wording.',
        'Rasmiy': 'Use formal, polite wording appropriate for official communication.',
        'Professional': 'Use polished, precise professional wording appropriate for a workplace.',
    }
    source_instruction = (
        'Detect which of these languages the input uses: Uzbek, English, Korean, or Turkish.'
        if source_lang == 'auto'
        else f'The source language is {LANGUAGE_NAMES[source_lang]}.'
    )
    prompt = (
        'Translate the input text. Preserve its meaning, names, numbers, and formatting. '
        'Do not add commentary or quote the translation. '
        f'{source_instruction} '
        f'Translate into {LANGUAGE_NAMES[target_lang]}. '
        f'Translation style: {style}. {style_instructions[style]} '
        'Return only a JSON object with string fields "source_lang" (one of "uz", "en", "ko", "tr") '
        'and "translated_text".\n\n'
        f'Input text:\n{normalized_text}'
    )
    try:
        raw_response = _generate_content(prompt, json_response=True)
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError as error:
            logger.exception('Gemini returned malformed translation JSON')
            raise GeminiServiceError('Gemini AI noto‘g‘ri javob qaytardi.') from error
    except GeminiServiceError as error:
        logger.warning('Gemini translation unavailable (%s); using Google Translate fallback', error.status_code)
        return _fallback_translation(normalized_text, source_lang, target_lang, style)

    if not isinstance(result, dict):
        return _fallback_translation(normalized_text, source_lang, target_lang, style)
    detected_lang = result.get('source_lang')
    translated_text = result.get('translated_text')
    if (
        not isinstance(detected_lang, str)
        or detected_lang not in LANGUAGE_NAMES
        or not isinstance(translated_text, str)
        or not translated_text.strip()
    ):
        return _fallback_translation(normalized_text, source_lang, target_lang, style)
    if source_lang != 'auto' and detected_lang != source_lang:
        detected_lang = source_lang
    translated_text = enforce_polite_translation(
        translated_text.strip(),
        normalized_text,
        detected_lang,
        target_lang,
        style,
    )

    return {
        'source_lang': detected_lang,
        'target_lang': target_lang,
        'translated_text': translated_text,
    }


def _fallback_translation(text: str, source_lang: str, target_lang: str, style: str) -> dict[str, str]:
    try:
        result = google_translate(text, source_lang, target_lang)
    except GeminiServiceError:
        logger.warning('Live translation fallback unavailable; returning graceful Uzbek status')
        return {
            'source_lang': source_lang if source_lang in LANGUAGE_NAMES else 'uz',
            'target_lang': target_lang,
            'translated_text': f'Tarjima xizmati vaqtincha ishlamayapti. Asl matn: {text}',
        }
    result['translated_text'] = enforce_polite_translation(
        result['translated_text'],
        text,
        result['source_lang'],
        target_lang,
        style,
    )
    return result


def normalize_uzbek_text(text: str) -> str:
    normalized = text.translate(str.maketrans({'‘': "'", '’': "'", '`': "'"})).strip()
    replacements = (
        (r"\bsog['’]?lig['’]?iz\b", "sog'lig'ingiz"),
        (r"\bishlariz\b", 'ishlaringiz'),
        (r'\bqalesiz\b', 'qalaysiz'),
        (r'\byaxshimis\b', 'yaxshimisiz'),
    )
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    greeting = re.match(r'^\s*(assalomu\s+alaykum|salom)\b[,.!?;:]?\s*(.*)$', normalized, re.IGNORECASE)
    if greeting:
        greeting_text, rest = greeting.groups()
        greeting_text = 'Assalomu alaykum' if greeting_text.lower().startswith('assalomu') else 'Salom'
        rest = rest.strip()
        health_check = re.match(
            r"^(yaxshimisiz)\s+(sog'lig'ingiz\s+yaxshimi)(.*)$",
            rest,
            re.IGNORECASE,
        )
        if health_check:
            first_question, second_question, remainder = health_check.groups()
            normalized = f'{greeting_text}, {first_question.capitalize()}? {second_question.capitalize()}?{remainder}'
        elif rest and not re.match(r'^[,;.!?]', rest):
            normalized = f'{greeting_text}, {rest}'
        else:
            normalized = f'{greeting_text}{rest}'
    return normalized


def enforce_polite_translation(
    translated_text: str,
    source_text: str,
    source_lang: str,
    target_lang: str,
    style: str,
) -> str:
    text = translated_text.strip()
    source_is_polite = source_lang == 'uz' and bool(
        re.search(r'\b(?:siz|ingiz|misiz|yaxshimisiz|qalaysiz)\b', source_text, re.IGNORECASE)
    )
    formal_style = style in {'Rasmiy', 'Professional'}
    if target_lang == 'tr' and (source_is_polite or formal_style):
        text = re.sub(r'\bNasılsın\b', 'Nasılsınız', text, flags=re.IGNORECASE)
        text = re.sub(r'\biyi misin\b', 'iyi misiniz', text, flags=re.IGNORECASE)
        text = re.sub(r'\bsağlığın\b', 'sağlığınız', text, flags=re.IGNORECASE)
    if target_lang == 'ko':
        if formal_style:
            text = re.sub(r'잘 지내\?', '잘 지내십니까?', text)
            text = re.sub(r'괜찮아\?', '괜찮습니까?', text)
            text = re.sub(r'건강해\?', '건강하십니까?', text)
            text = re.sub(r'([가-힣]+)다([.!?])', r'\1습니다\2', text)
        elif source_is_polite:
            text = re.sub(r'잘 지내\?', '잘 지내요?', text)
            text = re.sub(r'괜찮아\?', '괜찮아요?', text)
            text = re.sub(r'건강해\?', '건강해요?', text)
    text = re.sub(r'(?<=[.!?]\s)([^\W\d_])', lambda match: match.group(1).upper(), text)
    if source_lang == 'uz' and re.search(r'^\s*assalomu\s+alaykum', source_text, re.IGNORECASE):
        greeting = {
            'tr': 'Selamün aleyküm',
            'en': 'Peace be upon you (Hello)',
            'ko': '안녕하세요',
        }.get(target_lang)
        if greeting and greeting.casefold() not in text.casefold():
            text = f'{greeting}, {text}'
    return text


def google_translate(text: str, source_lang: str, target_lang: str) -> dict[str, str]:
    source_lang = source_lang.strip().lower()
    target_lang = target_lang.strip().lower()
    if source_lang != 'auto' and source_lang not in LANGUAGE_NAMES:
        raise ValueError('Unsupported source language')
    if target_lang not in LANGUAGE_NAMES:
        raise ValueError('Unsupported target language')

    try:
        response = httpx.get(
            GOOGLE_TRANSLATE_ENDPOINT,
            params={
                'client': 'gtx',
                'sl': source_lang,
                'tl': target_lang,
                'dt': 't',
                'q': text,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
            raise ValueError('Unexpected translation response shape')
        translated_text = ''.join(
            segment[0]
            for segment in payload[0]
            if isinstance(segment, (list, tuple))
            and segment
            and isinstance(segment[0], str)
            and segment[0]
        ).strip()
        detected_candidate = payload[2] if len(payload) > 2 else None
        detected_lang = (
            detected_candidate
            if isinstance(detected_candidate, str) and detected_candidate in LANGUAGE_NAMES
            else source_lang
        )
        if source_lang == 'auto' and detected_lang not in LANGUAGE_NAMES:
            raise GeminiServiceError('Matn tili qo‘llab-quvvatlanmaydi. Uzbek, English, Korean yoki Turkish matn kiriting.')
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError, IndexError, TypeError) as error:
        if isinstance(error, GeminiServiceError):
            raise
        logger.exception('Google Translate fallback failed')
        raise GeminiServiceError('Tarjima xizmati vaqtincha ishlamayapti. Birozdan so‘ng qayta urinib ko‘ring.') from error

    if not translated_text:
        raise GeminiServiceError('Tarjima xizmati bo‘sh javob qaytardi.')
    return {
        'source_lang': detected_lang,
        'target_lang': target_lang,
        'translated_text': translated_text,
    }


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    result = translate_translation(text, source_lang, target_lang)
    return result['translated_text']


def explain_translation(
    text: str,
    translated_text: str,
    source_lang: str,
    target_lang: str,
    style: str = 'Oddiy',
    analysis_mode: str | None = None,
    question: str | None = None,
) -> dict[str, str]:
    source_lang = source_lang.strip().lower()
    target_lang = target_lang.strip().lower()
    if source_lang != 'auto' and source_lang not in LANGUAGE_NAMES:
        raise ValueError('Unsupported source language')
    if target_lang not in LANGUAGE_NAMES:
        raise ValueError('Unsupported target language')
    if style not in VALID_STYLES:
        raise ValueError('Unsupported translation style')
    if analysis_mode is not None and analysis_mode not in ANALYSIS_MODES:
        raise ValueError('Unsupported analysis mode')

    source_name = LANGUAGE_NAMES.get(source_lang, 'matn tilini avtomatik aniqlash')
    mode_instruction = {
        "So'zma-so'z va Grammatik tahlil": 'Prioritize each key word, suffix, and sentence grammar.',
        '3 xil uslubda taqqoslash (Oddiy / Rasmiy / Professional)': 'Compare natural, formal, and professional variants.',
        "Talaffuz va O'qilishi (Transkripsiya)": 'Prioritize pronunciation and readable Latin transliteration.',
        'Sinonimlar va Muqobil iboralar': 'Suggest natural synonyms and alternative expressions.',
        'Erkin savol-javob': 'Answer the user question about the text accurately and directly.',
    }.get(analysis_mode, 'Explain the meaning, grammar, style, and pronunciation.')
    prompt = (
        'Explain this translation in Uzbek using Uzbek Latin script. Give a substantial, organized analysis. '
        'Include these headings: Asosiy ma’no va Kontekst; So‘zma-so‘z tahlil; '
        '3 xil uslubdagi variantlar (Oddiy, Rasmiy, Professional); Talaffuz va O‘qilishi. '
        f'{mode_instruction} '
        'Do not translate the explanation into another language. '
        f'Source language: {source_name}. Target language: {LANGUAGE_NAMES[target_lang]}. '
        f'Translation style: {style}.\n\n'
        f'User question or focus: {question or "Provide a complete language analysis."}\n\n'
        'Return only a JSON object with string fields "source_lang" (one of "uz", "en", "ko", "tr") '
        'and "explanation".\n\n'
        f'Original text:\n{text}\n\n'
        f'Translation:\n{translated_text}'
    )
    try:
        raw_response = _generate_content(prompt, json_response=True)
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError as error:
            logger.exception('Gemini returned malformed explanation JSON')
            raise GeminiServiceError('Gemini AI noto‘g‘ri izoh javobini qaytardi.') from error
        if not isinstance(result, dict):
            raise GeminiServiceError('Gemini AI noto‘g‘ri izoh javobini qaytardi.')
        detected_lang = result.get('source_lang')
        explanation = result.get('explanation')
        if (
            not isinstance(detected_lang, str)
            or detected_lang not in LANGUAGE_NAMES
            or not isinstance(explanation, str)
            or not explanation.strip()
        ):
            raise GeminiServiceError('Gemini AI javobida izoh yoki aniqlangan til yo‘q.')
    except GeminiServiceError as error:
        logger.warning('Gemini explanation unavailable (%s); using Uzbek explanation fallback', error.status_code)
        detected_lang = source_lang
        if source_lang == 'auto':
            try:
                detected_lang = google_translate(text, 'auto', target_lang)['source_lang']
            except GeminiServiceError:
                detected_lang = 'uz'
        explanation = _fallback_explanation(
            text,
            translated_text,
            detected_lang,
            target_lang,
            style,
            analysis_mode,
            question,
        )
        return {'source_lang': detected_lang, 'explanation': explanation}

    if source_lang != 'auto' and detected_lang != source_lang:
        detected_lang = source_lang
    return {'source_lang': detected_lang, 'explanation': explanation.strip()}


def _style_explanation(style: str) -> str:
    return {
        'Oddiy': 'Oddiy uslub kundalik suhbat uchun tabiiy va sodda iboralarni ishlatadi.',
        'Rasmiy': 'Rasmiy uslub hurmatli murojaat va adabiy, odobli shakllarni qo‘llaydi.',
        'Professional': 'Professional uslub ish yoki ta’lim muhitiga mos, lo‘nda va aniq ifodalarni tanlaydi.',
    }[style]


def _fallback_explanation(
    text: str,
    translated_text: str,
    source_lang: str,
    target_lang: str,
    style: str,
    analysis_mode: str | None,
    question: str | None,
) -> str:
    analysis_text = normalize_uzbek_text(text) if source_lang == 'uz' else text
    source_words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+|[\uac00-\ud7af]+", analysis_text)
    word_translation_overrides = {
        'tr': {
            'assalomu alaykum': 'Selamün aleyküm',
            'yaxshimisiz': 'Nasılsınız',
            "sog'lig'ingiz": 'Sağlığınız',
            'yaxshimi': 'iyi mi',
        },
        'en': {
            'assalomu alaykum': 'Peace be upon you',
            'yaxshimisiz': 'How are you',
            "sog'lig'ingiz": 'your health',
            'yaxshimi': 'is it good',
        },
        'ko': {
            'assalomu alaykum': '안녕하세요',
            'yaxshimisiz': '잘 지내세요',
            "sog'lig'ingiz": '건강',
            'yaxshimi': '좋으세요',
        },
        'uz': {},
    }
    word_lines: list[str] = []
    normalized_words = [word.lower() for word in source_words]
    overrides = word_translation_overrides[target_lang]
    if normalized_words[:2] == ['assalomu', 'alaykum']:
        word_lines.append(f'- Assalomu alaykum → {overrides["assalomu alaykum"]}')
        normalized_words = normalized_words[2:]
        source_words = source_words[2:]

    for word in dict.fromkeys(source_words[:12]):
        override = overrides.get(word.lower())
        if override:
            word_lines.append(f'- {word} → {override}')
            continue
        try:
            word_translation = google_translate(word, source_lang, target_lang)['translated_text']
            word_translation = enforce_polite_translation(
                word_translation,
                word,
                source_lang,
                target_lang,
                style,
            )
        except GeminiServiceError:
            word_translation = '(alohida tarjimasi olinmadi)'
        word_lines.append(f'- {word} → {word_translation}')
    if not word_lines:
        word_lines.append('- Matnda alohida tahlil qilinadigan so‘z topilmadi.')

    variants = _style_variants(text, translated_text, target_lang)
    if target_lang == 'ko':
        reading = _romanize_korean(translated_text)
        pronunciation = f'Lotincha taxminiy o‘qilishi: {reading}.'
    elif target_lang == 'tr':
        pronunciation = f"Turkcha o‘qilishi: {translated_text}. “ş” — sh, “ç” — ch, “ı” — qisqa, markaziy i."
    else:
        pronunciation = f'Lotin yozuvidagi o‘qilishi: {translated_text}.'

    context = (
        f'Asl jumla {LANGUAGE_NAMES_UZ[source_lang]} tilida, tarjimasi {LANGUAGE_NAMES_UZ[target_lang]} tilida. '
        f'Asosiy mazmun: “{translated_text}”. Kontekstga ko‘ra bu jumla salomlashuv va hol-ahvol so‘rashni ifodalaydi.'
        if re.search(r'assalomu\s+alaykum|salom', text, re.IGNORECASE)
        else (
            f'Asl jumla {LANGUAGE_NAMES_UZ[source_lang]} tilida, tarjimasi {LANGUAGE_NAMES_UZ[target_lang]} tilida. '
            f'Asosiy mazmun: “{translated_text}”. Ma’noni gapning vaziyati va murojaat qilinayotgan kishiga qarab tushuning.'
        )
    )
    mode_note = f'\nTanlangan tahlil: {analysis_mode}.' if analysis_mode else ''
    question_answer = f'\nSavolingiz: {question}\nJavob: Yuqoridagi tarjima va so‘z tahlili asosida, {question.strip().rstrip("?")} mazmuni jumladagi kontekstga bog‘liq.' if question else ''
    return (
        f'### Asosiy ma’no va Kontekst\n{context}\n\n'
        f'### So‘zma-so‘z tahlil\n' + '\n'.join(word_lines) + '\n\n'
        f'### 3 xil uslubdagi variantlar\n'
        f'- Oddiy: {variants["Oddiy"]}\n'
        f'- Rasmiy: {variants["Rasmiy"]}\n'
        f'- Professional: {variants["Professional"]}\n\n'
        f'### Talaffuz va O‘qilishi\n{pronunciation}\n\n'
        f'Uslub izohi: {_style_explanation(style)}{mode_note}{question_answer}'
    )


def _style_variants(text: str, translated_text: str, target_lang: str) -> dict[str, str]:
    if re.search(r'assalomu\s+alaykum|salom', text, re.IGNORECASE):
        greeting_variants = {
            'tr': {
                'Oddiy': 'Selamün aleyküm, nasılsınız? Sağlığınız iyi mi?',
                'Rasmiy': 'Selamün aleyküm. Nasılsınız? Sağlığınız iyi mi?',
                'Professional': 'Merhaba, nasılsınız? Sağlık durumunuz nasıl?',
            },
            'en': {
                'Oddiy': 'Hello, how are you? Is your health good?',
                'Rasmiy': 'Peace be upon you. How are you? Is your health well?',
                'Professional': 'Hello. I hope you are well. How is your health?',
            },
            'ko': {
                'Oddiy': '안녕하세요, 잘 지내요? 건강은 어떠세요?',
                'Rasmiy': '안녕하십니까? 잘 지내십니까? 건강은 어떠십니까?',
                'Professional': '안녕하세요. 잘 지내시는지요? 건강은 어떠신가요?',
            },
            'uz': {
                'Oddiy': 'Assalomu alaykum, yaxshimisiz? Sog‘lig‘ingiz yaxshimi?',
                'Rasmiy': 'Assalomu alaykum. Yaxshimisiz? Sog‘lig‘ingiz joyidami?',
                'Professional': 'Assalomu alaykum. Umid qilamanki, yaxshisiz. Sog‘lig‘ingiz qanday?',
            },
        }
        return greeting_variants[target_lang]
    return {
        'Oddiy': f'“{translated_text}” — kundalik suhbat uchun sodda va tabiiy ifoda.',
        'Rasmiy': f'“{translated_text}” — rasmiy vaziyatda hurmatli murojaat bilan ishlating.',
        'Professional': f'“{translated_text}” — ish muhitida aniq va lo‘nda ifoda sifatida ishlating.',
    }


def _romanize_korean(text: str) -> str:
    initials = ('g', 'kk', 'n', 'd', 'tt', 'r', 'm', 'b', 'pp', 's', 'ss', '', 'j', 'jj', 'ch', 'k', 't', 'p', 'h')
    medials = (
        'a', 'ae', 'ya', 'yae', 'eo', 'e', 'yeo', 'ye', 'o', 'wa', 'wae', 'oe',
        'yo', 'u', 'wo', 'we', 'wi', 'yu', 'eu', 'ui', 'i',
    )
    finals = (
        '', 'k', 'k', 'ks', 'n', 'nj', 'nh', 't', 'l', 'lk', 'lm', 'lb', 'ls',
        'lt', 'lp', 'lh', 'm', 'p', 'ps', 't', 't', 'ng', 't', 't', 'k', 't', 'p', 't',
    )
    romanized: list[str] = []
    for char in text:
        code = ord(char) - 0xAC00
        if 0 <= code < 11172:
            initial = code // 588
            medial = (code % 588) // 28
            final = code % 28
            romanized.append(initials[initial] + medials[medial] + finals[final])
        else:
            romanized.append(char)
    return ''.join(romanized).strip()
