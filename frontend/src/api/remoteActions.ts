import api from './client';

export interface ActionType {
  key: string;
  name: string;
  description: string;
  min_role: string;
}

export interface RemoteAction {
  id: string;
  agent_id: string;
  action_type: string;
  status: string;
  parameters: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  error: string | null;
  expires_at: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export const remoteActionsApi = {
  getTypes: () => api.get<ActionType[]>('/api/v1/remote-actions/types'),
  create: (data: { agent_id: string; action_type: string; parameters?: Record<string, unknown> }) =>
    api.post<RemoteAction>('/api/v1/remote-actions', data),
  list: (agentId?: string, status?: string) => {
    const params = new URLSearchParams();
    if (agentId) params.set('agent_id', agentId);
    if (status) params.set('status', status);
    return api.get<RemoteAction[]>(`/api/v1/remote-actions?${params}`);
  },
  get: (id: string) => api.get<RemoteAction>(`/api/v1/remote-actions/${id}`),
  cancel: (id: string) => api.post(`/api/v1/remote-actions/${id}/cancel`),
};
