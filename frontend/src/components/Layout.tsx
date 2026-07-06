import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { clearTokens } from '../api/client'

export default function Layout() {
  const navigate = useNavigate()

  function logout() {
    clearTokens()
    navigate('/login')
  }

  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="brand">SubTrack</div>
        <NavLink to="/subscriptions">Subscriptions</NavLink>
        <NavLink to="/transactions">Transactions</NavLink>
        <NavLink to="/accounts">Accounts</NavLink>
        <div className="spacer" />
        <button onClick={logout}>Sign out</button>
      </nav>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
