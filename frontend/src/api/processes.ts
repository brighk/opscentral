import api from './client';

export interface ProcessInfo {
  pid: number;
  name: string;
  cpu_percent: number;
  memory_percent: number;
  memory_mb: number;
  status: string;
  username: string | null;
  num_threads: number;
  command: string;
  agent_id: string;
  recorded_at: string;
}

export const processesApi = {
  getProcesses: (agentId?: string) =>
    api.get<ProcessInfo[]>('/api/v1/monitoring/processes', {
      params: agentId ? { agent_id: agentId } : {},
    }),
};
