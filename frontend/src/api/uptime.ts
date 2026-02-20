import api from './client';

export interface UptimeStat {
  check_id: string;
  name: string;
  check_type: string;
  target: string;
  status: string;
  uptime_percent: number | null;
  total_checks: number;
  successful_checks: number;
  avg_response_time_ms: number | null;
  min_response_time_ms: number | null;
  max_response_time_ms: number | null;
  last_checked_at: string | null;
  ssl_certificate: SslCertificate | null;
}

export interface SslCertificate {
  issuer: string | null;
  subject: string | null;
  not_before: string | null;
  not_after: string | null;
  days_until_expiry: number | null;
  is_expired: boolean | null;
  is_expiring_soon: boolean | null;
  error?: string;
}

export interface ResponseTimePoint {
  timestamp: string;
  response_time_ms: number | null;
  status: string;
  status_code: number | null;
}

export const uptimeApi = {
  stats: (params?: { check_id?: string; period?: string }) =>
    api.get<UptimeStat[]>('/api/v1/uptime/stats', { params }).then(r => r.data),

  responseTimes: (checkId: string, period?: string) =>
    api.get<ResponseTimePoint[]>(`/api/v1/uptime/response-times/${checkId}`, {
      params: { period: period || '24h' },
    }).then(r => r.data),

  sslInfo: (checkId: string) =>
    api.get(`/api/v1/uptime/ssl/${checkId}`).then(r => r.data),
};
