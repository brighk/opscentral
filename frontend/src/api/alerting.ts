import api from './client';

export interface AlertRule {
  id: string;
  name: string;
  description: string | null;
  metric_name: string;
  condition: string;
  threshold: number;
  duration_seconds: number;
  agent_id: string | null;
  severity: string;
  is_enabled: boolean;
  notify_email: boolean;
  created_at: string;
}

export interface AlertRuleCreate {
  name: string;
  description?: string;
  metric_name: string;
  condition: string;
  threshold: number;
  duration_seconds?: number;
  agent_id?: string;
  severity?: string;
  notify_email?: boolean;
}

export interface Alert {
  id: string;
  rule_id: string | null;
  agent_id: string | null;
  status: string;
  severity: string;
  title: string;
  message: string | null;
  metric_value: number | null;
  fired_at: string;
  resolved_at: string | null;
  acknowledged_at: string | null;
  created_at: string;
}

export const alertingApi = {
  listRules: () => api.get<AlertRule[]>('/api/v1/alerting/rules'),
  createRule: (data: AlertRuleCreate) => api.post<AlertRule>('/api/v1/alerting/rules', data),
  updateRule: (id: string, data: Partial<AlertRuleCreate>) =>
    api.put<AlertRule>(`/api/v1/alerting/rules/${id}`, data),
  deleteRule: (id: string) => api.delete(`/api/v1/alerting/rules/${id}`),

  listAlerts: (status?: string) =>
    api.get<Alert[]>('/api/v1/alerting/alerts', { params: status ? { status } : {} }),
  acknowledgeAlert: (id: string) => api.post(`/api/v1/alerting/alerts/${id}/acknowledge`),
  resolveAlert: (id: string) => api.post(`/api/v1/alerting/alerts/${id}/resolve`),
};
