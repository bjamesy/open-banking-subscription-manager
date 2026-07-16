// Adapted from the cresidential project's ConnectBank: same react-plaid-link
// flow, but authenticated (JWT interceptor) and against /link/token +
// /link/exchange, which persist the encrypted Item server-side.
import { useCallback, useEffect, useState } from 'react'
import { usePlaidLink } from 'react-plaid-link'
import {
  createLinkToken,
  exchangePublicToken,
  getConsentStatus,
  grantConsent,
  reconnectItem,
} from '../api/client'

type Props = {
  onConnected: () => void
  // When set, opens Plaid Link in update mode against this Item (re-auth of
  // an existing connection) instead of creating a new one.
  itemId?: number
}

export default function ConnectBank({ onConnected, itemId }: Props) {
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // Reconnect implies consent was already given at first link — only fresh
  // links need to check/gate on it, so this starts (and stays) true there.
  const [consented, setConsented] = useState(Boolean(itemId))
  const [showConsent, setShowConsent] = useState(false)

  useEffect(() => {
    createLinkToken(itemId)
      .then(setLinkToken)
      .catch(() => setError('Could not initialize bank connection — check Plaid configuration.'))
  }, [itemId])

  useEffect(() => {
    if (itemId) return
    getConsentStatus()
      .then((s) => setConsented(s.consented))
      .catch(() => setConsented(false))
  }, [itemId])

  const onSuccess = useCallback(
    async (publicToken: string) => {
      setBusy(true)
      try {
        if (itemId) {
          await reconnectItem(itemId)
        } else {
          await exchangePublicToken(publicToken)
        }
        onConnected()
      } catch {
        setError(itemId ? 'Failed to reconnect bank account.' : 'Failed to connect bank account.')
      } finally {
        setBusy(false)
      }
    },
    [onConnected, itemId],
  )

  const { open, ready } = usePlaidLink({ token: linkToken ?? '', onSuccess })

  function handleClick() {
    if (!itemId && !consented) {
      setShowConsent(true)
      return
    }
    open()
  }

  async function handleAgree() {
    try {
      await grantConsent()
      setConsented(true)
      setShowConsent(false)
      open()
    } catch {
      setError('Failed to record consent — try again.')
    }
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <button className={itemId ? 'ghost' : 'primary'} onClick={handleClick} disabled={!ready || busy}>
        {busy ? (itemId ? 'Reconnecting…' : 'Connecting…') : itemId ? 'Reconnect' : 'Connect bank account'}
      </button>
      {showConsent && (
        <div className="card" style={{ padding: 16, marginTop: 8, maxWidth: 420 }}>
          <p style={{ fontSize: 13, marginBottom: 10 }}>
            Connecting your bank shares read-only transaction data with SubTrack via
            Plaid. Merchant names and amounts are sent to Anthropic&apos;s Claude API to
            help detect recurring subscriptions. Data is retained until you delete
            your account (Settings), which also revokes SubTrack&apos;s bank access.
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="primary" onClick={handleAgree}>
              Agree &amp; continue
            </button>
            <button className="ghost" onClick={() => setShowConsent(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
