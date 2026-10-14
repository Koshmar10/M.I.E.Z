import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { FiShoppingCart, FiDollarSign, FiClock, FiRotateCcw, FiList, FiPackage } from 'react-icons/fi'
import { api } from '../../api/client'

type OrderRow = {
  id: number
  order_number: string
  customer: number
  customer_name: string
  value_ron: string
  date: string
  status: 'PROCESSING' | 'SHIPPED' | 'DELIVERED' | 'CANCELLED'
  channel: 'EMAG' | 'WEBSITE' | 'DIRECT'
}

type OrderItemDetail = {
  id: number
  product: number
  product_name: string
  product_sku: string
  quantity: number
  unit_price_ron: string
  line_total_ron: string
}

type OrderDetail = {
  id: number
  order_number: string
  customer: number
  customer_name: string
  created_by: number | null
  created_by_username: string | null
  value_ron: string
  date: string
  status: string
  channel: string
  notes: string
  items: OrderItemDetail[]
}

type OrderListResponse = {
  total_count: number
  total_ron_sum: string
  count: number
  next: string | null
  previous: string | null
  results: OrderRow[]
}

type SalesKpiResponse = {
  orders_today: number
  revenue_today_ron: string
  pending_orders: number
  returns_this_week: number
  pct_changes: {
    orders: number
    revenue: number
  }
}

type DailyOrdersPoint = {
  date: string
  orders_count: number
}

type DailyOrdersResponse = {
  days: DailyOrdersPoint[]
}

type TopProduct = {
  product_id: number
  product_name: string
  product_sku: string
  units_sold: number
}

type TopProductsResponse = {
  week_start: string
  week_end: string
  products: TopProduct[]
}

const statusOptions: Array<{ label: string; value: string }> = [
  { label: 'All statuses', value: '' },
  { label: 'Processing', value: 'PROCESSING' },
  { label: 'Shipped', value: 'SHIPPED' },
  { label: 'Delivered', value: 'DELIVERED' },
  { label: 'Cancelled', value: 'CANCELLED' },
]

const channelOptions: Array<{ label: string; value: string }> = [
  { label: 'All channels', value: '' },
  { label: 'eMAG', value: 'EMAG' },
  { label: 'Website', value: 'WEBSITE' },
  { label: 'Direct', value: 'DIRECT' },
]

const statusBadgeClass: Record<string, string> = {
  PROCESSING: 'bg-[var(--input-background)] text-[var(--foreground)] border border-[var(--border)]',
  SHIPPED: 'bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20',
  DELIVERED: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  CANCELLED: 'bg-rose-50 text-rose-700 border border-rose-200',
}

const channelBadgeClass: Record<string, string> = {
  EMAG: 'bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20',
  WEBSITE: 'bg-[var(--input-background)] text-[var(--foreground)] border border-[var(--border)]',
  DIRECT: 'bg-[var(--input-background)] text-[var(--muted-foreground)] border border-[var(--border)]',
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
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleDateString('ro-RO')
}

const formatShortDay = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleDateString('ro-RO', { weekday: 'short' })
}

const SalesDashboard = () => {
  const [kpis, setKpis] = useState<SalesKpiResponse | null>(null)
  const [loadingKpis, setLoadingKpis] = useState(true)
  const [kpisError, setKpisError] = useState('')

  const [dailyOrders, setDailyOrders] = useState<DailyOrdersPoint[]>([])
  const [topProducts, setTopProducts] = useState<TopProduct[]>([])
  const [analyticsWeek, setAnalyticsWeek] = useState<{ week_start: string; week_end: string } | null>(null)
  const [loadingAnalytics, setLoadingAnalytics] = useState(true)
  const [analyticsError, setAnalyticsError] = useState('')

  const [orders, setOrders] = useState<OrderRow[]>([])
  const [loadingOrders, setLoadingOrders] = useState(true)
  const [ordersError, setOrdersError] = useState('')

  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [channelFilter, setChannelFilter] = useState('')

  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [totalRonSum, setTotalRonSum] = useState('0')
  const [nextPageUrl, setNextPageUrl] = useState<string | null>(null)
  const [previousPageUrl, setPreviousPageUrl] = useState<string | null>(null)

  const [selectedOrder, setSelectedOrder] = useState<OrderDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [detailError, setDetailError] = useState('')

  useEffect(() => {
    setPage(1)
  }, [search, statusFilter, channelFilter])

  useEffect(() => {
    const loadKpis = async () => {
      try {
        setLoadingKpis(true)
        setKpisError('')

        setKpis(await api.get<SalesKpiResponse>('/api/sales/dashboard/'))
      } catch (error) {
        console.error('Failed to load sales KPIs:', error)
        setKpisError('Could not load KPI cards right now.')
      } finally {
        setLoadingKpis(false)
      }
    }

    loadKpis()
  }, [])

  useEffect(() => {
    const loadAnalytics = async () => {
      try {
        setLoadingAnalytics(true)
        setAnalyticsError('')

        const [dailyResult, topProductsResult] = await Promise.allSettled([
          api.get<DailyOrdersResponse>('/api/sales/daily-orders/'),
          api.get<TopProductsResponse>('/api/sales/top-products/'),
        ])

        let dailyLoaded = false

        if (dailyResult.status === 'fulfilled') {
          const dailyData = dailyResult.value
          const normalizedDays = Array.isArray(dailyData.days) ? [...dailyData.days] : []
          normalizedDays.sort((a, b) => a.date.localeCompare(b.date))
          setDailyOrders(normalizedDays)
          dailyLoaded = true
        } else {
          setDailyOrders([])
        }

        if (topProductsResult.status === 'fulfilled') {
          const topData = topProductsResult.value
          setTopProducts(Array.isArray(topData.products) ? topData.products : [])
          setAnalyticsWeek({ week_start: topData.week_start, week_end: topData.week_end })
        } else {
          setTopProducts([])
          setAnalyticsWeek(null)
        }

        if (!dailyLoaded) {
          throw new Error('Daily trend data could not be loaded.')
        }
      } catch (error) {
        console.error('Failed to load sales analytics:', error)
        setAnalyticsError('Could not load weekly sales analytics right now.')
      } finally {
        setLoadingAnalytics(false)
      }
    }

    loadAnalytics()
  }, [])

  useEffect(() => {
    const loadOrders = async () => {
      try {
        setLoadingOrders(true)
        setOrdersError('')

        const params = new URLSearchParams()
        params.set('page', String(page))
        params.set('page_size', '10')

        if (search.trim()) {
          params.set('search', search.trim())
        }
        if (statusFilter) {
          params.set('status', statusFilter)
        }
        if (channelFilter) {
          params.set('channel', channelFilter)
        }

        const data = await api.get<OrderListResponse>(`/api/orders/?${params.toString()}`)
        setOrders(Array.isArray(data.results) ? data.results : [])
        setTotalCount(data.total_count ?? 0)
        setTotalRonSum(data.total_ron_sum ?? '0')
        setNextPageUrl(data.next ?? null)
        setPreviousPageUrl(data.previous ?? null)
      } catch (error) {
        console.error('Failed to load orders list:', error)
        setOrdersError('Could not load orders right now.')
      } finally {
        setLoadingOrders(false)
      }
    }

    loadOrders()
  }, [search, statusFilter, channelFilter, page])

  const openOrderDetail = async (orderId: number) => {
    try {
      setLoadingDetail(true)
      setDetailError('')
      setSelectedOrder(null)

      setSelectedOrder(await api.get<OrderDetail>(`/api/orders/${orderId}/`))
    } catch (error) {
      console.error('Failed to load order detail:', error)
      setDetailError('Could not load order details.')
    } finally {
      setLoadingDetail(false)
    }
  }

  const closeModal = () => {
    setSelectedOrder(null)
    setDetailError('')
  }

  const dailyChartData = useMemo(() => {
    return dailyOrders.map(point => ({
      label: formatShortDay(point.date),
      orders: point.orders_count,
    }))
  }, [dailyOrders])

  const averageOrderValue = useMemo(() => {
    if (!totalCount) {
      return 0
    }
    return Number(totalRonSum) / totalCount
  }, [totalCount, totalRonSum])

  const kpiCards = kpis
    ? [
        { title: 'Orders Today', value: kpis.orders_today, sub: `${kpis.pct_changes.orders}% vs yesterday`, Icon: FiShoppingCart },
        { title: 'Revenue Today', value: formatCurrencyRon(kpis.revenue_today_ron), sub: `${kpis.pct_changes.revenue}% vs yesterday`, Icon: FiDollarSign },
        { title: 'Processing Orders', value: kpis.pending_orders, sub: 'awaiting fulfilment', Icon: FiClock },
        { title: 'Cancelled This Week', value: kpis.returns_this_week, sub: 'last 7 days', Icon: FiRotateCcw },
        { title: 'Orders In View', value: totalCount, sub: 'after filters', Icon: FiList },
      ]
    : []

  return (
    <div className="space-y-6">
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <h2 className="text-[1.05rem] font-semibold tracking-tight">Sales Dashboard</h2>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">Today's KPI snapshot with order operations.</p>

        {loadingKpis ? (
          <p className="text-sm text-[var(--muted-foreground)] mt-3">Loading KPI cards...</p>
        ) : kpisError ? (
          <p className="text-sm text-[var(--destructive)] mt-3">{kpisError}</p>
        ) : kpis ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mt-4">
            {kpiCards.map(card => {
              const Icon = card.Icon
              return (
                <article
                  key={card.title}
                  className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 flex items-start justify-between gap-3"
                >
                  <div className="flex flex-col">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium">{card.title}</p>
                    <p className="text-2xl font-semibold mt-1 tracking-tight">{card.value}</p>
                    <p className="text-xs text-[var(--muted-foreground)] mt-1">{card.sub}</p>
                  </div>
                  <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
                    <Icon size={18} />
                  </div>
                </article>
              )
            })}
          </div>
        ) : null}

      </section>

      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-[1.05rem] font-semibold tracking-tight">Weekly Orders Trend</h3>
            <p className="text-sm text-[var(--muted-foreground)] mt-1">Last 7 days and top products for current ISO week.</p>
          </div>
          {analyticsWeek && (
            <p className="text-xs text-[var(--muted-foreground)]">
              Week: {formatDate(analyticsWeek.week_start)} – {formatDate(analyticsWeek.week_end)}
            </p>
          )}
        </div>

        {loadingAnalytics ? (
          <p className="text-sm text-[var(--muted-foreground)] mt-3">Loading chart data...</p>
        ) : analyticsError ? (
          <p className="text-sm text-[var(--destructive)] mt-3">{analyticsError}</p>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mt-4">
            <div className="xl:col-span-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium mb-3">Orders per day</p>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dailyChartData} margin={{ top: 8, right: 4, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid var(--border)' }} />
                    <Bar dataKey="orders" fill="var(--primary)" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium mb-3">Top products this week</p>
              {topProducts.length === 0 ? (
                <p className="text-sm text-[var(--muted-foreground)]">No product sales this week yet.</p>
              ) : (
                <ul className="space-y-2">
                  {topProducts.map((item, index) => (
                    <li key={item.product_id} className="rounded-lg border border-[var(--border)] px-3 py-2 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="w-6 h-6 rounded-md bg-[var(--input-background)] text-[var(--primary)] text-[11px] font-bold grid place-items-center shrink-0">
                          {index + 1}
                        </span>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold truncate">{item.product_name}</p>
                          <p className="text-xs text-[var(--muted-foreground)] truncate">{item.product_sku}</p>
                        </div>
                      </div>
                      <span className="text-sm font-semibold shrink-0">{item.units_sold}<span className="text-xs text-[var(--muted-foreground)] font-normal ml-1">units</span></span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>

      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { title: 'Filtered Orders', value: totalCount, Icon: FiList },
            { title: 'Filtered Total Value', value: formatCurrencyRon(totalRonSum), Icon: FiDollarSign },
            { title: 'Average Order Value', value: formatCurrencyRon(averageOrderValue), Icon: FiPackage },
          ].map(({ title, value, Icon }) => (
            <article key={title} className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 flex items-start justify-between gap-3">
              <div className="flex flex-col">
                <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium">{title}</p>
                <p className="text-2xl font-semibold mt-1 tracking-tight">{value}</p>
              </div>
              <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
                <Icon size={18} />
              </div>
            </article>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="md:col-span-2">
            <label className="block text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Search</label>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Order number or customer name"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/30"
            />
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Status</label>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm"
            >
              {statusOptions.map((option) => (
                <option key={option.label} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-1">Channel</label>
            <select
              value={channelFilter}
              onChange={(event) => setChannelFilter(event.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm"
            >
              {channelOptions.map((option) => (
                <option key={option.label} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {loadingOrders ? (
          <p className="text-sm text-[var(--muted-foreground)]">Loading orders...</p>
        ) : ordersError ? (
          <p className="text-sm text-[var(--destructive)]">{ordersError}</p>
        ) : (
          <>
            <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
              <table className="min-w-full text-sm">
                <thead className="bg-[var(--input-background)]">
                  <tr>
                    {['Order', 'Customer', 'Date', 'Status', 'Channel'].map(h => (
                      <th key={h} className="text-left text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] px-4 py-2.5">{h}</th>
                    ))}
                    <th className="text-right text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] px-4 py-2.5">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr
                      key={order.id}
                      className="border-t border-[var(--border)] cursor-pointer hover:bg-[var(--input-background)] transition-colors"
                      onClick={() => openOrderDetail(order.id)}
                    >
                      <td className="px-4 py-2.5 font-semibold">{order.order_number}</td>
                      <td className="px-4 py-2.5">{order.customer_name}</td>
                      <td className="px-4 py-2.5">{formatDate(order.date)}</td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass[order.status] ?? 'bg-[var(--input-background)] text-[var(--muted-foreground)] border border-[var(--border)]'}`}>
                          {order.status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${channelBadgeClass[order.channel] ?? 'bg-[var(--input-background)] text-[var(--muted-foreground)] border border-[var(--border)]'}`}>
                          {order.channel}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right font-semibold">{formatCurrencyRon(order.value_ron)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-[var(--muted-foreground)]">Page {page}</p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={!previousPageUrl}
                  className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--input-background)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={!nextPageUrl}
                  className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--input-background)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      {(loadingDetail || selectedOrder || detailError) && (
        <div className="fixed inset-0 z-50 bg-black/40 p-4 flex items-center justify-center" onClick={closeModal}>
          <div className="w-full max-w-3xl max-h-[85vh] overflow-y-auto bg-[var(--card)] rounded-2xl border border-[var(--border)] p-5" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-[1.05rem] font-semibold tracking-tight">Order Details</h3>
                {selectedOrder && (
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">
                    {selectedOrder.order_number} · {selectedOrder.customer_name}
                  </p>
                )}
              </div>
              <button
                type="button"
                className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--input-background)] transition-colors"
                onClick={closeModal}
              >
                Close
              </button>
            </div>

            {loadingDetail ? (
              <p className="text-sm text-[var(--muted-foreground)] mt-4">Loading order details...</p>
            ) : detailError ? (
              <p className="text-sm text-[var(--destructive)] mt-4">{detailError}</p>
            ) : selectedOrder ? (
              <div className="space-y-4 mt-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {[
                    { label: 'Status', value: selectedOrder.status },
                    { label: 'Channel', value: selectedOrder.channel },
                    { label: 'Date', value: formatDate(selectedOrder.date) },
                    { label: 'Total', value: formatCurrencyRon(selectedOrder.value_ron) },
                  ].map(({ label, value }) => (
                    <div key={label} className="rounded-xl border border-[var(--border)] p-3">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium">{label}</p>
                      <p className="text-sm font-semibold mt-1">{value}</p>
                    </div>
                  ))}
                </div>

                <div>
                  <h4 className="text-sm font-semibold">Line Items</h4>
                  <div className="overflow-x-auto mt-2 rounded-xl border border-[var(--border)]">
                    <table className="min-w-full text-sm">
                      <thead className="bg-[var(--input-background)]">
                        <tr>
                          <th className="text-left text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] px-4 py-2.5">Product</th>
                          <th className="text-left text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] px-4 py-2.5">SKU</th>
                          <th className="text-right text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] px-4 py-2.5">Qty</th>
                          <th className="text-right text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] px-4 py-2.5">Unit Price</th>
                          <th className="text-right text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] px-4 py-2.5">Line Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedOrder.items.map((item) => (
                          <tr key={item.id} className="border-t border-[var(--border)]">
                            <td className="px-4 py-2.5">{item.product_name}</td>
                            <td className="px-4 py-2.5 text-[var(--muted-foreground)]">{item.product_sku}</td>
                            <td className="px-4 py-2.5 text-right">{item.quantity}</td>
                            <td className="px-4 py-2.5 text-right">{formatCurrencyRon(item.unit_price_ron)}</td>
                            <td className="px-4 py-2.5 text-right font-semibold">{formatCurrencyRon(item.line_total_ron)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}

export default SalesDashboard