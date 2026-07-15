// Adapted from the cresidential project's ConnectBank: same react-plaid-link
// flow, but authenticated (JWT interceptor) and against /link/token +
// /link/exchange, which persist the encrypted Item server-side.
import { useCallback, useEffect, useState } from 'react'
import { usePlaidLink } from 'react-plaid-link'
import { createLinkToken, exchangePublicToken, reconnectItem } from '../api/client'

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

  useEffect(() => {
    createLinkToken(itemId)
      .then(setLinkToken)
      .catch(() => setError('Could not initialize bank connection — check Plaid configuration.'))
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

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <button className={itemId ? 'ghost' : 'primary'} onClick={() => open()} disabled={!ready || busy}>
        {busy ? (itemId ? 'Reconnecting…' : 'Connecting…') : itemId ? 'Reconnect' : 'Connect bank account'}
      </button>
    </div>
  )
}
