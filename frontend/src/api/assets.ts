import api from './client';

export interface Asset {
  id: string;
  hostname: string;
  asset_type: string;
  os_type: string | null;
  os_version: string | null;
  cpu_model: string | null;
  cpu_cores: number | null;
  ram_total_gb: number | null;
  disk_total_gb: number | null;
  ip_addresses: string[] | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AssetDetail extends Asset {
  agent_id: string | null;
  mac_addresses: string[] | null;
  system_info: Record<string, unknown> | null;
  software: Software[];
}

export interface Software {
  id: string;
  name: string;
  version: string | null;
  publisher: string | null;
}

export const assetsApi = {
  list: () => api.get<Asset[]>('/api/v1/assets'),
  get: (id: string) => api.get<AssetDetail>(`/api/v1/assets/${id}`),
  getSoftware: (id: string) => api.get<Software[]>(`/api/v1/assets/${id}/software`),
};
