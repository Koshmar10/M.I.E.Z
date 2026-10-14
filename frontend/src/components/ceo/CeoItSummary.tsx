import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../../api/client'

type ItStatsResponse = {
  open_ticket: number
  in_progress: number
  resolved_this_week: number
  ceo_it_summary: {
    avg_resolution_time_hrs: number
    sla_met_percentage: number
    critical_open?: number
    critical_open_tickets?: number
  }
}

type TicketTrendWeek = {
  week_start: string
  opened_count: number
  closed_count: number
}

const formatWeekLabel = (weekStart: string) => {
  const parsed = new Date(weekStart)
  if (Number.isNaN(parsed.getTime())) return weekStart
  return parsed.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
}

const CeoItSummary = () => {
  const [stats, setStats] = useState<ItStatsResponse | null>(null)
  const [trend, setTrend] = useState<TicketTrendWeek[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError('')

        const [statsData, trendData] = await Promise.all([
          api.get<ItStatsResponse>('/api/it/dashboard/'),
          api.get<{ weeks?: TicketTrendWeek[] }>('/api/it/ticket-trend/'),
        ])

        setStats(statsData)
        setTrend(Array.isArray(trendData.weeks) ? trendData.weeks : [])
      } catch (err) {
        console.error('Could not load CEO IT summary', err)
        setError('Could not load IT summary data right now.')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [])

  const kpis = useMemo(() => {
    if (!stats) return []
    const critical = stats.ceo_it_summary.critical_open ?? stats.ceo_it_summary.critical_open_tickets ?? 0
    return [
      { label: 'Open Tickets', value: stats.open_ticket },
      { label: 'Avg Resolution', value: stats.ceo_it_summary.avg_resolution_time_hrs, suffix: 'hrs' },
      { label: 'SLA Compliance', value: stats.ceo_it_summary.sla_met_percentage, suffix: '%' },
      { label: 'Critical Open', value: critical },
    ]
  }, [stats])

  const chartData = useMemo(
    () =>
      trend.map(week => ({
        label: formatWeekLabel(week.week_start),
        Opened: week.opened_count,
        Closed: week.closed_count,
      })),
    [trend]
  )

  return (
    <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[1.05rem] font-semibold tracking-tight">CEO IT Summary</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            Open ticket load, SLA compliance and 6-week throughput.
          </p>
        </div>
        <Link to="/it/dashboard" className="text-sm text-[var(--primary)] hover:opacity-80 font-medium transition-opacity whitespace-nowrap">
          View full dashboard &rarr;
        </Link>
      </header>

      {loading && <p className="text-sm text-[var(--muted-foreground)]">Loading IT summary...</p>}
      {!loading && error && <p className="text-sm text-[var(--destructive)]">{error}</p>}

      {!loading && !error && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          <div className="grid grid-cols-2 gap-3">
            {kpis.map(kpi => (
              <div key={kpi.label} className="rounded-xl border border-[var(--border)] bg-[var(--input-background)] p-4">
                <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium">{kpi.label}</p>
                <p className="text-2xl font-semibold mt-1 tracking-tight">
                  {kpi.value}
                  {kpi.suffix ? <span className="text-base font-medium text-[var(--muted-foreground)] ml-1">{kpi.suffix}</span> : null}
                </p>
              </div>
            ))}
          </div>

          <div className="border border-[var(--border)] rounded-xl p-4">
            <h3 className="text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)] mb-2">
              Tickets Opened vs Closed (Last 6 Weeks)
            </h3>
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 4, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid var(--border)' }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
                  <Bar dataKey="Opened" fill="var(--primary)" radius={[6, 6, 0, 0]} />
                  <Bar dataKey="Closed" fill="#D48A6B" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

export default CeoItSummary
