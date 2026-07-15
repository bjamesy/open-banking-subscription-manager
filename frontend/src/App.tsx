import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Accounts from './pages/Accounts'
import Login from './pages/Login'
import Settings from './pages/Settings'
import Subscriptions from './pages/Subscriptions'
import Transactions from './pages/Transactions'
import { getAccessToken } from './api/client'

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!getAccessToken()) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/subscriptions" replace />} />
        <Route path="/subscriptions" element={<Subscriptions />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/accounts" element={<Accounts />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
