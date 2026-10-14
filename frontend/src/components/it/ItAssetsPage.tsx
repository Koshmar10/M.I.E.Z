import { useEffect, useMemo, useState } from 'react'
import { FiPlus, FiRefreshCw, FiSearch, FiX } from 'react-icons/fi'
import { api, errorMessage, type Page } from '../../api/client'

type AssetCategory = 'LAPTOP' | 'MONITOR' | 'PHONE' | 'PERIPHERAL' | 'OTHER'
type AssetStatus = 'AVAILABLE' | 'ASSIGNED' | 'MAINTENANCE' | 'RETIRED'

type AssetRow = {
  id: number
  name: string
  serial_number: string
  category: AssetCategory
  assigned_to: number | null
  assigned_to_username: string | null
  assigned_to_name: string | null
  status: AssetStatus
  notes: string
  created_at: string
}

type EmployeeOption = {
  id: number
  username: string
  first_name: string
  last_name: string
  role: string
}

type AssetFormState = {
  name: string
  serial_number: string
  category: AssetCategory
  assigned_to: string
  status: AssetStatus
  notes: string
}


const categoryLabels: Record<AssetCategory, string> = {
  LAPTOP: 'Laptop',
  MONITOR: 'Monitor',
  PHONE: 'Phone',
  PERIPHERAL: 'Peripheral',
  OTHER: 'Other',
}

const statusLabels: Record<AssetStatus, string> = {
  AVAILABLE: 'Available',
  ASSIGNED: 'Assigned',
  MAINTENANCE: 'Maintenance',
  RETIRED: 'Retired',
}

const categoryBadgeClass: Record<AssetCategory, string> = {
  LAPTOP: 'bg-slate-100 text-slate-700 border border-slate-200',
  MONITOR: 'bg-cyan-50 text-cyan-700 border border-cyan-200',
  PHONE: 'bg-violet-50 text-violet-700 border border-violet-200',
  PERIPHERAL: 'bg-amber-50 text-amber-700 border border-amber-200',
  OTHER: 'bg-[var(--input-background)] text-[var(--muted-foreground)] border border-[var(--border)]',
}

const statusBadgeClass: Record<AssetStatus, string> = {
  AVAILABLE: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  ASSIGNED: 'bg-blue-50 text-blue-700 border border-blue-200',
  MAINTENANCE: 'bg-amber-50 text-amber-700 border border-amber-200',
  RETIRED: 'bg-[var(--input-background)] text-[var(--muted-foreground)] border border-[var(--border)]',
}

const emptyForm: AssetFormState = {
  name: '',
  serial_number: '',
  category: 'LAPTOP',
  assigned_to: '',
  status: 'AVAILABLE',
  notes: '',
}

const formatDate = (value: string) => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

const assetLabel = (asset: AssetRow) => asset.assigned_to_name || asset.assigned_to_username || 'Unassigned'

function AssetForm({
  value,
  employees,
  onChange,
}: {
  value: AssetFormState
  employees: EmployeeOption[]
  onChange: (next: AssetFormState) => void
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <label className="space-y-1">
        <span className="block text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Name</span>
        <input
          value={value.name}
          onChange={(event) => onChange({ ...value, name: event.target.value })}
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm"
          placeholder="Laptop 01"
        />
      </label>

      <label className="space-y-1">
        <span className="block text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Serial number</span>
        <input
          value={value.serial_number}
          onChange={(event) => onChange({ ...value, serial_number: event.target.value })}
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm"
          placeholder="SN-001"
        />
      </label>

      <label className="space-y-1">
        <span className="block text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Category</span>
        <select
          value={value.category}
          onChange={(event) => onChange({ ...value, category: event.target.value as AssetCategory })}
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm"
        >
          {Object.entries(categoryLabels).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </label>

      <label className="space-y-1">
        <span className="block text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Status</span>
        <select
          value={value.status}
          onChange={(event) => onChange({ ...value, status: event.target.value as AssetStatus })}
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm"
        >
          {Object.entries(statusLabels).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </label>

      <label className="space-y-1 md:col-span-2">
        <span className="block text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Assigned to</span>
        <select
          value={value.assigned_to}
          onChange={(event) => onChange({ ...value, assigned_to: event.target.value })}
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm"
        >
          <option value="">Unassigned</option>
          {employees.map((employee) => {
            const label = `${employee.first_name} ${employee.last_name}`.trim() || employee.username
            return (
              <option key={employee.id} value={employee.id}>
                {label} ({employee.username})
              </option>
            )
          })}
        </select>
      </label>

      <label className="space-y-1 md:col-span-2">
        <span className="block text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Notes</span>
        <textarea
          rows={4}
          value={value.notes}
          onChange={(event) => onChange({ ...value, notes: event.target.value })}
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm"
          placeholder="Asset condition, location, handover details..."
        />
      </label>
    </div>
  )
}

export default function ItAssetsPage() {
  const [assets, setAssets] = useState<AssetRow[]>([])
  const [employees, setEmployees] = useState<EmployeeOption[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [employeeError, setEmployeeError] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<'ALL' | AssetCategory>('ALL')
  const [statusFilter, setStatusFilter] = useState<'ALL' | AssetStatus>('ALL')
  const [search, setSearch] = useState('')
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [selectedAsset, setSelectedAsset] = useState<AssetRow | null>(null)
  const [createForm, setCreateForm] = useState<AssetFormState>(emptyForm)
  const [editForm, setEditForm] = useState<AssetFormState>(emptyForm)
  const [savingCreate, setSavingCreate] = useState(false)
  const [savingEdit, setSavingEdit] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const loadAssets = async () => {
    try {
      setLoading(true)
      setError('')

      setAssets(await api.get<AssetRow[]>('/api/it/assets/'))
    } catch (err) {
      console.error('Failed to load assets:', err)
      setError('Could not load assets right now.')
    } finally {
      setLoading(false)
    }
  }

  const loadEmployees = async () => {
    try {
      setEmployeeError('')
      const data = await api.get<Page<EmployeeOption>>('/api/employees/', { page_size: 100 })
      setEmployees(data.results)
    } catch (err) {
      console.error('Failed to load employees:', err)
      setEmployeeError('Could not load employees for assignment.')
    }
  }

  useEffect(() => {
    void loadAssets()
    void loadEmployees()
  }, [])

  const filteredAssets = useMemo(() => {
    const query = search.trim().toLowerCase()
    return assets.filter((asset) => {
      const matchesCategory = categoryFilter === 'ALL' || asset.category === categoryFilter
      const matchesStatus = statusFilter === 'ALL' || asset.status === statusFilter
      const matchesSearch = !query || [asset.name, asset.serial_number, asset.assigned_to_name, asset.assigned_to_username, asset.notes]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query))

      return matchesCategory && matchesStatus && matchesSearch
    })
  }, [assets, categoryFilter, search, statusFilter])

  const openCreate = () => {
    setCreateForm(emptyForm)
    setIsCreateOpen(true)
  }

  const closeCreate = () => {
    setIsCreateOpen(false)
    setCreateForm(emptyForm)
  }

  const openAsset = (asset: AssetRow) => {
    setSelectedAsset(asset)
    setDeleteError('')
    setEditForm({
      name: asset.name,
      serial_number: asset.serial_number,
      category: asset.category,
      assigned_to: asset.assigned_to ? String(asset.assigned_to) : '',
      status: asset.status,
      notes: asset.notes,
    })
  }

  const closeAsset = () => {
    setSelectedAsset(null)
    setDeleteError('')
  }

  const createAsset = async () => {
    try {
      setSavingCreate(true)

      await api.post('/api/it/assets/', {
        ...createForm,
        assigned_to: createForm.assigned_to ? Number(createForm.assigned_to) : null,
      })

      await loadAssets()
      closeCreate()
    } catch (err) {
      console.error('Failed to create asset:', err)
      setError(errorMessage(err, 'Could not create asset right now.'))
    } finally {
      setSavingCreate(false)
    }
  }

  const saveAsset = async () => {
    if (!selectedAsset) return

    try {
      setSavingEdit(true)
      setDeleteError('')

      const updated = await api.patch<AssetRow>(`/api/it/assets/${selectedAsset.id}/`, {
        ...editForm,
        assigned_to: editForm.assigned_to ? Number(editForm.assigned_to) : null,
      })
      setAssets((current) => current.map((asset) => (asset.id === updated.id ? updated : asset)))
      setSelectedAsset(updated)
      setEditForm({
        name: updated.name,
        serial_number: updated.serial_number,
        category: updated.category,
        assigned_to: updated.assigned_to ? String(updated.assigned_to) : '',
        status: updated.status,
        notes: updated.notes,
      })
    } catch (err) {
      console.error('Failed to update asset:', err)
      setDeleteError(errorMessage(err, 'Could not save asset changes.'))
    } finally {
      setSavingEdit(false)
    }
  }

  const deleteAsset = async () => {
    if (!selectedAsset) return

    if (!window.confirm(`Delete ${selectedAsset.name}?`)) {
      return
    }

    try {
      setSavingEdit(true)
      await api.delete(`/api/it/assets/${selectedAsset.id}/`)
      setAssets((current) => current.filter((asset) => asset.id !== selectedAsset.id))
      closeAsset()
    } catch (err) {
      console.error('Failed to delete asset:', err)
      setDeleteError('Could not delete this asset.')
    } finally {
      setSavingEdit(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-[1.15rem] font-semibold tracking-tight">Assets</h2>
            <p className="text-sm text-[var(--muted-foreground)] mt-1">Track laptops, monitors, phones, and other physical assets.</p>
          </div>

          <button
            type="button"
            onClick={openCreate}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-[var(--primary-foreground)] transition-opacity hover:opacity-90"
          >
            <FiPlus />
            Add Asset
          </button>
        </div>
      </section>

      <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5 space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 w-full lg:max-w-3xl">
            <label className="space-y-1 md:col-span-3 lg:col-span-1">
              <span className="block text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Search</span>
              <div className="relative">
                <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] pl-9 pr-3 py-2 text-sm"
                  placeholder="Name, serial, assignee, notes"
                />
              </div>
            </label>

            <label className="space-y-1">
              <span className="block text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Category</span>
              <select
                value={categoryFilter}
                onChange={(event) => setCategoryFilter(event.target.value as 'ALL' | AssetCategory)}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm"
              >
                <option value="ALL">All categories</option>
                {Object.entries(categoryLabels).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1">
              <span className="block text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Status</span>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as 'ALL' | AssetStatus)}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm"
              >
                <option value="ALL">All statuses</option>
                {Object.entries(statusLabels).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <button
            type="button"
            onClick={() => void loadAssets()}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2 text-sm font-medium transition-colors hover:bg-[var(--input-background)]"
          >
            <FiRefreshCw />
            Refresh
          </button>
        </div>

        {employeeError && <p className="text-sm text-[var(--destructive)]">{employeeError}</p>}
        {error && <p className="text-sm text-[var(--destructive)]">{error}</p>}

        {loading ? (
          <p className="text-sm text-[var(--muted-foreground)]">Loading assets...</p>
        ) : (
          <div className="overflow-x-auto border border-[var(--border)] rounded-xl">
            <table className="min-w-full bg-[var(--card)] text-sm">
              <thead className="bg-[var(--input-background)]">
                <tr>
                  {['Name', 'Serial', 'Category', 'Assigned To', 'Status', 'Created'].map((heading) => (
                    <th key={heading} className="px-4 py-2.5 text-left text-[11px] uppercase tracking-[0.14em] font-semibold text-[var(--muted-foreground)]">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredAssets.map((asset) => (
                  <tr
                    key={asset.id}
                    onClick={() => openAsset(asset)}
                    className="border-t border-[var(--border)] hover:bg-[var(--input-background)] cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-2.5 font-medium">{asset.name}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-[var(--muted-foreground)]">{asset.serial_number}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${categoryBadgeClass[asset.category]}`}>
                        {categoryLabels[asset.category]}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 whitespace-nowrap">{assetLabel(asset)}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass[asset.status]}`}>
                        {statusLabels[asset.status]}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-[var(--muted-foreground)]">{formatDate(asset.created_at)}</td>
                  </tr>
                ))}
                {filteredAssets.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-sm text-[var(--muted-foreground)]">
                      No assets match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {isCreateOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 p-4 flex items-center justify-center" onClick={(event) => event.target === event.currentTarget && closeCreate()}>
          <div className="w-full max-w-3xl rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
              <h3 className="text-[1rem] font-semibold tracking-tight">Add Asset</h3>
              <button type="button" onClick={closeCreate} className="rounded-lg p-2 text-[var(--muted-foreground)] hover:bg-[var(--input-background)] hover:text-[var(--foreground)] transition-colors">
                <FiX />
              </button>
            </div>

            <div className="p-5 space-y-5">
              <AssetForm value={createForm} employees={employees} onChange={setCreateForm} />

              <div className="flex justify-end gap-3">
                <button type="button" onClick={closeCreate} className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium hover:bg-[var(--input-background)] transition-colors">
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => void createAsset()}
                  disabled={savingCreate}
                  className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {savingCreate ? 'Saving...' : 'Create Asset'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedAsset && (
        <div className="fixed inset-0 z-50 bg-black/40" onClick={(event) => event.target === event.currentTarget && closeAsset()}>
          <div className="absolute right-0 top-0 h-full w-full max-w-2xl bg-[var(--card)] border-l border-[var(--border)] shadow-2xl flex flex-col">
            <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
              <div>
                <h3 className="text-[1rem] font-semibold tracking-tight">Asset Details</h3>
                <p className="text-sm text-[var(--muted-foreground)]">{selectedAsset.name}</p>
              </div>
              <button type="button" onClick={closeAsset} className="rounded-lg p-2 text-[var(--muted-foreground)] hover:bg-[var(--input-background)] hover:text-[var(--foreground)] transition-colors">
                <FiX />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Created</p>
                  <p className="mt-1">{formatDate(selectedAsset.created_at)}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">Assigned to</p>
                  <p className="mt-1">{assetLabel(selectedAsset)}</p>
                </div>
              </div>

              {deleteError && <p className="text-sm text-[var(--destructive)]">{deleteError}</p>}

              <AssetForm value={editForm} employees={employees} onChange={setEditForm} />
            </div>

            <div className="border-t border-[var(--border)] px-5 py-4 flex flex-col-reverse sm:flex-row sm:items-center justify-end gap-3">
              <button type="button" onClick={() => void deleteAsset()} disabled={savingEdit} className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700 hover:bg-rose-100 transition-colors disabled:cursor-not-allowed disabled:opacity-60">
                Delete
              </button>
              <button type="button" onClick={closeAsset} className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium hover:bg-[var(--input-background)] transition-colors">
                Close
              </button>
              <button type="button" onClick={() => void saveAsset()} disabled={savingEdit} className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60">
                {savingEdit ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}