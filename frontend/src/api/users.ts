import api from './client';

export interface ManagedUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown>;
  performed_at: string;
}

export const usersApi = {
  list: () =>
    api.get<ManagedUser[]>('/api/v1/auth/users').then(r => r.data),

  invite: (data: { email: string; full_name: string; role: string; password: string }) =>
    api.post('/api/v1/auth/users/invite', data).then(r => r.data),

  updateRole: (userId: string, role: string) =>
    api.put(`/api/v1/auth/users/${userId}/role`, { role }).then(r => r.data),

  deactivate: (userId: string) =>
    api.delete(`/api/v1/auth/users/${userId}`).then(r => r.data),

  auditLog: (params?: { limit?: number }) =>
    api.get<AuditLogEntry[]>('/api/v1/auth/audit-log', { params }).then(r => r.data),
};
