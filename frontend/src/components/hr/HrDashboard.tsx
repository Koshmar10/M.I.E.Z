import React from 'react'
import { FiUsers, FiCalendar, FiBriefcase, FiTrendingUp, FiZap, FiCheckCircle, FiAlertTriangle } from 'react-icons/fi'
import { CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, BarChart, Bar } from 'recharts'
import { api, errorMessage, type Page } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import UpcomingEventsWidget from './UpcomingEventsWidget'
import Markdown from '../common/Markdown'

type HrKpiResponse = {
  total_employees: number
  new_hires_this_month: number
  leave_requests_this_month: number
  pending_leave_requests: number
  full_time_employees: number
  non_full_time_employees: number
  retention_rate: number
  active_employees: number
}

type AgentReport = {
  id: number
  name: string
  slug: string
  period: string
  generated_at: string
  digest_data: {
    week: string
    week_start: string
    week_end: string
    content: string
    tool_calls: number
    summary_line?: string
    critical?: any[]
    warning?: any[]
    info?: any[]
  } | null
}

type Tab = 'overview' | 'agent-reports'

type DepartmentHeadcount = {
  department: string
  total: number
  active: number
  on_leave: number
  utilisation_pct: number
}

type AttendanceWeek = {
  week_start: string
  attendance_rate: number
}

type CeoSummaryResponse = {
  department_headcount: DepartmentHeadcount[]
  attendance_rate_weeks: AttendanceWeek[]
}

type Employee = {
  id: number
  username: string
  first_name: string
  last_name: string
  email: string
  role: string
  position: string
  employment_type: string
  department: { id: number; name: string } | null
  start_date: string
}

const formatDate = (value: string) =>
  new Date(value).toLocaleDateString('ro-RO')

const roleBadge: Record<string, string> =  {
  CEO:       'bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20',
  HR:        'bg-[var(--input-background)] text-[var(--foreground)] border border-[var(--border)]',
  IT:        'bg-[var(--input-background)] text-[var(--foreground)] border border-[var(--border)]',
  SALES:     'bg-emerald-50 text-emerald-700 border border-emerald-200',
  INVENTORY: 'bg-amber-50 text-amber-700 border border-amber-200',
}

const HrDashboard = () => {
  const { user } = useAuth()
  const isCeo = user?.role === 'CEO'

  const [activeTab, setActiveTab] = React.useState<Tab>('overview')

  const [kpis, setKpis] = React.useState<HrKpiResponse | null>(null)
  const [loadingKpis, setLoadingKpis] = React.useState(true)
  const [kpisError, setKpisError] = React.useState('')

  const [ceoSummary, setCeoSummary] = React.useState<CeoSummaryResponse | null>(null)
  const [loadingSummary, setLoadingSummary] = React.useState(false)

  const [employees, setEmployees] = React.useState<Employee[]>([])
  const [loadingEmployees, setLoadingEmployees] = React.useState(false)
  const [employeesError, setEmployeesError] = React.useState('')
  const [empSearch, setEmpSearch] = React.useState('')

  const [agentReports, setAgentReports] = React.useState<AgentReport[]>([])
  const [loadingReports, setLoadingReports] = React.useState(false)
  const [expandedReport, setExpandedReport] = React.useState<number | null>(null)

  const isHr = user?.role === 'HR'
  const [isPolling, setIsPolling] = React.useState(false)
  const [triggerError, setTriggerError] = React.useState('')

  const fetchReports = React.useCallback(() => {
    setLoadingReports(true)
    api.get<AgentReport[]>('/api/reports/', { category: 'HR' })
      .then(setAgentReports)
      .catch(() => setAgentReports([]))
      .finally(() => setLoadingReports(false))
  }, [])

  const [latestDigest, setLatestDigest] = React.useState<AgentReport | null>(null)

  const fetchLatestDigest = React.useCallback(() => {
    if (!isCeo && !isHr) return
    api.get<AgentReport>('/api/hr/latest-digest/')
      .then(setLatestDigest)
      .catch(() => undefined) // 404 until a first digest exists
  }, [isCeo, isHr])

  React.useEffect(() => {
    fetchLatestDigest()
  }, [fetchLatestDigest])

  // KPIs
  React.useEffect(() => {
    api.get<HrKpiResponse>('/api/hr/dashboard/')
      .then(setKpis)
      .catch(() => setKpisError('Could not load HR KPI data.'))
      .finally(() => setLoadingKpis(false))
  }, [])

  // CEO summary (department headcount + attendance trend)
  React.useEffect(() => {
    if (!isCeo) return
    setLoadingSummary(true)
    api.get<CeoSummaryResponse>('/api/hr/ceo-summary/')
      .then(setCeoSummary)
      .catch(console.error)
      .finally(() => setLoadingSummary(false))
  }, [isCeo])

  // Employee list
  React.useEffect(() => {
    if (!isCeo) return
    setLoadingEmployees(true)
    api.get<Page<Employee>>('/api/employees/', { page_size: 50 })
      .then(data => setEmployees(data.results))
      .catch(() => setEmployeesError('Could not load employees.'))
      .finally(() => setLoadingEmployees(false))
  }, [isCeo])

  // Agent reports (lazy — only when tab is active)
  React.useEffect(() => {
    if (activeTab !== 'agent-reports') return
    fetchReports()
  }, [activeTab, fetchReports])

  const triggerAgent = async () => {
    try {
      setTriggerError('')
      const triggerTime = Date.now()
      
      await api.post('/api/hr/run-insights-agent/')

      setIsPolling(true)

      // Wait for a digest newer than the trigger; the agent runs in the background.
      const pollInterval = setInterval(() => {
        api.get<AgentReport>('/api/hr/latest-digest/')
          .then(data => {
            if (data.generated_at && new Date(data.generated_at).getTime() > triggerTime) {
              clearInterval(pollInterval)
              setIsPolling(false)
              fetchReports()
              fetchLatestDigest()
            }
          })
          .catch(() => undefined) // no digest yet
      }, 3000)
      
      // Safety timeout after 2 minutes
      setTimeout(() => {
        clearInterval(pollInterval)
        setIsPolling(false)
      }, 120000)
      
    } catch (e) {
      setTriggerError(errorMessage(e, 'Error triggering agent'))
      setIsPolling(false)
    }
  }

  const filteredEmployees = React.useMemo(() => {
    if (!empSearch.trim()) return employees
    const q = empSearch.toLowerCase()
    return employees.filter(e =>
      `${e.first_name} ${e.last_name}`.toLowerCase().includes(q) ||
      e.position.toLowerCase().includes(q) ||
      e.role.toLowerCase().includes(q)
    )
  }, [employees, empSearch])

  const maxAttendance = React.useMemo(
    () => Math.max(...(ceoSummary?.attendance_rate_weeks.map(w => w.attendance_rate) ?? [1]), 1),
    [ceoSummary]
  )

  const kpiCards = [
    { title: 'Total Employees', value: kpis?.total_employees ?? 0, sub: `+${kpis?.new_hires_this_month ?? 0} this month`, Icon: FiUsers },
    { title: 'Leave Requests', value: kpis?.leave_requests_this_month ?? 0, sub: `${kpis?.pending_leave_requests ?? 0} pending approval`, Icon: FiCalendar },
    { title: 'Full-Time', value: kpis?.full_time_employees ?? 0, sub: `${kpis?.non_full_time_employees ?? 0} non full-time`, Icon: FiBriefcase },
    { title: 'Retention Rate', value: `${(kpis?.retention_rate ?? 0).toFixed(1)}%`, sub: `${kpis?.active_employees ?? 0}/${kpis?.total_employees ?? 0} active`, Icon: FiTrendingUp },
  ]

  const formatReportDate = (iso: string) =>
    new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })

  return (
    <div className="space-y-6">

      {/* Tab bar */}
      <div className="flex gap-6 border-b border-[var(--border)]">
        {(['overview', 'agent-reports'] as Tab[]).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`relative px-1 pb-3 text-sm font-medium transition-colors cursor-pointer ${
              activeTab === tab
                ? 'text-[var(--foreground)]'
                : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            {tab === 'overview' ? 'Overview' : 'Agent Reports'}
            {activeTab === tab && (
              <span className="absolute left-0 right-0 -bottom-px h-[2px] bg-[var(--primary)] rounded-full" />
            )}
          </button>
        ))}
      </div>

      {activeTab === 'agent-reports' && (
        <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-[1.05rem] font-semibold tracking-tight">HR Agent Reports</h2>
              <p className="text-sm text-[var(--muted-foreground)] mt-1">Weekly digests generated by the autonomous HR Insights Agent.</p>
              {triggerError && <p className="text-sm text-[var(--destructive)] mt-1">{triggerError}</p>}
            </div>
            {(isCeo || isHr) && (
              <button
                onClick={triggerAgent}
                disabled={isPolling}
                className="shrink-0 inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-semibold bg-[var(--primary)] text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {isPolling && (
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                )}
                {isPolling ? 'Generating...' : 'Run Insights Now'}
              </button>
            )}
          </div>
          {loadingReports ? (
            <p className="text-sm text-[var(--muted-foreground)]">Loading reports…</p>
          ) : agentReports.length === 0 ? (
            <p className="text-sm text-[var(--muted-foreground)]">No HR agent reports yet. The agent runs every Monday at 06:00.</p>
          ) : (
            <ul className="space-y-3">
              {agentReports.map(report => (
                <li key={report.id} className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden">
                  <button
                    onClick={() => setExpandedReport(expandedReport === report.id ? null : report.id)}
                    className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[var(--input-background)] transition-colors cursor-pointer"
                  >
                    <div>
                      <p className="text-sm font-semibold">{report.name}</p>
                      <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                        {report.period} · Generated {formatReportDate(report.generated_at)}
                        {report.digest_data?.tool_calls != null && ` · ${report.digest_data.tool_calls} tool calls`}
                      </p>
                    </div>
                    <span className="text-[var(--muted-foreground)] text-sm ml-4 shrink-0">
                      {expandedReport === report.id ? '▲' : '▼'}
                    </span>
                  </button>
                  {expandedReport === report.id && report.digest_data?.content && (
                    <div className="px-4 pb-4 pt-3 border-t border-[var(--border)]">
                      <Markdown>{report.digest_data.content}</Markdown>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {activeTab === 'overview' && (
      <>

      {/* Latest Agent Digest Inline Card */}
      {(isCeo || isHr) && (
        <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
                <FiZap size={18} />
              </div>
              <div>
                <h2 className="text-[1.05rem] font-semibold tracking-tight">Weekly HR Insights</h2>
                <p className="text-sm text-[var(--muted-foreground)] mt-0.5">
                  {latestDigest ? `Generated ${formatReportDate(latestDigest.generated_at)}` : 'Loading...'}
                </p>
              </div>
            </div>
            <button
              onClick={() => setActiveTab('agent-reports')}
              className="text-sm text-[var(--primary)] hover:opacity-80 font-medium transition-opacity"
            >
              View full report &rarr;
            </button>
          </div>

          {latestDigest?.digest_data ? (
            <div className="space-y-4">
              <p className="text-sm font-medium bg-[var(--input-background)] border border-[var(--border)] rounded-lg p-3">
                {latestDigest.digest_data.summary_line || 'No summary available.'}
              </p>

              {(() => {
                const data = latestDigest.digest_data as any;
                const critical: any[] = Array.isArray(data.critical) ? data.critical : [];
                const warning: any[] = Array.isArray(data.warning) ? data.warning : [];

                if (critical.length === 0 && warning.length === 0) {
                  return (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 shrink-0">
                        <FiCheckCircle size={18} />
                      </div>
                      <p className="text-sm font-semibold text-emerald-800">No issues detected this week</p>
                    </div>
                  );
                }

                const itemsToShow = [
                  ...critical.map((c: any) => ({...c, level: 'CRITICAL'})), 
                  ...warning.map((w: any) => ({...w, level: 'WARNING'}))
                ].slice(0, 2);

                return (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
                    {itemsToShow.map((insight, idx) => {
                      const isCritical = insight.level === 'CRITICAL';
                      return (
                        <div
                          key={idx}
                          className={`rounded-xl border bg-[var(--card)] p-4 flex flex-col border-l-4 ${
                            isCritical ? 'border-l-rose-500 border-rose-200' : 'border-l-amber-500 border-amber-200'
                          }`}
                        >
                          <h4
                            className={`text-[11px] font-bold uppercase tracking-[0.14em] mb-1.5 inline-flex items-center gap-1.5 ${
                              isCritical ? 'text-rose-700' : 'text-amber-700'
                            }`}
                          >
                            <FiAlertTriangle size={12} />
                            {insight.level}
                          </h4>
                          <h3 className="text-sm font-semibold mb-1.5 leading-tight">{insight.title}</h3>
                          <p className="text-sm text-[var(--muted-foreground)] mb-3 flex-1">{insight.description}</p>
                          <div className="mt-auto bg-[var(--input-background)] p-2.5 rounded border border-[var(--border)] text-xs">
                            <span className="font-semibold block mb-0.5">Suggested Action:</span>
                            <span className="text-[var(--muted-foreground)]">{insight.suggested_action}</span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )
              })()}
            </div>
          ) : (
            <p className="text-sm text-[var(--muted-foreground)] italic py-2">No recent insights available.</p>
          )}
        </section>
      )}

      {/* KPI Cards */}
      <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5">
        <h2 className="text-[1.05rem] font-semibold tracking-tight">HR Dashboard</h2>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">Human resources metrics and headcount overview.</p>

        {loadingKpis ? (
          <p className="text-sm text-[var(--muted-foreground)] mt-3">Loading KPI data…</p>
        ) : kpisError ? (
          <p className="text-sm text-[var(--destructive)] mt-3">{kpisError}</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
            {kpiCards.map(card => {
              const Icon = card.Icon
              return (
                <article
                  key={card.title}
                  className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 flex items-start justify-between gap-3"
                >
                  <div className="flex flex-col">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium">{card.title}</p>
                    <p className="text-2xl font-semibold mt-1 tracking-tight">{card.value}</p>
                    <p className="text-xs text-[var(--muted-foreground)] mt-1">{card.sub}</p>
                  </div>
                  <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
                    <Icon size={18} />
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>

      <UpcomingEventsWidget />

      {/* CEO-only: Department Headcount + Attendance Trend */}
      {isCeo && (
        <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-[1.05rem] font-semibold tracking-tight">Department Overview</h3>
              <p className="text-sm text-[var(--muted-foreground)] mt-1">Headcount and 6-week attendance rate by department.</p>
            </div>
          </div>

          {loadingSummary ? (
            <p className="text-sm text-[var(--muted-foreground)] mt-3">Loading summary…</p>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mt-4">

              {/* Department headcount table */}
              <div className="xl:col-span-2 rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden">
                <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium px-4 pt-4 pb-2">Headcount by department</p>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-t border-[var(--border)] bg-[var(--input-background)]">
                      {['Department', 'Total', 'Active', 'On Leave', 'Utilisation'].map(h => (
                        <th key={h} className="text-left px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(ceoSummary?.department_headcount ?? []).map(row => (
                      <tr key={row.department} className="border-t border-[var(--border)] hover:bg-[var(--input-background)] transition-colors">
                        <td className="px-4 py-2.5 font-medium">{row.department}</td>
                        <td className="px-4 py-2.5">{row.total}</td>
                        <td className="px-4 py-2.5 text-emerald-700 font-medium">{row.active}</td>
                        <td className="px-4 py-2.5 text-amber-700 font-medium">{row.on_leave}</td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-[var(--input-background)] rounded-full h-1.5 overflow-hidden">
                              <div
                                className="h-1.5 rounded-full bg-[var(--primary)]"
                                style={{ width: `${Math.max(0, Math.min(100, row.utilisation_pct))}%` }}
                              />
                            </div>
                            <span className="text-xs font-semibold w-10 text-right">{row.utilisation_pct}%</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Attendance rate 6-week trend */}
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium mb-3">Attendance rate — last 6 weeks</p>
                <div className="h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={(ceoSummary?.attendance_rate_weeks ?? []).map(week => ({
                        label: new Date(week.week_start).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }),
                        attendance: week.attendance_rate,
                      }))}
                      margin={{ top: 8, right: 4, left: -16, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                      <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, Math.max(maxAttendance, 100)]} tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} unit="%" />
                      <Tooltip
                        formatter={(value: number) => [`${value}%`, 'Attendance']}
                        contentStyle={{ borderRadius: 8, border: '1px solid var(--border)' }}
                      />
                      <Bar dataKey="attendance" fill="var(--primary)" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {/* CEO-only: Employee List */}
      {isCeo && (
        <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
                <FiUsers size={18} />
              </div>
              <div>
                <h3 className="text-[1.05rem] font-semibold tracking-tight">All Employees</h3>
                <p className="text-sm text-[var(--muted-foreground)] mt-1">Full roster across all departments.</p>
              </div>
            </div>
            <span className="text-sm text-[var(--muted-foreground)]">{filteredEmployees.length} of {employees.length}</span>
          </div>

          <input
            value={empSearch}
            onChange={e => setEmpSearch(e.target.value)}
            placeholder="Search by name, position, or role…"
            className="w-full max-w-sm rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm"
          />

          {loadingEmployees ? (
            <p className="text-sm text-[var(--muted-foreground)]">Loading employees…</p>
          ) : employeesError ? (
            <p className="text-sm text-[var(--destructive)]">{employeesError}</p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="bg-[var(--input-background)]">
                    {['Name', 'Position', 'Department', 'Role', 'Type', 'Start Date'].map(h => (
                      <th key={h} className="text-left text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-semibold px-4 py-2.5">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredEmployees.map(emp => (
                    <tr key={emp.id} className="border-t border-[var(--border)] hover:bg-[var(--input-background)] transition-colors">
                      <td className="px-4 py-2.5">
                        <p className="text-sm font-semibold">{emp.first_name} {emp.last_name}</p>
                        <p className="text-xs text-[var(--muted-foreground)]">{emp.email}</p>
                      </td>
                      <td className="px-4 py-2.5 text-sm">{emp.position || '—'}</td>
                      <td className="px-4 py-2.5 text-sm">{emp.department?.name ?? '—'}</td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${roleBadge[emp.role] ?? 'bg-[var(--input-background)] text-[var(--muted-foreground)] border border-[var(--border)]'}`}>
                          {emp.role}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-sm text-[var(--muted-foreground)]">{emp.employment_type?.replace('_', ' ') ?? '—'}</td>
                      <td className="px-4 py-2.5 text-sm text-[var(--muted-foreground)]">{formatDate(emp.start_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      </>
      )}
    </div>
  )
}

export default HrDashboard
