import { useEffect, useState } from 'react'
import { FiSearch, FiPackage, FiCheckCircle, FiAlertTriangle, FiXCircle, FiX, FiActivity, FiDollarSign } from 'react-icons/fi'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts'
import { api } from '../../api/client'

interface Product {
  id: number
  name: string
  sku: string
  category: string
  unit_price_ron: string
  stock_count: number
  min_stock: number
  created_at: string
  updated_at: string
}

const getStatus = (stock: number, minStock: number) => {
  if (stock === 0) return 'Out'
  if (stock <= minStock) return 'Low'
  return 'OK'
}

const StatusBadge = ({ status }: { status: string }) => {
  if (status === 'Out') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[0.72rem] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
        <FiXCircle size={11} /> Depleted
      </span>
    )
  }
  if (status === 'Low') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[0.72rem] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        <FiAlertTriangle size={11} /> Low Stock
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[0.72rem] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
      <FiCheckCircle size={11} /> Healthy
    </span>
  )
}

const getHistory = (currentStock: number) => {
  const points = []
  let val = currentStock + 15
  for (let i = 1; i <= 6; i++) {
    points.push({ day: `${i * 5}d`, qty: val })
    val = Math.max(0, val - Math.floor(Math.random() * 5))
  }
  points[5].qty = currentStock
  return points
}

const DetailDrawer = ({ open, onClose, product }: { open: boolean; onClose: () => void; product: Product | null }) => {
  if (!product) return null
  const status = getStatus(product.stock_count, product.min_stock)
  const stockValue = parseFloat(product.unit_price_ron) * product.stock_count
  const history = getHistory(product.stock_count)

  return (
    <>
      <div
        className={`fixed inset-0 bg-black/30 backdrop-blur-sm z-40 transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      />
      <div className={`fixed inset-y-0 right-0 w-full max-w-md bg-[var(--card)] border-l border-[var(--border)] z-50 transform transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] flex flex-col ${open ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="p-5 border-b border-[var(--border)] flex items-center justify-between sticky top-0 z-10 bg-[var(--card)]">
          <div>
            <h2 className="text-[1.05rem] font-semibold tracking-tight">{product.name}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="px-2 py-0.5 bg-[var(--muted)] text-[var(--muted-foreground)] rounded text-xs font-mono">{product.sku}</span>
              <span className="text-sm text-[var(--muted-foreground)]">· {product.category}</span>
            </div>
          </div>
          <button onClick={onClose} className="p-2 bg-[var(--muted)] hover:bg-[var(--border)] rounded-full text-[var(--muted-foreground)] transition-colors">
            <FiX size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--input-background)]">
              <p className="text-[0.72rem] uppercase tracking-wide text-[var(--muted-foreground)] font-medium mb-1">Stock</p>
              <p className="text-2xl font-semibold">{product.stock_count}</p>
            </div>
            <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--input-background)]">
              <p className="text-[0.72rem] uppercase tracking-wide text-[var(--muted-foreground)] font-medium mb-2">Status</p>
              <StatusBadge status={status} />
            </div>
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-[var(--input-background)] p-4 space-y-2.5">
            <div className="flex items-center gap-2 text-[var(--muted-foreground)] mb-3">
              <FiDollarSign size={14} />
              <p className="text-[0.78rem] font-semibold uppercase tracking-wide">Financials</p>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--muted-foreground)]">Unit price</span>
              <span className="text-sm font-semibold">{parseFloat(product.unit_price_ron).toFixed(2)} RON</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--muted-foreground)]">Stock value</span>
              <span className="text-sm font-semibold text-[var(--primary)]">{stockValue.toLocaleString('ro-RO')} RON</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-[var(--muted-foreground)]">Min threshold</span>
              <span className="text-sm font-semibold">{product.min_stock} units</span>
            </div>
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-[var(--input-background)] p-4">
            <div className="flex items-center gap-2 text-[var(--muted-foreground)] mb-4">
              <FiActivity size={14} />
              <p className="text-[0.78rem] font-semibold uppercase tracking-wide">30-Day Trajectory</p>
            </div>
            <div className="h-36 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={history} margin={{ top: 5, right: 0, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorStock" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: 'var(--muted-foreground)', fontSize: 10 }} />
                  <RechartsTooltip contentStyle={{ borderRadius: '10px', border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--card-foreground)', boxShadow: 'none' }} />
                  <Area type="monotone" dataKey="qty" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorStock)" animationDuration={1200} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

export default function ProductsStockPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)

  useEffect(() => {
    api
      .get<Product[]>('/api/inventory/products/')
      .then(setProducts)
      .catch(() => undefined)
      .finally(() => setLoading(false))
  }, [])

  const categories = ['All', ...Array.from(new Set(products.map(p => p.category)))]

  const filtered = products.filter(p => {
    const s = getStatus(p.stock_count, p.min_stock)
    return (
      (p.name.toLowerCase().includes(search.toLowerCase()) || p.sku.toLowerCase().includes(search.toLowerCase())) &&
      (categoryFilter === 'All' || p.category === categoryFilter) &&
      (statusFilter === 'All' || s === statusFilter)
    )
  })

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-[1.15rem] font-semibold tracking-tight">Products & Stock</h2>
          <p className="text-[0.875rem] text-[var(--muted-foreground)] mt-0.5">
            {filtered.length} of {products.length} products
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]" size={14} />
            <input
              type="text"
              placeholder="Search name or SKU…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="h-9 pl-8 pr-3 text-[0.875rem] rounded-lg border border-[var(--border)] bg-[var(--input-background)] text-[var(--card-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)] w-56"
            />
          </div>
          <select
            value={categoryFilter}
            onChange={e => setCategoryFilter(e.target.value)}
            className="h-9 px-3 text-[0.875rem] rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)] cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          >
            {categories.map(c => <option key={c} value={c}>{c === 'All' ? 'All categories' : c}</option>)}
          </select>
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="h-9 px-3 text-[0.875rem] rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)] cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          >
            <option value="All">All statuses</option>
            <option value="OK">Healthy</option>
            <option value="Low">Low stock</option>
            <option value="Out">Out of stock</option>
          </select>
        </div>
      </div>

      <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[0.875rem]">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--muted)]/40">
                <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Product</th>
                <th className="px-5 py-2.5 text-right text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Stock</th>
                <th className="px-5 py-2.5 text-right text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Min</th>
                <th className="px-5 py-2.5 text-right text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Unit price</th>
                <th className="px-5 py-2.5 text-center text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-[var(--muted-foreground)]">Loading…</td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-[var(--muted-foreground)]">No products match your filters.</td>
                </tr>
              ) : (
                filtered.map(p => {
                  const s = getStatus(p.stock_count, p.min_stock)
                  return (
                    <tr
                      key={p.id}
                      onClick={() => setSelectedProduct(p)}
                      className="group border-t border-[var(--border)] hover:bg-[var(--muted)]/40 cursor-pointer transition-colors"
                    >
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-[var(--input-background)] border border-[var(--border)] flex items-center justify-center shrink-0 text-[var(--muted-foreground)] group-hover:text-[var(--primary)] transition-colors">
                            <FiPackage size={15} />
                          </div>
                          <div>
                            <p className="font-medium group-hover:text-[var(--primary)] transition-colors">{p.name}</p>
                            <p className="text-xs text-[var(--muted-foreground)] font-mono mt-0.5">{p.sku} · {p.category}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3 text-right font-semibold">{p.stock_count}</td>
                      <td className="px-5 py-3 text-right text-[var(--muted-foreground)]">{p.min_stock}</td>
                      <td className="px-5 py-3 text-right text-[var(--muted-foreground)]">{parseFloat(p.unit_price_ron).toFixed(2)} RON</td>
                      <td className="px-5 py-3 text-center">
                        <StatusBadge status={s} />
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <DetailDrawer open={!!selectedProduct} onClose={() => setSelectedProduct(null)} product={selectedProduct} />
    </div>
  )
}
