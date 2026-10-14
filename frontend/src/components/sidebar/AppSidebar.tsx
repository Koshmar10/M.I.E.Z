import { useEffect, useMemo, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  FiFileText,
  FiGrid,
  FiHome,
  FiLogOut,
  FiMenu,
  FiMonitor,
  FiPackage,
  FiSettings,
  FiUserPlus,
  FiUsers,
  FiZap,
  FiBarChart2,
} from 'react-icons/fi'
import { api } from '../../api/client'
import { useAuth } from '../../context/AuthContext'

const SIDEBAR_COLLAPSED_KEY = 'miez.sidebar.collapsed'

type Department = {
  id: number
  name: string
  slug: string
  icon?: string
}

type NavItem = {
  label: string
  to: string
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
  roles?: Array<'CEO' | 'HR' | 'EMPLOYEE' | 'IT' | 'SALES' | 'INVENTORY'>
}

const CEO_NAV: NavItem[] = [
  { label: 'Dashboard', to: '/dashboard', icon: FiGrid, roles: ['CEO'] },
  { label: 'Employees', to: '/employees', icon: FiUserPlus, roles: ['CEO'] },
  { label: 'Reports', to: '/reports', icon: FiFileText, roles: ['CEO'] },
  { label: 'Workflows', to: '/workflows', icon: FiZap, roles: ['CEO'] },
]

const HR_NAV: NavItem[] = [
  { label: 'Dashboard', to: '/hr/dashboard', icon: FiGrid, roles: ['HR'] },
  { label: 'Employees', to: '/hr/employees', icon: FiUsers, roles: ['HR'] },
  { label: 'Attendance', to: '/hr/attendance', icon: FiBarChart2, roles: ['HR'] },
  { label: 'Leave Requests', to: '/hr/leave-requests', icon: FiFileText, roles: ['HR'] },
  { label: 'Contracts', to: '/hr/contracts', icon: FiSettings, roles: ['HR'] },
  { label: 'Payroll', to: '/hr/payroll', icon: FiPackage, roles: ['HR'] },
]

const IT_NAV: NavItem[] = [
  { label: 'Dashboard', to: '/it/dashboard', icon: FiGrid, roles: ['IT'] },
  { label: 'Assets', to: '/it/assets', icon: FiPackage, roles: ['IT'] },
  { label: 'All Tickets', to: '/it/tickets', icon: FiFileText, roles: ['IT'] },
  { label: 'My Assigned', to: '/it/assigned', icon: FiUsers, roles: ['IT'] },
  { label: 'Create Ticket', to: '/it/create', icon: FiUserPlus, roles: ['IT'] },
]

const SALES_NAV: NavItem[] = [
  { label: 'Dashboard', to: '/sales/dashboard', icon: FiGrid, roles: ['SALES'] },
  { label: 'Orders', to: '/sales/orders', icon: FiPackage, roles: ['SALES'] },
  { label: 'Customers', to: '/sales/customers', icon: FiUsers, roles: ['SALES'] },
  { label: 'Products', to: '/sales/products', icon: FiHome, roles: ['SALES'] },
  { label: 'Invoices', to: '/sales/invoices', icon: FiFileText, roles: ['SALES'] },
]

const INVENTORY_NAV: NavItem[] = [
  { label: 'Dashboard', to: '/inventory/dashboard', icon: FiGrid, roles: ['INVENTORY'] },
  { label: 'Products & Stock', to: '/inventory/products-stock', icon: FiPackage, roles: ['INVENTORY'] },
  { label: 'Receive Stock', to: '/inventory/receive-stock', icon: FiZap, roles: ['INVENTORY'] },
  { label: 'Stock Movements', to: '/inventory/stock-movements', icon: FiBarChart2, roles: ['INVENTORY'] },
  { label: 'Low Stock Alerts', to: '/inventory/low-stock-alert', icon: FiMonitor, roles: ['INVENTORY'] },
]

const DEFAULT_NAV: NavItem[] = [{ label: 'Reports', to: '/reports', icon: FiFileText }]

const departmentIcons = {
  Monitor: FiMonitor,
  Users: FiUsers,
  BarChart3: FiBarChart2,
  Package: FiPackage,
  Building2: FiHome,
} as const

const AppSidebar = () => {
  const { logout, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [isCollapsed, setIsCollapsed] = useState(() => localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true')
  const [departments, setDepartments] = useState<Department[]>([])
  const [lowStockCount, setLowStockCount] = useState<number>(0)

  const navItems = useMemo(() => {
    if (user?.role === 'CEO') return CEO_NAV
    if (user?.role === 'HR') return HR_NAV
    if (user?.role === 'IT') return IT_NAV
    if (user?.role === 'SALES') return SALES_NAV
    if (user?.role === 'INVENTORY') return INVENTORY_NAV
    return DEFAULT_NAV
  }, [user?.role])

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(isCollapsed))
  }, [isCollapsed])

  useEffect(() => {
    const fetchDepartments = async () => {
      if (user?.role !== 'CEO') {
        setDepartments([])
        return
      }

      try {
        setDepartments(await api.get<Department[]>('/api/departments/'))
      } catch {
        setDepartments([])
      }
    }

    const onDepartmentsUpdated = (event: Event) => {
      const customEvent = event as CustomEvent<Department[]>
      if (Array.isArray(customEvent.detail)) {
        setDepartments(customEvent.detail)
        return
      }
      void fetchDepartments()
    }

    void fetchDepartments()
    window.addEventListener('departments-updated', onDepartmentsUpdated as EventListener)

    return () => {
      window.removeEventListener('departments-updated', onDepartmentsUpdated as EventListener)
    }
  }, [location.pathname, user?.role])

  useEffect(() => {
    if (user?.role === 'INVENTORY' || user?.role === 'CEO') {
      const fetchAlerts = async () => {
        try {
          const lowStock = await api.get<unknown[]>('/api/inventory/products/?status=LOW&status=OUT')
          setLowStockCount(lowStock.length)
        } catch {
          // the badge is optional; leave it as it was
        }
      }
      void fetchAlerts()
    }
  }, [user?.role, location.pathname])

  const handleLogout = async () => {
    await logout()
    await navigate('/login', { replace: true })
  }

  return (
    <aside
      className={`bg-[var(--sidebar)] text-[var(--sidebar-foreground)] flex flex-col transition-all duration-200 h-screen sticky top-0 shrink-0 ${isCollapsed ? 'w-20' : 'w-[260px]'
        }`}
    >
      <div className="px-2 pt-4 pb-2 gap-3 flex flex-row items-center">
        <button
          className="border border-[var(--sidebar-border)] bg-[var(--sidebar-accent)] text-[var(--sidebar-foreground)] w-12 h-12 rounded-[12px] cursor-pointer grid place-items-center shrink-0"
          type="button"
          onClick={() => setIsCollapsed(current => !current)}
          aria-label="Toggle sidebar"
        >
          <FiMenu aria-hidden="true" />
        </button>
        {!isCollapsed && (
          <>
            <div className="w-10 h-10 rounded-lg bg-[#D1353B] flex items-center justify-center shrink-0">
              <span className="text-white text-[17px]" style={{ fontWeight: 700 }}>M</span>
            </div>
            <div className="font-semibold tracking-wide">M.I.E.Z</div>
          </>
        )}
      </div>

      <nav className="flex-1 py-3 flex flex-col gap-1 px-2 overflow-y-auto" aria-label="Main navigation">
        {navItems.map(item => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-[14px] transition-colors w-full text-left no-underline relative ${isActive
                  ? 'bg-[var(--sidebar-primary)] text-[var(--sidebar-primary-foreground)]'
                  : 'text-white/70 hover:bg-white/10 hover:text-[var(--sidebar-foreground)]'
                }`
              }
              title={isCollapsed ? item.label : undefined}
            >
              <Icon className="w-5 h-5 shrink-0" aria-hidden={true} />
              {!isCollapsed && <span className="flex-1">{item.label}</span>}
              {item.label === 'Low Stock Alerts' && lowStockCount > 0 && (
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${isCollapsed ? 'absolute top-1.5 right-1.5' : ''} bg-rose-500 text-white leading-none shadow-sm`}>
                  {lowStockCount}
                </span>
              )}
            </NavLink>
          )
        })}

        {user?.role === 'CEO' && departments.length > 0 && (
          <div>
            {!isCollapsed && (
              <p className="mt-2 mb-1.5 text-xs uppercase tracking-[0.2em] text-white/30">
                Departments
              </p>
            )}
            {departments.map(dep => {
              const iconName = dep.icon ?? 'Building2'
              const Icon = iconName in departmentIcons ? departmentIcons[iconName as keyof typeof departmentIcons] : FiHome

              return (
                <NavLink
                  key={dep.id}
                  to={`/departments/${dep.slug}`}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-xl text-[14px] transition-colors w-full text-left no-underline ${isActive
                      ? 'bg-[var(--sidebar-primary)] text-[var(--sidebar-primary-foreground)]'
                      : 'text-white/70 hover:bg-white/10 hover:text-[var(--sidebar-foreground)]'
                    }`
                  }
                  title={isCollapsed ? dep.name : undefined}
                >
                  <Icon className="w-5 h-5 shrink-0" aria-hidden={true} />
                  {!isCollapsed && <span>{dep.name}</span>}
                </NavLink>
              )
            })}
          </div>
        )}
      </nav>

      <div className="border-t border-white/10 px-2 py-3 flex flex-col gap-1">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-xl text-[14px] transition-colors w-full text-left no-underline ${isActive
              ? 'bg-white/10 text-[var(--sidebar-foreground)]'
              : 'text-white/60 hover:bg-white/10 hover:text-[var(--sidebar-foreground)]'
            }`
          }
          title={isCollapsed ? 'Settings' : undefined}
        >
          <FiSettings className="w-5 h-5 shrink-0" aria-hidden="true" />
          {!isCollapsed && <span>Settings</span>}
        </NavLink>

        <button
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-[14px] text-white/60 hover:bg-white/10 hover:text-[var(--sidebar-foreground)] w-full text-left transition-colors"
          type="button"
          onClick={() => void handleLogout()}
          title={isCollapsed ? 'Logout' : undefined}
        >
          <FiLogOut className="w-5 h-5 shrink-0" aria-hidden="true" />
          {!isCollapsed && <span>Logout</span>}
        </button>
      </div>
    </aside>
  )
}

export default AppSidebar
