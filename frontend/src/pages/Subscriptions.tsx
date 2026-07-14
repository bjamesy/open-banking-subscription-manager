import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  addSubscription,
  listSubscriptions,
  updateSubscriptionStatus,
  type Subscription,
} from '../api/client'

// Approximate charges per month for each cadence, for the spend summary.
const MONTHLY_FACTOR: Record<string, number> = {
  weekly: 4.33,
  biweekly: 2.17,
  monthly: 1,
  quarterly: 1 / 3,
  yearly: 1 / 12,
}

function money(n: number, currency: string | null): string {
  return n.toLocaleString(undefined, {
    style: 'currency',
    currency: currency ?? 'CAD',
  })
}

export default function Subscriptions() {
  const [subs, setSubs] = useState<Subscription[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [merchant, setMerchant] = useState('')
  const [amount, setAmount] = useState('')
  const [cadence, setCadence] = useState('monthly')

  const reload = useCallback(() => {
    listSubscriptions()
      .then(setSubs)
      .catch(() => setError('Failed to load subscriptions.'))
  }, [])

  useEffect(reload, [reload])

  async function setStatus(id: number, status: 'confirmed' | 'dismissed') {
    await updateSubscriptionStatus(id, status)
    reload()
  }

  async function submitAdd(e: React.FormEvent) {
    e.preventDefault()
    await addSubscription({ merchant, amount, cadence })
    setMerchant('')
    setAmount('')
    setShowAdd(false)
    reload()
  }

  const monthlyTotal = (subs ?? []).reduce(
    (sum, s) => sum + s.amount * (MONTHLY_FACTOR[s.cadence ?? ''] ?? 1),
    0,
  )

  return (
    <>
      <div className="page-header">
        <h1>Subscriptions</h1>
        <button className="ghost" onClick={() => setShowAdd((v) => !v)}>
          {showAdd ? 'Cancel' : 'Add manually'}
        </button>
      </div>

      {subs !== null && subs.length > 0 && (
        <div className="stats">
          <div className="stat">
            <div className="label">Active subscriptions</div>
            <div className="value">{subs.length}</div>
          </div>
          <div className="stat">
            <div className="label">Est. monthly spend</div>
            <div className="value">{money(monthlyTotal, subs[0]?.currency ?? null)}</div>
          </div>
        </div>
      )}

      {showAdd && (
        <form className="toolbar" onSubmit={submitAdd}>
          <div>
            <label htmlFor="m">Merchant</label>
            <input id="m" required value={merchant} onChange={(e) => setMerchant(e.target.value)} />
          </div>
          <div>
            <label htmlFor="a">Amount</label>
            <input
              id="a"
              required
              type="number"
              step="0.01"
              min="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="c">Cadence</label>
            <select id="c" value={cadence} onChange={(e) => setCadence(e.target.value)}>
              {Object.keys(MONTHLY_FACTOR).map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
          <button className="primary" type="submit">
            Add
          </button>
        </form>
      )}

      {error && <p className="error">{error}</p>}

      <div className="card">
        {subs === null ? (
          <div className="empty">Loading…</div>
        ) : subs.length === 0 ? (
          <div className="empty">
            <p>No subscriptions detected yet.</p>
            <p className="muted">
              <Link to="/accounts">Connect a bank account</Link> to run your first scan
              — re-scan anytime from Accounts to pick up new activity — or add one
              manually above.
            </p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Merchant</th>
                <th className="num">Amount</th>
                <th>Cadence</th>
                <th>Next charge</th>
                <th>Status</th>
                <th>Source</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {subs.map((s) => (
                <tr key={s.id}>
                  <td style={{ textTransform: 'capitalize' }}>{s.merchant_normalized}</td>
                  <td className="num">{money(s.amount, s.currency)}</td>
                  <td>{s.cadence ?? '—'}</td>
                  <td>{s.next_expected_charge ?? '—'}</td>
                  <td>
                    <span className={`badge ${s.status}`}>{s.status}</span>
                  </td>
                  <td className="muted">
                    {s.detection_source}
                    {s.detection_source === 'heuristic' && s.confidence_score != null
                      ? ` · ${Math.round(s.confidence_score * 100)}%`
                      : ''}
                  </td>
                  <td className="num">
                    {s.status === 'detected' && (
                      <button className="subtle" onClick={() => setStatus(s.id, 'confirmed')}>
                        Confirm
                      </button>
                    )}
                    {s.status !== 'dismissed' && (
                      <button
                        className="subtle danger"
                        onClick={() => setStatus(s.id, 'dismissed')}
                      >
                        Dismiss
                      </button>
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
