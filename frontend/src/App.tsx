import { type Dispatch, type SetStateAction, useEffect, useRef, useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { emitUiChime, playUiChime, playUiClick } from './utils/sound'
import './App.css'

type ThemeMode = 'dark-teal' | 'ocean-teal'
type LanguageCode = 'uz' | 'en' | 'ko' | 'tr'
type SourceLanguageCode = LanguageCode | 'auto'
type TranslationStyle = 'Oddiy' | 'Rasmiy' | 'Professional'
type LatestTranslation = {
  text: string
  translated_text: string
  source_lang: LanguageCode
  target_lang: LanguageCode
  style: TranslationStyle
}

const AI_MODES = [
  "So'zma-so'z va Grammatik tahlil",
  '3 xil uslubda taqqoslash (Oddiy / Rasmiy / Professional)',
  "Talaffuz va O'qilishi (Transkripsiya)",
  'Sinonimlar va Muqobil iboralar',
  'Erkin savol-javob',
] as const
type AiMode = (typeof AI_MODES)[number]
const LATEST_TRANSLATION_KEY = 'linguaai-latest-translation'

type AuthUser = {
  id: number
  nickname: string
  email?: string
  full_name?: string
  is_active: boolean
  created_at: string
}

const LANGUAGE_ITEMS = [
  { code: 'uz', label: 'O‘zbekcha', flag: '🇺🇿' },
  { code: 'en', label: 'English', flag: '🇬🇧' },
  { code: 'ko', label: '한국어', flag: '🇰🇷' },
  { code: 'tr', label: 'Türkçe', flag: '🇹🇷' },
] as const

const API_BASE = import.meta.env.VITE_API_BASE_URL
  ?? 'https://linguaai-or6y.onrender.com/api'

function useLocalStorage<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initialValue
    const saved = window.localStorage.getItem(key)
    if (saved === null) return initialValue
    try {
      return JSON.parse(saved) as T
    } catch {
      return initialValue
    }
  })

  useEffect(() => {
    window.localStorage.setItem(key, JSON.stringify(value))
  }, [key, value])

  return [value, setValue] as const
}

async function apiRequest<T>(path: string, options: RequestInit & { token?: string } = {}): Promise<T> {
  const headers = new Headers(options.headers ?? {})
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (options.token) {
    headers.set('Authorization', `Bearer ${options.token}`)
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error((data as { detail?: string }).detail ?? 'Xatolik yuz berdi')
  }

  return data as T
}

function App() {
  const [theme, setTheme] = useLocalStorage<ThemeMode>('linguaai-theme', 'dark-teal')

  useEffect(() => {
    if (theme !== 'dark-teal' && theme !== 'ocean-teal') {
      setTheme('dark-teal')
      return
    }
    document.documentElement.setAttribute('data-theme', theme)
    document.body.setAttribute('data-theme', theme)
  }, [theme, setTheme])

  return (
    <BrowserRouter>
      <AppLayout theme={theme} setTheme={setTheme} />
    </BrowserRouter>
  )
}

function AppLayout({ theme, setTheme }: { theme: ThemeMode; setTheme: Dispatch<SetStateAction<ThemeMode>> }) {
  const [token, setToken] = useLocalStorage<string>('linguaai-token', '')
  const [user, setUser] = useLocalStorage<AuthUser | null>('linguaai-user', null)
  const [soundEnabled, setSoundEnabled] = useLocalStorage('linguaai-sound-enabled', true)
  const [guest, setGuest] = useState(() => window.sessionStorage.getItem('linguaai-guest') === 'true')
  const [recoveryCode, setRecoveryCode] = useState('')
  const navigate = useNavigate()
  const soundEnabledRef = useRef(soundEnabled)

  useEffect(() => {
    soundEnabledRef.current = soundEnabled
  }, [soundEnabled, soundEnabledRef])

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (!soundEnabledRef.current || !(event.target instanceof Element)) return
      if (event.target.closest('button, a, select, [role="tab"]')) playUiClick()
    }
    const handleChime = () => {
      if (soundEnabledRef.current) playUiChime()
    }
    document.addEventListener('click', handleClick)
    window.addEventListener('linguaai:chime', handleChime)
    return () => {
      document.removeEventListener('click', handleClick)
      window.removeEventListener('linguaai:chime', handleChime)
    }
  }, [soundEnabledRef])

  const navItems = [
    { to: '/', label: 'Bosh sahifa', icon: '🏠' },
    { to: '/tarjimon', label: 'Tarjimon', icon: '🌐' },
    ...(token ? [
      { to: '/assistant', label: 'AI yordamchi', icon: '🤖' },
      { to: '/tarix', label: 'Tarix', icon: '🕒' },
      { to: '/sevimlilar', label: 'Sevimlilar', icon: '⭐' },
    ] : []),
    ...(guest || token ? [{ to: '/sozlamalar', label: 'Sozlamalar', icon: '⚙️' }] : []),
    ...(token ? [{ to: '/profil', label: 'Profil', icon: '👤' }] : []),
  ]

  const signOut = () => {
    setToken('')
    setUser(null)
    setGuest(false)
    window.sessionStorage.removeItem('linguaai-guest')
    navigate('/')
  }

  return (
    <div className="app-shell" data-theme={theme}>
      <header className="topbar">
        <div className="brand" aria-label="LinguaAI logosi">
          <span className="brand-mark">L</span>
          <div>
            <strong>LinguaAI</strong>
            <small>by Xayrullayeva Gulasal</small>
          </div>
        </div>

        {(guest || token) && (
          <nav className="nav" aria-label="Asosiy navigatsiya">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} aria-label={item.label} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                <span aria-hidden="true">{item.icon}</span> {item.label}
              </NavLink>
            ))}
          </nav>
        )}

        <div className="topbar-actions">
          {token && user?.nickname && (
            <button
              type="button"
              className="profile-badge"
              aria-label={`Salom, ${user.nickname}!`}
              onClick={() => navigate('/profil')}
            >
              <span className="profile-avatar">{user.nickname.charAt(0).toUpperCase()}</span>
              <span>Salom, {user.nickname}!</span>
            </button>
          )}
          <button
            type="button"
            className={`sound-toggle ${soundEnabled ? 'is-on' : ''}`}
            aria-pressed={soundEnabled}
            aria-label={soundEnabled ? 'Ovozli effektlarni o‘chirish' : 'Ovozli effektlarni yoqish'}
            onClick={() => setSoundEnabled(!soundEnabled)}
          >
            <span aria-hidden="true">{soundEnabled ? '🔊' : '🔇'}</span>
            <span className="sound-toggle-label">Ovozli effektlar</span>
          </button>
          <button
            type="button"
            className="header-theme-toggle"
            aria-label={theme === 'dark-teal' ? 'Moviy Okean mavzusiga o‘tish' : 'Chuqur Zumrad mavzusiga o‘tish'}
            onClick={() => setTheme(theme === 'dark-teal' ? 'ocean-teal' : 'dark-teal')}
          >
            {theme === 'dark-teal' ? '◈' : '✦'}
          </button>
          {(token || guest) && <button type="button" className="secondary-button header-signout" onClick={signOut}>{token ? 'Chiqish' : 'Kirish'}</button>}
        </div>
      </header>

      <main className="page-shell">
        {!token && !guest ? (
          <AuthPage
            setToken={setToken}
            setUser={setUser}
            onGuest={() => {
              window.sessionStorage.setItem('linguaai-guest', 'true')
              setGuest(true)
              navigate('/')
            }}
            onRecoveryCode={setRecoveryCode}
            onAuthenticated={() => {
              window.sessionStorage.removeItem('linguaai-guest')
              setGuest(false)
              navigate('/tarjimon')
            }}
          />
        ) : (
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/tarjimon" element={<TranslationPage token={token} />} />
            <Route path="/tarix" element={<HistoryPage token={token} />} />
            <Route path="/sevimlilar" element={<FavoritesPage token={token} />} />
            <Route path="/assistant" element={<AiAssistantPage />} />
            <Route path="/sozlamalar" element={<SettingsPage theme={theme} setTheme={setTheme} />} />
            <Route path="/profil" element={<ProfilePage user={user} signOut={signOut} />} />
            <Route path="*" element={<TranslationPage token={token} />} />
          </Routes>
        )}
      </main>
      {recoveryCode && (
        <RecoveryCodeModal
          code={recoveryCode}
          onClose={() => setRecoveryCode('')}
        />
      )}
    </div>
  )
}

function LandingPage() {
  return (
    <div className="landing-page">
      <section className="hero-panel">
        <div className="hero-copy">
          <span className="eyebrow">LinguaAI</span>
          <h1>Tilni tez, aniq va ishonchli tarjima qiling.</h1>
          <p>
            O‘qish, ishlash va muloqot uchun yaratilgan zamonaviy tarjimon. O‘zbek, ingliz,
            koreys va turk tillari orasida bir zumda ishlaydi.
          </p>
          <div className="cta-group">
            <NavLink className="primary-button" to="/tarjimon">Tarjima qilish</NavLink>
            <NavLink className="secondary-button" to="/sozlamalar">Sozlamalar</NavLink>
          </div>
          <div className="languages-row" aria-label="Qo‘llab-quvvatlanadigan tillar">
            {LANGUAGE_ITEMS.map((lang) => (
              <span key={lang.code} className="language-pill">
                {lang.label}
              </span>
            ))}
          </div>
        </div>

        <div className="hero-card">
          <div className="mini-header">
            <span className="status-dot" />
            Yangi tarjima
          </div>
          <div className="translation-example">
            <div>
              <label>O‘zbekcha</label>
              <p>Salom, bugun qayerga boramiz?</p>
            </div>
            <div className="swap-arrow">⇄</div>
            <div>
              <label>English</label>
              <p>Hello, where are we going today?</p>
            </div>
          </div>
          <ul className="feature-list">
            <li>Tezkor kontekstli tarjima</li>
            <li>Tarix va sevimlilar</li>
            <li>AI yordamchi bilan ishlash</li>
          </ul>
        </div>
      </section>

      <section className="metrics-grid">
        <MetricCard label="4 ta til" value="uz • en • ko • tr" />
        <MetricCard label="Kunlik foydalanish" value="24/7" />
        <MetricCard label="Mobil moslik" value="Touch-first" />
        <MetricCard label="Xavfsizlik" value="JWT + shifrlash" />
      </section>
    </div>
  )
}

function TranslationPage({ token }: { token: string }) {
  const [sourceLang, setSourceLang] = useState<SourceLanguageCode>('uz')
  const [targetLang, setTargetLang] = useState<LanguageCode>('en')
  const [style, setStyle] = useState<TranslationStyle>('Oddiy')
  const [text, setText] = useState('Salom, dunyo!')
  const [result, setResult] = useState('')
  const [detectedSourceLang, setDetectedSourceLang] = useState<LanguageCode | null>(null)
  const [explanation, setExplanation] = useState('')
  const [explanationLoading, setExplanationLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [swapped, setSwapped] = useState(false)

  const handleTranslate = async () => {
    setLoading(true)
    setError('')
    setExplanation('')
    setDetectedSourceLang(null)
    try {
      const payload = await apiRequest<{
        translated_text: string
        source_lang: LanguageCode
      }>('/v1/translations', {
        method: 'POST',
        body: JSON.stringify({ text, source_lang: sourceLang, target_lang: targetLang, style }),
      })
      setResult(payload.translated_text)
      setDetectedSourceLang(payload.source_lang)
      window.localStorage.setItem(LATEST_TRANSLATION_KEY, JSON.stringify({
        text,
        translated_text: payload.translated_text,
        source_lang: payload.source_lang,
        target_lang: targetLang,
        style,
      } satisfies LatestTranslation))
      emitUiChime()
      if (token) {
        await apiRequest('/translations', {
          method: 'POST',
          token,
          body: JSON.stringify({
            source_text: text,
            source_lang: payload.source_lang,
            target_lang: targetLang,
            translated_text: payload.translated_text,
          }),
        })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tarjima qilishda xatolik yuz berdi.')
    } finally {
      setLoading(false)
    }
  }

  const handleExplain = async () => {
    setExplanationLoading(true)
    setError('')
    try {
      const payload = await apiRequest<{ explanation: string }>('/v1/translations/explain', {
        method: 'POST',
        body: JSON.stringify({
          text,
          translated_text: result,
          source_lang: sourceLang,
          target_lang: targetLang,
          style,
        }),
      })
      setExplanation(payload.explanation)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Izoh olishda xatolik yuz berdi.')
    } finally {
      setExplanationLoading(false)
    }
  }

  const handleSwap = () => {
    if (sourceLang === 'auto') return
    setSourceLang(targetLang)
    setTargetLang(sourceLang)
    setSwapped(!swapped)
  }

  const copyResult = async () => {
    if (!result) return
    try {
      await navigator.clipboard.writeText(result)
      emitUiChime()
    } catch {
      setError('Nusxalash amalga oshmadi. Matnni qo‘lda belgilang va nusxalang.')
    }
  }

  return (
    <div className="panel-stack">
      <section className="content-panel">
        <div className="panel-header">
          <h2>Tarjimon</h2>
          <span className="badge">{(detectedSourceLang ?? sourceLang).toUpperCase()} → {targetLang.toUpperCase()}</span>
        </div>

        <div className="language-controls">
          <div className="language-field">
            <span className="language-control-heading">Manba tili <b className="language-select-badge">{sourceLang === 'auto' ? '✨ Avtomatik' : `${LANGUAGE_ITEMS.find((lang) => lang.code === sourceLang)?.flag} ${sourceLang.toUpperCase()}`}</b></span>
            <div className="language-chip-row" role="group" aria-label="Manba tili">
              <button type="button" className={`language-chip ${sourceLang === 'auto' ? 'active' : ''}`} aria-pressed={sourceLang === 'auto'} onClick={() => { setSourceLang('auto'); setDetectedSourceLang(null) }}>✨ Avtomatik</button>
              {LANGUAGE_ITEMS.map((lang) => (
                <button key={lang.code} type="button" className={`language-chip ${sourceLang === lang.code ? 'active' : ''}`} aria-pressed={sourceLang === lang.code} onClick={() => { setSourceLang(lang.code); setDetectedSourceLang(null) }}>{lang.flag} {lang.code.toUpperCase()} {lang.label}</button>
              ))}
            </div>
          </div>

          <button type="button" className={`swap-button ${swapped ? 'swapped' : ''}`} onClick={handleSwap} aria-label="Tillarni almashtirish" disabled={sourceLang === 'auto'}>
            ⇄
          </button>

          <div className="language-field">
            <span className="language-control-heading">Maqsad tili <b className="language-select-badge">{LANGUAGE_ITEMS.find((lang) => lang.code === targetLang)?.flag} {targetLang.toUpperCase()}</b></span>
            <div className="language-chip-row" role="group" aria-label="Maqsad tili">
              {LANGUAGE_ITEMS.map((lang) => (
                <button key={lang.code} type="button" className={`language-chip ${targetLang === lang.code ? 'active' : ''}`} aria-pressed={targetLang === lang.code} onClick={() => { setTargetLang(lang.code); setDetectedSourceLang(null) }}>{lang.flag} {lang.code.toUpperCase()} {lang.label}</button>
              ))}
            </div>
          </div>
        </div>

        <div className="style-picker" role="group" aria-label="Tarjima uslubi">
          <span>Tarjima uslubi</span>
          <div className="style-cards">
            {([
              ['Oddiy', '💬'],
              ['Rasmiy', '🏛️'],
              ['Professional', '💼'],
            ] as const).map(([label, icon]) => (
              <button
                key={label}
                type="button"
                className={`style-card ${style === label ? 'active' : ''}`}
                aria-pressed={style === label}
                onClick={() => setStyle(label)}
              >
                <span aria-hidden="true">{icon}</span>{label}
              </button>
            ))}
          </div>
        </div>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          maxLength={5000}
          placeholder="Matn kiriting..."
          aria-label="Tarjima qilinadigan matn"
        />
        <div className="character-meter" aria-label={`${text.length} / 5000 belgi`}>
          <span><span style={{ width: `${Math.min(text.length / 50, 100)}%` }} /></span>
          <small>{text.length} / 5000</small>
        </div>
        <div className="quick-phrases" aria-label="Namunaviy iboralar">
          {['Assalomu alaykum, yaxshimisiz?', 'Rahmat, juda yordam berdingiz.', 'Bugun ob-havo qanday?'].map((phrase) => (
            <button key={phrase} type="button" onClick={() => setText(phrase)}>{phrase}</button>
          ))}
        </div>

        <div className="panel-actions">
          <button type="button" className="primary-button" onClick={handleTranslate} disabled={loading}>
            {loading ? 'Tarjima qilinmoqda...' : 'Tarjima qilish'}
          </button>
          <button type="button" className="secondary-button" onClick={() => void copyResult()} disabled={!result}>
            Nusxalash
          </button>
        </div>

        {error && <div className="status error">{error}</div>}
      </section>

      <section className="content-panel output-panel">
        <div className="panel-header">
          <h2>Natija</h2>
          <span className="badge">{targetLang.toUpperCase()}</span>
        </div>
        <div className="result-box">{result || 'Tarjima natijasi shu yerda chiqadi.'}</div>
        <div className="panel-actions">
          <button type="button" className="secondary-button" onClick={handleExplain} disabled={!result || explanationLoading}>
            {explanationLoading ? 'Izoh tayyorlanmoqda...' : 'O‘zbekcha izoh'}
          </button>
        </div>
        {explanation && <div className="status explanation" aria-live="polite">{explanation}</div>}
      </section>
    </div>
  )
}

function HistoryPage({ token }: { token: string }) {
  const [items, setItems] = useState<Array<{ text: string; translated_text: string; source_lang: string; target_lang: string }>>([])

  useEffect(() => {
    if (!token) return
    apiRequest<Array<{ text: string; translated_text: string; source_lang: string; target_lang: string }>>('/translations', {
      method: 'GET',
      token,
    })
      .then((data) => setItems(data))
      .catch(() => setItems([]))
  }, [token])

  return (
    <section className="content-panel">
      <div className="panel-header"><h2>Tarix</h2></div>
      {items.length === 0 ? (
        <div className="empty-state">Hozircha tarjima tarixi yo‘q.</div>
      ) : (
        <ul className="history-list">
          {items.map((item, index) => (
            <li key={`${item.text}-${index}`} className="history-item">
              <strong>{item.source_lang.toUpperCase()} → {item.target_lang.toUpperCase()}</strong>
              <p>{item.text}</p>
              <span>{item.translated_text}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function FavoritesPage({ token }: { token: string }) {
  const [items, setItems] = useState<Array<{ text: string; translated_text: string; source_lang: string; target_lang: string }>>([])

  useEffect(() => {
    if (!token) return
    apiRequest<Array<{ text: string; translated_text: string; source_lang: string; target_lang: string }>>('/favorites', {
      method: 'GET',
      token,
    })
      .then((data) => setItems(data))
      .catch(() => setItems([]))
  }, [token])

  return (
    <section className="content-panel">
      <div className="panel-header"><h2>Sevimlilar</h2></div>
      {items.length === 0 ? (
        <div className="empty-state">Sevimli tarjimalar yo‘q.</div>
      ) : (
        <ul className="history-list">
          {items.map((item, index) => (
            <li key={`${item.text}-${index}`} className="history-item">
              <strong>{item.source_lang.toUpperCase()} → {item.target_lang.toUpperCase()}</strong>
              <p>{item.text}</p>
              <span>{item.translated_text}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function AiAssistantPage() {
  const [mode, setMode] = useState<AiMode>(AI_MODES[0])
  const [message, setMessage] = useState('')
  const [latestTranslation, setLatestTranslation] = useState<LatestTranslation | null>(() => {
    try {
      const saved = window.localStorage.getItem(LATEST_TRANSLATION_KEY)
      return saved ? JSON.parse(saved) as LatestTranslation : null
    } catch {
      return null
    }
  })
  const [reply, setReply] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const loadLatestTranslation = () => {
    try {
      const saved = window.localStorage.getItem(LATEST_TRANSLATION_KEY)
      if (!saved) {
        setError('Hozircha yuklash uchun tarjima topilmadi.')
        return
      }
      setLatestTranslation(JSON.parse(saved) as LatestTranslation)
      setError('')
    } catch {
      setError('Oxirgi tarjimani o‘qib bo‘lmadi.')
    }
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError('')
    try {
      const payload = await apiRequest<{ explanation: string }>('/v1/translations/explain', {
        method: 'POST',
        body: JSON.stringify({
          text: latestTranslation?.text ?? message,
          translated_text: latestTranslation?.translated_text ?? message,
          source_lang: latestTranslation?.source_lang ?? 'auto',
          target_lang: latestTranslation?.target_lang ?? 'uz',
          style: latestTranslation?.style ?? 'Oddiy',
          analysis_mode: mode,
          question: message || mode,
        }),
      })
      setReply(payload.explanation)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tahlilni tayyorlashda xatolik yuz berdi.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="content-panel assistant-panel">
      <div className="panel-header"><h2>AI yordamchi</h2></div>
      <div className="assistant-mode-chips" aria-label="Tahlil turini tanlang">
        {AI_MODES.map((item) => (
          <button key={item} type="button" className={mode === item ? 'active' : ''} onClick={() => setMode(item)}>
            {item}
          </button>
        ))}
      </div>
      <div className="panel-actions">
        <button type="button" className="secondary-button" onClick={loadLatestTranslation}>
          Oxirgi tarjimani yuklash
        </button>
      </div>
      {latestTranslation && (
        <div className="latest-translation-card" aria-live="polite">
          <strong>{latestTranslation.source_lang.toUpperCase()} → {latestTranslation.target_lang.toUpperCase()}</strong>
          <p>{latestTranslation.text}</p>
          <span>{latestTranslation.translated_text}</span>
        </div>
      )}
      <label>
        <span>{mode === 'Erkin savol-javob' ? 'Savolingiz' : 'Qo‘shimcha so‘rov (ixtiyoriy)'}</span>
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          aria-label="AI yordamchiga savol"
          placeholder={mode === 'Erkin savol-javob' ? 'Tarjima haqida savolingizni yozing...' : 'Tahlilda alohida e’tibor berish kerak bo‘lgan jihat...'}
        />
      </label>
      <div className="panel-actions">
        <button type="button" className="primary-button" onClick={handleSubmit} disabled={loading}>
          {loading ? 'Tahlil tayyorlanmoqda...' : 'Tahlil qilish'}
        </button>
      </div>
      {error && <div className="status error">{error}</div>}
      <div className="result-box">{reply || 'Tarjima tahlili shu yerda ko‘rinadi.'}</div>
    </section>
  )
}

function SettingsPage({ theme, setTheme }: { theme: ThemeMode; setTheme: Dispatch<SetStateAction<ThemeMode>> }) {
  return (
    <section className="content-panel settings-panel">
      <div className="panel-header"><h2>Sozlamalar</h2></div>
      <div className="setting-row">
        <div>
          <strong>Mavzu rejimi</strong>
          <p>Ikki yorqin qoramtir teal rang palitrasidan birini tanlang.</p>
        </div>
        <div className="theme-toggle" aria-label="Mavzu rejimini tanlang">
          <button type="button" className={theme === 'dark-teal' ? 'active' : ''} onClick={() => setTheme('dark-teal')}>Chuqur Zumrad</button>
          <button type="button" className={theme === 'ocean-teal' ? 'active' : ''} onClick={() => setTheme('ocean-teal')}>Moviy Okean</button>
        </div>
      </div>
    </section>
  )
}

function ProfilePage({ user, signOut }: { user: AuthUser | null; signOut: () => void }) {
  const navigate = useNavigate()

  if (!user) {
    return (
      <section className="content-panel empty-panel">
        <h2>Profil</h2>
        <p>Profilga kirish uchun hisobingizga kiring.</p>
        <button type="button" className="primary-button" onClick={() => navigate('/kirish')}>Kirish</button>
      </section>
    )
  }

  return (
    <section className="content-panel profile-panel">
      <div className="panel-header"><h2>Profil</h2></div>
      <div className="profile-card">
        <h3>{user.nickname || user.full_name}</h3>
        {user.email && <p>{user.email}</p>}
        <div className="profile-meta">
          <span>Holat: {user.is_active ? 'Faol' : 'Nofaol'}</span>
          <span>Ro‘yxatdan o‘tgan: {new Date(user.created_at).toLocaleDateString('uz-UZ')}</span>
        </div>
        <button type="button" className="secondary-button" onClick={signOut}>Chiqish</button>
      </div>
    </section>
  )
}

function AuthPage({
  setToken,
  setUser,
  onGuest,
  onRecoveryCode,
  onAuthenticated,
}: {
  setToken: Dispatch<SetStateAction<string>>
  setUser: Dispatch<SetStateAction<AuthUser | null>>
  onGuest: () => void
  onRecoveryCode: (code: string) => void
  onAuthenticated: () => void
}) {
  const [mode, setMode] = useState<'login' | 'register' | 'reset'>('login')
  const [nickname, setNickname] = useState('')
  const [recoveryCode, setRecoveryCodeInput] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const passwordStrength = [
    password.length >= 8,
    /[A-Z]/.test(password) && /[a-z]/.test(password),
    /\d/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ].filter(Boolean).length

  const handleSubmit = async () => {
    setLoading(true)
    setError('')
    try {
      if (mode === 'login') {
        const response = await apiRequest<{ access_token: string; user: AuthUser }>('/v1/auth/login', {
          method: 'POST',
          body: JSON.stringify({ nickname, password }),
        })
        setToken(response.access_token)
        setUser(response.user)
        onAuthenticated()
        return
      }

      if (password !== confirmPassword) {
        throw new Error('Parollar mos kelmadi.')
      }
      if (mode === 'register') {
        const response = await apiRequest<{ access_token: string; user: AuthUser; recovery_code: string }>('/v1/auth/register', {
          method: 'POST',
          body: JSON.stringify({ nickname, password, confirm_password: confirmPassword }),
        })
        setToken(response.access_token)
        setUser(response.user)
        onRecoveryCode(response.recovery_code)
        onAuthenticated()
        return
      }

      const response = await apiRequest<{ recovery_code: string }>('/v1/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({
          nickname,
          recovery_code: recoveryCode,
          new_password: password,
          confirm_password: confirmPassword,
        }),
      })
      onRecoveryCode(response.recovery_code)
      setMode('login')
      setPassword('')
      setConfirmPassword('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'So‘rovni bajarishda xatolik yuz berdi.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="auth-showcase">
      <aside className="auth-showcase-panel">
        <div className="auth-brand-lockup">
          <span className="brand-mark">L</span>
          <div><strong>LinguaAI</strong><small>by Xayrullayeva Gulasal</small></div>
        </div>
        <span className="eyebrow">Tillar orasidagi masofani yo‘qoting</span>
        <h1>Sun'iy intellekt yordamida <span>4 ta tilda mukammal muloqot qiling</span></h1>
        <div className="auth-preview-cards">
          <article className="auth-preview-card"><span>⚡</span><div><strong>Lahzali va aniq AI tarjima</strong><small>O‘zbek, Ingliz, Koreys, Turk tillari</small></div></article>
          <article className="auth-preview-card"><span>🧠</span><div><strong>5 rejimli AI Til Ustozi</strong><small>Grammatika, uslub va transkripsiya</small></div></article>
          <article className="auth-preview-card"><span>🛡️</span><div><strong>Bir martalik maxfiy tiklash kodi</strong><small>Xavfsiz hisob va shaxsiy lug‘at</small></div></article>
        </div>
        <div className="auth-live-demo">
          <div className="demo-heading"><span className="status-dot" /> Jonli tarjima namoyishi <span>AI ACTIVE</span></div>
          <p className="demo-source">“Assalomu alaykum, yaxshimisiz?”</p>
          <div className="demo-translations">
            <span><b>EN</b> Hello, how are you?</span>
            <span><b>KO</b> 안녕하세요, 잘 지내세요?</span>
            <span><b>TR</b> Selamün aleyküm, nasılsınız?</span>
          </div>
        </div>
      </aside>

      <section className="content-panel auth-panel">
        <div className="auth-heading">
          <span className="eyebrow">{mode === 'reset' ? 'HISOBNI TIKLASH' : 'XAVFSIZ KIRISH'}</span>
          <h2>{mode === 'login' ? 'Xush kelibsiz' : mode === 'register' ? 'Hisob yarating' : 'Parolni tiklash'}</h2>
          <p>Davom etish uchun quyidagi ma’lumotlarni kiriting.</p>
        </div>
        <div className="auth-switch">
          <button type="button" aria-label="Kirish" className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError('') }}>🔑 Kirish</button>
          <button type="button" aria-label="Hisob yaratish" className={mode === 'register' ? 'active' : ''} onClick={() => { setMode('register'); setError('') }}>✨ Hisob yaratish</button>
          <button type="button" aria-label="Parolni unutdingizmi?" className={mode === 'reset' ? 'active' : ''} onClick={() => { setMode('reset'); setError('') }}>🛡️ Parolni tiklash</button>
        </div>

        <label className="auth-field">
          <span>Taxallus</span>
          <span className="auth-input-wrap"><span aria-hidden="true">♙</span><input value={nickname} onChange={(event) => setNickname(event.target.value)} autoComplete="username" placeholder="Taxallusingiz" /></span>
        </label>

        {mode === 'reset' && (
          <label className="auth-field">
            <span>Tiklash kodi</span>
            <span className="auth-input-wrap"><span aria-hidden="true">⌘</span><input value={recoveryCode} onChange={(event) => setRecoveryCodeInput(event.target.value.toUpperCase())} placeholder="LNG-XXXX-XXXX" autoComplete="off" /></span>
          </label>
        )}

        <PasswordField label={mode === 'reset' ? 'Yangi parol' : 'Parol'} value={password} onChange={setPassword} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
        {mode === 'register' && (
          <div className="password-strength" aria-label={`Parol mustahkamligi: ${passwordStrength} / 4`}>
            <div>{[1, 2, 3, 4].map((level) => <span key={level} className={passwordStrength >= level ? `strength-${passwordStrength}` : ''} />)}</div>
            <small>{passwordStrength < 2 ? 'Zaif parol' : passwordStrength < 4 ? 'O‘rtacha parol' : 'Mustahkam parol'}</small>
          </div>
        )}
        {mode !== 'login' && (
          <PasswordField label="Parolni tasdiqlash" value={confirmPassword} onChange={setConfirmPassword} autoComplete="new-password" />
        )}

        {error && <div className="status error">{error}</div>}

        <button type="button" className="primary-button auth-submit" onClick={handleSubmit} disabled={loading}>
          {loading ? 'Iltimos, kuting...' : mode === 'login' ? 'Kirish' : mode === 'register' ? 'Hisob yaratish' : 'Parolni tiklash'}
        </button>
        <button type="button" className="guest-button" aria-label="Mehmon sifatida davom etish" onClick={onGuest}>🚀 Mehmon sifatida darhol sinab ko‘rish</button>
      </section>
    </section>
  )
}

function PasswordField({
  label,
  value,
  onChange,
  autoComplete,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  autoComplete: string
}) {
  const [visible, setVisible] = useState(false)
  return (
    <label className="password-field">
      <span>{label}</span>
      <span className="password-input-wrap">
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          type={visible ? 'text' : 'password'}
          autoComplete={autoComplete}
          placeholder="Kamida 6 ta belgi"
        />
        <span className="password-lock" aria-hidden="true">🔒</span>
        <button
          type="button"
          className="password-visibility"
          aria-label={visible ? 'Parolni yashirish' : 'Parolni ko‘rsatish'}
          onClick={() => setVisible(!visible)}
        >
          {visible ? '◉' : '◎'}
        </button>
      </span>
    </label>
  )
}

function RecoveryCodeModal({ code, onClose }: { code: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState('')

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setCopyError('')
      emitUiChime()
    } catch {
      setCopyError('Nusxalash amalga oshmadi. Kodni qo‘lda saqlab oling.')
    }
  }

  return (
    <div className="modal-backdrop">
      <section className="recovery-modal" role="dialog" aria-modal="true" aria-labelledby="recovery-title">
        <span className="recovery-icon">!</span>
        <h2 id="recovery-title">Tiklash kodingiz</h2>
        <p>Bu kodni xavfsiz joyda saqlang. Kod faqat bir marta ishlaydi va parol tiklangach yangilanadi.</p>
        <strong className="recovery-code">{code}</strong>
        <button type="button" className="primary-button" onClick={copyCode}>
          {copied ? 'Nusxalandi' : 'Kodni nusxalash'}
        </button>
        {copyError && <div className="status error">{copyError}</div>}
        <button type="button" className="secondary-button" onClick={onClose}>Saqladim, davom etish</button>
      </section>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

export default App
