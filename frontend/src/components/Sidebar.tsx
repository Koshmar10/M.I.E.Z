import React, { useEffect, useState } from 'react'
import { NavLink, useLocation, Outlet } from 'react-router-dom'
import {
  Menu, Bell, ChevronDown, LayoutDashboard, UserPlus,
  FileText, Zap, Settings, LogOut, Bot
} from 'lucide-react'

// Navigation items configuration
const NAV_ITEMS = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/' },
  { icon: UserPlus, label: 'Register Employees', href: '/employees' },
  { icon: FileText, label: 'Reports', href: '/reports' },
  { icon: Zap, label: 'Workflows', href: '/workflows' },
]

const FOOTER_ITEMS = [
  { icon: Settings, label: 'Settings', href: '/settings' },
  { icon: LogOut, label: 'Logout', href: '/logout' },
]

const SIDEBAR_COLLAPSED_KEY = 'miez.sidebar.collapsed'

// Navigation Link Component using React Router
interface NavLinkItemProps {
  icon: React.ComponentType<{ size: number }>
  label: string
  href: string
  isCollapsed?: boolean
}

const NavLinkItem: React.FC<NavLinkItemProps> = ({ icon: Icon, label, href, isCollapsed = false }) => (
  <NavLink
    to={href}
    className={({ isActive }) =>
      `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
        isActive
          ? 'text-white bg-[var(--danger)]'
          : 'text-[var(--ink-subtle)] hover:text-[var(--ink)] hover:bg-[var(--accent-soft)]'
      }`
    }
  >
    <Icon size={18} />
    {!isCollapsed && <span className="text-sm font-medium">{label}</span>}
  </NavLink>
)

interface SidebarProps {
  unreadNotifications?: number
  onLogout?: () => void
}

const Sidebar: React.FC<SidebarProps> = ({ unreadNotifications = 0, onLogout }) => {
  const [isCollapsed, setIsCollapsed] = useState(false)

  // Load sidebar state from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(SIDEBAR_COLLAPSED_KEY)
    if (saved !== null) {
      setIsCollapsed(saved === 'true')
    }
  }, [])

  // Persist sidebar state to localStorage when it changes
  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(isCollapsed))
  }, [isCollapsed])

  return (
    <div className="flex flex-col h-screen font-sans" style={{ backgroundColor: 'var(--bg)' }}>
      {/* Top Navbar */}
      <header className="flex items-center justify-between h-[60px] px-4 shrink-0 border-b" style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}>
        {/* Left: Menu & Logo */}
        <div className="flex items-center gap-4" style={{ width: isCollapsed ? 'auto' : '260px' }}>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="transition-colors hover:opacity-70"
            style={{ color: 'var(--ink-subtle)' }}
            aria-label="Toggle sidebar"
          >
            <Menu size={20} />
          </button>
          {!isCollapsed && (
            <div className="flex items-center gap-2">
              <div
                className="flex items-center justify-center w-7 h-7 rounded-md font-bold text-sm text-white"
                style={{ backgroundColor: 'var(--danger)' }}
              >
                M
              </div>
              <span className="font-bold tracking-wide text-sm" style={{ color: 'var(--ink)' }}>M.I.E.Z</span>
            </div>
          )}
        </div>

        {/* Center: Title */}
        <div className="flex-1 text-center">
          <span className="text-sm" style={{ color: 'var(--ink-subtle)' }}>Dashboard — </span>
          <span className="text-sm font-medium" style={{ color: 'var(--ink)' }}>CEO</span>
        </div>

        {/* Right: Notification Bell */}
        <div className="flex items-center gap-3">
          <button
            className="relative transition-colors hover:opacity-70"
            style={{ color: 'var(--ink-subtle)' }}
            aria-label={`Notifications${unreadNotifications > 0 ? ` (${unreadNotifications} unread)` : ''}`}
          >
            <Bell size={18} />
            {unreadNotifications > 0 && (
              <span
                className="absolute -top-1 -right-1 w-4 h-4 text-xs font-bold rounded-full flex items-center justify-center text-white"
                style={{ backgroundColor: 'var(--danger)' }}
              >
                {unreadNotifications > 9 ? '9+' : unreadNotifications}
              </span>
            )}
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside
          className={`flex flex-col justify-between py-4 shrink-0 border-r transition-all duration-300 ${
            isCollapsed ? 'w-[88px]' : 'w-[260px]'
          }`}
          style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }}
        >
          <nav className="flex flex-col gap-1 px-3">
            {NAV_ITEMS.map((item) => (
              <NavLinkItem
                key={item.href}
                {...item}
                isCollapsed={isCollapsed}
              />
            ))}
          </nav>

          <div className="flex flex-col gap-1 px-3 border-t pt-3" style={{ borderColor: 'var(--border)' }}>
            {FOOTER_ITEMS.map((item) => (
              <NavLinkItem
                key={item.href}
                {...item}
                isCollapsed={isCollapsed}
              />
            ))}
          </div>
        </aside>

        <main className="flex-1 p-8 overflow-y-auto">
          <Outlet />
        </main>
      </div>

      {/* Floating Assistant Widget */}
      <div className="fixed bottom-6 right-6">
        <button
          className="px-4 py-2.5 rounded-full flex items-center gap-2.5 shadow-lg transition-colors border hover:opacity-80"
          style={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--ink)' }}
          aria-label="Open MIEZ Assistant"
        >
          <span className="w-2 h-2 bg-green-500 rounded-full" />
          <Bot size={16} />
          <span className="text-sm font-medium tracking-wide">MIEZ Assistant</span>
          <ChevronDown size={14} style={{ color: 'var(--ink-subtle)' }} />
        </button>
      </div>
    </div>
  )
}

export default Sidebar