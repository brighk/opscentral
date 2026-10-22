import axios from './client';

export interface WebhookEndpoint {
  id: string;
  name: string;
  url: string;
  event_types: string[];
  is_active: boolean;
  failure_count: number;
  last_triggered_at: string | null;
  last_status_code: number | null;
  created_at: string;
}

export interface WebhookDelivery {
  id: string;
  endpoint_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  status_code: number | null;
  response_body: string | null;
  duration_ms: number | null;
  created_at: string;
}

export interface ExternalIntegration {
  id: string;
  provider: string;
  name: string;
  is_active: boolean;
  created_at: string;
}

export interface EventType {
  key: string;
  description: string;
}

export const integrationsApi = {
  // Webhooks
  listWebhooks: () => axios.get<WebhookEndpoint[]>('/api/v1/webhooks'),
  createWebhook: (data: { name: string; url: string; secret?: string; event_types: string[] }) =>
    axios.post<WebhookEndpoint>('/api/v1/webhooks', data),
  updateWebhook: (id: string, data: { name?: string; url?: string; event_types?: string[]; is_active?: boolean }) =>
    axios.put<WebhookEndpoint>(`/api/v1/webhooks/${id}`, data),
  deleteWebhook: (id: string) => axios.delete(`/api/v1/webhooks/${id}`),
  getDeliveries: (id: string) => axios.get<WebhookDelivery[]>(`/api/v1/webhooks/${id}/deliveries`),
  testWebhook: (id: string) => axios.post(`/api/v1/webhooks/${id}/test`),
  getEventTypes: () => axios.get<EventType[]>('/api/v1/webhooks/event-types'),

  // External Integrations
  listIntegrations: () => axios.get<ExternalIntegration[]>('/api/v1/integrations'),
  createIntegration: (data: { provider: string; name: string; config: Record<string, unknown> }) =>
    axios.post<ExternalIntegration>('/api/v1/integrations', data),
  updateIntegration: (id: string, data: { name?: string; config?: Record<string, unknown>; is_active?: boolean }) =>
    axios.put<ExternalIntegration>(`/api/v1/integrations/${id}`, data),
  deleteIntegration: (id: string) => axios.delete(`/api/v1/integrations/${id}`),
  testIntegration: (id: string) => axios.post<{ detail: string }>(`/api/v1/integrations/${id}/test`),
};
