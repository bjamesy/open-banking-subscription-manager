import { useCallback, useEffect, useState } from 'react'
import { AxiosError } from 'axios'
import ConnectBank from '../components/ConnectBank'
import { getRescanJob, listAccounts, startRescan, type Account, type RescanJob } from '../api/client'

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export default function Accounts() {
  const [accounts, setAccounts] = useState<Account[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rescanning, setRescanning] = useState(false)
  const [rescanMsg, setRescanMsg] = useState<string | null>(null)

  const reload = useCallback(() => {
    listAccounts()
      .then(setAccounts)
      .catch(() => setError('Failed to load accounts.'))
  }, [])

  useEffect(reload, [reload])

  async function rescan() {
    setRescanning(true)
    setRescanMsg(null)
    setError(null)
    try {
      let job: RescanJob = await startRescan()
      while (job.status === 'pending' || job.status === 'running') {
        await sleep(1000)
        job = await getRescanJob(job.id)
      }
      if (job.status === 'done') {
        const synced = job.items_synced ?? 0
        const failed = job.items_failed ?? 0
        setRescanMsg(
          failed > 0
            ? `Synced ${synced} of ${synced + failed} accounts — some failed.`
            : `Synced ${synced} account${synced === 1 ? '' : 's'}.`,
        )
        reload()
      } else {
        setError(job.error ?? 'Re-scan failed.')
      }
    } catch (err) {
      if (err instanceof AxiosError && err.response?.status === 409) {
        setError('A re-scan is already in progress.')
      } else {
        setError('Re-scan failed.')
      }
    } finally {
      setRescanning(false)
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Accounts</h1>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            className="ghost"
            onClick={rescan}
            disabled={rescanning || !accounts?.length}
          >
            {rescanning ? 'Re-scanning…' : 'Re-scan'}
          </button>
          <ConnectBank onConnected={reload} />
        </div>
      </div>

      {rescanMsg && <p className="muted">{rescanMsg}</p>}
      {error && <p className="error">{error}</p>}

      <div className="card">
        {accounts === null ? (
          <div className="empty">Loading…</div>
        ) : accounts.length === 0 ? (
          <div className="empty">
            <p>No bank accounts connected.</p>
            <p className="muted">
              Use “Connect bank account” to link your bank via Plaid. Transactions
              import and subscription detection runs once, right away — use
              “Re-scan” anytime afterward to pick up new activity.
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
                <th />
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
                    <span
                      className={`badge ${a.item_status === 'active' ? 'confirmed' : ''}`}
                      style={a.item_status !== 'active' ? { color: 'var(--danger)', borderColor: '#fecaca' } : undefined}
                    >
                      {a.item_status}
                    </span>
                    {a.error && <div className="muted" style={{ fontSize: 12 }}>{a.error}</div>}
                  </td>
                  <td className="muted">
                    {a.last_synced_at
                      ? new Date(a.last_synced_at).toLocaleString()
                      : 'never'}
                  </td>
                  <td className="num">
                    {a.item_status !== 'active' && (
                      <ConnectBank itemId={a.item_id} onConnected={() => { reload(); rescan() }} />
                    )}
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
