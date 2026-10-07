/**
 * The one place the frontend talks to the backend.
 *
 *   const orders = await api.get<OrderPage>('/api/orders/', { status: 'PROCESSING' })
 *   await api.patch(`/api/orders/${id}/`, { status: 'SHIPPED' })
 *
 * - The login is a Django session cookie, sent automatically (same origin via the Vite proxy).
 * - Writes (POST/PUT/PATCH/DELETE) carry the CSRF token Django requires.
 * - A failed request throws ApiError with the HTTP status and the server's error body.
 * - A 401 on any request (session expired) fires the `unauthorized` event; AuthContext logs out.
 */

export type ApiErrorBody = {
  detail?: string
  code?: string
  field_errors?: Record<string, string[]>
}

export class ApiError extends Error {
  readonly status: number
  readonly body: ApiErrorBody

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail ?? `Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export const UNAUTHORIZED_EVENT = 'miez:unauthorized'

type Query = Record<string, string | number | boolean | null | undefined>
type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

function csrfToken(): string | undefined {
  return document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('csrftoken='))
    ?.slice('csrftoken='.length)
}

async function ensureCsrfToken(): Promise<string | undefined> {
  // GET /api/auth/me/ always sets the cookie, even when logged out.
  if (!csrfToken()) await fetch('/api/auth/me/')
  return csrfToken()
}

function withQuery(path: string, query?: Query): string {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.append(key, String(value))
  }
  const search = params.toString()
  return search ? `${path}${path.includes('?') ? '&' : '?'}${search}` : path
}

/** DRF returns absolute `next`/`previous` links; keep only path + query so they go through the proxy. */
export function relativeUrl(url: string): string {
  const parsed = new URL(url, window.location.origin)
  return parsed.pathname + parsed.search
}

async function send(method: Method, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (method !== 'GET') {
    const token = await ensureCsrfToken()
    if (token) headers['X-CSRFToken'] = token
  }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(relativeUrl(path), {
    method,
    headers,
    credentials: 'same-origin',
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    const errorBody = (await response.json().catch(() => ({}))) as ApiErrorBody
    throw new ApiError(response.status, errorBody)
  }
  return response
}

async function json<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const response = await send(method, path, body)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string, query?: Query) => json<T>('GET', withQuery(path, query)),
  post: <T = void>(path: string, body?: unknown) => json<T>('POST', path, body),
  put: <T = void>(path: string, body?: unknown) => json<T>('PUT', path, body),
  patch: <T = void>(path: string, body?: unknown) => json<T>('PATCH', path, body),
  delete: <T = void>(path: string) => json<T>('DELETE', path),
  /** For file downloads (reports). */
  blob: async (path: string) => (await send('GET', path)).blob(),
}
