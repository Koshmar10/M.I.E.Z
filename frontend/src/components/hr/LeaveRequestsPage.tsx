import { useEffect, useMemo, useState } from 'react'
import { FiCheck, FiClock, FiX } from 'react-icons/fi'
import { api } from '../../api/client'

type LeaveStatus = 'PENDING' | 'APPROVED' | 'REJECTED'
type LeaveType = 'VACATION' | 'SICK' | 'UNPAID'

type LeaveRequest = {
  id: number
  employee: {
    id: number
    name: string
    username: string
  }
  department: null | {
    id: number
    name: string
    slug: string
  }
  type: LeaveType
  from_date: string
  to_date: string
  days: number
  status: LeaveStatus
  reason: string
  approved_by: null | {
    id: number
    name: string
    username: string
  }
  created_at: string
}

type TabKey = 'ALL' | LeaveStatus

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'ALL', label: 'All' },
  { key: 'PENDING', label: 'Pending' },
  { key: 'APPROVED', label: 'Approved' },
  { key: 'REJECTED', label: 'Rejected' },
]

const TYPE_LABELS: Record<LeaveType, string> = {
  VACATION: 'Annual',
  SICK: 'Medical',
  UNPAID: 'Personal',
}

const STATUS_LABELS: Record<LeaveStatus, string> = {
  PENDING: 'Pending',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
}

const STATUS_STYLES: Record<LeaveStatus, string> = {
  PENDING: 'bg-amber-50 text-amber-700 border-amber-200',
  APPROVED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  REJECTED: 'bg-rose-50 text-rose-700 border-rose-200',
}

const formatDate = (value: string) =>
  new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })

export default function LeaveRequestsPage() {
  const [requests, setRequests] = useState<LeaveRequest[]>([])
  const [activeTab, setActiveTab] = useState<TabKey>('ALL')
  const [loading, setLoading] = useState(true)
  const [updatingId, setUpdatingId] = useState<number | null>(null)

  useEffect(() => {
    const loadRequests = async () => {
      setLoading(true)
      try {
        const data = await api.get<LeaveRequest[]>('/api/leave-requests/')
        setRequests(Array.isArray(data) ? data : [])
      } catch (error) {
        console.error('Failed to load leave requests', error)
        setRequests([])
      } finally {
        setLoading(false)
      }
    }

    void loadRequests()
  }, [])

  const filteredRequests = useMemo(() => {
    if (activeTab === 'ALL') {
      return requests
    }

    return requests.filter(request => request.status === activeTab)
  }, [activeTab, requests])

  const counts = useMemo(() => {
    return {
      ALL: requests.length,
      PENDING: requests.filter(request => request.status === 'PENDING').length,
      APPROVED: requests.filter(request => request.status === 'APPROVED').length,
      REJECTED: requests.filter(request => request.status === 'REJECTED').length,
    }
  }, [requests])

  const updateRequestStatus = async (id: number, nextStatus: 'approve' | 'reject') => {
    if (updatingId === id) {
      return
    }

    setUpdatingId(id)
    try {
      const payload = await api.patch<{ id: number; status: LeaveStatus }>(`/api/leave-requests/${id}/${nextStatus}/`, {})

      setRequests(current =>
        current.map(request =>
          request.id === payload.id
            ? {
                ...request,
                status: payload.status,
                approved_by: payload.status === 'PENDING' ? request.approved_by : request.approved_by,
              }
            : request,
        ),
      )
    } catch (error) {
      console.error(`Failed to ${nextStatus} leave request`, error)
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-[1.18rem] font-semibold">Leave Requests</h2>
          <p className="text-[0.92rem] text-[var(--muted-foreground)]">
            Review all employee leave requests and approve or reject them inline.
          </p>
        </div>

        <div className="rounded-full border border-[var(--border)] bg-white px-4 py-2 text-sm font-medium text-[var(--foreground)] shadow-sm">
          Total requests: {counts.ALL}
        </div>
      </header>

      <div className="flex flex-wrap gap-2">
        {TABS.map(tab => {
          const isActive = activeTab === tab.key

          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'border-[#D1353B] bg-[#D1353B] text-white'
                  : 'border-[var(--border)] bg-white text-[var(--foreground)] hover:border-[#D1353B] hover:text-[#D1353B]'
              }`}
            >
              {tab.label} <span className="ml-1.5 opacity-70">({counts[tab.key]})</span>
            </button>
          )
        })}
      </div>

      <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-[var(--border)] px-5 py-4">
          <FiClock className="h-4 w-4 text-[var(--muted-foreground)]" />
          <span className="text-sm font-semibold">Requests</span>
        </div>

        {loading ? (
          <div className="py-16 text-center text-sm text-[var(--muted-foreground)]">Loading…</div>
        ) : filteredRequests.length === 0 ? (
          <div className="py-16 text-center text-sm text-[var(--muted-foreground)]">No leave requests found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-[rgba(0,0,0,0.015)]">
                <tr className="border-b border-[var(--border)]">
                  {['Employee', 'Department', 'Type', 'From', 'To', 'Days', 'Status', 'Actions'].map(column => (
                    <th key={column} className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredRequests.map(request => {
                  const canAct = request.status === 'PENDING'

                  return (
                    <tr key={request.id} className="border-b border-[var(--border)] last:border-0 hover:bg-gray-50 transition-colors">
                      <td className="px-5 py-4">
                        <div className="flex flex-col gap-0.5">
                          <span className="font-medium text-[var(--foreground)]">{request.employee.name}</span>
                          <span className="text-xs text-[var(--muted-foreground)]">@{request.employee.username}</span>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-[var(--muted-foreground)]">{request.department?.name ?? '—'}</td>
                      <td className="px-5 py-4 text-[var(--muted-foreground)]">{TYPE_LABELS[request.type]}</td>
                      <td className="px-5 py-4 text-[var(--muted-foreground)]">{formatDate(request.from_date)}</td>
                      <td className="px-5 py-4 text-[var(--muted-foreground)]">{formatDate(request.to_date)}</td>
                      <td className="px-5 py-4 text-[var(--muted-foreground)]">{request.days}</td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${STATUS_STYLES[request.status]}`}>
                          {STATUS_LABELS[request.status]}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        {canAct ? (
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              disabled={updatingId === request.id}
                              onClick={() => void updateRequestStatus(request.id, 'approve')}
                              className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 transition-colors hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              <FiCheck className="h-3.5 w-3.5" />
                              Approve
                            </button>
                            <button
                              type="button"
                              disabled={updatingId === request.id}
                              onClick={() => void updateRequestStatus(request.id, 'reject')}
                              className="inline-flex items-center gap-1.5 rounded-full border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 transition-colors hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              <FiX className="h-3.5 w-3.5" />
                              Reject
                            </button>
                          </div>
                        ) : (
                          <span className="text-xs text-[var(--muted-foreground)]">
                            {request.approved_by ? `Updated by ${request.approved_by.name}` : 'No actions available'}
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}