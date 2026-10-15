import { type Dispatch, type SetStateAction, useEffect, useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import './App.css'

type ThemeMode = 'light' | 'dark'
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
  { code: 'uz', label: 'O‘zbekcha' },
  { code: 'en', label: 'English' },
  { code: 'ko', label: '한국어' },
  { code: 'tr', label: 'Türkçe' },
] as const

const API_BASE = import.meta.env.VITE_API_BASE_URL
  ?? (import.meta.env.DEV ? 'http://127.0.0.1:8000/api' : '/api')

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
  const [theme, setTheme] = useLocalStorage<ThemeMode>('linguaai-theme', 'light')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    document.body.setAttribute('data-theme', theme)
  }, [theme])

  return (
    <BrowserRouter>
      <AppLayout theme={theme} setTheme={setTheme} />
    </BrowserRouter>
  )
}

function AppLayout({ theme, setTheme }: { theme: ThemeMode; setTheme: Dispatch<SetStateAction<ThemeMode>> }) {
  const [token, setToken] = useLocalStorage<string>('linguaai-token', '')
  const [user, setUser] = useLocalStorage<AuthUser | null>('linguaai-user', null)
  const [guest, setGuest] = useState(() => window.sessionStorage.getItem('linguaai-guest') === 'true')
  const [recoveryCode, setRecoveryCode] = useState('')
  const navigate = useNavigate()

  const navItems = [
    { to: '/', label: 'Bosh sahifa' },
    { to: '/tarjimon', label: 'Tarjimon' },
    ...(token ? [
      { to: '/tarix', label: 'Tarix' },
      { to: '/sevimlilar', label: 'Sevimlilar' },
      { to: '/assistant', label: 'AI yordamchi' },
    ] : []),
    ...(guest || token ? [{ to: '/sozlamalar', label: 'Sozlamalar' }] : []),
    ...(token ? [{ to: '/profil', label: 'Profil' }] : []),
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
              <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                {item.label}
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
            className="header-theme-toggle"
            aria-label={theme === 'light' ? 'Qorong‘i mavzuni yoqish' : 'Yorug‘ mavzuni yoqish'}
            onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
          >
            {theme === 'light' ? '☾' : '☀'}
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
  }

  return (
    <div className="panel-stack">
      <section className="content-panel">
        <div className="panel-header">
          <h2>Tarjimon</h2>
          <span className="badge">{(detectedSourceLang ?? sourceLang).toUpperCase()} → {targetLang.toUpperCase()}</span>
        </div>

        <div className="language-controls">
          <label>
            <span>Manba tili</span>
            <select
              value={sourceLang}
              onChange={(event) => {
                setSourceLang(event.target.value as SourceLanguageCode)
                setDetectedSourceLang(null)
              }}
            >
              <option value="auto">Avtomatik aniqlash</option>
              {LANGUAGE_ITEMS.map((lang) => (
                <option key={lang.code} value={lang.code}>{lang.label}</option>
              ))}
            </select>
          </label>

          <button type="button" className="swap-button" onClick={handleSwap} aria-label="Tillarni almashtirish" disabled={sourceLang === 'auto'}>
            ⇄
          </button>

          <label>
            <span>Maqsad tili</span>
            <select
              value={targetLang}
              onChange={(event) => {
                setTargetLang(event.target.value as LanguageCode)
                setDetectedSourceLang(null)
              }}
            >
              {LANGUAGE_ITEMS.map((lang) => (
                <option key={lang.code} value={lang.code}>{lang.label}</option>
              ))}
            </select>
          </label>
        </div>

        <label className="style-control">
          <span>Tarjima uslubi</span>
          <select value={style} onChange={(event) => setStyle(event.target.value as TranslationStyle)}>
            <option value="Oddiy">Oddiy</option>
            <option value="Rasmiy">Rasmiy</option>
            <option value="Professional">Professional</option>
          </select>
        </label>

        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Matn kiriting..."
          aria-label="Tarjima qilinadigan matn"
        />

        <div className="panel-actions">
          <button type="button" className="primary-button" onClick={handleTranslate} disabled={loading}>
            {loading ? 'Tarjima qilinmoqda...' : 'Tarjima qilish'}
          </button>
          <button type="button" className="secondary-button" onClick={() => void navigator.clipboard.writeText(result)}>
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
          <p>Yengil va qorong‘i rejim o‘rtasida tanlang.</p>
        </div>
        <div className="theme-toggle" aria-label="Mavzu rejimini tanlang">
          <button type="button" className={theme === 'light' ? 'active' : ''} onClick={() => setTheme('light')}>Yengil</button>
          <button type="button" className={theme === 'dark' ? 'active' : ''} onClick={() => setTheme('dark')}>Qorong‘i</button>
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
    <section className="content-panel auth-panel">
      <div className="auth-heading">
        <span className="eyebrow">LinguaAI</span>
        <h1>{mode === 'login' ? 'Xush kelibsiz' : mode === 'register' ? 'Hisob yarating' : 'Parolni tiklash'}</h1>
        <p>Davom etish uchun hisobingizga kiring yoki yangi hisob yarating.</p>
      </div>
      <div className="auth-switch">
        <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError('') }}>Kirish</button>
        <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => { setMode('register'); setError('') }}>Hisob yaratish</button>
        <button type="button" className={mode === 'reset' ? 'active' : ''} onClick={() => { setMode('reset'); setError('') }}>Parolni unutdingizmi?</button>
      </div>

      <label>
        <span>Taxallus</span>
        <input value={nickname} onChange={(event) => setNickname(event.target.value)} autoComplete="username" placeholder="Taxallusingiz" />
      </label>

      {mode === 'reset' && (
        <label>
          <span>Tiklash kodi</span>
          <input value={recoveryCode} onChange={(event) => setRecoveryCodeInput(event.target.value.toUpperCase())} placeholder="LNG-XXXX-XXXX" autoComplete="off" />
        </label>
      )}

      <PasswordField label={mode === 'reset' ? 'Yangi parol' : 'Parol'} value={password} onChange={setPassword} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
      {mode !== 'login' && (
        <PasswordField label="Parolni tasdiqlash" value={confirmPassword} onChange={setConfirmPassword} autoComplete="new-password" />
      )}

      {error && <div className="status error">{error}</div>}

      <button type="button" className="primary-button" onClick={handleSubmit} disabled={loading}>
        {loading ? 'Iltimos, kuting...' : mode === 'login' ? 'Kirish' : mode === 'register' ? 'Hisob yaratish' : 'Parolni tiklash'}
      </button>
      <button type="button" className="guest-button" onClick={onGuest}>Mehmon sifatida davom etish</button>
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
