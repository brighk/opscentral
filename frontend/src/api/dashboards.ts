import api from './client';

export interface DashboardSummary {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  created_at: string;
}

export interface DashboardWidget {
  id: string;
  widget_type: string;
  title: string;
  config: Record<string, unknown>;
  position_x: number;
  position_y: number;
  width: number;
  height: number;
}

export interface Dashboard extends DashboardSummary {
  widgets: DashboardWidget[];
}

export const dashboardsApi = {
  list: () =>
    api.get<DashboardSummary[]>('/api/v1/dashboards').then(r => r.data),

  get: (id: string) =>
    api.get<Dashboard>(`/api/v1/dashboards/${id}`).then(r => r.data),

  create: (data: { name: string; description?: string; widgets?: Partial<DashboardWidget>[] }) =>
    api.post('/api/v1/dashboards', data).then(r => r.data),

  update: (id: string, data: { name?: string; description?: string; widgets?: Partial<DashboardWidget>[] }) =>
    api.put(`/api/v1/dashboards/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    api.delete(`/api/v1/dashboards/${id}`).then(r => r.data),

  setDefault: (id: string) =>
    api.post(`/api/v1/dashboards/${id}/set-default`).then(r => r.data),

  addWidget: (dashboardId: string, widget: Partial<DashboardWidget>) =>
    api.post(`/api/v1/dashboards/${dashboardId}/widgets`, widget).then(r => r.data),

  removeWidget: (dashboardId: string, widgetId: string) =>
    api.delete(`/api/v1/dashboards/${dashboardId}/widgets/${widgetId}`).then(r => r.data),
};
