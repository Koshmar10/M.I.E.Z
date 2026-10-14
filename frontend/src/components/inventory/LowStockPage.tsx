import { useEffect, useState } from 'react'
import { FiTruck, FiAlertTriangle, FiBox, FiCheckCircle } from 'react-icons/fi'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'

type ApiProduct = {
  id: number
  name: string
  sku: string
  category?: string
  stock_count: number
  min_stock: number
  shortfall: number
  status: 'OK' | 'LOW' | 'OUT'
  supplier?: string
}

export default function LowStockPage() {
  const [products, setProducts] = useState<ApiProduct[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api
      .get<ApiProduct[]>('/api/inventory/products/?status=LOW&status=OUT')
      .then(setProducts)
      .catch(() => setProducts([]))
      .finally(() => setLoading(false))
  }, [])

  const openReceive = (p: ApiProduct) => {
    const params = new URLSearchParams({ productId: String(p.id), sku: p.sku, name: p.name })
    navigate(`/inventory/receive-stock?${params.toString()}`)
  }

  if (loading) return null

  if (products.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="w-16 h-16 bg-emerald-50 rounded-2xl flex items-center justify-center text-emerald-500 border border-emerald-100">
          <FiCheckCircle size={28} />
        </div>
        <div className="text-center">
          <h2 className="text-[1.1rem] font-semibold">All stock levels are healthy</h2>
          <p className="text-[0.875rem] text-[var(--muted-foreground)] mt-1">No replenishments needed at this time.</p>
        </div>
      </div>
    )
  }

  const outCount = products.filter(p => p.status === 'OUT').length

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-[1.15rem] font-semibold tracking-tight">Critical Stock Alerts</h2>
          <p className="text-[0.875rem] text-[var(--muted-foreground)] mt-0.5">
            Products below safety levels that need replenishment.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {outCount > 0 && (
            <span className="h-8 px-3 inline-flex items-center gap-2 bg-rose-50 text-rose-700 text-[0.78rem] font-semibold rounded-lg border border-rose-200">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500" />
              </span>
              {outCount} depleted
            </span>
          )}
          <span className="h-8 px-3 inline-flex items-center gap-2 bg-[var(--card)] text-[var(--card-foreground)] text-[0.78rem] font-semibold rounded-lg border border-[var(--border)]">
            <FiBox size={13} className="text-[var(--primary)]" />
            {products.length} affected
          </span>
        </div>
      </div>

      <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--muted)]/30 flex items-center gap-2">
          <FiAlertTriangle size={15} className="text-rose-500" />
          <span className="text-[0.875rem] font-medium">Products requiring attention</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-[0.875rem]">
            <thead>
              <tr className="border-b border-[var(--border)]">
                <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Product</th>
                <th className="px-5 py-2.5 text-center text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Current</th>
                <th className="px-5 py-2.5 text-center text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Minimum</th>
                <th className="px-5 py-2.5 text-center text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Shortfall</th>
                <th className="px-5 py-2.5 text-right text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide" />
              </tr>
            </thead>
            <tbody>
              {products.map(p => {
                const shortfall = Math.max(0, p.min_stock - p.stock_count)
                const isOut = p.status === 'OUT'
                return (
                  <tr key={p.id} className="border-t border-[var(--border)] hover:bg-[var(--muted)]/40 transition-colors">
                    <td className="px-5 py-3">
                      <p className="font-medium">{p.name}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-[var(--muted-foreground)] font-mono bg-[var(--muted)] px-1.5 py-0.5 rounded">{p.sku}</span>
                        {p.category && <span className="text-xs text-[var(--muted-foreground)]">{p.category}</span>}
                      </div>
                    </td>
                    <td className="px-5 py-3 text-center">
                      <span className={`text-[1.05rem] font-semibold ${isOut ? 'text-rose-600' : 'text-amber-600'}`}>{p.stock_count}</span>
                    </td>
                    <td className="px-5 py-3 text-center text-[var(--muted-foreground)] font-medium">{p.min_stock}</td>
                    <td className="px-5 py-3 text-center">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-[0.78rem] font-semibold ${isOut ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-amber-50 text-amber-700 border border-amber-200'}`}>
                        -{shortfall}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button
                        onClick={() => openReceive(p)}
                        className="h-8 px-3 text-[0.78rem] font-semibold rounded-lg bg-[var(--primary)] text-white hover:opacity-90 transition-opacity inline-flex items-center gap-1.5"
                      >
                        <FiTruck size={13} /> Refill
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
