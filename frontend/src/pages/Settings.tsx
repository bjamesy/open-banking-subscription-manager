import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearTokens, deleteAccount } from '../api/client'

function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

export default function Settings() {
  const [confirming, setConfirming] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submitDelete(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!window.confirm('Delete your account and all linked data? This cannot be undone.')) {
      return
    }
    setBusy(true)
    try {
      await deleteAccount(password)
      clearTokens()
      navigate('/login')
    } catch (err: unknown) {
      setError(errorDetail(err, 'Failed to delete account.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Settings</h1>
      </div>

      <div className="card danger-zone">
        <h2>Danger zone</h2>
        <p>
          Permanently delete your account and all data — linked bank connections
          (revoked at Plaid, not just unlinked here), transactions, and
          subscriptions. This cannot be undone.
        </p>

        {!confirming ? (
          <button className="danger" onClick={() => setConfirming(true)}>
            Delete account
          </button>
        ) : (
          <form onSubmit={submitDelete}>
            <div style={{ marginBottom: 12 }}>
              <label htmlFor="delete-password">
                Password (leave blank if you signed in with Google)
              </label>
              <input
                id="delete-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ width: '100%', maxWidth: 320 }}
              />
            </div>
            {error && <p className="error">{error}</p>}
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="danger" type="submit" disabled={busy}>
                {busy ? 'Deleting…' : 'Confirm delete'}
              </button>
              <button
                className="ghost"
                type="button"
                onClick={() => {
                  setConfirming(false)
                  setPassword('')
                  setError(null)
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </>
  )
}
