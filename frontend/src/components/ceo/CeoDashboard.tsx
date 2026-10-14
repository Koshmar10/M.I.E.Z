import { useEffect, useMemo, useState } from 'react'
import {
  FiMonitor,
  FiUsers,
  FiBarChart2,
  FiPackage,
  FiHome,
  FiTrash2,
  FiPlus,
  FiClock,
  FiLayers,
} from 'react-icons/fi'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useAuth } from '../../context/AuthContext'
import UpcomingEventsWidget from '../hr/UpcomingEventsWidget'
import CeoItSummary from './CeoItSummary'
import { api } from '../../api/client'
import CeoSalesSummary from './CeoSalesSummary'
import CeoInventorySummary from './CeoInventorySummary'

type Department = {
  id: number
  name: string
  slug: string
  icon?: string
}

type DepartmentHeadcountRow = {
  department: string
  total: number
  active: number
  on_leave: number
  utilisation_pct: number
}

type AttendanceRateWeek = {
  week_start: string
  attendance_rate: number
}

type CeoHrSummaryResponse = {
  department_headcount: DepartmentHeadcountRow[]
  attendance_rate_weeks: AttendanceRateWeek[]
}

const iconMap = {
  Monitor: FiMonitor,
  Users: FiUsers,
  BarChart3: FiBarChart2,
  Package: FiPackage,
  Building2: FiHome,
} as const

const CeoDashboard = () => {
  const { user } = useAuth()
  const [departments, setDepartments] = useState<Department[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [icon, setIcon] = useState('Building2')
  const [hrSummary, setHrSummary] = useState<CeoHrSummaryResponse | null>(null)
  const [hrSummaryLoading, setHrSummaryLoading] = useState(true)
  const [hrSummaryError, setHrSummaryError] = useState('')

  useEffect(() => {
    const fetchDepartments = async () => {
      if (user?.role !== 'CEO') {
        setDepartments([])
        setIsLoading(false)
        return
      }

      try {
        const data = await api.get<Department[]>('/api/departments/')
        setDepartments(data)
        window.dispatchEvent(new CustomEvent('departments-updated', { detail: data }))
      } catch (error) {
        console.error('Eroare la incarcarea departamentelor', error)
      } finally {
        setIsLoading(false)
      }
    }

    void fetchDepartments()
  }, [user?.role])

  useEffect(() => {
    const fetchHrSummary = async () => {
      if (user?.role !== 'CEO') {
        setHrSummary(null)
        setHrSummaryLoading(false)
        return
      }

      try {
        setHrSummaryLoading(true)
        setHrSummaryError('')

        setHrSummary(await api.get<CeoHrSummaryResponse>('/api/hr/ceo-summary/'))
      } catch (error) {
        console.error('Eroare la incarcarea HR summary pentru CEO', error)
        setHrSummaryError('Could not load HR summary data right now.')
      } finally {
        setHrSummaryLoading(false)
      }
    }

    void fetchHrSummary()
  }, [user?.role])

  const attendanceChartData = useMemo(() => {
    return (hrSummary?.attendance_rate_weeks ?? []).map(point => {
      const weekDate = new Date(point.week_start)
      const label = Number.isNaN(weekDate.getTime())
        ? point.week_start
        : weekDate.toLocaleDateString('ro-RO', { month: 'short', day: 'numeric' })

      return {
        ...point,
        label,
      }
    })
  }, [hrSummary])

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/api/departments/${id}/`)
      setDepartments(current => {
        const next = current.filter(dep => dep.id !== id)
        window.dispatchEvent(new CustomEvent('departments-updated', { detail: next }))
        return next
      })
    } catch (error) {
      console.error('Eroare la stergere', error)
    }
  }

  const toSlug = (value: string) =>
    value
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')

  const handleCreate = async (event: React.SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault()

    const payload = {
      name: name.trim(),
      slug: slug.trim() || toSlug(name),
      icon,
    }

    if (!payload.name || !payload.slug) {
      return
    }

    try {
      const createdDepartment = await api.post<Department>('/api/departments/', payload)

      setDepartments(current => {
        const next = [...current, createdDepartment].sort((a, b) => a.name.localeCompare(b.name))
        window.dispatchEvent(new CustomEvent('departments-updated', { detail: next }))
        return next
      })
      setName('')
      setSlug('')
      setIcon('Building2')
    } catch (error) {
      console.error('Eroare la creare', error)
    }
  }

  const stats = useMemo(() => {
    return [
      {
        label: 'Departments',
        value: departments.length,
        sub: departments.length === 1 ? 'active module' : 'active modules',
        Icon: FiLayers,
      },
      {
        label: 'Employee Teams',
        value: departments.length,
        sub: 'mirrors department count',
        Icon: FiUsers,
      },
      {
        label: 'Pending Actions',
        value: departments.length === 0 ? 1 : 0,
        sub: departments.length === 0 ? 'add a first department' : 'all caught up',
        Icon: FiClock,
      },
    ]
  }, [departments])

  if (isLoading) {
    return <div className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">Loading...</div>
  }

  if (user?.role !== 'CEO') {
    return (
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <h2>Dashboard</h2>
        <p>Department management is only available for CEO accounts.</p>
      </section>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <header className="mb-4">
          <h2 className="text-[1.05rem] font-semibold tracking-tight">CEO HR Summary</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            Department headcount, leave status and attendance utilisation trend.
          </p>
        </header>

        {hrSummaryLoading && (
          <p className="text-sm text-[var(--muted-foreground)]">Loading HR summary...</p>
        )}

        {!hrSummaryLoading && hrSummaryError && (
          <p className="text-sm text-[var(--destructive)]">{hrSummaryError}</p>
        )}

        {!hrSummaryLoading && !hrSummaryError && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <div className="border border-[var(--border)] rounded-xl overflow-hidden">
              <table className="w-full text-left text-[0.9rem]">
                <thead className="bg-[var(--input-background)]">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Department</th>
                    <th className="px-3 py-2 font-semibold">Total</th>
                    <th className="px-3 py-2 font-semibold">Active</th>
                    <th className="px-3 py-2 font-semibold">On Leave</th>
                    <th className="px-3 py-2 font-semibold">Utilisation %</th>
                  </tr>
                </thead>
                <tbody>
                  {(hrSummary?.department_headcount ?? []).map(row => (
                    <tr key={row.department} className="border-t border-[var(--border)]">
                      <td className="px-3 py-2 font-medium">{row.department}</td>
                      <td className="px-3 py-2">{row.total}</td>
                      <td className="px-3 py-2 text-emerald-600 font-semibold">{row.active}</td>
                      <td className="px-3 py-2 text-amber-600 font-semibold">{row.on_leave}</td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <div className="h-2 flex-1 rounded-full bg-[var(--input-background)] overflow-hidden">
                            <div
                              className="h-full rounded-full bg-[var(--primary)]"
                              style={{ width: `${Math.max(0, Math.min(100, row.utilisation_pct))}%` }}
                            />
                          </div>
                          <span className="text-[0.8rem] font-semibold">{row.utilisation_pct.toFixed(1)}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="border border-[var(--border)] rounded-xl p-4">
              <h3 className="text-[0.95rem] font-semibold mb-2">Attendance Rate per Week (Last 6 Weeks)</h3>
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={attendanceChartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                    <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} unit="%" />
                    <Tooltip
                      formatter={(value: number) => [`${value.toFixed(1)}%`, 'Attendance Rate']}
                      labelFormatter={(value: string) => `Week of ${value}`}
                    />
                    <Line
                      type="monotone"
                      dataKey="attendance_rate"
                      stroke="var(--primary)"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {!hrSummaryLoading && !hrSummaryError && (
          <div className="mt-5">
            <UpcomingEventsWidget />
          </div>
        )}
      </section>

      <CeoItSummary />
      <CeoSalesSummary />
      <CeoInventorySummary />

      <header className="flex flex-col gap-1">
        <h2 className="text-[1.05rem] font-semibold tracking-tight">Department Management</h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          Add or remove departments to customize your organization.
        </p>
      </header>

      <form className="grid grid-cols-[1.2fr_1fr_0.8fr_auto] gap-[0.6rem] bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-[0.9rem]" onSubmit={(event) => void handleCreate(event)}>
        <input
          className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--input-background)] text-[var(--foreground)]"
          value={name}
          onChange={event => setName(event.target.value)}
          placeholder="Department name"
          aria-label="Department name"
        />
        <input
          className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--input-background)] text-[var(--foreground)]"
          value={slug}
          onChange={event => setSlug(event.target.value)}
          placeholder="Slug (optional)"
          aria-label="Department slug"
        />
        <select className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--input-background)] text-[var(--foreground)]" value={icon} onChange={event => setIcon(event.target.value)} aria-label="Department icon">
          <option value="Building2">Building</option>
          <option value="Monitor">IT</option>
          <option value="Users">HR</option>
          <option value="BarChart3">Sales</option>
          <option value="Package">Inventory</option>
        </select>
        <button className="min-h-[40px] rounded-[10px] bg-[var(--primary)] text-[var(--primary-foreground)] px-[0.9rem] font-bold cursor-pointer inline-flex items-center gap-[0.35rem] border-none" type="submit">
          <FiPlus />
          Add Department
        </button>
      </form>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {stats.map(stat => {
          const Icon = stat.Icon
          return (
            <article
              key={stat.label}
              className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-4 flex items-start justify-between gap-3"
            >
              <div className="flex flex-col">
                <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] font-medium">{stat.label}</p>
                <p className="text-2xl font-semibold mt-1 tracking-tight">{stat.value}</p>
                <p className="text-xs text-[var(--muted-foreground)] mt-1">{stat.sub}</p>
              </div>
              <div className="w-10 h-10 rounded-xl bg-[var(--input-background)] grid place-items-center text-[var(--primary)] shrink-0">
                <Icon size={18} />
              </div>
            </article>
          )
        })}
      </div>

      {departments.length === 0 ? (
        <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl px-[1.2rem] py-[2.2rem] min-h-[340px] flex flex-col items-center justify-center text-center gap-[0.7rem]">
          <div className="w-[54px] h-[54px] rounded-full border border-[var(--border)] bg-[var(--input-background)] grid place-items-center text-[var(--primary)]">
            <FiHome />
          </div>
          <h3>No Departments Added</h3>
          <p>
            Get started by adding your first department. Each department will unlock
            specialized tools and views for your team.
          </p>
        </section>
      ) : (
        <section className="grid grid-cols-4 gap-4">
          {departments.map(dep => {
            const iconName = dep.icon ?? 'Building2'
            const Icon = iconName in iconMap ? iconMap[iconName as keyof typeof iconMap] : FiHome
            return (
              <article key={dep.id} className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-4 flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <div className="w-[44px] h-[44px] rounded-2xl bg-[var(--input-background)] text-[var(--primary)] grid place-items-center">
                    <Icon />
                  </div>
                  <button
                    type="button"
                    className="w-[34px] h-[34px] rounded-lg border border-[var(--border)] bg-transparent text-[var(--destructive)] grid place-items-center cursor-pointer hover:bg-[#d1353b14]"
                    onClick={() => void handleDelete(dep.id)}
                    aria-label={`Delete ${dep.name}`}
                  >
                    <FiTrash2 />
                  </button>
                </div>

                <div className="flex flex-col gap-1">
                  <h4 className="font-semibold">{dep.name}</h4>
                  <p className="text-[0.9rem] text-[var(--muted-foreground)]">
                    {`Module path: /departments/${dep.slug}`}
                  </p>
                </div>
              </article>
            )
          })}
        </section>
      )}
    </div>
  )
}

export default CeoDashboard