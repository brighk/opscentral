import api from './client';

export interface Vulnerability {
  id: string;
  asset_id: string;
  asset_hostname: string;
  software_name: string;
  installed_version: string;
  cve_id: string | null;
  severity: string;
  score: number | null;
  summary: string;
  fixed_version: string | null;
  is_resolved: boolean;
  discovered_at: string;
}

export interface VulnSummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
  total: number;
}

export interface VulnScan {
  id: string;
  tenant_id: string;
  started_at: string;
  completed_at: string | null;
  assets_scanned: number;
  packages_scanned: number;
  vulnerabilities_found: number;
}

export const vulnerabilitiesApi = {
  list: (params?: { severity?: string; asset_id?: string; resolved?: boolean }) =>
    api.get<Vulnerability[]>('/api/v1/vulnerabilities', { params }).then(r => r.data),

  summary: () =>
    api.get<VulnSummary>('/api/v1/vulnerabilities/summary').then(r => r.data),

  byAsset: () =>
    api.get('/api/v1/vulnerabilities/by-asset').then(r => r.data),

  scans: () =>
    api.get<VulnScan[]>('/api/v1/vulnerabilities/scans').then(r => r.data),

  triggerScan: () =>
    api.post('/api/v1/vulnerabilities/scan').then(r => r.data),

  resolve: (id: string) =>
    api.post(`/api/v1/vulnerabilities/${id}/resolve`).then(r => r.data),
};
