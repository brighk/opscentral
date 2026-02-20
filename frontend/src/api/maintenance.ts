import api from './client';

export interface MaintenanceWindow {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  start_time: string;
  end_time: string;
  scope: string;
  scope_ids: string[];
  is_active: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceWindowCreate {
  name: string;
  description?: string;
  start_time: string;
  end_time: string;
  scope?: string;
  scope_ids?: string[];
  is_active?: boolean;
}

export interface MaintenanceWindowUpdate {
  name?: string;
  description?: string;
  start_time?: string;
  end_time?: string;
  scope?: string;
  scope_ids?: string[];
  is_active?: boolean;
}

export const maintenanceApi = {
  list: () => api.get<MaintenanceWindow[]>('/api/v1/maintenance'),
  listActive: () => api.get<MaintenanceWindow[]>('/api/v1/maintenance/active'),
  create: (data: MaintenanceWindowCreate) =>
    api.post<MaintenanceWindow>('/api/v1/maintenance', data),
  update: (id: string, data: MaintenanceWindowUpdate) =>
    api.put<MaintenanceWindow>(`/api/v1/maintenance/${id}`, data),
  delete: (id: string) => api.delete(`/api/v1/maintenance/${id}`),
};
