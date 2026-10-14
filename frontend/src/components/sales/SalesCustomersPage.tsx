import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts'

type CustomerRow = {
  id: number
  name: string
  contact_name: string
  location: string
  tier: 'Gold' | 'Silver' | 'Bronze' | 'Individual'
  orders_count: number
  total_value_ron: string
}

type CustomerOrder = {
  id: number
  order_number: string
  value_ron: string
  date: string
  status: string
  channel: string
}

type CustomerDetail = {
  id: number
  name: string
  contact_name: string
  contact_email: string
  contact_phone: string
  address: string
  location: string
  tier: string
  notes: string
  orders: CustomerOrder[]
}

type CustomerListResponse = {
  count: number
  next: string | null
  previous: string | null
  results: CustomerRow[]
}

const tierBadgeClass: Record<string, string> = {
  Gold: 'bg-amber-50 text-amber-800 border border-amber-300',
  Silver: 'bg-slate-100 text-slate-700 border border-slate-300',
  Bronze: 'bg-orange-50 text-orange-800 border border-orange-300',
  Individual: 'bg-blue-50 text-blue-700 border border-blue-200',
}

const formatCurrencyRon = (value: string | number) => {
  const numeric = Number(value || 0)
  return new Intl.NumberFormat('ro-RO', {
    style: 'currency',
    currency: 'RON',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric)
}

const formatDate = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('ro-RO')
}

const SalesCustomersPage = () => {
  const [customers, setCustomers] = useState<CustomerRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [nextPageUrl, setNextPageUrl] = useState<string | null>(null)
  const [previousPageUrl, setPreviousPageUrl] = useState<string | null>(null)

  const [selectedCustomer, setSelectedCustomer] = useState<CustomerDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [detailError, setDetailError] = useState('')

  useEffect(() => {
    setPage(1)
  }, [search])

  useEffect(() => {
    const loadCustomers = async () => {
      try {
        setLoading(true)
        setError('')

        const params = new URLSearchParams()
        params.set('page', String(page))
        params.set('page_size', '10')

        const data = await api.get<CustomerListResponse>(`/api/customers/?${params.toString()}`)
        setCustomers(data.results)
        setTotalCount(data.count)
        setNextPageUrl(data.next)
        setPreviousPageUrl(data.previous)
      } catch (err) {
        console.error('Failed to load customers:', err)
        setError('Could not load customers right now.')
      } finally {
        setLoading(false)
      }
    }

    void loadCustomers()
  }, [page])

  const filteredCustomers = search.trim()
    ? customers.filter((c) => c.name.toLowerCase().includes(search.trim().toLowerCase()))
    : customers

  const chartData = filteredCustomers.map((c) => ({
    name: c.name.length > 18 ? `${c.name.slice(0, 16)}…` : c.name,
    orders: c.orders_count,
  }))

  const openCustomerDetail = async (customerId: number) => {
    try {
      setLoadingDetail(true)
      setDetailError('')
      setSelectedCustomer(null)

      setSelectedCustomer(await api.get<CustomerDetail>(`/api/customers/${customerId}/`))
    } catch (err) {
      console.error('Failed to load customer detail:', err)
      setDetailError('Could not load customer details.')
    } finally {
      setLoadingDetail(false)
    }
  }

  const closeModal = () => {
    setSelectedCustomer(null)
    setDetailError('')
  }

  return (
    <div className="space-y-6">
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">Customers</h2>
            <p className="text-sm text-black/60 mt-1">Ranked by total revenue. Click a row to view order history.</p>
          </div>
          <div className="text-right text-sm text-black/60">
            <p>{totalCount} customers</p>
          </div>
        </div>
      </section>

      {chartData.length > 0 && (
        <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
          <h3 className="text-sm font-semibold mb-4">Orders per Customer (current page)</h3>
          <ResponsiveContainer width="100%" height={Math.max(180, chartData.length * 36)}>
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 0, right: 20, left: 8, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
              <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
              <RechartsTooltip
                formatter={(value: number) => [`${value} orders`, 'Orders']}
                contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
              />
              <Bar dataKey="orders" fill="#6366f1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </section>
      )}

      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
        <div className="max-w-sm">
          <label className="text-xs font-semibold uppercase tracking-wide text-black/50">Search</label>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Customer name"
            className="w-full mt-1 rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm"
          />
        </div>

        {loading ? (
          <p className="text-sm text-black/60">Loading customers...</p>
        ) : error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full border-separate border-spacing-y-2">
                <thead>
                  <tr>
                    <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">Name</th>
                    <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">Contact</th>
                    <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">Location</th>
                    <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">Tier</th>
                    <th className="text-right text-xs uppercase tracking-wide text-black/50 px-3">Orders</th>
                    <th className="text-right text-xs uppercase tracking-wide text-black/50 px-3">Total Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCustomers.map((customer) => (
                    <tr
                      key={customer.id}
                      className="bg-white border border-[var(--border)] cursor-pointer hover:bg-black/[0.02]"
                      onClick={() => void openCustomerDetail(customer.id)}
                    >
                      <td className="px-3 py-2 text-sm font-semibold">{customer.name}</td>
                      <td className="px-3 py-2 text-sm text-black/60">{customer.contact_name || '—'}</td>
                      <td className="px-3 py-2 text-sm text-black/60">{customer.location || '—'}</td>
                      <td className="px-3 py-2 text-sm">
                        <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${tierBadgeClass[customer.tier] ?? 'bg-slate-100 text-slate-700 border border-slate-300'}`}>
                          {customer.tier}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-sm text-right">{customer.orders_count}</td>
                      <td className="px-3 py-2 text-sm text-right font-semibold">{formatCurrencyRon(customer.total_value_ron)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-black/60">Page {page} · {totalCount} total</p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={!previousPageUrl}
                  className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={!nextPageUrl}
                  className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      {(loadingDetail || selectedCustomer || detailError) && (
        <div
          className="fixed inset-0 z-50 bg-black/40 p-4 flex items-center justify-center"
          onClick={closeModal}
        >
          <div
            className="w-full max-w-3xl max-h-[85vh] overflow-y-auto bg-white rounded-2xl border border-[var(--border)] p-5"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold">Customer Details</h3>
                {selectedCustomer && (
                  <p className="text-sm text-black/60 mt-1">{selectedCustomer.name}</p>
                )}
              </div>
              <button
                type="button"
                className="rounded-lg border border-[var(--border)] px-3 py-1 text-sm"
                onClick={closeModal}
              >
                Close
              </button>
            </div>

            {loadingDetail ? (
              <p className="text-sm text-black/60 mt-4">Loading customer details...</p>
            ) : detailError ? (
              <p className="text-sm text-red-600 mt-4">{detailError}</p>
            ) : selectedCustomer ? (
              <div className="space-y-4 mt-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  <div className="rounded-xl border border-[var(--border)] p-3">
                    <p className="text-xs uppercase tracking-wide text-black/50">Contact</p>
                    <p className="text-sm font-semibold mt-1">{selectedCustomer.contact_name || '—'}</p>
                  </div>
                  <div className="rounded-xl border border-[var(--border)] p-3">
                    <p className="text-xs uppercase tracking-wide text-black/50">Email</p>
                    <p className="text-sm font-semibold mt-1 break-all">{selectedCustomer.contact_email || '—'}</p>
                  </div>
                  <div className="rounded-xl border border-[var(--border)] p-3">
                    <p className="text-xs uppercase tracking-wide text-black/50">Phone</p>
                    <p className="text-sm font-semibold mt-1">{selectedCustomer.contact_phone || '—'}</p>
                  </div>
                  <div className="rounded-xl border border-[var(--border)] p-3">
                    <p className="text-xs uppercase tracking-wide text-black/50">Location</p>
                    <p className="text-sm font-semibold mt-1">{selectedCustomer.location || '—'}</p>
                  </div>
                  <div className="rounded-xl border border-[var(--border)] p-3">
                    <p className="text-xs uppercase tracking-wide text-black/50">Tier</p>
                    <p className="text-sm font-semibold mt-1">{selectedCustomer.tier}</p>
                  </div>
                  {selectedCustomer.notes && (
                    <div className="rounded-xl border border-[var(--border)] p-3 sm:col-span-2 lg:col-span-3">
                      <p className="text-xs uppercase tracking-wide text-black/50">Notes</p>
                      <p className="text-sm mt-1">{selectedCustomer.notes}</p>
                    </div>
                  )}
                </div>

                <div>
                  <h4 className="text-sm font-semibold">Order History</h4>
                  {selectedCustomer.orders.length === 0 ? (
                    <p className="text-sm text-black/60 mt-2">No orders yet.</p>
                  ) : (
                    <div className="overflow-x-auto mt-2">
                      <table className="min-w-full border-separate border-spacing-y-2">
                        <thead>
                          <tr>
                            <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">Order</th>
                            <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">Date</th>
                            <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">Status</th>
                            <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">Channel</th>
                            <th className="text-right text-xs uppercase tracking-wide text-black/50 px-3">Value</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedCustomer.orders.map((order) => (
                            <tr key={order.id} className="bg-white border border-[var(--border)]">
                              <td className="px-3 py-2 text-sm font-semibold">{order.order_number}</td>
                              <td className="px-3 py-2 text-sm">{formatDate(order.date)}</td>
                              <td className="px-3 py-2 text-sm">{order.status}</td>
                              <td className="px-3 py-2 text-sm">{order.channel}</td>
                              <td className="px-3 py-2 text-sm text-right font-semibold">{formatCurrencyRon(order.value_ron)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}

export default SalesCustomersPage
