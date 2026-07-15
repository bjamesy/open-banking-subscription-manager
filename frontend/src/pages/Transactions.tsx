import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  listAccounts,
  listTransactions,
  type Account,
  type TransactionPage,
} from '../api/client'

const PAGE_SIZE = 50

export default function Transactions() {
  const [page, setPage] = useState<TransactionPage | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountId, setAccountId] = useState<number | ''>('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listAccounts().then(setAccounts).catch(() => {})
  }, [])

  useEffect(() => {
    listTransactions({
      account_id: accountId === '' ? undefined : accountId,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      limit: PAGE_SIZE,
      offset,
    })
      .then(setPage)
      .catch(() => setError('Failed to load transactions.'))
  }, [accountId, startDate, endDate, offset])

  const accountName = (id: number) =>
    accounts.find((a) => a.id === id)?.name ?? `#${id}`

  return (
    <>
      <div className="page-header">
        <h1>Transactions</h1>
      </div>

      <div className="toolbar">
        <div>
          <label htmlFor="acct">Account</label>
          <select
            id="acct"
            value={accountId}
            onChange={(e) => {
              setOffset(0)
              setAccountId(e.target.value === '' ? '' : Number(e.target.value))
            }}
          >
            <option value="">All accounts</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
                {a.mask ? ` ····${a.mask}` : ''}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="from">From</label>
          <input
            id="from"
            type="date"
            value={startDate}
            onChange={(e) => {
              setOffset(0)
              setStartDate(e.target.value)
            }}
          />
        </div>
        <div>
          <label htmlFor="to">To</label>
          <input
            id="to"
            type="date"
            value={endDate}
            onChange={(e) => {
              setOffset(0)
              setEndDate(e.target.value)
            }}
          />
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="card">
        {page === null ? (
          <div className="empty">Loading…</div>
        ) : page.total === 0 ? (
          <div className="empty">
            <p>No transactions yet.</p>
            <p className="muted">
              <Link to="/accounts">Connect a bank account</Link> to import transaction
              history.
            </p>
          </div>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Merchant</th>
                    <th>Account</th>
                    <th className="num">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((t) => (
                    <tr key={t.id}>
                      <td>{t.posted_at}</td>
                      <td>{t.merchant_raw}</td>
                      <td className="muted">{accountName(t.account_id)}</td>
                      <td className="num">
                        {t.amount.toLocaleString(undefined, {
                          style: 'currency',
                          currency: t.currency ?? 'CAD',
                        })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <button
                className="ghost"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                Previous
              </button>
              <span>
                {offset + 1}–{Math.min(offset + PAGE_SIZE, page.total)} of {page.total}
              </span>
              <button
                className="ghost"
                disabled={offset + PAGE_SIZE >= page.total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </>
  )
}
