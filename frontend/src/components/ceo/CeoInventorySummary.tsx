import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { FiAlertTriangle, FiXCircle } from 'react-icons/fi'
import { api } from '../../api/client'

type InventoryKpiResponse = {
  total_products: number
  low_stock_count: number
  out_of_stock_count: number
  deliveries_today: number
}

type CriticalProduct = {
  id: number
  name: string
  sku: string
  category: string
  stock_count: number
  min_stock: number
  status: 'LOW' | 'OUT' | 'OK'
  shortfall: number
}

const CeoInventorySummary = () => {
  const [kpis, setKpis] = useState<InventoryKpiResponse | null>(null)
  const [critical, setCritical] = useState<CriticalProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError('')

        const [kpiData, list] = await Promise.all([
          api.get<InventoryKpiResponse>('/api/inventory/dashboard/'),
          api.get<CriticalProduct[]>('/api/inventory/products/?status=LOW&status=OUT'),
        ])

        setKpis(kpiData)
        setCritical(list)
      } catch (err) {
        console.error('Could not load CEO Inventory summary', err)
        setError('Could not load Inventory summary data right now.')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [])

  const kpiTiles = useMemo(() => {
    if (!kpis) return []
    return [
      { label: 'Total Products', value: kpis.total_products, sub: 'active SKUs' },
      { label: 'Low Stock', value: kpis.low_stock_count, sub: 'below threshold' },
      { label: 'Out of Stock', value: kpis.out_of_stock_count, sub: 'needs restock' },
      { label: 'Deliveries Today', value: kpis.deliveries_today, sub: 'expected arrivals' },
    ]
  }, [kpis])

  const healthBreakdown = useMemo(() => {
    if (!kpis) return null
    const total = Math.max(kpis.total_products, 1)
    const healthy = Math.max(kpis.total_products - kpis.low_stock_count - kpis.out_of_stock_count, 0)
    return {
      total: kpis.total_products,
      healthy,
      low: kpis.low_stock_count,
      out: kpis.out_of_stock_count,
      healthyPct: (healthy / total) * 100,
      lowPct: (kpis.low_stock_count / total) * 100,
      outPct: (kpis.out_of_stock_count / total) * 100,
    }
  }, [kpis])

  const criticalSorted = useMemo(() => {
    return [...critical].sort((a, b) => b.shortfall - a.shortfall).slice(0, 5)
  }, [critical])

  return (
    <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[1.05rem] font-semibold tracking-tight">CEO Inventory Summary</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            Stock health overview and items that need immediate restock.
          </p>
        </div>
        <Link to="/inventory/dashboard" className="text-sm text-[var(--primary)] hover:opacity-80 font-medium transition-opacity whitespace-nowrap">
          View full dashboard &rarr;
        </Link>
      </header>

      {loading && <p className="text-sm text-[var(--muted-foreground)]">Loading Inventory summary...</p>}
      {!loading && error && <p className="text-sm text-[var(--destructive)]">{error}</p>}

      {!loading && !error && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              {kpiTiles.map(kpi => (
                <div key={kpi.label} className="rounded-xl border border-[var(--border)] bg-[var(--input-background)] p-4">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium">{kpi.label}</p>
                  <p className="text-2xl font-semibold mt-1 tracking-tight">{kpi.value}</p>
                  <p className="text-xs text-[var(--muted-foreground)] mt-1">{kpi.sub}</p>
                </div>
              ))}
            </div>

            {healthBreakdown && (
              <div className="rounded-xl border border-[var(--border)] p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)]">Stock health breakdown</h3>
                  <span className="text-xs text-[var(--muted-foreground)]">{healthBreakdown.total} total</span>
                </div>
                <div className="flex h-2 w-full rounded-full overflow-hidden bg-[var(--input-background)]">
                  <div className="bg-emerald-500" style={{ width: `${healthBreakdown.healthyPct}%` }} />
                  <div className="bg-amber-500" style={{ width: `${healthBreakdown.lowPct}%` }} />
                  <div className="bg-rose-500" style={{ width: `${healthBreakdown.outPct}%` }} />
                </div>
                <div className="flex items-center justify-between mt-3 text-xs">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-emerald-500" />
                    <span className="text-[var(--muted-foreground)]">Healthy</span>
                    <span className="font-semibold">{healthBreakdown.healthy}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-amber-500" />
                    <span className="text-[var(--muted-foreground)]">Low</span>
                    <span className="font-semibold">{healthBreakdown.low}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-rose-500" />
                    <span className="text-[var(--muted-foreground)]">Out</span>
                    <span className="font-semibold">{healthBreakdown.out}</span>
                  </span>
                </div>
              </div>
            )}
          </div>

          <div className="border border-[var(--border)] rounded-xl p-4">
            <h3 className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-3">Critical stock alerts</h3>
            {criticalSorted.length === 0 ? (
              <p className="text-sm text-[var(--muted-foreground)]">No critical alerts. Everything is in stock.</p>
            ) : (
              <ul className="space-y-2">
                {criticalSorted.map(item => {
                  const isOut = item.status === 'OUT'
                  return (
                    <li
                      key={item.id}
                      className="rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 flex items-center justify-between gap-3"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span
                          className={`w-7 h-7 rounded-md grid place-items-center shrink-0 border ${
                            isOut ? 'bg-rose-50 text-rose-600 border-rose-200' : 'bg-amber-50 text-amber-600 border-amber-200'
                          }`}
                        >
                          {isOut ? <FiXCircle size={14} /> : <FiAlertTriangle size={14} />}
                        </span>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold truncate">{item.name}</p>
                          <p className="text-xs text-[var(--muted-foreground)] truncate">
                            {item.sku} · stock {item.stock_count}/{item.min_stock}
                          </p>
                        </div>
                      </div>
                      <span
                        className={`text-xs font-semibold px-2 py-0.5 rounded-full border whitespace-nowrap ${
                          isOut ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-amber-50 text-amber-700 border-amber-200'
                        }`}
                      >
                        -{item.shortfall}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

export default CeoInventorySummary
