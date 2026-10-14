import { useEffect, useState } from 'react'
import { api, errorMessage } from '../../api/client'

type InvoiceRow = {
  id: number
  invoice_number: string
  order: number
  order_number: string
  customer_name: string
  amount_ron: string
  status: string
  effective_status: string
  issued_date: string
  due_date: string | null
}

type InvoiceListResponse = {
  count: number
  next: string | null
  previous: string | null
  results: InvoiceRow[]
  paid_total: string
  pending_total: string
  overdue_total: string
}

type InvoiceLineItem = {
  id: number
  product: number
  product_name: string
  quantity: number
  unit_price_ron: string
  subtotal_ron: string
}

type InvoiceDetail = {
  id: number
  invoice_number: string
  order: number
  order_number: string
  customer_name: string
  issued_date: string
  due_date: string | null
  status: string
  amount_ron: string
  line_items: InvoiceLineItem[]
}

type StatusFilter = '' | 'PAID' | 'ISSUED' | 'OVERDUE'

const STATUS_TABS: { label: string; value: StatusFilter }[] = [
  { label: 'All', value: '' },
  { label: 'Paid', value: 'PAID' },
  { label: 'Pending', value: 'ISSUED' },
  { label: 'Overdue', value: 'OVERDUE' },
]

const effectiveStatusBadge = (status: string) => {
  const s = status.toUpperCase()
  if (s === 'OVERDUE') {
    return (
      <span className="inline-flex rounded-full px-2 py-1 text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
        Overdue
      </span>
    )
  }
  if (s === 'PAID') {
    return (
      <span className="inline-flex rounded-full px-2 py-1 text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
        Paid
      </span>
    )
  }
  if (s === 'DRAFT') {
    return (
      <span className="inline-flex rounded-full px-2 py-1 text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
        Draft
      </span>
    )
  }
  return (
    <span className="inline-flex rounded-full px-2 py-1 text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
      Pending
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

const formatDate = (value: string | null) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('ro-RO')
}

const SalesInvoicesPage = () => {
  const [invoices, setInvoices] = useState<InvoiceRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('')
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [nextPageUrl, setNextPageUrl] = useState<string | null>(null)
  const [previousPageUrl, setPreviousPageUrl] = useState<string | null>(null)

  const [paidTotal, setPaidTotal] = useState('0.00')
  const [pendingTotal, setPendingTotal] = useState('0.00')
  const [overdueTotal, setOverdueTotal] = useState('0.00')

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [markingPaid, setMarkingPaid] = useState(false)

  useEffect(() => {
    setPage(1)
  }, [statusFilter])

  useEffect(() => {
    const loadInvoices = async () => {
      try {
        setLoading(true)
        setError('')

        const params = new URLSearchParams()
        params.set('page', String(page))
        params.set('page_size', '20')
        if (statusFilter) params.set('status', statusFilter)

        const data = await api.get<InvoiceListResponse>(`/api/invoices/?${params.toString()}`)
        setInvoices(Array.isArray(data.results) ? data.results : [])
        setTotalCount(data.count ?? 0)
        setNextPageUrl(data.next ?? null)
        setPreviousPageUrl(data.previous ?? null)
        setPaidTotal(data.paid_total ?? '0.00')
        setPendingTotal(data.pending_total ?? '0.00')
        setOverdueTotal(data.overdue_total ?? '0.00')
      } catch (err) {
        console.error('Failed to load invoices:', err)
        setError('Could not load invoices right now.')
      } finally {
        setLoading(false)
      }
    }

    loadInvoices()
  }, [statusFilter, page])

  const openInvoiceDetail = async (invoiceId: number) => {
    try {
      setDrawerOpen(true)
      setDetailLoading(true)
      setDetailError('')
      setSelectedInvoice(null)

      setSelectedInvoice(await api.get<InvoiceDetail>(`/api/invoices/${invoiceId}/`))
    } catch (err) {
      console.error('Failed to load invoice detail:', err)
      setDetailError('Could not load invoice details.')
    } finally {
      setDetailLoading(false)
    }
  }

  const closeDrawer = () => {
    setDrawerOpen(false)
    setSelectedInvoice(null)
    setDetailError('')
  }

  const markInvoicePaid = async () => {
    if (!selectedInvoice || markingPaid) {
      return
    }

    try {
      setMarkingPaid(true)
      const updated = await api.patch<InvoiceDetail>(`/api/invoices/${selectedInvoice.id}/`, { status: 'PAID' })
      setSelectedInvoice(updated)
      setInvoices((prev) =>
        prev.map((row) =>
          row.id === updated.id
            ? {
                ...row,
                status: updated.status,
                effective_status: updated.status,
              }
            : row
        )
      )
    } catch (err) {
      console.error('Failed to mark invoice paid:', err)
      setDetailError(errorMessage(err, 'Could not update invoice status.'))
    } finally {
      setMarkingPaid(false)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-[1.15rem] font-semibold tracking-tight">Invoices</h2>
          <p className="text-[0.875rem] text-[var(--muted-foreground)] mt-0.5">Billing status across all sales orders.</p>
        </div>
        <span className="text-[0.78rem] text-[var(--muted-foreground)] bg-[var(--muted)] px-2.5 py-0.5 rounded-full border border-[var(--border)]">
          {totalCount} total
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
          <p className="text-[0.72rem] uppercase tracking-wide text-[var(--muted-foreground)] font-medium">Paid</p>
          <p className="text-[1.6rem] font-bold text-emerald-600 mt-1 leading-none">{formatCurrencyRon(paidTotal)}</p>
        </div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
          <p className="text-[0.72rem] uppercase tracking-wide text-[var(--muted-foreground)] font-medium">Pending</p>
          <p className="text-[1.6rem] font-bold text-amber-600 mt-1 leading-none">{formatCurrencyRon(pendingTotal)}</p>
        </div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
          <p className="text-[0.72rem] uppercase tracking-wide text-[var(--muted-foreground)] font-medium">Overdue</p>
          <p className="text-[1.6rem] font-bold text-rose-600 mt-1 leading-none">{formatCurrencyRon(overdueTotal)}</p>
        </div>
      </div>

      <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border)] flex items-center gap-2">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setStatusFilter(tab.value)}
              className={`h-7 px-3 text-[0.8rem] rounded-md border transition-colors ${
                statusFilter === tab.value
                  ? 'bg-[var(--primary)] text-white border-[var(--primary)]'
                  : 'bg-transparent text-[var(--muted-foreground)] border-[var(--border)] hover:bg-[var(--muted)]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="px-5 py-8 text-[0.875rem] text-[var(--muted-foreground)]">Loading…</p>
        ) : error ? (
          <p className="px-5 py-8 text-[0.875rem] text-rose-600">{error}</p>
        ) : invoices.length === 0 ? (
          <p className="px-5 py-8 text-[0.875rem] text-[var(--muted-foreground)]">No invoices found.</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-[0.875rem]">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-[var(--muted)]/40">
                    <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Invoice</th>
                    <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Order</th>
                    <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Customer</th>
                    <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Issued</th>
                    <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Due</th>
                    <th className="px-5 py-2.5 text-left text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Status</th>
                    <th className="px-5 py-2.5 text-right text-[0.72rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((invoice) => (
                    <tr
                      key={invoice.id}
                      className="border-t border-[var(--border)] hover:bg-[var(--muted)]/40 transition-colors cursor-pointer"
                      onClick={() => openInvoiceDetail(invoice.id)}
                    >
                      <td className="px-5 py-3 font-semibold font-mono text-[0.8rem]">{invoice.invoice_number}</td>
                      <td className="px-5 py-3 text-[var(--muted-foreground)] font-mono text-[0.8rem]">{invoice.order_number}</td>
                      <td className="px-5 py-3">{invoice.customer_name}</td>
                      <td className="px-5 py-3 text-[var(--muted-foreground)]">{formatDate(invoice.issued_date)}</td>
                      <td className="px-5 py-3 text-[var(--muted-foreground)]">{formatDate(invoice.due_date)}</td>
                      <td className="px-5 py-3">{effectiveStatusBadge(invoice.effective_status)}</td>
                      <td className="px-5 py-3 text-right font-semibold">{formatCurrencyRon(invoice.amount_ron)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="px-5 py-3 border-t border-[var(--border)] bg-[var(--muted)]/20 flex items-center justify-between">
              <p className="text-[0.78rem] text-[var(--muted-foreground)]">Page {page} · {totalCount} total</p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={!previousPageUrl}
                  className="h-8 px-3 text-[0.8rem] rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--muted)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={!nextPageUrl}
                  className="h-8 px-3 text-[0.8rem] rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--muted)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      <div
        className={`fixed inset-0 bg-black/30 backdrop-blur-sm z-40 transition-opacity duration-300 ${drawerOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={closeDrawer}
      />
      <div
        className={`fixed inset-y-0 right-0 w-full max-w-xl bg-[var(--card)] border-l border-[var(--border)] z-50 transform transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] flex flex-col ${drawerOpen ? 'translate-x-0' : 'translate-x-full'}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="p-5 border-b border-[var(--border)] flex items-center justify-between">
          <div>
            <p className="text-[0.7rem] uppercase tracking-[0.2em] text-[var(--muted-foreground)]">Invoice</p>
            <h3 className="text-lg font-semibold mt-1">{selectedInvoice?.invoice_number ?? 'Invoice Detail'}</h3>
            {selectedInvoice && (
              <p className="text-sm text-[var(--muted-foreground)]">Order {selectedInvoice.order_number}</p>
            )}
          </div>
          <button
            type="button"
            onClick={closeDrawer}
            className="h-8 px-3 text-[0.8rem] rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--muted)] transition-colors"
          >
            Close
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {detailLoading ? (
            <p className="text-[0.875rem] text-[var(--muted-foreground)]">Loading invoice details...</p>
          ) : detailError ? (
            <p className="text-[0.875rem] text-rose-600">{detailError}</p>
          ) : selectedInvoice ? (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="rounded-xl border border-[var(--border)] p-3">
                  <p className="text-[0.7rem] uppercase tracking-[0.2em] text-[var(--muted-foreground)]">Customer</p>
                  <p className="text-sm font-semibold mt-1">{selectedInvoice.customer_name}</p>
                </div>
                <div className="rounded-xl border border-[var(--border)] p-3">
                  <p className="text-[0.7rem] uppercase tracking-[0.2em] text-[var(--muted-foreground)]">Status</p>
                  <p className="text-sm font-semibold mt-1">{selectedInvoice.status}</p>
                </div>
                <div className="rounded-xl border border-[var(--border)] p-3">
                  <p className="text-[0.7rem] uppercase tracking-[0.2em] text-[var(--muted-foreground)]">Issued</p>
                  <p className="text-sm font-semibold mt-1">{formatDate(selectedInvoice.issued_date)}</p>
                </div>
                <div className="rounded-xl border border-[var(--border)] p-3">
                  <p className="text-[0.7rem] uppercase tracking-[0.2em] text-[var(--muted-foreground)]">Due</p>
                  <p className="text-sm font-semibold mt-1">{formatDate(selectedInvoice.due_date)}</p>
                </div>
                <div className="rounded-xl border border-[var(--border)] p-3 sm:col-span-2">
                  <p className="text-[0.7rem] uppercase tracking-[0.2em] text-[var(--muted-foreground)]">Total</p>
                  <p className="text-lg font-semibold mt-1">{formatCurrencyRon(selectedInvoice.amount_ron)}</p>
                </div>
              </div>

              {selectedInvoice.status !== 'PAID' && (
                <button
                  type="button"
                  onClick={markInvoicePaid}
                  disabled={markingPaid}
                  className="h-10 px-4 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {markingPaid ? 'Updating...' : 'Mark as Paid'}
                </button>
              )}

              <div>
                <h4 className="text-sm font-semibold">Line Items</h4>
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-[0.85rem]">
                    <thead>
                      <tr className="border-b border-[var(--border)] bg-[var(--muted)]/40">
                        <th className="px-3 py-2 text-left text-[0.7rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Product</th>
                        <th className="px-3 py-2 text-right text-[0.7rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Qty</th>
                        <th className="px-3 py-2 text-right text-[0.7rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Unit</th>
                        <th className="px-3 py-2 text-right text-[0.7rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Subtotal</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedInvoice.line_items.map((item) => (
                        <tr key={item.id} className="border-b border-[var(--border)]">
                          <td className="px-3 py-2">{item.product_name}</td>
                          <td className="px-3 py-2 text-right">{item.quantity}</td>
                          <td className="px-3 py-2 text-right">{formatCurrencyRon(item.unit_price_ron)}</td>
                          <td className="px-3 py-2 text-right font-semibold">{formatCurrencyRon(item.subtotal_ron)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <p className="text-[0.875rem] text-[var(--muted-foreground)]">Select an invoice to view details.</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default SalesInvoicesPage
