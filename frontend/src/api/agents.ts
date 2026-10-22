import api, { type Paginated } from './client';

export interface Agent {
  id: string;
  hostname: string;
  display_name: string | null;
  os_type: string | null;
  os_version: string | null;
  agent_version: string | null;
  ip_address: string | null;
  last_seen: string | null;
  is_active: boolean;
  created_at: string;
}

export interface AgentRegisterResponse {
  agent_id: string;
  api_key: string;
}

export interface AgentStatusLog {
  id: number;
  status: string;
  message: string | null;
  recorded_at: string;
}

export const agentsApi = {
  list: () => api.get<Paginated<Agent>>('/api/v1/agents'),

  register: (data: { hostname: string; display_name?: string; os_type?: string; os_version?: string }) =>
    api.post<AgentRegisterResponse>('/api/v1/agents/register', data),

  deactivate: (agentId: string) =>
    api.delete(`/api/v1/agents/${agentId}`),

  getStatusHistory: (agentId: string, days?: number) =>
    api.get<AgentStatusLog[]>(`/api/v1/agents/${agentId}/status-history`, {
      params: days ? { days } : {},
    }),
};
