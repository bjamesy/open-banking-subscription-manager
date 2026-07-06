import { useCallback, useEffect, useState } from 'react'
import ConnectBank from '../components/ConnectBank'
import { listAccounts, type Account } from '../api/client'

export default function Accounts() {
  const [accounts, setAccounts] = useState<Account[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(() => {
    listAccounts()
      .then(setAccounts)
      .catch(() => setError('Failed to load accounts.'))
  }, [])

  useEffect(reload, [reload])

  return (
    <>
      <div className="page-header">
        <h1>Accounts</h1>
        <ConnectBank onConnected={reload} />
      </div>

      {error && <p className="error">{error}</p>}

      <div className="card">
        {accounts === null ? (
          <div className="empty">Loading…</div>
        ) : accounts.length === 0 ? (
          <div className="empty">
            <p>No bank accounts connected.</p>
            <p className="muted">
              Use “Connect bank account” to link your bank via Plaid. Transactions
              import automatically and subscription detection runs on every sync.
            </p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Account</th>
                <th>Institution</th>
                <th>Type</th>
                <th>Status</th>
                <th>Last synced</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id}>
                  <td>
                    {a.name}
                    {a.mask && <span className="muted"> ····{a.mask}</span>}
                  </td>
                  <td>{a.institution_name ?? '—'}</td>
                  <td className="muted">
                    {[a.type, a.subtype].filter(Boolean).join(' / ') || '—'}
                  </td>
                  <td>
                    <span className={`badge ${a.item_status === 'active' ? 'confirmed' : ''}`}>
                      {a.item_status}
                    </span>
                  </td>
                  <td className="muted">
                    {a.last_synced_at
                      ? new Date(a.last_synced_at).toLocaleString()
                      : 'never'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
