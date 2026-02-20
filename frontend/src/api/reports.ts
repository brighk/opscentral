import api from './client';

export interface Report {
  id: string;
  report_type: string;
  format: string;
  status: string;
  file_path: string | null;
  parameters: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
}

export interface ComplianceScore {
  overall_score: number;
  patching_score: number;
  uptime_score: number;
  vulnerability_score: number;
  agent_coverage_score: number;
  calculated_at: string;
}

export interface ReportSchedule {
  id: string;
  report_type: string;
  frequency: string;
  recipients: string[] | null;
  is_active: boolean;
  next_run_at: string | null;
  created_at: string;
}

export const reportsApi = {
  list: () => api.get<Report[]>('/api/v1/reports'),
  generate: (reportType: string, format: string = 'pdf') =>
    api.post<Report>('/api/v1/reports', { report_type: reportType, format }),
  delete: (id: string) => api.delete(`/api/v1/reports/${id}`),
  download: (id: string) => api.get(`/api/v1/reports/${id}/download`, { responseType: 'blob' }),
  getCompliance: () => api.get<ComplianceScore | null>('/api/v1/reports/compliance'),
  getComplianceHistory: (days: number = 30) =>
    api.get<ComplianceScore[]>(`/api/v1/reports/compliance/history?days=${days}`),
  listSchedules: () => api.get<ReportSchedule[]>('/api/v1/reports/schedules'),
  createSchedule: (data: { report_type: string; frequency: string; recipients?: string[] }) =>
    api.post<ReportSchedule>('/api/v1/reports/schedules', data),
  deleteSchedule: (id: string) => api.delete(`/api/v1/reports/schedules/${id}`),
};
