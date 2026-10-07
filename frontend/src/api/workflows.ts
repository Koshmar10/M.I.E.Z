import { api } from './client'

export type Workflow = {
  id: number
  name: string
  trigger_type: string
  trigger_label: string
  trigger_config: Record<string, string | number>
  actions: string[]
  action_labels: string[]
  is_active: boolean
  last_triggered_at: string | null
  created_at: string
  updated_at: string
}

export type WorkflowLog = {
  id: number
  workflow: number
  workflow_name: string
  triggered_at: string
  trigger_type: string
  actions_log: { action: string; success: boolean; message: string }[]
  success: boolean
}

export type TriggerOption = { value: string; label: string }
export type ActionOption  = { value: string; label: string }

export type WorkflowPayload = {
  name: string
  trigger_type: string
  trigger_config: Record<string, string | number>
  actions: string[]
  is_active: boolean
}

export const workflowsApi = {
  list: () => api.get<Workflow[]>('/api/workflows/'),
  create: (data: WorkflowPayload) => api.post<Workflow>('/api/workflows/', data),
  update: (id: number, data: Partial<WorkflowPayload>) => api.patch<Workflow>(`/api/workflows/${id}/`, data),
  remove: (id: number) => api.delete(`/api/workflows/${id}/`),
  toggle: (id: number, is_active: boolean) =>
    api.patch<{ id: number; is_active: boolean }>(`/api/workflows/${id}/toggle/`, { is_active }),
  triggers: () => api.get<TriggerOption[]>('/api/workflows/triggers/'),
  actions: () => api.get<ActionOption[]>('/api/workflows/actions/'),
  logs: () => api.get<WorkflowLog[]>('/api/workflows/logs/'),
}
