import { useEffect, useMemo, useState } from 'react'
import { FiArrowLeft, FiEdit2, FiX } from 'react-icons/fi'
import { useNavigate, useParams } from 'react-router-dom'
import { api, errorMessage } from '../../api/client'
import { useAuth } from '../../context/AuthContext'

type ContractStatus = 'ACTIVE' | 'EXPIRING' | 'EXPIRED' | 'PENDING'
type ContractType = 'EMPLOYMENT' | 'CONTRACTOR'

type ContractDetail = {
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

type DepartmentOption = {
  id: number
  name: string
}

const STATUS_LABELS: Record<ContractStatus, string> = {
  ACTIVE: 'Active',
  EXPIRING: 'Expiring Soon',
  EXPIRED: 'Expired',
  PENDING: 'Pending',
}

const STATUS_STYLES: Record<ContractStatus, string> = {
  ACTIVE: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  EXPIRING: 'border-amber-200 bg-amber-50 text-amber-700',
  EXPIRED: 'border-rose-200 bg-rose-50 text-rose-700',
  PENDING: 'border-slate-200 bg-slate-50 text-slate-700',
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

const inputClass =
  'w-full rounded-xl border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm text-[var(--foreground)] outline-none transition-all focus:border-[#D1353B] focus:ring-2 focus:ring-[#D1353B]/20'
const labelClass = 'mb-1 block text-sm font-medium text-[var(--foreground)]'

type EditForm = {
  type: ContractType
  start_date: string
  end_date: string
  salary_ron: string
  department: string // department id as string, '' = unassigned
}

function EditContractModal({
  contract,
  departments,
  onClose,
  onSaved,
}: {
  contract: ContractDetail
  departments: DepartmentOption[]
  onClose: () => void
  onSaved: (c: ContractDetail) => void
}) {
  const matchedDept = departments.find(d => d.name === contract.department)
  const [form, setForm] = useState<EditForm>({
    type: contract.type,
    start_date: contract.start_date,
    end_date: contract.end_date ?? '',
    salary_ron: contract.salary_ron,
    department: matchedDept ? String(matchedDept.id) : '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const set = (key: keyof EditForm, val: string) => setForm(prev => ({ ...prev, [key]: val }))

  const save = async () => {
    setError('')
    setSaving(true)
    try {
      const data = await api.patch<ContractDetail>(`/api/contracts/${contract.id}/`, {
        type: form.type,
        start_date: form.start_date,
        end_date: form.end_date || null,
        salary_ron: form.salary_ron,
        department: form.department === '' ? null : Number(form.department),
      })
      onSaved(data)
    } catch (e: unknown) {
      setError(errorMessage(e, 'Failed to save contract.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl bg-[var(--card)] text-[var(--card-foreground)] shadow-xl">
        <div className="flex items-center justify-between border-b border-[var(--border)] px-6 py-5">
          <div>
            <h2 className="text-base font-semibold">Edit contract</h2>
            <p className="text-sm text-[var(--muted-foreground)]">{contract.contract_number} · {contract.employee_name}</p>
          </div>
          <button onClick={onClose} className="text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]">
            <FiX className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5 px-6 py-5">
          <div>
            <label className={labelClass}>Contract type</label>
            <select value={form.type} onChange={e => set('type', e.target.value)} className={inputClass}>
              <option value="EMPLOYMENT">Employment</option>
              <option value="CONTRACTOR">Contractor</option>
            </select>
          </div>

          <div>
            <label className={labelClass}>Department</label>
            <select value={form.department} onChange={e => set('department', e.target.value)} className={inputClass}>
              <option value="">Unassigned</option>
              {departments.map(d => (
                <option key={d.id} value={String(d.id)}>{d.name}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Start date</label>
              <input type="date" value={form.start_date} onChange={e => set('start_date', e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>End date</label>
              <input type="date" value={form.end_date} onChange={e => set('end_date', e.target.value)} className={inputClass} />
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">Leave empty for an open-ended contract.</p>
            </div>
          </div>

          <div>
            <label className={labelClass}>Salary (RON)</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.salary_ron}
              onChange={e => set('salary_ron', e.target.value)}
              className={inputClass}
            />
          </div>

          {error && <p className="text-sm text-[var(--destructive)]">{error}</p>}
        </div>

        <div className="flex justify-end gap-3 border-t border-[var(--border)] px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--foreground)] transition-colors hover:bg-[var(--muted)]"
          >
            Cancel
          </button>
          <button
            onClick={() => void save()}
            disabled={saving}
            className="rounded-lg bg-[#D1353B] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ContractDetailPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const { user } = useAuth()
  const [contract, setContract] = useState<ContractDetail | null>(null)
  const [departments, setDepartments] = useState<DepartmentOption[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)

  const canEdit = user?.role === 'CEO' || user?.role === 'HR'

  useEffect(() => {
    const loadContract = async () => {
      if (!id) {
        setError('Missing contract id.')
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        setError('')

        setContract(await api.get<ContractDetail>(`/api/contracts/${id}/`))
      } catch (fetchError) {
        console.error('Failed to load contract detail', fetchError)
        setError('Could not load contract details right now.')
      } finally {
        setLoading(false)
      }
    }

    void loadContract()
  }, [id])

  useEffect(() => {
    if (!canEdit) return
    const loadDepartments = async () => {
      try {
        setDepartments(await api.get<DepartmentOption[]>('/api/departments/'))
      } catch (err) {
        console.error('Failed to load departments', err)
      }
    }
    void loadDepartments()
  }, [canEdit])

  const statusClass = useMemo(() => {
    if (!contract) {
      return STATUS_STYLES.PENDING
    }

    return STATUS_STYLES[contract.status]
  }, [contract])

  if (loading) {
    return <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">Loading contract details...</section>
  }

  if (error || !contract) {
    return (
      <section className="flex flex-col gap-4">
        <button
          type="button"
          onClick={() => void navigate('/hr/contracts')}
          className="inline-flex w-fit items-center gap-2 rounded-full border border-[var(--border)] bg-white px-4 py-2 text-sm font-medium text-[var(--foreground)] shadow-sm transition-colors hover:border-[#D1353B] hover:text-[#D1353B]"
        >
          <FiArrowLeft className="h-4 w-4" />
          Back to Contracts
        </button>

        <div className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
          <h2 className="text-[1.18rem] font-semibold">Contract details unavailable</h2>
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">{error || 'Contract not found.'}</p>
        </div>
      </section>
    )
  }

  return (
    <section className="flex flex-col gap-4">
      <button
        type="button"
        onClick={() => void navigate('/hr/contracts')}
        className="inline-flex w-fit items-center gap-2 rounded-full border border-[var(--border)] bg-white px-4 py-2 text-sm font-medium text-[var(--foreground)] shadow-sm transition-colors hover:border-[#D1353B] hover:text-[#D1353B]"
      >
        <FiArrowLeft className="h-4 w-4" />
        Back to Contracts
      </button>

      <div className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--border)] pb-4">
          <div>
            <p className="text-sm text-[var(--muted-foreground)]">Contract {contract.contract_number}</p>
            <h2 className="mt-1 text-[1.18rem] font-semibold">{contract.employee_name}</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">Employee contract details</p>
          </div>

          <div className="flex items-center gap-3">
            <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${statusClass}`}>
              {STATUS_LABELS[contract.status]}
            </span>
            {canEdit && (
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="inline-flex items-center gap-2 rounded-full bg-[#D1353B] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
              >
                <FiEdit2 className="h-4 w-4" />
                Edit
              </button>
            )}
          </div>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <article className="rounded-xl border border-[var(--border)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">Department</p>
            <p className="mt-1 font-medium">{contract.department ?? 'Unassigned'}</p>
          </article>
          <article className="rounded-xl border border-[var(--border)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">Contract Type</p>
            <p className="mt-1 font-medium">{TYPE_LABELS[contract.type]}</p>
          </article>
          <article className="rounded-xl border border-[var(--border)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">Start Date</p>
            <p className="mt-1 font-medium">{formatDate(contract.start_date)}</p>
          </article>
          <article className="rounded-xl border border-[var(--border)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">End Date</p>
            <p className="mt-1 font-medium">{formatDate(contract.end_date)}</p>
          </article>
          <article className="rounded-xl border border-[var(--border)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">Salary</p>
            <p className="mt-1 font-medium">{Number(contract.salary_ron).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} RON</p>
          </article>
          <article className="rounded-xl border border-[var(--border)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">Status</p>
            <p className="mt-1 font-medium">{STATUS_LABELS[contract.status]}</p>
          </article>
        </div>
      </div>

      {editing && (
        <EditContractModal
          contract={contract}
          departments={departments}
          onClose={() => setEditing(false)}
          onSaved={(updated) => {
            setContract(updated)
            setEditing(false)
          }}
        />
      )}
    </section>
  )
}
