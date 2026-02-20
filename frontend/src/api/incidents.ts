import api from './client';

export interface Incident {
  id: string;
  title: string;
  description: string | null;
  severity: string;
  status: string;
  source: string;
  alert_id: string | null;
  assigned_to: string | null;
  commander_id: string | null;
  created_by: string;
  resolved_at: string | null;
  closed_at: string | null;
  created_at: string;
}

export interface IncidentCreate {
  title: string;
  description?: string;
  severity?: string;
  source?: string;
  assigned_to?: string;
  commander_id?: string;
}

export interface IncidentUpdateEntry {
  id: string;
  incident_id: string;
  message: string;
  update_type: string;
  created_by: string;
  new_status: string | null;
  created_at: string;
}

export interface Postmortem {
  id: string;
  incident_id: string;
  summary: string;
  root_cause: string | null;
  impact: string | null;
  timeline: string | null;
  lessons_learned: string | null;
  action_items: string | null;
  created_by: string;
  created_at: string;
}

export interface IncidentStats {
  total: number;
  open: number;
  investigating: number;
  resolved: number;
  closed: number;
  mttr_hours: number | null;
}

export const incidentsApi = {
  list: (status?: string, severity?: string) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (severity) params.set('severity', severity);
    const qs = params.toString();
    return api.get<Incident[]>(`/api/v1/incidents${qs ? `?${qs}` : ''}`);
  },
  get: (id: string) => api.get<Incident>(`/api/v1/incidents/${id}`),
  create: (data: IncidentCreate) => api.post<Incident>('/api/v1/incidents', data),
  update: (id: string, data: Partial<IncidentCreate> & { status?: string }) =>
    api.put<Incident>(`/api/v1/incidents/${id}`, data),
  delete: (id: string) => api.delete(`/api/v1/incidents/${id}`),
  resolve: (id: string) => api.post<Incident>(`/api/v1/incidents/${id}/resolve`),
  getStats: () => api.get<IncidentStats>('/api/v1/incidents/stats'),
  listUpdates: (id: string) =>
    api.get<IncidentUpdateEntry[]>(`/api/v1/incidents/${id}/updates`),
  addUpdate: (id: string, data: { message: string; update_type?: string; new_status?: string }) =>
    api.post<IncidentUpdateEntry>(`/api/v1/incidents/${id}/updates`, data),
  getPostmortem: (id: string) =>
    api.get<Postmortem>(`/api/v1/incidents/${id}/postmortem`),
  createPostmortem: (id: string, data: { summary: string; root_cause?: string; impact?: string; timeline?: string; lessons_learned?: string; action_items?: string }) =>
    api.post<Postmortem>(`/api/v1/incidents/${id}/postmortem`, data),
  updatePostmortem: (id: string, data: { summary: string; root_cause?: string; impact?: string; timeline?: string; lessons_learned?: string; action_items?: string }) =>
    api.put<Postmortem>(`/api/v1/incidents/${id}/postmortem`, data),
};
