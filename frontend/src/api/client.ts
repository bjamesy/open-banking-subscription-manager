import axios, { AxiosError } from 'axios'

// All calls go through /api (Vite dev proxy strips the prefix; production
// should route /api to the backend the same way).
const api = axios.create({ baseURL: '/api' })

// --- token storage -----------------------------------------------------

const ACCESS_KEY = 'subtrack.access_token'
const REFRESH_KEY = 'subtrack.refresh_token'

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY)
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access)
  localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, try one refresh, replay the request, and hard-logout on failure.
let refreshing: Promise<void> | null = null

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const original = error.config
  const refreshToken = localStorage.getItem(REFRESH_KEY)
  if (
    error.response?.status !== 401 ||
    !original ||
    (original as { _retried?: boolean })._retried ||
    original.url === '/auth/refresh' ||
    !refreshToken
  ) {
    throw error
  }

  refreshing ??= axios
    .post('/api/auth/refresh', { refresh_token: refreshToken })
    .then((r) => setTokens(r.data.access_token, r.data.refresh_token))
    .finally(() => {
      refreshing = null
    })

  try {
    await refreshing
  } catch {
    clearTokens()
    window.location.assign('/login')
    throw error
  }

  ;(original as { _retried?: boolean })._retried = true
  return api.request(original)
})

// --- types (mirror the backend response models) ------------------------

export type Subscription = {
  id: number
  merchant_normalized: string
  amount: number
  currency: string | null
  cadence: string | null
  confidence_score: number | null
  status: 'detected' | 'confirmed' | 'dismissed'
  next_expected_charge: string | null
  detection_source: string | null
}

export type Account = {
  id: number
  item_id: number
  name: string
  mask: string | null
  type: string | null
  subtype: string | null
  currency: string | null
  institution_name: string | null
  item_status: string
  error: string | null
  last_synced_at: string | null
}

export type Transaction = {
  id: number
  account_id: number
  amount: number
  currency: string | null
  merchant_raw: string
  merchant_normalized: string | null
  posted_at: string
}

export type TransactionPage = {
  items: Transaction[]
  total: number
  limit: number
  offset: number
}

// --- endpoints ----------------------------------------------------------

export async function register(email: string, password: string): Promise<void> {
  await api.post('/auth/register', { email, password })
}

export async function login(email: string, password: string): Promise<void> {
  const r = await api.post('/auth/login', { email, password })
  setTokens(r.data.access_token, r.data.refresh_token)
}

export async function loginWithGoogle(idToken: string): Promise<void> {
  const r = await api.post('/auth/google', { id_token: idToken })
  setTokens(r.data.access_token, r.data.refresh_token)
}

export async function logout(): Promise<void> {
  // Best-effort: a failed revocation shouldn't trap the user in a logged-in
  // UI state — local tokens get cleared by the caller regardless.
  await api.post('/auth/logout').catch(() => {})
}

export async function deleteAccount(password: string): Promise<void> {
  await api.delete('/auth/me', { data: { password: password || undefined } })
}

export async function listSubscriptions(status?: string): Promise<Subscription[]> {
  const r = await api.get('/subscriptions', { params: status ? { status } : {} })
  return r.data
}

export async function updateSubscriptionStatus(
  id: number,
  status: 'confirmed' | 'dismissed',
): Promise<Subscription> {
  const r = await api.patch(`/subscriptions/${id}`, { status })
  return r.data
}

export async function addSubscription(input: {
  merchant: string
  amount: string
  cadence?: string
}): Promise<Subscription> {
  const r = await api.post('/subscriptions', input)
  return r.data
}

export async function listAccounts(): Promise<Account[]> {
  const r = await api.get('/accounts')
  return r.data
}

export async function listTransactions(params: {
  account_id?: number
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}): Promise<TransactionPage> {
  const r = await api.get('/transactions', { params })
  return r.data
}

export async function createLinkToken(itemId?: number): Promise<string> {
  const r = await api.post('/link/token', itemId ? { item_id: itemId } : {})
  return r.data.link_token
}

export async function exchangePublicToken(publicToken: string): Promise<void> {
  await api.post('/link/exchange', { public_token: publicToken })
}

export async function reconnectItem(itemId: number): Promise<void> {
  await api.post(`/accounts/${itemId}/reconnect`)
}

export type RescanJob = {
  id: number
  status: 'pending' | 'running' | 'done' | 'failed'
  items_synced: number | null
  items_failed: number | null
  error: string | null
}

export async function startRescan(): Promise<RescanJob> {
  const r = await api.post('/accounts/rescan')
  return r.data
}

export async function getRescanJob(id: number): Promise<RescanJob> {
  const r = await api.get(`/accounts/rescan/${id}`)
  return r.data
}
