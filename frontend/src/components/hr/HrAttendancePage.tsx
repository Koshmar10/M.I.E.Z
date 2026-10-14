import { useEffect, useMemo, useState } from 'react'
import { FiChevronLeft, FiChevronRight } from 'react-icons/fi'
import { api } from '../../api/client'
import { useAuth } from '../../context/AuthContext'

type AttendanceStatus = 'PRESENT' | 'ABSENT' | 'REMOTE' | 'LEAVE' | null

type AttendanceGridRow = {
  employee_id: number
  employee_name: string
  department: string | null
  statuses: Record<string, AttendanceStatus>
}

type AttendanceResponse = {
  week_start: string
  week_end: string
  days: string[]
  grid: AttendanceGridRow[]
}

const statusMeta: Record<Exclude<AttendanceStatus, null>, { label: string; short: string; dot: string; cell: string }> = {
  PRESENT: {
    label: 'Present',
    short: 'P',
    dot: 'bg-emerald-500',
    cell: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  },
  REMOTE: {
    label: 'Remote',
    short: 'R',
    dot: 'bg-sky-500',
    cell: 'bg-sky-50 text-sky-700 border-sky-200',
  },
  ABSENT: {
    label: 'Absent',
    short: 'A',
    dot: 'bg-rose-500',
    cell: 'bg-rose-50 text-rose-700 border-rose-200',
  },
  LEAVE: {
    label: 'Leave',
    short: 'L',
    dot: 'bg-amber-500',
    cell: 'bg-amber-50 text-amber-700 border-amber-200',
  },
}

const weekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const isWeekend = (dateValue: string) => {
  const d = new Date(dateValue)
  return d.getDay() === 0 || d.getDay() === 6
}

const formatDateShort = (dateValue: string) => {
  const d = new Date(dateValue)
  return Number.isNaN(d.getTime()) ? dateValue : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
}

const getMondayOfWeek = (d: Date) => {
  const date = new Date(d)
  const day = date.getDay()
  date.setDate(date.getDate() + (day === 0 ? -6 : 1 - day))
  date.setHours(0, 0, 0, 0)
  return date
}

const addDays = (d: Date, days: number) => {
  const date = new Date(d)
  date.setDate(date.getDate() + days)
  return date
}

const formatWeekRange = (weekStart: Date) => {
  const weekEnd = addDays(weekStart, 6)
  const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' }
  if (weekStart.getFullYear() !== weekEnd.getFullYear()) {
    return `${weekStart.toLocaleDateString('en-GB', { ...opts, year: 'numeric' })} – ${weekEnd.toLocaleDateString('en-GB', { ...opts, year: 'numeric' })}`
  }
  return `${weekStart.toLocaleDateString('en-GB', opts)} – ${weekEnd.toLocaleDateString('en-GB', { ...opts, year: 'numeric' })}`
}

const HrAttendancePage = () => {
  const { user } = useAuth()
  const [selectedWeekStart, setSelectedWeekStart] = useState(() => getMondayOfWeek(new Date()))
  const [data, setData] = useState<AttendanceResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedDepartment, setSelectedDepartment] = useState('ALL')

  useEffect(() => {
    const load = async () => {
      try {
        setIsLoading(true)
        setError('')
        const weekParam = selectedWeekStart.toISOString().slice(0, 10)
        setData(await api.get<AttendanceResponse>('/api/attendance/', { week: weekParam }))
      } catch {
        setError('Could not load attendance data.')
        setData(null)
      } finally {
        setIsLoading(false)
      }
    }
    void load()
  }, [selectedWeekStart])

  const dayInfo = useMemo(
    () => (data?.days ?? []).map((v, i) => ({ value: v, label: weekdayLabels[i] ?? '', isWeekend: isWeekend(v) })),
    [data?.days]
  )

  const departments = useMemo(() => {
    const names = (data?.grid ?? []).map(r => r.department ?? 'Unassigned')
    return ['ALL', ...Array.from(new Set(names)).sort()]
  }, [data?.grid])

  const filteredGrid = useMemo(
    () =>
      (data?.grid ?? []).filter(
        r => selectedDepartment === 'ALL' || (r.department ?? 'Unassigned') === selectedDepartment
      ),
    [data?.grid, selectedDepartment]
  )

  const summary = useMemo(() => {
    const weekdays = dayInfo.filter(d => !d.isWeekend)
    const workdayCount = Math.max(weekdays.length, 1)
    const totalPossible = filteredGrid.length * workdayCount
    let presentCount = 0
    let absentCount = 0
    for (const row of filteredGrid) {
      for (const day of weekdays) {
        const s = row.statuses[day.value]
        if (s === 'PRESENT' || s === 'REMOTE') presentCount++
        else if (s === 'ABSENT') absentCount++
      }
    }
    return {
      avgAttendance: totalPossible > 0 ? Math.round((presentCount / totalPossible) * 1000) / 10 : 0,
      onLeave: filteredGrid.filter(r => weekdays.some(d => r.statuses[d.value] === 'LEAVE')).length,
      absences: absentCount,
    }
  }, [filteredGrid, dayInfo])

  const presentDays = (row: AttendanceGridRow) =>
    dayInfo.filter(d => !d.isWeekend && (row.statuses[d.value] === 'PRESENT' || row.statuses[d.value] === 'REMOTE')).length

  if (user?.role !== 'HR' && user?.role !== 'CEO') {
    return (
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <p className="text-[0.92rem] text-[var(--muted-foreground)]">This page is available for HR and CEO only.</p>
      </section>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-[1.15rem] font-semibold tracking-tight">Attendance</h2>
          <p className="text-[0.875rem] text-[var(--muted-foreground)] mt-0.5">Weekly presence grid</p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Department filter */}
          <select
            value={selectedDepartment}
            onChange={e => setSelectedDepartment(e.target.value)}
            className="h-9 px-3 text-[0.875rem] rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)] cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          >
            {departments.map(dep => (
              <option key={dep} value={dep}>{dep === 'ALL' ? 'All departments' : dep}</option>
            ))}
          </select>

          {/* Week navigation */}
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setSelectedWeekStart(w => addDays(w, -7))}
              className="h-9 w-9 flex items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--muted)] transition-colors"
              aria-label="Previous week"
            >
              <FiChevronLeft className="w-4 h-4" />
            </button>
            <div className="h-9 px-3 flex items-center text-[0.875rem] font-medium rounded-lg border border-[var(--border)] bg-[var(--card)] whitespace-nowrap">
              {formatWeekRange(selectedWeekStart)}
            </div>
            <button
              type="button"
              onClick={() => setSelectedWeekStart(w => addDays(w, 7))}
              className="h-9 w-9 flex items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--muted)] transition-colors"
              aria-label="Next week"
            >
              <FiChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Stats */}
      {!isLoading && !error && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
            <p className="text-[0.78rem] text-[var(--muted-foreground)] uppercase tracking-wide">Attendance rate</p>
            <p className="text-[1.75rem] font-bold mt-1 leading-none">{summary.avgAttendance}<span className="text-base font-normal text-[var(--muted-foreground)]">%</span></p>
          </div>
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
            <p className="text-[0.78rem] text-[var(--muted-foreground)] uppercase tracking-wide">On leave</p>
            <p className="text-[1.75rem] font-bold mt-1 leading-none">{summary.onLeave}</p>
          </div>
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-4">
            <p className="text-[0.78rem] text-[var(--muted-foreground)] uppercase tracking-wide">Absences</p>
            <p className="text-[1.75rem] font-bold mt-1 leading-none">{summary.absences}</p>
          </div>
        </div>
      )}

      {/* Grid */}
      {isLoading ? (
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-6 text-[0.875rem] text-[var(--muted-foreground)]">Loading…</div>
      ) : error ? (
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-6 text-[0.875rem] text-rose-600">{error}</div>
      ) : (
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl overflow-hidden">
          {/* Legend */}
          <div className="flex items-center gap-4 px-4 py-2.5 border-b border-[var(--border)] text-[0.78rem] text-[var(--muted-foreground)]">
            {Object.entries(statusMeta).map(([key, meta]) => (
              <span key={key} className="inline-flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${meta.dot}`} />
                {meta.label}
              </span>
            ))}
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-slate-300" />
              Weekend
            </span>
          </div>

          <div className="overflow-auto">
            <table className="min-w-full border-collapse text-[0.875rem]">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="sticky left-0 z-10 bg-[var(--card)] text-left px-4 py-2.5 text-[0.78rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide min-w-[200px]">Employee</th>
                  <th className="sticky left-[200px] z-10 bg-[var(--card)] text-left px-4 py-2.5 text-[0.78rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide min-w-[160px]">Department</th>
                  {dayInfo.map(day => (
                    <th key={day.value} className={`text-center px-2 py-2.5 min-w-[72px] text-[0.78rem] font-semibold uppercase tracking-wide ${day.isWeekend ? 'text-slate-400' : 'text-[var(--muted-foreground)]'}`}>
                      <div>{day.label}</div>
                      <div className="font-normal normal-case tracking-normal text-[0.72rem] mt-0.5">{formatDateShort(day.value)}</div>
                    </th>
                  ))}
                  <th className="text-center px-4 py-2.5 text-[0.78rem] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide min-w-[80px]">Days in</th>
                </tr>
              </thead>
              <tbody>
                {filteredGrid.length === 0 ? (
                  <tr>
                    <td colSpan={dayInfo.length + 3} className="px-4 py-6 text-center text-[var(--muted-foreground)]">
                      No employees found.
                    </td>
                  </tr>
                ) : (
                  filteredGrid.map(row => (
                    <tr key={row.employee_id} className="border-b border-[var(--border)] hover:bg-[var(--muted)]/40 transition-colors">
                      <td className="sticky left-0 z-10 bg-[var(--card)] px-4 py-2.5 font-medium">{row.employee_name}</td>
                      <td className="sticky left-[200px] z-10 bg-[var(--card)] px-4 py-2.5 text-[var(--muted-foreground)]">{row.department ?? 'Unassigned'}</td>
                      {dayInfo.map(day => {
                        if (day.isWeekend) {
                          return <td key={day.value} className="px-2 py-2.5 text-center text-slate-300">—</td>
                        }
                        const status = row.statuses[day.value]
                        if (!status) {
                          return <td key={day.value} className="px-2 py-2.5 text-center text-[var(--muted-foreground)]/40">—</td>
                        }
                        const meta = statusMeta[status]
                        return (
                          <td key={day.value} className="px-2 py-2.5 text-center">
                            <span
                              className={`inline-block w-2.5 h-2.5 rounded-full ${meta.dot}`}
                              title={meta.label}
                            />
                          </td>
                        )
                      })}
                      <td className="px-4 py-2.5 text-center font-semibold text-[var(--muted-foreground)]">{presentDays(row)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default HrAttendancePage
