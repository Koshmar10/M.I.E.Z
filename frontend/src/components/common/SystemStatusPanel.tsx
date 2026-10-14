import React, { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { useAuth } from '../../context/AuthContext'

interface SystemStatus {
  id: number
  name: string
  uptime_pct: number
  status: 'ONLINE' | 'DEGRADED' | 'OFFLINE'
  last_incident_date: string | null
  created_at: string
  updated_at: string
}

interface SystemStatusPanelProps {
  pollInterval?: number // in milliseconds, default 60000
  compact?: boolean
}

const SystemStatusPanel: React.FC<SystemStatusPanelProps> = ({ 
  pollInterval = 60000, 
  compact = false 
}) => {
  const [systems, setSystems] = useState<SystemStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { user } = useAuth()

  useEffect(() => {
    const fetchSystemStatus = async () => {
      try {
        setSystems(await api.get<SystemStatus[]>('/api/it/system-status/'))
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error occurred')
      } finally {
        setLoading(false)
      }
    }

    void fetchSystemStatus()
    const interval = setInterval(fetchSystemStatus, pollInterval)
    return () => clearInterval(interval)
  }, [pollInterval])

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'ONLINE':
        return 'bg-emerald-500'
      case 'DEGRADED':
        return 'bg-amber-500'
      case 'OFFLINE':
        return 'bg-rose-500'
      default:
        return 'bg-[var(--muted-foreground)]'
    }
  }

  const getStatusRowClass = (status: string): string => {
    switch (status) {
      case 'ONLINE':
        return 'border-emerald-200 bg-emerald-50'
      case 'DEGRADED':
        return 'border-amber-200 bg-amber-50'
      case 'OFFLINE':
        return 'border-rose-200 bg-rose-50'
      default:
        return 'border-[var(--border)] bg-[var(--input-background)]'
    }
  }

  // Only show if user is CEO or IT
  if (!user || (user.role !== 'CEO' && user.role !== 'IT')) {
    return null
  }

  if (compact) {
    return (
      <div className="flex gap-2">
        {systems.map((system) => (
          <div key={system.id} className="flex items-center gap-1" title={`${system.name}: ${system.status} (${system.uptime_pct}%)`}>
            <div className={`w-3 h-3 rounded-full ${getStatusColor(system.status)}`} />
          </div>
        ))}
      </div>
    )
  }

  return (
    <section className="bg-[var(--card)] text-[var(--card-foreground)] border border-[var(--border)] rounded-2xl p-5">
      <header className="mb-4">
        <h2 className="text-[1.05rem] font-semibold tracking-tight">System Status</h2>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">Live infrastructure health snapshot.</p>
      </header>

      {loading && <p className="text-sm text-[var(--muted-foreground)]">Loading system status...</p>}
      {error && <p className="text-sm text-[var(--destructive)]">Error: {error}</p>}

      {!loading && systems.length > 0 && (
        <div className="space-y-2.5">
          {systems.map((system) => (
            <div key={system.id} className={`rounded-xl border p-3 ${getStatusRowClass(system.status)}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-2.5 h-2.5 rounded-full ${getStatusColor(system.status)}`} />
                  <div>
                    <h3 className="text-sm font-semibold">{system.name}</h3>
                    <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{system.status}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold">{system.uptime_pct}%</p>
                  <p className="text-[11px] text-[var(--muted-foreground)] uppercase tracking-[0.14em]">uptime</p>
                </div>
              </div>
              {system.last_incident_date && (
                <p className="text-xs text-[var(--muted-foreground)] mt-2">
                  Last incident: {new Date(system.last_incident_date).toLocaleString()}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {!loading && systems.length === 0 && (
        <p className="text-sm text-[var(--muted-foreground)]">No systems found</p>
      )}
    </section>
  )
}

export default SystemStatusPanel
