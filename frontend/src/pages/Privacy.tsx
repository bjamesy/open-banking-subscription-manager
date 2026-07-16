import { Link } from 'react-router-dom'

export default function Privacy() {
  return (
    <div className="doc-page">
      <Link to="/" className="back-link">
        ← Back
      </Link>
      <h1>Privacy Policy</h1>
      <p className="updated">Last updated: July 2026</p>

      <h2>1. Overview</h2>
      <p>
        SubTrack connects to your Canadian bank accounts through Plaid to import
        transaction history and automatically detect recurring subscription
        payments. SubTrack is strictly read-only: it cannot move money, initiate
        payments, or make changes to your bank accounts.
      </p>

      <h2>2. Information We Collect</h2>
      <p>When you use SubTrack, we collect:</p>
      <ul>
        <li>
          <strong>Account information</strong> — the email address you register
          with. Your password is never stored in plain text; it is hashed with
          bcrypt before being saved.
        </li>
        <li>
          <strong>Bank connection data</strong> — when you link a bank account via
          Plaid, we store an encrypted access token (Fernet encryption) that lets
          us request updated transaction data on your behalf. We never see or
          store your bank login credentials — those are handled entirely by Plaid.
        </li>
        <li>
          <strong>Transaction data</strong> — merchant names, amounts, dates, and
          account associations for transactions in accounts you connect.
        </li>
        <li>
          <strong>Detected subscriptions</strong> — the recurring payments SubTrack
          identifies from your transaction history, along with any changes you
          make to them (confirming, dismissing, or adding one manually).
        </li>
      </ul>

      <h2>3. How We Use Your Information</h2>
      <p>
        We use your transaction data to detect recurring subscription payments and
        present them to you. Detection happens in two stages: a heuristic pass
        that runs entirely within SubTrack, and — for transactions the heuristic
        pass isn't confident about — an AI-assisted pass. In that second stage,
        merchant names and amounts (not your name, email, or full bank details)
        are sent to Anthropic's Claude API to help classify whether a charge is a
        genuine subscription and estimate its billing cadence.
      </p>

      <h2>4. Third-Party Services</h2>
      <p>
        SubTrack relies on two third-party services to operate:
      </p>
      <ul>
        <li>
          <strong>Plaid</strong>, which connects to your bank on a read-only
          basis. See{' '}
          <a href="https://plaid.com/legal/" target="_blank" rel="noreferrer">
            Plaid's Privacy Policy
          </a>
          .
        </li>
        <li>
          <strong>Anthropic</strong>, which processes transaction data (merchant
          names and amounts only) to assist subscription detection. See{' '}
          <a href="https://www.anthropic.com/legal/privacy" target="_blank" rel="noreferrer">
            Anthropic's Privacy Policy
          </a>
          .
        </li>
      </ul>

      <h2>5. Data Retention &amp; Deletion</h2>
      <p>
        We retain your data for as long as your account exists. You can
        permanently delete your account at any time from Settings → Delete
        account. Deleting your account removes all of your data — linked bank
        connections, transactions, and detected subscriptions — and revokes
        SubTrack's access to your bank at Plaid. This action cannot be undone.
      </p>

      <h2>6. Data Security</h2>
      <p>
        Bank access tokens are encrypted at rest (Fernet) and only decrypted
        in-memory, briefly, to make a sync request. Passwords are hashed with
        bcrypt. Sessions use short-lived access tokens and revocable refresh
        tokens — signing out immediately invalidates all of your active sessions.
      </p>

      <h2>7. Your Rights</h2>
      <p>You have the right to:</p>
      <ul>
        <li>Access the data we hold about you (visible directly in the app).</li>
        <li>Correct inaccurate information.</li>
        <li>Withdraw consent for AI-assisted processing by deleting your account.</li>
        <li>Request permanent deletion of your account and all associated data.</li>
      </ul>

      <h2>8. Data Residency</h2>
      <p>
        SubTrack's hosting location and data-residency posture are finalized as
        part of our production deployment. This section will be updated with
        specifics once that is complete.
      </p>

      <h2>9. Children's Privacy</h2>
      <p>
        SubTrack is not directed at, and is not intended for use by, individuals
        under the age of 18.
      </p>

      <h2>10. Changes to This Policy</h2>
      <p>
        We may update this policy from time to time. Material changes — such as a
        new use of your data — will require you to re-consent the next time you
        connect a bank account.
      </p>

      <h2>11. Contact</h2>
      <p>
        Questions about this policy or your data can be sent to{' '}
        <a href="mailto:privacy@subtrack.app">privacy@subtrack.app</a>.
      </p>
    </div>
  )
}
