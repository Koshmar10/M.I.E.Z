import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { FiClock } from 'react-icons/fi'
import { api } from '../../api/client'

type UpcomingEventType = 'CONTRACT_EXPIRY' | 'ONBOARDING' | 'PAYROLL_PROCESSING'

type UpcomingEvent = {
  id: string
  type: UpcomingEventType
  date: string
  days_until: number
  is_warning: boolean
  title: string
  description: string
  dot_color: 'red' | 'blue'
  link: string | null
}

type UpcomingEventsResponse = {
  events: UpcomingEvent[]
}

const TYPE_LABELS: Record<UpcomingEventType, string> = {
  CONTRACT_EXPIRY: 'Contract expiry',
  ONBOARDING: 'New employee onboarding',
  PAYROLL_PROCESSING: 'Payroll processing',
}

const DOT_STYLES: Record<UpcomingEvent['dot_color'], string> = {
  red: 'bg-rose-500',
  blue: 'bg-blue-500',
}

const formatDate = (value: string) =>
  new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })

const formatDistance = (daysUntil: number) => {
  if (daysUntil <= 0) return 'Today'
  if (daysUntil === 1) return 'Tomorrow'
  return `In ${daysUntil} days`
}

export default function UpcomingEventsWidget() {
  const [events, setEvents] = useState<UpcomingEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadEvents = async () => {
      setLoading(true)
      try {
        const data = await api.get<UpcomingEventsResponse>('/api/hr/upcoming-events/', { days: 30 })
        setEvents(Array.isArray(data?.events) ? data.events : [])
      } catch (error) {
        console.error('Failed to load upcoming events', error)
        setEvents([])
      } finally {
        setLoading(false)
      }
    }

    loadEvents()
  }, [])

  const visibleEvents = useMemo(() => events.slice(0, 8), [events])

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-[1rem] font-semibold">Upcoming HR events</h3>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            Contract expiries, new onboarding and payroll deadlines.
          </p>
        </div>
        <div className="rounded-full border border-[var(--border)] px-3 py-1 text-xs font-medium text-[var(--muted-foreground)]">
          Next 30 days
        </div>
      </div>

      {loading ? (
        <p className="mt-4 text-sm text-[var(--muted-foreground)]">Loading upcoming events…</p>
      ) : visibleEvents.length === 0 ? (
        <p className="mt-4 text-sm text-[var(--muted-foreground)]">No upcoming HR events found.</p>
      ) : (
        <ul className="mt-4 space-y-2.5">
          {visibleEvents.map(event => {
            const content = (
              <>
                <div className="flex items-start gap-3">
                  <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${DOT_STYLES[event.dot_color]}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-[var(--foreground)]">{event.title}</span>
                      {event.is_warning && (
                        <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                          Warning
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                      {TYPE_LABELS[event.type]} · {formatDate(event.date)} · {formatDistance(event.days_until)}
                    </p>
                    <p className="mt-1 text-xs text-[var(--muted-foreground)]">{event.description}</p>
                  </div>
                  <span className="text-xs text-[var(--muted-foreground)]">{event.link ? 'Open' : ''}</span>
                </div>
              </>
            )

            const rowClasses = `block rounded-xl border px-4 py-3 transition-colors ${
              event.is_warning
                ? 'border-amber-200 bg-amber-50/70 hover:bg-amber-50'
                : 'border-[var(--border)] bg-[var(--card)] hover:bg-gray-50'
            }`

            if (event.link) {
              return (
                <li key={event.id}>
                  <Link to={event.link} className={rowClasses}>
                    {content}
                  </Link>
                </li>
              )
            }

            return (
              <li key={event.id}>
                <div className={rowClasses}>{content}</div>
              </li>
            )
          })}
        </ul>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-[var(--muted-foreground)]">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-rose-500" />
          Contract expiry
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-blue-500" />
          Onboarding / payroll
        </span>
        <span className="inline-flex items-center gap-1.5">
          <FiClock className="h-3.5 w-3.5" />
          Warning accent for events within 7 days
        </span>
      </div>
    </section>
  )
}