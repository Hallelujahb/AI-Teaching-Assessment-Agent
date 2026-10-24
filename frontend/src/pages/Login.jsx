import { useEffect, useState } from 'react'
import { applyTheme, initialTheme } from '../theme'
import './Login.css'

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const Icon = ({ children, size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
)
const MailIcon = () => <Icon><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></Icon>
const LockIcon = () => <Icon><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></Icon>
const EyeIcon = () => <Icon><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></Icon>
const EyeOffIcon = () => <Icon><path d="M9.9 4.2A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4M6.6 6.6A17 17 0 0 0 2 12s3.5 7 10 7a10 10 0 0 0 5.4-1.6" /><path d="m3 3 18 18M10 10a3 3 0 0 0 4 4" /></Icon>
const ArrowIcon = () => <Icon size={16}><path d="M5 12h14M13 6l6 6-6 6" /></Icon>
const MoonIcon = () => <Icon size={16}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" /></Icon>
const SunIcon = () => <Icon size={16}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></Icon>
const CapIcon = () => <Icon size={16}><path d="m22 9-10-5L2 9l10 5 10-5Z" /><path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5M22 9v6" /></Icon>

export default function Login({ onLogin, onRegister, onForgot }) {
  const [theme, setTheme] = useState(initialTheme)
  const [role, setRole] = useState('student') // student | lecturer | admin
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [keep, setKeep] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { applyTheme(theme) }, [theme])

  async function submit(e) {
    e.preventDefault()
    if (busy) return
    setError('')
    setBusy(true)
    try {
      const res = await fetch(`${API}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: identifier.trim(), password, as: role }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.message || data.error || 'Could not sign in. Try again.')
      const store = keep ? localStorage : sessionStorage
      store.setItem('qeleme_token', data.token)
      store.setItem('qeleme_user', JSON.stringify(data.user))
      if (onLogin) onLogin(data)
      else window.location.assign('/')
    } catch (err) {
      setError(err.message || 'Could not sign in. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const go = (fn, hash) => () => (fn ? fn() : (window.location.hash = hash))

  return (
    <div className="lg-page">
      <aside className="lg-brand">
        <span className="lg-circle" />
        <span className="lg-ring" />
        <div className="lg-brand-main">
          <div className="lg-logo">
            <span className="lg-logo-box">ቀ</span>
            <span className="lg-logo-text">ቀለሜ</span>
          </div>
          <h2 className="lg-tagline">Review Smart.</h2>
        </div>
        <div className="lg-brand-foot"><CapIcon /> Made for students and educators</div>
      </aside>

      <main className="lg-main">
        <form className="lg-form" onSubmit={submit} noValidate>
          <p className="lg-welcome">Welcome to ቀለሜ</p>
          <h1 className="lg-title">Sign in to continue</h1>
          <p className="lg-sub">Choose your academic role, then enter your account details.</p>

          <div className="lg-label lg-role-label">I am signing in as</div>
          <div className="lg-seg" role="tablist">
            {['student', 'lecturer'].map((r) => (
              <button key={r} type="button" role="tab" aria-selected={role === r}
                      className={role === r ? 'on' : ''} onClick={() => setRole(r)}>
                {r === 'student' ? 'Student' : 'Lecturer'}
              </button>
            ))}
          </div>

          <label className="lg-label" htmlFor="lg-id">
            {role === 'admin' ? 'Administrator email' : 'Institutional email'}
          </label>
          <div className="lg-field">
            <MailIcon />
            <input id="lg-id" type="text" autoComplete="username" placeholder="name@university.edu"
                   value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
          </div>

          <div className="lg-row">
            <label className="lg-label" htmlFor="lg-pw">Password</label>
            <button type="button" className="lg-link" onClick={go(onForgot, '#/forgot')}>Forgot password?</button>
          </div>
          <div className="lg-field">
            <LockIcon />
            <input id="lg-pw" type={show ? 'text' : 'password'} autoComplete="current-password"
                   placeholder="Enter your password" value={password}
                   onChange={(e) => setPassword(e.target.value)} />
            <button type="button" className="lg-eye" onClick={() => setShow(!show)}
                    aria-label={show ? 'Hide password' : 'Show password'}>
              {show ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>

          <label className="lg-check">
            <input type="checkbox" checked={keep} onChange={(e) => setKeep(e.target.checked)} />
            Keep me signed in on this device
          </label>

          {error && <div className="lg-error" role="alert">{error}</div>}

          <button type="submit" className="lg-primary" disabled={busy}>
            {busy ? 'Signing in…' : <>Sign in <ArrowIcon /></>}
          </button>

          <div className="lg-or"><span>New to ቀለሜ?</span></div>
          <button type="button" className="lg-secondary" onClick={go(onRegister, '#/register')}>
            Create a student or lecturer account
          </button>

          <hr className="lg-hr" />
          <button type="button" className="lg-link lg-admin"
                  onClick={() => setRole(role === 'admin' ? 'student' : 'admin')}>
            {role === 'admin' ? 'Back to student / lecturer sign in' : 'Administrator sign in'}
          </button>

          <button type="button" className="lg-theme"
                  onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </button>
        </form>
      </main>
    </div>
  )
}
