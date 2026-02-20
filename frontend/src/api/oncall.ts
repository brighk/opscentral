import api from './client';

export interface OnCallSchedule {
  id: string;
  name: string;
  description: string | null;
  rotation_type: string;
  participants: string[];
  handoff_time: string;
  handoff_day: number;
  timezone: string;
  is_active: boolean;
  created_by: string;
  created_at: string;
}

export interface OnCallScheduleCreate {
  name: string;
  description?: string;
  rotation_type?: string;
  participants?: string[];
  handoff_time?: string;
  handoff_day?: number;
  timezone?: string;
}

export interface OnCallOverride {
  id: string;
  schedule_id: string;
  user_id: string;
  start_time: string;
  end_time: string;
  reason: string | null;
  created_by: string;
  created_at: string;
}

export interface EscalationPolicy {
  id: string;
  name: string;
  description: string | null;
  steps: { delay_minutes: number; targets: { type: string; id: string }[] }[];
  repeat_count: number;
  is_active: boolean;
  created_by: string;
  created_at: string;
}

export interface EscalationPolicyCreate {
  name: string;
  description?: string;
  steps?: { delay_minutes: number; targets: { type: string; id: string }[] }[];
  repeat_count?: number;
}

export interface CurrentOnCall {
  schedule_id: string;
  schedule_name: string;
  user_id: string | null;
  is_override: boolean;
}

export const oncallApi = {
  listSchedules: () => api.get<OnCallSchedule[]>('/api/v1/oncall/schedules'),
  createSchedule: (data: OnCallScheduleCreate) =>
    api.post<OnCallSchedule>('/api/v1/oncall/schedules', data),
  getSchedule: (id: string) => api.get<OnCallSchedule>(`/api/v1/oncall/schedules/${id}`),
  updateSchedule: (id: string, data: Partial<OnCallScheduleCreate> & { is_active?: boolean }) =>
    api.put<OnCallSchedule>(`/api/v1/oncall/schedules/${id}`, data),
  deleteSchedule: (id: string) => api.delete(`/api/v1/oncall/schedules/${id}`),
  getCurrent: (id: string) => api.get<CurrentOnCall>(`/api/v1/oncall/schedules/${id}/current`),
  listOverrides: (scheduleId: string) =>
    api.get<OnCallOverride[]>(`/api/v1/oncall/schedules/${scheduleId}/overrides`),
  createOverride: (scheduleId: string, data: { user_id: string; start_time: string; end_time: string; reason?: string }) =>
    api.post<OnCallOverride>(`/api/v1/oncall/schedules/${scheduleId}/overrides`, data),
  deleteOverride: (id: string) => api.delete(`/api/v1/oncall/overrides/${id}`),
  listPolicies: () => api.get<EscalationPolicy[]>('/api/v1/oncall/policies'),
  createPolicy: (data: EscalationPolicyCreate) =>
    api.post<EscalationPolicy>('/api/v1/oncall/policies', data),
  updatePolicy: (id: string, data: Partial<EscalationPolicyCreate> & { is_active?: boolean }) =>
    api.put<EscalationPolicy>(`/api/v1/oncall/policies/${id}`, data),
  deletePolicy: (id: string) => api.delete(`/api/v1/oncall/policies/${id}`),
  whoami: () => api.get<CurrentOnCall[]>('/api/v1/oncall/whoami'),
};
