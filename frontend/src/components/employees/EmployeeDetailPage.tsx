import { useEffect, useMemo, useState, type SyntheticEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
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
  email: string
  first_name: string
  last_name: string
  phone: string
  position: string
  employment_type: 'FULL_TIME' | 'PART_TIME' | 'CONTRACTOR'
  start_date: string
  salary_ron: string
  address: string
  role: string
  is_active: boolean
  department: null | Department
}

type EmployeeEditFormData = {
  first_name: string
  last_name: string
  position: string
  phone: string
  department: string
  is_active: boolean
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

const createEditFormData = (employee: Employee): EmployeeEditFormData => ({
  first_name: employee.first_name,
  last_name: employee.last_name,
  position: employee.position,
  phone: employee.phone,
  department: employee.department ? String(employee.department.id) : '',
  is_active: employee.is_active,
})

const EmployeeDetailPage = () => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { id } = useParams()
  const [employee, setEmployee] = useState<Employee | null>(null)
  const [departments, setDepartments] = useState<Department[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [editFormData, setEditFormData] = useState<EmployeeEditFormData>({
    first_name: '',
    last_name: '',
    position: '',
    phone: '',
    department: '',
    is_active: true,
  })
  const [editErrors, setEditErrors] = useState<Partial<Record<string, string[]>>>({})

  useEffect(() => {
    const fetchEmployee = async () => {
      if (!id) {
        setError('Missing employee id.')
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        setError('')

        setEmployee(await api.get<Employee>(`/api/employees/${id}/`))
      } catch (fetchError) {
        console.error('Failed to load employee detail', fetchError)
        setError('Could not load employee details right now.')
      } finally {
        setIsLoading(false)
      }
    }

    void fetchEmployee()
  }, [id])

  useEffect(() => {
    const fetchDepartments = async () => {
      try {
        setDepartments(await api.get<Department[]>('/api/departments/'))
      } catch (fetchError) {
        console.error('Failed to load departments', fetchError)
        setDepartments([])
      }
    }

    void fetchDepartments()
  }, [])

  const displayName = useMemo(() => {
    if (!employee) {
      return ''
    }

    const fullName = `${employee.first_name} ${employee.last_name}`.trim()
    return fullName || employee.username
  }, [employee])

  const canEditEmployee = user?.role === 'CEO' || user?.role === 'HR'

  const openEditForm = () => {
    if (!employee) {
      return
    }

    setEditFormData(createEditFormData(employee))
    setEditErrors({})
    setIsEditing(true)
  }

  const handleEditFieldChange = (field: keyof EmployeeEditFormData, value: string | boolean) => {
    setEditFormData(current => ({
      ...current,
      [field]: value,
    }))
  }

  const handleEditSubmit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!id) {
      return
    }

    setIsSaving(true)
    setEditErrors({})

    try {
      const payload = {
        first_name: editFormData.first_name,
        last_name: editFormData.last_name,
        position: editFormData.position,
        phone: editFormData.phone,
        department: editFormData.department ? Number(editFormData.department) : null,
        is_active: editFormData.is_active,
      }

      const updatedEmployee = await api.patch<Employee>(`/api/employees/${id}/`, payload)
      setEmployee(updatedEmployee)
      setEditFormData(createEditFormData(updatedEmployee))
      setIsEditing(false)
    } catch (saveError) {
      console.error('Failed to update employee', saveError)
      setEditErrors(fieldErrors(saveError) ?? { non_field_errors: ['Could not save employee. Please try again.'] })
    } finally {
      setIsSaving(false)
    }
  }

  const renderEditError = (field: keyof EmployeeEditFormData | 'non_field_errors') => {
    const errors = editErrors[field]
    if (!errors || errors.length === 0) {
      return null
    }

    return <p className="text-[0.82rem] text-red-600">{errors[0]}</p>
  }

  if (isLoading) {
    return <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5">Loading employee details...</section>
  }

  if (error || !employee) {
    return (
      <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5 flex flex-col gap-3">
        <p>{error || 'Employee not found.'}</p>
        <button
          type="button"
          className="self-start border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)] rounded-[10px] px-3 py-[0.45rem] cursor-pointer font-semibold"
          onClick={() => void navigate(-1)}
        >
          Back
        </button>
      </section>
    )
  }

  return (
    <section className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5 flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-[1.18rem] font-semibold">{displayName}</h2>
          <p className="text-[0.92rem] text-[var(--muted-foreground)]">Employee details</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {canEditEmployee && (
            <button
              type="button"
              className="border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)] rounded-[10px] px-3 py-[0.45rem] cursor-pointer font-semibold"
              onClick={() => {
                if (isEditing) {
                  setIsEditing(false)
                  setEditErrors({})
                  return
                }

                openEditForm()
              }}
            >
              {isEditing ? 'Close edit form' : 'Edit'}
            </button>
          )}
          <button
            type="button"
            className="border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)] rounded-[10px] px-3 py-[0.45rem] cursor-pointer font-semibold"
            onClick={() => void navigate(-1)}
          >
            Back to list
          </button>
        </div>
      </div>

      {isEditing && (
        <section className="border border-[var(--border)] rounded-xl p-4 bg-[var(--card)]">
          <h3 className="text-[1rem] font-semibold mb-3">Edit employee</h3>

          <form className="grid grid-cols-1 md:grid-cols-2 gap-3" onSubmit={(event) => void handleEditSubmit(event)}>
            <input
              className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]"
              value={editFormData.first_name}
              onChange={event => handleEditFieldChange('first_name', event.target.value)}
              placeholder="First name"
              required
            />
            <input
              className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]"
              value={editFormData.last_name}
              onChange={event => handleEditFieldChange('last_name', event.target.value)}
              placeholder="Last name"
              required
            />
            <input
              className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]"
              value={editFormData.position}
              onChange={event => handleEditFieldChange('position', event.target.value)}
              placeholder="Position"
              required
            />
            <input
              className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]"
              value={editFormData.phone}
              onChange={event => handleEditFieldChange('phone', event.target.value)}
              placeholder="Phone (+40...)"
              required
            />

            <select
              className="min-h-[40px] border border-[var(--border)] rounded-[10px] px-[0.7rem] bg-[var(--card)] text-[var(--card-foreground)]"
              value={editFormData.department}
              onChange={event => handleEditFieldChange('department', event.target.value)}
            >
              <option value="">No department</option>
              {departments.map(department => (
                <option key={department.id} value={String(department.id)}>
                  {department.name}
                </option>
              ))}
            </select>

            <label className="inline-flex items-center gap-[0.45rem] text-[0.92rem] text-[var(--muted-foreground)]">
              <input
                className="w-4 h-4"
                type="checkbox"
                checked={editFormData.is_active}
                onChange={event => handleEditFieldChange('is_active', event.target.checked)}
              />
              Active employee
            </label>

            <div className="md:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-2">
              {renderEditError('first_name')}
              {renderEditError('last_name')}
              {renderEditError('position')}
              {renderEditError('phone')}
              {renderEditError('department')}
              {renderEditError('is_active')}
              {renderEditError('non_field_errors')}
            </div>

            <div className="md:col-span-2 flex justify-end gap-2 mt-1">
              <button
                type="button"
                className="min-h-[40px] border border-[var(--border)] rounded-[10px] bg-[var(--card)] text-[var(--card-foreground)] px-[0.9rem] font-semibold cursor-pointer"
                onClick={() => {
                  setIsEditing(false)
                  setEditErrors({})
                  setEditFormData(createEditFormData(employee))
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="min-h-[40px] rounded-[10px] bg-[var(--primary)] text-[var(--primary-foreground)] px-[0.95rem] font-bold cursor-pointer inline-flex items-center justify-center border-none disabled:opacity-70 disabled:cursor-not-allowed"
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : 'Save changes'}
              </button>
            </div>
          </form>
        </section>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <article className="border border-[var(--border)] rounded-xl p-4">
          <p className="text-[0.8rem] text-[var(--muted-foreground)]">Role</p>
          <p className="font-medium mt-1">{formatRole(employee.role)}</p>
        </article>
        <article className="border border-[var(--border)] rounded-xl p-4">
          <p className="text-[0.8rem] text-[var(--muted-foreground)]">Department</p>
          <p className="font-medium mt-1">{employee.department?.name ?? 'Unassigned'}</p>
        </article>
        <article className="border border-[var(--border)] rounded-xl p-4">
          <p className="text-[0.8rem] text-[var(--muted-foreground)]">Contract Type</p>
          <p className="font-medium mt-1">{formatContract(employee.employment_type)}</p>
        </article>
        <article className="border border-[var(--border)] rounded-xl p-4">
          <p className="text-[0.8rem] text-[var(--muted-foreground)]">Status</p>
          <p className="font-medium mt-1">{employee.is_active ? 'Active' : 'Inactive'}</p>
        </article>
        <article className="border border-[var(--border)] rounded-xl p-4">
          <p className="text-[0.8rem] text-[var(--muted-foreground)]">Email</p>
          <p className="font-medium mt-1">{employee.email || '-'}</p>
        </article>
        <article className="border border-[var(--border)] rounded-xl p-4">
          <p className="text-[0.8rem] text-[var(--muted-foreground)]">Phone</p>
          <p className="font-medium mt-1">{employee.phone || '-'}</p>
        </article>
        <article className="border border-[var(--border)] rounded-xl p-4">
          <p className="text-[0.8rem] text-[var(--muted-foreground)]">Position</p>
          <p className="font-medium mt-1">{employee.position || '-'}</p>
        </article>
        <article className="border border-[var(--border)] rounded-xl p-4">
          <p className="text-[0.8rem] text-[var(--muted-foreground)]">Start Date</p>
          <p className="font-medium mt-1">{employee.start_date || '-'}</p>
        </article>
      </div>
    </section>
  )
}

export default EmployeeDetailPage