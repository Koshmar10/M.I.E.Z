import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { FiTruck, FiPackage, FiSearch, FiPlus, FiCheckCircle } from 'react-icons/fi'
import { api, type Page } from '../../api/client'

type Movement = {
  id: number
  movement_type: string
  product_obj?: { id: number; name: string; sku: string }
  product_name?: string
  product_sku?: string
  supplier_obj?: { id: number; name: string }
  supplier_name?: string
  quantity: number
  expected_date?: string | null
  notes?: string
  created_by_username?: string
  created_at: string
}

type Product = { id: number; name: string; sku: string }

export default function ReceiveStockPage() {
  const location = useLocation()
  const urlParams = new URLSearchParams(location.search)
  const urlProductId = urlParams.get('productId') ?? ''

  const [showForm, setShowForm] = useState(!!urlProductId)
  const [products, setProducts] = useState<Product[]>([])
  const [suppliers, setSuppliers] = useState<Array<{ id: number; name: string }>>([])
  const [form, setForm] = useState({ product: urlProductId, supplier: '', qty: '', expected_date: '', notes: '' })
  const [submitted, setSubmitted] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [search, setSearch] = useState('')
  const [recentDeliveries, setRecentDeliveries] = useState<Movement[]>([])
  const [loadingDeliveries, setLoadingDeliveries] = useState(true)

  const fetchDeliveries = async () => {
    setLoadingDeliveries(true)
    try {
      const data = await api.get<Page<Movement>>('/api/inventory/stock-movements/', { type: 'INBOUND' })
      setRecentDeliveries(data.results)
    } catch {
      // keep the list as it was
    }
    finally { setLoadingDeliveries(false) }
  }

  useEffect(() => {
    void fetchDeliveries()
    api.get<Product[]>('/api/inventory/products/').then(setProducts).catch(() => undefined)
    api.get<Array<{ id: number; name: string }>>('/api/inventory/suppliers/').then(setSuppliers).catch(() => undefined)
  }, [])

  const handleSubmit = async () => {
    if (!form.product || !form.supplier || !form.qty || Number(form.qty) <= 0) return
    setIsSubmitting(true)
    try {
      await api.post('/api/inventory/stock-movements/', {
        product: Number(form.product),
        movement_type: 'INBOUND',
        quantity: Number(form.qty),
        supplier: Number(form.supplier),
        expected_date: form.expected_date || null,
        notes: form.notes,
      })
      setSubmitted(true)
      setShowForm(false)
      void fetchDeliveries()
    } catch {
      // the form stays open so the user can try again
    }
    finally { setIsSubmitting(false) }
  }

  const filteredDeliveries = recentDeliveries.filter(d => {
    if (!search) return true
    const name = d.product_name ?? d.product_obj?.name ?? ''
    return name.toLowerCase().includes(search.toLowerCase()) || `INB-${d.id}`.toLowerCase().includes(search.toLowerCase())
  })

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-[1.15rem] font-semibold tracking-tight">Receive Stock</h2>
          <p className="text-[0.875rem] text-[var(--muted-foreground)] mt-0.5">Log incoming shipments and update the warehouse.</p>
        </div>
        <button
          onClick={() => { setShowForm(s => !s); setSubmitted(false) }}
          className="h-9 px-4 text-[0.875rem] font-semibold rounded-lg bg-[var(--primary)] text-white hover:opacity-90 transition-opacity inline-flex items-center gap-2"
        >
          <FiPlus size={15} className={`transition-transform duration-200 ${showForm ? 'rotate-45' : ''}`} />
          {showForm ? 'Cancel' : 'Log delivery'}
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <FiPackage size={15} className="text-[var(--muted-foreground)]" />
            <h3 className="text-[0.875rem] font-semibold">New delivery entry</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Product *', field: 'product' as const, type: 'select', options: products.map(p => ({ value: String(p.id), label: p.name })) },
              { label: 'Supplier *', field: 'supplier' as const, type: 'select', options: suppliers.map(s => ({ value: String(s.id), label: s.name })) },
            ].map(({ label, field, options }) => (
              <div key={field} className="flex flex-col gap-1.5">
                <label className="text-[0.72rem] font-medium text-[var(--muted-foreground)] uppercase tracking-wide">{label}</label>
                <select
                  value={form[field]}
                  onChange={e => setForm({ ...form, [field]: e.target.value })}
                  className="h-9 px-3 text-[0.875rem] rounded-lg border border-[var(--border)] bg-[var(--input-background)] text-[var(--card-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                >
                  <option value="">Select…</option>
                  {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            ))}
            <div className="flex flex-col gap-1.5">
              <label className="text-[0.72rem] font-medium text-[var(--muted-foreground)] uppercase tracking-wide">Quantity *</label>
              <input
                type="number"
                value={form.qty}
                onChange={e => setForm({ ...form, qty: e.target.value })}
                placeholder="0"
                className="h-9 px-3 text-[0.875rem] rounded-lg border border-[var(--border)] bg-[var(--input-background)] text-[var(--card-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-[0.72rem] font-medium text-[var(--muted-foreground)] uppercase tracking-wide">Expected date</label>
              <input
                type="date"
                value={form.expected_date}
                onChange={e => setForm({ ...form, expected_date: e.target.value })}
                className="h-9 px-3 text-[0.875rem] rounded-lg border border-[var(--border)] bg-[var(--input-background)] text-[var(--card-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              />
            </div>
          </div>

          <div className="mt-4 flex flex-col gap-1.5">
            <label className="text-[0.72rem] font-medium text-[var(--muted-foreground)] uppercase tracking-wide">Notes</label>
            <textarea
              value={form.notes}
              onChange={e => setForm({ ...form, notes: e.target.value })}
              placeholder="Damages, missing items, inspection notes…"
              rows={2}
              className="px-3 py-2 text-[0.875rem] rounded-lg border border-[var(--border)] bg-[var(--input-background)] text-[var(--card-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)] resize-none"
            />
          </div>

          <div className="mt-4 flex items-center gap-3 pt-4 border-t border-[var(--border)]">
            <button
              disabled={!form.product || !form.supplier || !form.qty || Number(form.qty) <= 0 || isSubmitting}
              onClick={() => void handleSubmit()}
              className="h-9 px-4 text-[0.875rem] font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSubmitting ? 'Saving…' : 'Confirm receipt'}
            </button>
            <button onClick={() => setShowForm(false)} className="h-9 px-4 text-[0.875rem] text-[var(--muted-foreground)] hover:text-[var(--card-foreground)] transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Success banner */}
      {submitted && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FiCheckCircle size={18} className="text-emerald-600 shrink-0" />
            <div>
              <p className="text-[0.875rem] font-semibold text-emerald-900">Delivery logged successfully</p>
              <p className="text-[0.78rem] text-emerald-700 mt-0.5">Inventory updated with +{form.qty} units.</p>
            </div>
          </div>
          <button
            onClick={() => { setSubmitted(false); setForm({ product: '', supplier: '', qty: '', expected_date: '', notes: '' }) }}
            className="text-[0.78rem] font-semibold text-emerald-700 hover:text-emerald-900 transition-colors"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Recent deliveries */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border)] flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <FiTruck size={15} className="text-[var(--muted-foreground)]" />
            <span className="text-[0.875rem] font-medium">Recent deliveries</span>
          </div>
          <div className="relative">
            <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]" size={13} />
            <input
              type="text"
              placeholder="Search…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="h-8 pl-8 pr-3 text-[0.8rem] rounded-lg border border-[var(--border)] bg-[var(--input-background)] text-[var(--card-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)] w-44"
            />
          </div>
        </div>

        {loadingDeliveries ? (
          <p className="px-5 py-8 text-[0.875rem] text-[var(--muted-foreground)]">Loading…</p>
        ) : filteredDeliveries.length === 0 ? (
          <div className="px-5 py-10 text-center text-[var(--muted-foreground)]">
            <FiPackage size={32} className="mx-auto mb-3 opacity-30" />
            <p className="text-[0.875rem]">No deliveries found.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[0.875rem]">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">ID</th>
                  <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Product</th>
                  <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Supplier</th>
                  <th className="px-5 py-2.5 text-right text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Qty</th>
                  <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Expected</th>
                  <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Notes</th>
                </tr>
              </thead>
              <tbody>
                {filteredDeliveries.slice(0, 10).map(d => {
                  const prodName = d.product_name ?? d.product_obj?.name ?? 'Unknown'
                  const supplier = d.supplier_name ?? d.supplier_obj?.name ?? '—'
                  const dateObj = d.expected_date ? new Date(d.expected_date) : null
                  return (
                    <tr key={d.id} className="border-t border-[var(--border)] hover:bg-[var(--muted)]/40 transition-colors">
                      <td className="px-5 py-3 font-mono text-[0.78rem] text-[var(--muted-foreground)]">INB-{String(d.id).padStart(4, '0')}</td>
                      <td className="px-5 py-3">
                        <p className="font-medium">{prodName}</p>
                        <p className="text-xs text-[var(--muted-foreground)] font-mono">{d.product_obj?.sku ?? d.product_sku}</p>
                      </td>
                      <td className="px-5 py-3 text-[var(--muted-foreground)]">{supplier}</td>
                      <td className="px-5 py-3 text-right font-semibold text-emerald-600">+{d.quantity}</td>
                      <td className="px-5 py-3 text-[var(--muted-foreground)]">
                        {dateObj ? dateObj.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : '—'}
                      </td>
                      <td className="px-5 py-3 text-[var(--muted-foreground)] max-w-[180px] truncate">{d.notes || '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
