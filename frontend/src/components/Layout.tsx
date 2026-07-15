import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { clearTokens, logout as logoutRequest } from '../api/client'

export default function Layout() {
  const navigate = useNavigate()
  const [navOpen, setNavOpen] = useState(false)

  async function logout() {
    await logoutRequest()
    clearTokens()
    navigate('/login')
  }

  return (
    <div className="shell">
      {!navOpen && (
        <button className="nav-toggle" onClick={() => setNavOpen(true)} aria-label="Open menu">
          ☰
        </button>
      )}
      {navOpen && <div className="nav-overlay" onClick={() => setNavOpen(false)} />}
      <nav className={`sidebar${navOpen ? ' open' : ''}`}>
        <div className="brand">SubTrack</div>
        <NavLink to="/subscriptions" onClick={() => setNavOpen(false)}>
          Subscriptions
        </NavLink>
        <NavLink to="/transactions" onClick={() => setNavOpen(false)}>
          Transactions
        </NavLink>
        <NavLink to="/accounts" onClick={() => setNavOpen(false)}>
          Accounts
        </NavLink>
        <NavLink to="/settings" onClick={() => setNavOpen(false)}>
          Settings
        </NavLink>
        <div className="spacer" />
        <button onClick={logout}>Sign out</button>
      </nav>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
