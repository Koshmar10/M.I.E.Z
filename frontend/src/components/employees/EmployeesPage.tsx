import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, fieldErrors } from '../../api/client'
import { useAuth } from '../../context/AuthContext'

type Department = {
  id: number
  name: string
  slug: string
}

type Employee = {
  id: number
  username: string
  first_name: string
  last_name: string
  role: string
  employment_type: 'FULL_TIME' | 'PART_TIME' | 'CONTRACTOR'
  is_active: boolean
  department: null | {
    id: number
    name: string
    slug: string
  }
}

type EmployeeFormData = {
  first_name: string
  last_name: string
  email: string
  phone: string
  role: 'HR' | 'SALES' | 'IT' | 'INVENTORY'
  department: string
  position: string
  employment_type: 'FULL_TIME' | 'PART_TIME' | 'CONTRACTOR'
  start_date: string
  salary_ron: string
  address: string
  is_active: boolean
}

type PaginatedEmployees = {
  count: number
  next: string | null
  previous: string | null
  results: Employee[]
}

const initialFormData: EmployeeFormData = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '+40',
  role: 'SALES',
  department: '',
  position: '',
  employment_type: 'FULL_TIME',
  start_date: '',
  salary_ron: '',
  address: '',
  is_active: true,
}

const getDisplayName = (employee: Employee) => {
  const fullName = `${employee.first_name} ${employee.last_name}`.trim()
  return fullName || employee.username
}

const getInitials = (employee: Employee) => {
  const fullName = getDisplayName(employee)
  const parts = fullName.split(/\s+/).filter(Boolean)
  if (parts.length === 0) {
    return 'U'
  }

  const first = parts[0]?.[0] ?? ''
  const second = parts[1]?.[0] ?? ''
  return `${first}${second}`.toUpperCase() || 'U'
}

const formatRole = (role: string) => {
  if (role === 'SALES') return 'Sales'
  if (role === 'INVENTORY') return 'Inventory'
  return role
}

const formatContract = (employmentType: Employee['employment_type']) => {
  if (employmentType === 'FULL_TIME') return 'Full-time'
  if (employmentType === 'PART_TIME') return 'Part-time'
  return 'Contract'
}

const EmployeesPage = () => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [employees, setEmployees] = useState<Employee[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)

  const [isFormOpen, setIsFormOpen] = useState(false)
  const [formData, setFormData] = useState<EmployeeFormData>(initialFormData)
  const [formErrors, setFormErrors] = useState<Record<string, string[]>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  const canCreateEmployees = user?.role === 'CEO' || user?.role === 'HR'
  const detailRouteBase = location.pathname.startsWith('/employees') ? '/employees' : '/hr/employees'

  const fetchEmployees = async () => {
    setIsLoading(true)
    try {
      const params = new URLSearchParams({ page: String(page) })

      if (departmentFilter) {
        params.set('department', departmentFilter)
      }
      if (debouncedSearch) {
        params.set('search', debouncedSearch)
      }

      const data = await api.get<PaginatedEmployees>(`/api/employees/?${params.toString()}`)
      setEmployees(data.results)
      setTotal(data.count)
    } catch (error) {
      console.error('Failed to load employees', error)
      setEmployees([])
      setTotal(0)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedSearch(searchTerm.trim())
      setPage(1)
    }, 250)

    return () => window.clearTimeout(timeout)
  }, [searchTerm])

  useEffect(() => {
    fetchEmployees()
  }, [page, departmentFilter, debouncedSearch])

  useEffect(() => {
    const fetchDepartments = async () => {
      try {
        setDepartments(await api.get<Department[]>('/api/departments/'))
      } catch (error) {
        console.error('Failed to load departments', error)
        setDepartments([])
      }
    }

    fetchDepartments()
  }, [])

  useEffect(() => {
    setPage(1)
  }, [departmentFilter])

  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(total / 10))
  }, [total])

  const handleFormChange = (field: keyof EmployeeFormData, value: string | boolean) => {
    setFormData(current => ({
      ...current,
      [field]: value,
    }))
  }

  const handleCreateEmployee = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIsSubmitting(true)
    setFormErrors({})

    try {
      const payload = {
        ...formData,
        department: Number(formData.department),
        salary_ron: parseFloat(formData.salary_ron),
      }

      await api.post('/api/employees/', payload)

      setFormData(initialFormData)
      setIsFormOpen(false)
      setPage(1)
      await fetchEmployees()
    } catch (error) {
      console.error('Failed to create employee', error)
      setFormErrors(fieldErrors(error) ?? { non_field_errors: ['Could not create employee. Please try again.'] })
    } finally {
      setIsSubmitting(false)
    }
  }

  const renderError = (field: keyof EmployeeFormData | 'non_field_errors') => {
    const errors = formErrors[field]
    if (!errors || errors.length === 0) {
      return null
    }
    return <p className="text-[0.82rem] text-red-600">{errors[0]}</p>
  }

  return (
    <section className="flex flex-col gap-4">
      <header className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex flex-col gap-1">
          <h2 className="text-[1.18rem] font-semibold">Employees</h2>
          <p className="text-[0.92rem] text-[var(--muted-foreground)]">
            Search and review employees by role, department, contract and status.
          </p>
        </div>

        {canCreateEmployees && (
          <button
            type="button"
            className="min-h-[40px] rounded-[10px] bg-[var(--primary)] text-[var(--primary-foreground)] px-[0.95rem] font-bold cursor-pointer inline-flex items-center justify-center border-none"
            onClick={() => setIsFormOpen(current => !current)}
          >
            {isFormOpen ? 'Close form' : 'Add employee'}
          </button>
        )}
      </header>

      {canCreateEmployees && isFormOpen && (
        <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-4">
          <h3 className="text-[1rem] font-semibold mb-3">Create employee profile</h3>

          <form className="grid grid-cols-1 md:grid-cols-2 gap-3" onSubmit={handleCreateEmployee}>
            <input className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]" value={formData.first_name} onChange={event => handleFormChange('first_name', event.target.value)} placeholder="First name" required />
            <input className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]" value={formData.last_name} onChange={event => handleFormChange('last_name', event.target.value)} placeholder="Last name" required />
            <input className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]" type="email" value={formData.email} onChange={event => handleFormChange('email', event.target.value)} placeholder="Email" required />
            <input className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]" value={formData.phone} onChange={event => handleFormChange('phone', event.target.value)} placeholder="Phone (+40...)" required />

            <select className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]" value={formData.role} onChange={event => handleFormChange('role', event.target.value as EmployeeFormData['role'])}>
              <option value="HR">HR</option>
              <option value="SALES">Sales</option>
              <option value="IT">IT</option>
              <option value="INVENTORY">Inventory</option>
            </select>

            <select className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]" value={formData.department} onChange={event => handleFormChange('department', event.target.value)} required>
              <option value="">Select department</option>
              {departments.map(department => (
                <option key={department.id} value={String(department.id)}>{department.name}</option>
              ))}
            </select>

            <input className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]" value={formData.position} onChange={event => handleFormChange('position', event.target.value)} placeholder="Position" required />
            <select className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]" value={formData.employment_type} onChange={event => handleFormChange('employment_type', event.target.value as EmployeeFormData['employment_type'])} required>
              <option value="FULL_TIME">Full-time</option>
              <option value="PART_TIME">Part-time</option>
              <option value="CONTRACTOR">Contractor</option>
            </select>

            <input className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]" type="date" value={formData.start_date} onChange={event => handleFormChange('start_date', event.target.value)} required />
            <input className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]" type="number" step="0.01" value={formData.salary_ron} onChange={event => handleFormChange('salary_ron', event.target.value)} placeholder="Salary (RON)" required />

            <input className="md:col-span-2 min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]" value={formData.address} onChange={event => handleFormChange('address', event.target.value)} placeholder="Address" required />

            <label className="md:col-span-2 inline-flex items-center gap-[0.45rem] text-[0.92rem] text-[var(--muted-foreground)]">
              <input className="w-4 h-4" type="checkbox" checked={formData.is_active} onChange={event => handleFormChange('is_active', event.target.checked)} />
              Active employee
            </label>

            <div className="md:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-2">
              {renderError('first_name')}
              {renderError('last_name')}
              {renderError('email')}
              {renderError('phone')}
              {renderError('role')}
              {renderError('department')}
              {renderError('position')}
              {renderError('employment_type')}
              {renderError('start_date')}
              {renderError('salary_ron')}
              {renderError('address')}
              {renderError('is_active')}
              {renderError('non_field_errors')}
            </div>

            <div className="md:col-span-2 flex justify-end gap-2 mt-1">
              <button
                type="button"
                className="min-h-[40px] border border-[var(--border)] rounded-[10px] bg-[var(--card)] text-[var(--card-foreground)] px-[0.9rem] font-semibold cursor-pointer"
                onClick={() => {
                  setIsFormOpen(false)
                  setFormData(initialFormData)
                  setFormErrors({})
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="min-h-[40px] rounded-[10px] bg-[var(--primary)] text-[var(--primary-foreground)] px-[0.95rem] font-bold cursor-pointer inline-flex items-center justify-center border-none disabled:opacity-70 disabled:cursor-not-allowed"
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Saving...' : 'Create employee'}
              </button>
            </div>
          </form>
        </section>
      )}

      <div className="grid grid-cols-1 md:grid-cols-[1fr_280px] gap-3">
        <input
          className="min-h-[42px] border border-[var(--border)] rounded-[10px] px-[0.8rem] bg-[var(--card)] text-[var(--card-foreground)]"
          value={searchTerm}
          onChange={event => setSearchTerm(event.target.value)}
          placeholder="Search by employee name"
          aria-label="Search employees by name"
        />

        <select
          className="min-h-[42px] border border-[var(--border)] rounded-[10px] px-[0.75rem] bg-[var(--card)] text-[var(--card-foreground)]"
          value={departmentFilter}
          onChange={event => setDepartmentFilter(event.target.value)}
          aria-label="Filter by department"
        >
          <option value="">All departments</option>
          {departments.map(department => (
            <option key={department.id} value={department.slug}>{department.name}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5">Loading employees...</section>
      ) : employees.length === 0 ? (
        <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5">No employees found for current filters.</section>
      ) : (
        <>
          <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl overflow-hidden">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="text-left px-4 py-3 border-b border-[var(--border)] text-[0.8rem] text-[var(--muted-foreground)] uppercase tracking-[0.05em]">Avatar + Name</th>
                  <th className="text-left px-4 py-3 border-b border-[var(--border)] text-[0.8rem] text-[var(--muted-foreground)] uppercase tracking-[0.05em]">Role</th>
                  <th className="text-left px-4 py-3 border-b border-[var(--border)] text-[0.8rem] text-[var(--muted-foreground)] uppercase tracking-[0.05em]">Department</th>
                  <th className="text-left px-4 py-3 border-b border-[var(--border)] text-[0.8rem] text-[var(--muted-foreground)] uppercase tracking-[0.05em]">Contract</th>
                  <th className="text-left px-4 py-3 border-b border-[var(--border)] text-[0.8rem] text-[var(--muted-foreground)] uppercase tracking-[0.05em]">Status</th>
                </tr>
              </thead>
              <tbody>
                {employees.map(employee => (
                  <tr
                    key={employee.id}
                    className="cursor-pointer hover:bg-black/5 transition-colors"
                    onClick={() => navigate(`${detailRouteBase}/${employee.id}`)}
                  >
                    <td className="px-4 py-3 border-b border-[var(--border)]">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-[var(--primary)] text-[var(--primary-foreground)] grid place-items-center text-[0.8rem] font-bold">
                          {getInitials(employee)}
                        </div>
                        <span className="font-medium">{getDisplayName(employee)}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 border-b border-[var(--border)]">{formatRole(employee.role)}</td>
                    <td className="px-4 py-3 border-b border-[var(--border)]">{employee.department?.name ?? 'Unassigned'}</td>
                    <td className="px-4 py-3 border-b border-[var(--border)]">{formatContract(employee.employment_type)}</td>
                    <td className="px-4 py-3 border-b border-[var(--border)]">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-1 text-[0.76rem] font-semibold ${employee.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-200 text-gray-700'}`}
                      >
                        {employee.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <div className="inline-flex items-center gap-2 self-end">
            <button
              type="button"
              className="border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)] rounded-[10px] px-3 py-[0.45rem] cursor-pointer font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={page <= 1}
              onClick={() => setPage(current => Math.max(1, current - 1))}
            >
              Previous
            </button>
            <span className="text-[0.9rem]">{`Page ${page} / ${totalPages}`}</span>
            <button
              type="button"
              className="border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)] rounded-[10px] px-3 py-[0.45rem] cursor-pointer font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={page >= totalPages}
              onClick={() => setPage(current => Math.min(totalPages, current + 1))}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  )
}

export default EmployeesPage
