// Adapted from the cresidential project's ConnectBank: same react-plaid-link
// flow, but authenticated (JWT interceptor) and against /link/token +
// /link/exchange, which persist the encrypted Item server-side.
import { useCallback, useEffect, useState } from 'react'
import { usePlaidLink } from 'react-plaid-link'
import { createLinkToken, exchangePublicToken } from '../api/client'

type Props = {
  onConnected: () => void
}

export default function ConnectBank({ onConnected }: Props) {
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    createLinkToken()
      .then(setLinkToken)
      .catch(() => setError('Could not initialize bank connection — check Plaid configuration.'))
  }, [])

  const onSuccess = useCallback(
    async (publicToken: string) => {
      setBusy(true)
      try {
        await exchangePublicToken(publicToken)
        onConnected()
      } catch {
        setError('Failed to connect bank account.')
      } finally {
        setBusy(false)
      }
    },
    [onConnected],
  )

  const { open, ready } = usePlaidLink({ token: linkToken ?? '', onSuccess })

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <button className="primary" onClick={() => open()} disabled={!ready || busy}>
        {busy ? 'Connecting…' : 'Connect bank account'}
      </button>
    </div>
  )
}
