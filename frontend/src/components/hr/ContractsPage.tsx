import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FiClock, FiUsers } from 'react-icons/fi'
import { api } from '../../api/client'

type ContractStatus = 'ACTIVE' | 'EXPIRING' | 'EXPIRED'
type ContractType = 'EMPLOYMENT' | 'CONTRACTOR'
type FilterTab = 'ALL' | ContractStatus

type ContractRow = {
  id: number
  contract_number: string
  employee: number
  employee_name: string
  department: string | null
  type: ContractType
  start_date: string
  end_date: string | null
  salary_ron: string
  status: ContractStatus
}

type ContractsResponse = {
  contracts: ContractRow[]
}

const FILTER_TABS: Array<{ key: FilterTab; label: string }> = [
  { key: 'ALL', label: 'All' },
  { key: 'ACTIVE', label: 'Active' },
  { key: 'EXPIRING', label: 'Expiring Soon' },
  { key: 'EXPIRED', label: 'Expired' },
]

const STATUS_LABELS: Record<ContractStatus, string> = {
  ACTIVE: 'Active',
  EXPIRING: 'Expiring Soon',
  EXPIRED: 'Expired',
}

const STATUS_STYLES: Record<ContractStatus, string> = {
  ACTIVE: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  EXPIRING: 'border-amber-200 bg-amber-50 text-amber-700',
  EXPIRED: 'border-rose-200 bg-rose-50 text-rose-700',
}

const TYPE_LABELS: Record<ContractType, string> = {
  EMPLOYMENT: 'Employment',
  CONTRACTOR: 'Contractor',
}

const formatDate = (value: string | null) => {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

const getInitials = (name: string) => {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'U'
  const first = parts[0]?.[0] ?? ''
  const second = parts[1]?.[0] ?? ''
  return `${first}${second}`.toUpperCase() || 'U'
}

const getDisplayContractId = (id: number) => `CON-${String(id).padStart(3, '0')}`

export default function ContractsPage() {
  const navigate = useNavigate()
  const [contracts, setContracts] = useState<ContractRow[]>([])
  const [activeTab, setActiveTab] = useState<FilterTab>('ALL')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadContracts = async () => {
      setLoading(true)
      try {
        const data = await api.get<ContractsResponse>('/api/contracts/')
        setContracts(Array.isArray(data?.contracts) ? data.contracts : [])
      } catch (error) {
        console.error('Failed to load contracts', error)
        setContracts([])
      } finally {
        setLoading(false)
      }
    }

    loadContracts()
  }, [])

  const filteredContracts = useMemo(() => {
    if (activeTab === 'ALL') return contracts
    return contracts.filter(contract => contract.status === activeTab)
  }, [activeTab, contracts])

  const counts = useMemo(() => ({
    ALL: contracts.length,
    ACTIVE: contracts.filter(contract => contract.status === 'ACTIVE').length,
    EXPIRING: contracts.filter(contract => contract.status === 'EXPIRING').length,
    EXPIRED: contracts.filter(contract => contract.status === 'EXPIRED').length,
  }), [contracts])

  const openContract = (id: number) => {
    navigate(`/hr/contracts/${id}`)
  }

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-[1.18rem] font-semibold">Contracts</h2>
          <p className="text-[0.92rem] text-[var(--muted-foreground)]">
            Track employee contracts, renewal windows and expiry risk in one view.
          </p>
        </div>

        <div className="rounded-full border border-[var(--border)] bg-white px-4 py-2 text-sm font-medium text-[var(--foreground)] shadow-sm">
          Total contracts: {counts.ALL}
        </div>
      </header>

      <div className="flex flex-wrap gap-2">
        {FILTER_TABS.map(tab => {
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
          <span className="text-sm font-semibold">Employee contracts</span>
        </div>

        {loading ? (
          <div className="py-16 text-center text-sm text-[var(--muted-foreground)]">Loading…</div>
        ) : filteredContracts.length === 0 ? (
          <div className="py-16 text-center text-sm text-[var(--muted-foreground)]">No contracts found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-[rgba(0,0,0,0.015)]">
                <tr className="border-b border-[var(--border)]">
                  {['Contract ID', 'Employee', 'Department', 'Type', 'Start', 'End', 'Status', 'Renewal Due'].map(column => (
                    <th key={column} className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredContracts.map(contract => {
                  const displayId = getDisplayContractId(contract.id)
                  const renewalDueLabel =
                    contract.status === 'EXPIRED'
                      ? 'Overdue'
                      : contract.status === 'EXPIRING' && contract.end_date
                        ? `Due ${formatDate(contract.end_date)}`
                        : contract.end_date
                          ? formatDate(contract.end_date)
                          : '—'

                  const renewalDueClass =
                    contract.status === 'EXPIRED'
                      ? 'text-rose-600 font-semibold'
                      : contract.status === 'EXPIRING'
                        ? 'text-amber-600 font-semibold'
                        : 'text-[var(--muted-foreground)]'

                  return (
                    <tr
                      key={contract.id}
                      onClick={() => openContract(contract.id)}
                      onKeyDown={event => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          openContract(contract.id)
                        }
                      }}
                      tabIndex={0}
                      role="link"
                      className="cursor-pointer border-b border-[var(--border)] last:border-0 transition-colors hover:bg-gray-50 focus:bg-gray-50 focus:outline-none"
                    >
                      <td className="px-5 py-4 font-semibold text-[var(--foreground)]">
                        <div className="flex flex-col gap-0.5">
                          <span>{displayId}</span>
                          <span className="text-xs font-normal text-[var(--muted-foreground)]">Ref. {contract.contract_number}</span>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#D1353B] text-xs font-semibold text-white shadow-sm">
                            {getInitials(contract.employee_name)}
                          </div>
                          <span className="font-medium text-[var(--foreground)]">{contract.employee_name}</span>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-[var(--muted-foreground)]">{contract.department ?? '—'}</td>
                      <td className="px-5 py-4 text-[var(--muted-foreground)]">{TYPE_LABELS[contract.type]}</td>
                      <td className="px-5 py-4 text-[var(--muted-foreground)]">{formatDate(contract.start_date)}</td>
                      <td className="px-5 py-4 text-[var(--muted-foreground)]">{formatDate(contract.end_date)}</td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${STATUS_STYLES[contract.status]}`}>
                          {STATUS_LABELS[contract.status]}
                        </span>
                      </td>
                      <td className={`px-5 py-4 ${renewalDueClass}`}>{renewalDueLabel}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-[var(--border)] bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <FiUsers className="h-4 w-4" />
            Active contracts
          </div>
          <div className="mt-2 text-2xl font-semibold text-emerald-600">{counts.ACTIVE}</div>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <FiClock className="h-4 w-4" />
            Expiring soon
          </div>
          <div className="mt-2 text-2xl font-semibold text-amber-600">{counts.EXPIRING}</div>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <FiClock className="h-4 w-4" />
            Overdue renewals
          </div>
          <div className="mt-2 text-2xl font-semibold text-rose-600">{counts.EXPIRED}</div>
        </div>
      </div>
    </section>
  )
}