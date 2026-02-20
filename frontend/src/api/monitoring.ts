import api from './client';

export interface MetricDataPoint {
  time_bucket: string;
  metric_name: string;
  agent_id: string;
  avg_value: number;
  min_value: number;
  max_value: number;
}

export interface StatusOverview {
  total_agents: number;
  online_agents: number;
  offline_agents: number;
  total_assets: number;
  active_alerts: number;
  metrics_last_hour: number;
}

export const monitoringApi = {
  getMetrics: (params?: {
    agent_id?: string;
    metric_name?: string;
    start?: string;
    end?: string;
    bucket_seconds?: number;
  }) => api.get<MetricDataPoint[]>('/api/v1/monitoring/metrics', { params }),

  getStatus: () => api.get<StatusOverview>('/api/v1/monitoring/status'),
};
