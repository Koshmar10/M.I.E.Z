import { useEffect, useMemo, useState } from 'react'
import { FiClock, FiDollarSign } from 'react-icons/fi'
import { api } from '../../api/client'

type PayrollRow = {
  id: number
  employee: number
  employee_name: string
  department: string | null
  month: string
  base_salary_ron: string
  bonus_ron: string
  deductions_ron: string
  net_salary_ron: string
  recorded_net_salary_ron: string
  status: 'PROCESSED' | 'PENDING'
  is_paid: boolean
}

type PayrollSummary = {
  total_employees: number
  processed_count: number
  pending_count: number
  total_base_ron: string
  total_bonus_ron: string
  total_deductions_ron: string
  total_net_ron: string
}

type PayrollResponse = {
  month: string
  summary: PayrollSummary
  payroll: PayrollRow[]
}

const formatMoney = (value: string | number) => {
  const numeric = typeof value === 'string' ? Number(value) : value
  return new Intl.NumberFormat('ro-RO', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Number.isFinite(numeric) ? numeric : 0)
}

const formatMonthLabel = (month: string) => {
  const date = new Date(`${month}-01T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return month
  }

  return date.toLocaleDateString('en-GB', {
    month: 'long',
    year: 'numeric',
  })
}

const formatDateLabel = (value: Date) =>
  value.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })

const getInitials = (name: string) => {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'U'
  const first = parts[0]?.[0] ?? ''
  const second = parts[1]?.[0] ?? ''
  return `${first}${second}`.toUpperCase() || 'U'
}

const monthToInputValue = (value: Date) => {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

export default function PayrollSummaryPage() {
  const [month, setMonth] = useState<string>(monthToInputValue(new Date()))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [rows, setRows] = useState<PayrollRow[]>([])
  const [summary, setSummary] = useState<PayrollSummary | null>(null)

  useEffect(() => {
    const loadPayroll = async () => {
      setLoading(true)
      setError('')

      try {
        const data = await api.get<PayrollResponse>('/api/payroll/', { month })
        setRows(data.payroll)
        setSummary(data.summary)
      } catch (err) {
        console.error('Failed to load payroll summary', err)
        setRows([])
        setSummary(null)
        setError('Could not load payroll summary data.')
      } finally {
        setLoading(false)
      }
    }

    void loadPayroll()
  }, [month])

  const processingLabel = useMemo(() => {
    if (!summary) return 'Processing'
    if (summary.pending_count > 0) return `Pending: ${summary.pending_count} entries`

    const referenceDate = new Date(`${month}-25T00:00:00`)
    return `Processing: ${formatDateLabel(referenceDate)}`
  }, [month, summary])

  const totals = useMemo(() => {
    return {
      base: summary?.total_base_ron ?? '0.00',
      bonus: summary?.total_bonus_ron ?? '0.00',
      deductions: summary?.total_deductions_ron ?? '0.00',
      net: summary?.total_net_ron ?? '0.00',
    }
  }, [summary])

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-[1.18rem] font-semibold">Payroll Summary</h2>
          <p className="text-[0.92rem] text-[var(--muted-foreground)]">{formatMonthLabel(month)} payroll snapshot from recorded database entries.</p>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="month"
            value={month}
            onChange={(event) => setMonth(event.target.value)}
            className="rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm text-[var(--foreground)]"
            aria-label="Payroll month"
          />
          <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-semibold ${summary?.pending_count ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>
            <FiClock className="h-4 w-4" />
            {processingLabel}
          </div>
        </div>
      </header>

      <div className="grid gap-3 md:grid-cols-3">
        <article className="rounded-2xl border border-[var(--border)] bg-white p-4 shadow-sm">
          <p className="text-sm text-[var(--muted-foreground)]">Total Gross (Base)</p>
          <p className="mt-2 text-4xl font-semibold text-[var(--foreground)]">{formatMoney(totals.base)} RON</p>
        </article>

        <article className="rounded-2xl border border-[var(--border)] bg-white p-4 shadow-sm">
          <p className="text-sm text-[var(--muted-foreground)]">Total Bonuses</p>
          <p className="mt-2 text-4xl font-semibold text-emerald-600">{formatMoney(totals.bonus)} RON</p>
        </article>

        <article className="rounded-2xl border border-[var(--border)] bg-white p-4 shadow-sm">
          <p className="text-sm text-[var(--muted-foreground)]">Total Net Payout</p>
          <p className="mt-2 text-4xl font-semibold text-rose-600">{formatMoney(totals.net)} RON</p>
        </article>
      </div>

      <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-[var(--border)] px-5 py-4">
          <FiDollarSign className="h-4 w-4 text-[var(--muted-foreground)]" />
          <span className="text-sm font-semibold">{formatMonthLabel(month)} Payroll</span>
        </div>

        {loading ? (
          <div className="py-16 text-center text-sm text-[var(--muted-foreground)]">Loading payroll entries…</div>
        ) : error ? (
          <div className="py-16 text-center text-sm text-rose-600">{error}</div>
        ) : rows.length === 0 ? (
          <div className="py-16 text-center text-sm text-[var(--muted-foreground)]">No payroll entries found for this month.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-[rgba(0,0,0,0.015)]">
                <tr className="border-b border-[var(--border)]">
                  {['Employee', 'Department', 'Base Salary', 'Bonus', 'Deductions', 'Net Pay', 'Status'].map(column => (
                    <th key={column} className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={row.id} className="border-b border-[var(--border)] last:border-0 hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#D88964] text-[11px] font-semibold text-white">
                          {getInitials(row.employee_name)}
                        </div>
                        <span className="font-medium text-[var(--foreground)]">{row.employee_name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-[var(--muted-foreground)]">{row.department ?? '—'}</td>
                    <td className="px-5 py-4 font-medium text-[var(--foreground)]">{formatMoney(row.base_salary_ron)} RON</td>
                    <td className="px-5 py-4 font-medium text-emerald-600">+{formatMoney(row.bonus_ron)} RON</td>
                    <td className="px-5 py-4 font-medium text-rose-500">-{formatMoney(row.deductions_ron)} RON</td>
                    <td className="px-5 py-4 font-semibold text-[var(--foreground)]">{formatMoney(row.net_salary_ron)} RON</td>
                    <td className="px-5 py-4">
                      <span className={`inline-flex rounded-md px-2.5 py-1 text-xs font-semibold ${row.status === 'PROCESSED' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                        {row.status === 'PROCESSED' ? 'Processed' : 'Pending'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-[var(--border)] bg-[rgba(0,0,0,0.01)]">
                  <td className="px-5 py-3 font-semibold text-[var(--foreground)]">Totals</td>
                  <td className="px-5 py-3" />
                  <td className="px-5 py-3 font-semibold text-[var(--foreground)]">{formatMoney(totals.base)} RON</td>
                  <td className="px-5 py-3 font-semibold text-emerald-600">+{formatMoney(totals.bonus)} RON</td>
                  <td className="px-5 py-3 font-semibold text-rose-500">-{formatMoney(totals.deductions)} RON</td>
                  <td className="px-5 py-3 font-semibold text-rose-600">{formatMoney(totals.net)} RON</td>
                  <td className="px-5 py-3 text-xs text-[var(--muted-foreground)]">{summary?.processed_count ?? 0}/{summary?.total_employees ?? 0} processed</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}
