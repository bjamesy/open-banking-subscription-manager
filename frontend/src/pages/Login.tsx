import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, loginWithGoogle, register } from '../api/client'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID

function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

export default function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const googleButtonRef = useRef<HTMLDivElement>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'register') await register(email, password)
      await login(email, password)
      navigate('/subscriptions')
    } catch (err: unknown) {
      setError(errorDetail(err, 'Something went wrong — try again.'))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return

    let cancelled = false
    function init() {
      if (cancelled) return
      if (!window.google || !googleButtonRef.current) {
        setTimeout(init, 100)
        return
      }
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID!,
        callback: async (response) => {
          setError(null)
          setBusy(true)
          try {
            await loginWithGoogle(response.credential)
            navigate('/subscriptions')
          } catch (err: unknown) {
            setError(errorDetail(err, 'Google sign-in failed.'))
          } finally {
            setBusy(false)
          }
        },
      })
      window.google.accounts.id.renderButton(googleButtonRef.current, {
        theme: 'outline',
        size: 'large',
        shape: 'rectangular',
        text: 'continue_with',
        // Google draws the button at exactly this many pixels — a hardcoded
        // value drifts from the card's actual content width (340px card -
        // 28px padding each side = 284px) and overflows the card. Measure
        // the container instead of guessing.
        width: googleButtonRef.current.offsetWidth,
      })
    }
    init()
    return () => {
      cancelled = true
    }
  }, [navigate])

  return (
    <div className="login-wrap">
      <div className="login-card">
        <h1>SubTrack</h1>
        <p className="sub">
          {mode === 'login'
            ? 'Sign in to see your subscriptions.'
            : 'Create an account to get started.'}
        </p>
        <form onSubmit={submit}>
          <div>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label htmlFor="password">Password (8+ characters)</label>
            <input
              id="password"
              type="password"
              required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: '100%' }}
            />
          </div>
          {error && <p className="error">{error}</p>}
          <button className="primary" type="submit" disabled={busy}>
            {busy ? 'Working…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
        {GOOGLE_CLIENT_ID && (
          <>
            <p className="divider">or</p>
            <div ref={googleButtonRef} />
          </>
        )}
        <p className="switch">
          {mode === 'login' ? (
            <>
              No account?{' '}
              <button className="subtle" onClick={() => setMode('register')}>
                Register
              </button>
            </>
          ) : (
            <>
              Have an account?{' '}
              <button className="subtle" onClick={() => setMode('login')}>
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  )
}
