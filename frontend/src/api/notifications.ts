import api from './client';

export interface NotificationChannel {
  id: string;
  name: string;
  channel_type: string;
  is_enabled: boolean;
  config: Record<string, unknown>;
  created_at: string;
}

export interface CreateNotificationChannel {
  name: string;
  channel_type: string;
  is_enabled?: boolean;
  config: Record<string, unknown>;
}

export const notificationsApi = {
  listChannels: () => api.get<NotificationChannel[]>('/api/v1/notifications/channels'),
  createChannel: (data: CreateNotificationChannel) =>
    api.post<NotificationChannel>('/api/v1/notifications/channels', data),
  updateChannel: (id: string, data: Partial<CreateNotificationChannel>) =>
    api.put<NotificationChannel>(`/api/v1/notifications/channels/${id}`, data),
  deleteChannel: (id: string) => api.delete(`/api/v1/notifications/channels/${id}`),
  testChannel: (id: string) => api.post(`/api/v1/notifications/channels/${id}/test`),
};
