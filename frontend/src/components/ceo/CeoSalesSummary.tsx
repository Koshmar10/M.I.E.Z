import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../../api/client'

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

type RevenueTrendDay = {
  date: string
  current_year: string
  prior_year: string
}

type TopProduct = {
  product_id: number
  product_name: string
  product_sku: string
  units_sold: number
}

const formatCurrencyRon = (value: string | number) => {
  const numeric = Number(value || 0)
  return new Intl.NumberFormat('ro-RO', {
    style: 'currency',
    currency: 'RON',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(numeric)
}

const formatShortDay = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('en-GB', { weekday: 'short' })
}

const CeoSalesSummary = () => {
  const [kpis, setKpis] = useState<SalesKpiResponse | null>(null)
  const [trend, setTrend] = useState<RevenueTrendDay[]>([])
  const [topProducts, setTopProducts] = useState<TopProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError('')

        const [kpiData, trendData, topData] = await Promise.all([
          api.get<SalesKpiResponse>('/api/sales/dashboard/'),
          api.get<{ days: RevenueTrendDay[] }>('/api/sales/revenue-trend/'),
          api.get<{ products: TopProduct[] }>('/api/sales/top-products/'),
        ])

        setKpis(kpiData)
        setTrend(Array.isArray(trendData.days) ? trendData.days : [])
        setTopProducts(Array.isArray(topData.products) ? topData.products : [])
      } catch (err) {
        console.error('Could not load CEO Sales summary', err)
        setError('Could not load Sales summary data right now.')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [])

  const kpiTiles = useMemo(() => {
    if (!kpis) return []
    return [
      { label: 'Orders Today', value: kpis.orders_today, sub: `${kpis.pct_changes.orders}% vs yesterday` },
      { label: 'Revenue Today', value: formatCurrencyRon(kpis.revenue_today_ron), sub: `${kpis.pct_changes.revenue}% vs yesterday` },
      { label: 'Processing Orders', value: kpis.pending_orders, sub: 'awaiting fulfilment' },
      { label: 'Cancelled This Week', value: kpis.returns_this_week, sub: 'last 7 days' },
    ]
  }, [kpis])

  const chartData = useMemo(
    () =>
      trend.map(point => ({
        label: formatShortDay(point.date),
        'This year': Number(point.current_year || 0),
        'Prior year': Number(point.prior_year || 0),
      })),
    [trend]
  )

  return (
    <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[1.05rem] font-semibold tracking-tight">CEO Sales Summary</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            Today's KPIs, 7-day revenue trend and top-selling products.
          </p>
        </div>
        <Link to="/sales/dashboard" className="text-sm text-[var(--primary)] hover:opacity-80 font-medium transition-opacity whitespace-nowrap">
          View full dashboard &rarr;
        </Link>
      </header>

      {loading && <p className="text-sm text-[var(--muted-foreground)]">Loading Sales summary...</p>}
      {!loading && error && <p className="text-sm text-[var(--destructive)]">{error}</p>}

      {!loading && !error && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <div className="grid grid-cols-2 gap-3">
              {kpiTiles.map(kpi => (
                <div key={kpi.label} className="rounded-xl border border-[var(--border)] bg-[var(--input-background)] p-4">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium">{kpi.label}</p>
                  <p className="text-2xl font-semibold mt-1 tracking-tight">{kpi.value}</p>
                  <p className="text-xs text-[var(--muted-foreground)] mt-1">{kpi.sub}</p>
                </div>
              ))}
            </div>

            <div className="border border-[var(--border)] rounded-xl p-4">
              <h3 className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-2">
                Revenue Trend (Last 7 Days)
              </h3>
              <div className="h-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 8, right: 4, left: -16, bottom: 0 }}>
                    <defs>
                      <linearGradient id="ceo-sales-current" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--primary)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                    <Tooltip
                      formatter={(value: number) => formatCurrencyRon(value)}
                      contentStyle={{ borderRadius: 8, border: '1px solid var(--border)' }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
                    <Area type="monotone" dataKey="This year" stroke="var(--primary)" strokeWidth={2} fill="url(#ceo-sales-current)" dot={{ r: 2 }} />
                    <Area type="monotone" dataKey="Prior year" stroke="#D48A6B" strokeWidth={1.5} fillOpacity={0} strokeDasharray="4 3" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {topProducts.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] p-4">
              <h3 className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-3">Top products this week</h3>
              <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {topProducts.map((item, index) => (
                  <li key={item.product_id} className="rounded-lg border border-[var(--border)] px-3 py-2 flex items-center justify-between gap-3 bg-[var(--input-background)]">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="w-6 h-6 rounded-md bg-[var(--card)] text-[var(--primary)] text-[11px] font-bold grid place-items-center shrink-0 border border-[var(--border)]">
                        {index + 1}
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold truncate">{item.product_name}</p>
                        <p className="text-xs text-[var(--muted-foreground)] truncate">{item.product_sku}</p>
                      </div>
                    </div>
                    <span className="text-sm font-semibold shrink-0">
                      {item.units_sold}
                      <span className="text-xs text-[var(--muted-foreground)] font-normal ml-1">u</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

export default CeoSalesSummary
