import { useEffect, useState } from 'react'
import { api } from '../../api/client'

type ProductRow = {
  id: number
  name: string
  sku: string
  category: string
  unit_price_ron: string
  stock_count: number
  availability: string
}

type ProductListResponse = {
  total_count: number
  count: number
  next: string | null
  previous: string | null
  results: ProductRow[]
}

const categoryOptions = [
  { label: 'All categories', value: '' },
  { label: 'Electronics', value: 'Electronics' },
  { label: 'Furniture', value: 'Furniture' },
  { label: 'Lighting', value: 'Lighting' },
  { label: 'Accessories', value: 'Accessories' },
]

const availabilityBadge = (availability: string) => {
  const lower = availability.toLowerCase()
  if (lower === 'out of stock') {
    return (
      <span className="inline-flex rounded-full px-2 py-1 text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
        Out of Stock
      </span>
    )
  }
  if (lower === 'low stock') {
    return (
      <span className="inline-flex rounded-full px-2 py-1 text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
        Low Stock
      </span>
    )
  }
  return (
    <span className="inline-flex rounded-full px-2 py-1 text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
      In Stock
    </span>
  )
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

const SalesProductsPage = () => {
  const [products, setProducts] = useState<ProductRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [nextPageUrl, setNextPageUrl] = useState<string | null>(null)
  const [previousPageUrl, setPreviousPageUrl] = useState<string | null>(null)

  useEffect(() => {
    setPage(1)
  }, [search, categoryFilter])

  useEffect(() => {
    const loadProducts = async () => {
      try {
        setLoading(true)
        setError('')

        const params = new URLSearchParams()
        params.set('page', String(page))
        params.set('page_size', '20')
        if (search.trim()) params.set('search', search.trim())
        if (categoryFilter) params.set('category', categoryFilter)

        const data = await api.get<ProductListResponse>(`/api/products/?${params.toString()}`)
        setProducts(data.results)
        setTotalCount(data.total_count)
        setNextPageUrl(data.next)
        setPreviousPageUrl(data.previous)
      } catch (err) {
        console.error('Failed to load products:', err)
        setError('Could not load products right now.')
      } finally {
        setLoading(false)
      }
    }

    void loadProducts()
  }, [search, categoryFilter, page])

  return (
    <div className="space-y-6">
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">Product Catalogue</h2>
            <p className="text-sm text-black/60 mt-1">Browse availability and pricing before taking orders.</p>
          </div>
          <div className="text-right text-sm text-black/60">
            <p>{totalCount} products</p>
          </div>
        </div>
      </section>

      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="md:col-span-2">
            <label className="text-xs font-semibold uppercase tracking-wide text-black/50">Search</label>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Product name or SKU"
              className="w-full mt-1 rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-black/50">Category</label>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="w-full mt-1 rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm"
            >
              {categoryOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <p className="text-sm text-black/60">Loading products...</p>
        ) : error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full border-separate border-spacing-y-2">
                <thead>
                  <tr>
                    <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">Name</th>
                    <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">SKU</th>
                    <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">Category</th>
                    <th className="text-right text-xs uppercase tracking-wide text-black/50 px-3">Stock</th>
                    <th className="text-left text-xs uppercase tracking-wide text-black/50 px-3">Status</th>
                    <th className="text-right text-xs uppercase tracking-wide text-black/50 px-3">Unit Price</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((product) => (
                    <tr key={product.id} className="bg-white border border-[var(--border)]">
                      <td className="px-3 py-2 text-sm font-semibold">{product.name}</td>
                      <td className="px-3 py-2 text-sm text-black/60 font-mono">{product.sku}</td>
                      <td className="px-3 py-2 text-sm text-black/60">{product.category}</td>
                      <td className="px-3 py-2 text-sm text-right">{product.stock_count}</td>
                      <td className="px-3 py-2 text-sm">{availabilityBadge(product.availability)}</td>
                      <td className="px-3 py-2 text-sm text-right font-semibold">{formatCurrencyRon(product.unit_price_ron)}</td>
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
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={!previousPageUrl}
                  className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage((p) => p + 1)}
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
    </div>
  )
}

export default SalesProductsPage
