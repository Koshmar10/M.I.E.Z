import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'

export type AppNotification = {
  id: number
  type: 'INFO' | 'WARNING' | 'ERROR'
  title: string
  body: string
  is_read: boolean
  link: string
  created_at: string
}

type NotificationsResponse = {
  count: number
  unread_count: number
  results: AppNotification[]
}

const QUERY_KEY = ['notifications']

/** The current user's latest 20 notifications, refreshed every minute. */
export function useNotifications() {
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => api.get<NotificationsResponse>('/api/notifications/', { page_size: 20 }),
    refetchInterval: 60_000,
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: QUERY_KEY })

  const markRead = useMutation({ mutationFn: (id: number) => api.patch(`/api/notifications/${id}/`), onSuccess: refresh })
  const markAllRead = useMutation({ mutationFn: () => api.post('/api/notifications/mark-all-read/'), onSuccess: refresh })

  return {
    notifications: data?.results ?? [],
    unreadCount: data?.unread_count ?? 0,
    markRead: (id: number) => {
      markRead.mutate(id)
    },
    markAllRead: () => {
      markAllRead.mutate()
    },
  }
}
