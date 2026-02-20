import api from './client';

export interface HealthCheck {
  id: string;
  name: string;
  check_type: string;
  target: string;
  interval_seconds: number;
  timeout_seconds: number;
  is_enabled: boolean;
  expected_status: number | null;
  http_method: string;
  alert_after_failures: number;
  notify_channels: boolean;
  status: string;
  last_checked_at: string | null;
  last_response_time_ms: number | null;
  consecutive_failures: number;
  last_error: string | null;
  created_at: string;
}

export interface HealthCheckLog {
  id: number;
  check_id: string;
  status: string;
  response_time_ms: number | null;
  status_code: number | null;
  error: string | null;
  checked_at: string;
}

export interface CreateHealthCheck {
  name: string;
  check_type: string;
  target: string;
  interval_seconds?: number;
  timeout_seconds?: number;
  expected_status?: number;
  expected_body?: string;
  http_method?: string;
  alert_after_failures?: number;
  notify_channels?: boolean;
}

export const healthchecksApi = {
  list: () => api.get<HealthCheck[]>('/api/v1/healthchecks'),
  create: (data: CreateHealthCheck) => api.post<HealthCheck>('/api/v1/healthchecks', data),
  update: (id: string, data: Partial<CreateHealthCheck>) =>
    api.put<HealthCheck>(`/api/v1/healthchecks/${id}`, data),
  delete: (id: string) => api.delete(`/api/v1/healthchecks/${id}`),
  getLogs: (id: string, hours?: number) =>
    api.get<HealthCheckLog[]>(`/api/v1/healthchecks/${id}/logs`, {
      params: hours ? { hours } : {},
    }),
  test: (id: string) => api.post(`/api/v1/healthchecks/${id}/test`),
};
