import { useEffect, useState } from 'react'
import { FiArrowDownLeft, FiArrowUpRight, FiRefreshCw, FiTrash2, FiBox, FiChevronLeft, FiChevronRight } from 'react-icons/fi'
import { useNavigate } from 'react-router-dom'
import { api, type Page } from '../../api/client'

type Movement = {
  id: number
  movement_type: string
  product?: number | { id: number; name: string; sku: string }
  product_obj?: { id: number; name: string; sku: string }
  product_name?: string
  product_sku?: string
  supplier?: number | { id: number; name: string }
  supplier_obj?: { id: number; name: string }
  supplier_name?: string
  quantity: number
  expected_date?: string | null
  notes?: string
  created_by_username?: string
  created_at: string
}

type TypeConfig = { icon: React.ComponentType<any>; label: string; dot: string; qty: string }

const typeConfig: Record<string, TypeConfig> = {
  INBOUND:    { icon: FiArrowDownLeft, label: 'Inbound',    dot: 'bg-emerald-500', qty: 'text-emerald-600' },
  OUTBOUND:   { icon: FiArrowUpRight,  label: 'Outbound',   dot: 'bg-rose-500',    qty: 'text-rose-600' },
  ADJUSTMENT: { icon: FiRefreshCw,     label: 'Adjustment', dot: 'bg-sky-500',     qty: 'text-sky-600' },
  WRITE_OFF:  { icon: FiTrash2,        label: 'Write-off',  dot: 'bg-slate-400',   qty: 'text-slate-500' },
}

const qtyPrefix: Record<string, string> = { INBOUND: '+', OUTBOUND: '-', WRITE_OFF: '-' }

export default function StockMovementsPage() {
  const [movements, setMovements] = useState<Movement[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [count, setCount] = useState(0)
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const navigate = useNavigate()

  const fetchData = async (p = 1) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(p) })
      if (typeFilter !== 'ALL') params.set('type', typeFilter)
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)

      const data = await api.get<Page<Movement>>(`/api/inventory/stock-movements/?${params.toString()}`)
      setMovements(data.results)
      setCount(data.count)
    } catch {
      setMovements([]); setCount(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData(page) }, [page]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleReceive = (prod?: { id: number; name: string; sku: string }) => {
    if (!prod) return
    navigate(`/inventory/receive?${new URLSearchParams({ productId: String(prod.id), sku: prod.sku ?? '', name: prod.name ?? '' })}`)
  }

  const hasFilters = typeFilter !== 'ALL' || !!dateFrom || !!dateTo

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 flex-wrap">
        <div>
          <h2 className="text-[1.15rem] font-semibold tracking-tight">Stock Movements</h2>
          <p className="text-[0.875rem] text-[var(--muted-foreground)] mt-0.5">
            Ledger of all inbound, outbound, and adjustment events.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}
            className="h-9 px-3 text-[0.875rem] rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)] cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          >
            <option value="ALL">All types</option>
            <option value="INBOUND">Inbound</option>
            <option value="OUTBOUND">Outbound</option>
            <option value="ADJUSTMENT">Adjustments</option>
            <option value="WRITE_OFF">Write-offs</option>
          </select>
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            className="h-9 px-3 text-[0.875rem] rounded-lg border border-[var(--border)] bg-[var(--input-background)] text-[var(--card-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
          <span className="text-[var(--muted-foreground)] text-sm">–</span>
          <input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
            className="h-9 px-3 text-[0.875rem] rounded-lg border border-[var(--border)] bg-[var(--input-background)] text-[var(--card-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
          <button
            onClick={() => { setPage(1); fetchData(1) }}
            className="h-9 px-4 text-[0.875rem] font-semibold rounded-lg bg-[var(--primary)] text-white hover:opacity-90 transition-opacity"
          >
            Apply
          </button>
          {hasFilters && (
            <button
              onClick={() => { setTypeFilter('ALL'); setDateFrom(''); setDateTo(''); setPage(1); fetchData(1) }}
              className="h-9 px-3 text-[0.875rem] text-[var(--muted-foreground)] hover:text-[var(--card-foreground)] border border-[var(--border)] rounded-lg transition-colors"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl overflow-hidden relative">
        {loading && (
          <div className="absolute inset-0 bg-[var(--card)]/70 backdrop-blur-sm z-10 flex items-center justify-center">
            <div className="w-8 h-8 border-2 border-[var(--border)] border-t-[var(--primary)] rounded-full animate-spin" />
          </div>
        )}

        <div className="px-5 py-3 border-b border-[var(--border)] flex items-center justify-between">
          <span className="text-[0.875rem] font-medium">Movement history</span>
          <span className="text-[0.78rem] text-[var(--muted-foreground)] bg-[var(--muted)] px-2.5 py-0.5 rounded-full border border-[var(--border)]">
            {count} records
          </span>
        </div>

        {!loading && movements.length === 0 ? (
          <div className="py-16 text-center text-[var(--muted-foreground)]">
            <FiRefreshCw size={28} className="mx-auto mb-3 opacity-30" />
            <p className="text-[0.875rem]">No log entries. Adjust your filters or add stock.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[0.875rem]">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--muted)]/40">
                  <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Type</th>
                  <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Product</th>
                  <th className="px-5 py-2.5 text-right text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Qty</th>
                  <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Supplier</th>
                  <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Date</th>
                  <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">By</th>
                  <th className="px-5 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {movements.map(m => {
                  const t = (m.movement_type ?? '').toUpperCase()
                  const cfg = typeConfig[t] ?? { icon: FiBox, label: t, dot: 'bg-slate-400', qty: '' }
                  const Icon = cfg.icon
                  const prodName = m.product_name ?? m.product_obj?.name ?? 'Unknown'
                  const sku = m.product_sku ?? m.product_obj?.sku ?? ''
                  const supplier = m.supplier_name ?? m.supplier_obj?.name ?? '—'
                  const dateObj = new Date(m.created_at)
                  const prefix = qtyPrefix[t] ?? ''

                  return (
                    <tr key={m.id} className="border-t border-[var(--border)] hover:bg-[var(--muted)]/40 transition-colors">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`} />
                          <Icon size={14} className="text-[var(--muted-foreground)]" />
                          <span className="text-[0.78rem] font-medium">{cfg.label}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <p className="font-medium">{prodName}</p>
                        {sku && <p className="text-xs text-[var(--muted-foreground)] font-mono mt-0.5">{sku}</p>}
                      </td>
                      <td className={`px-5 py-3 text-right font-semibold ${cfg.qty}`}>
                        {prefix}{m.quantity}
                      </td>
                      <td className="px-5 py-3 text-[var(--muted-foreground)]">{supplier}</td>
                      <td className="px-5 py-3 text-[var(--muted-foreground)] whitespace-nowrap">
                        {dateObj.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })}
                        <span className="ml-1 text-xs">{dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </td>
                      <td className="px-5 py-3 text-[var(--muted-foreground)] text-[0.78rem]">
                        {m.created_by_username ?? 'System'}
                      </td>
                      <td className="px-5 py-3">
                        {m.product_obj && t === 'INBOUND' && (
                          <button
                            onClick={() => handleReceive(m.product_obj)}
                            className="h-7 px-3 text-[0.75rem] font-medium rounded-md border border-[var(--border)] hover:bg-[var(--muted)] transition-colors"
                          >
                            Receive again
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="px-5 py-3 border-t border-[var(--border)] bg-[var(--muted)]/20 flex items-center justify-between">
          <span className="text-[0.78rem] text-[var(--muted-foreground)]">Page {page}</span>
          <div className="flex items-center gap-1">
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
              className="h-8 w-8 flex items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--muted)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <FiChevronLeft size={15} />
            </button>
            <button
              disabled={movements.length < 20}
              onClick={() => setPage(p => p + 1)}
              className="h-8 w-8 flex items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--muted)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <FiChevronRight size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
