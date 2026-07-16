import { Link } from 'react-router-dom'

export default function Terms() {
  return (
    <div className="doc-page">
      <Link to="/" className="back-link">
        ← Back
      </Link>
      <h1>Terms of Service</h1>
      <p className="updated">Last updated: July 2026</p>

      <h2>1. Acceptance of Terms</h2>
      <p>
        By creating a SubTrack account, you agree to these Terms of Service and
        our <Link to="/privacy">Privacy Policy</Link>. If you do not agree, do not
        use SubTrack.
      </p>

      <h2>2. Description of Service</h2>
      <p>
        SubTrack connects to your Canadian bank accounts via Plaid, on a
        read-only basis, and analyzes your transaction history to identify
        recurring subscription payments. SubTrack cannot move money, initiate
        payments, or make any changes to your bank accounts. Subscription
        detection — including cadence, confidence, and merchant identification —
        is provided for informational purposes only and may be inaccurate.
        SubTrack is not a financial advisor, and nothing in the app constitutes
        financial advice.
      </p>

      <h2>3. Eligibility</h2>
      <p>
        You must be at least 18 years old and have the legal authority to link
        the bank accounts you connect to SubTrack.
      </p>

      <h2>4. Account Responsibilities</h2>
      <p>
        You are responsible for maintaining the confidentiality of your account
        credentials and for all activity under your account. Notify us promptly
        if you suspect unauthorized access.
      </p>

      <h2>5. Third-Party Services</h2>
      <p>
        SubTrack relies on Plaid to connect to your bank and Anthropic to assist
        with subscription detection. We are not responsible for the availability,
        accuracy, or conduct of these third-party services, which are governed by
        their own terms and privacy policies.
      </p>

      <h2>6. Prohibited Uses</h2>
      <p>You agree not to:</p>
      <ul>
        <li>Use SubTrack for any unlawful purpose.</li>
        <li>Attempt to gain unauthorized access to any part of the service.</li>
        <li>Interfere with or disrupt the service or its infrastructure.</li>
        <li>Connect bank accounts you are not legally authorized to access.</li>
      </ul>

      <h2>7. Termination</h2>
      <p>
        You may delete your account at any time from Settings → Delete account,
        which permanently removes your data and revokes SubTrack's access to your
        bank. We may suspend or terminate accounts that violate these terms.
      </p>

      <h2>8. Disclaimer of Warranties</h2>
      <p>
        SubTrack is provided "as is" without warranties of any kind, express or
        implied, including accuracy of detected subscriptions, cadence, or
        pricing information.
      </p>

      <h2>9. Limitation of Liability</h2>
      <p>
        To the maximum extent permitted by law, SubTrack and its operators are
        not liable for any indirect, incidental, or consequential damages arising
        from your use of the service, including decisions made based on detected
        subscription data.
      </p>

      <h2>10. Changes to These Terms</h2>
      <p>
        We may update these terms from time to time. Continued use of SubTrack
        after changes take effect constitutes acceptance of the updated terms.
      </p>

      <h2>11. Governing Law</h2>
      <p>
        These terms are governed by the laws of Canada, without regard to
        conflict-of-law principles.
      </p>

      <h2>12. Contact</h2>
      <p>
        Questions about these terms can be sent to{' '}
        <a href="mailto:privacy@subtrack.app">privacy@subtrack.app</a>.
      </p>
    </div>
  )
}
