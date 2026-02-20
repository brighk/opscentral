import api from './client';

export interface RunbookStep {
  name: string;
  action_type: string;
  parameters: Record<string, unknown>;
  on_failure: string;
}

export interface Runbook {
  id: string;
  name: string;
  description: string | null;
  steps: RunbookStep[];
  trigger_type: string;
  requires_approval: boolean;
  is_enabled: boolean;
  created_by: string;
  created_at: string;
}

export interface RunbookCreate {
  name: string;
  description?: string;
  steps: RunbookStep[];
  trigger_type?: string;
  requires_approval?: boolean;
}

export interface RunbookExecution {
  id: string;
  runbook_id: string;
  status: string;
  triggered_by: string;
  approved_by: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  created_at: string;
}

export interface RunbookStepExecution {
  id: string;
  step_index: number;
  step_name: string;
  status: string;
  result: Record<string, unknown> | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export const runbooksApi = {
  list: () => api.get<Runbook[]>('/api/v1/runbooks'),
  get: (id: string) => api.get<Runbook>(`/api/v1/runbooks/${id}`),
  create: (data: RunbookCreate) => api.post<Runbook>('/api/v1/runbooks', data),
  update: (id: string, data: Partial<RunbookCreate> & { is_enabled?: boolean }) =>
    api.put<Runbook>(`/api/v1/runbooks/${id}`, data),
  delete: (id: string) => api.delete(`/api/v1/runbooks/${id}`),
  execute: (id: string, parameters: Record<string, unknown> = {}) =>
    api.post<RunbookExecution>(`/api/v1/runbooks/${id}/execute`, { parameters }),
  listExecutions: (id: string) =>
    api.get<RunbookExecution[]>(`/api/v1/runbooks/${id}/executions`),
  listStepExecutions: (executionId: string) =>
    api.get<RunbookStepExecution[]>(`/api/v1/runbooks/executions/${executionId}/steps`),
  approve: (executionId: string) =>
    api.post<RunbookExecution>(`/api/v1/runbooks/executions/${executionId}/approve`),
  cancel: (executionId: string) =>
    api.post<RunbookExecution>(`/api/v1/runbooks/executions/${executionId}/cancel`),
};
