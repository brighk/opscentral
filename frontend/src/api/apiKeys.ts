import api from './client';

export interface APIKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[] | null;
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string;
}

export interface APIKeyCreated extends APIKey {
  raw_key: string;
}

export interface APIKeyCreateRequest {
  name: string;
  scopes?: string[];
  expires_at?: string;
}

export const apiKeysApi = {
  list: () => api.get<APIKey[]>('/api/v1/api-keys'),
  create: (data: APIKeyCreateRequest) => api.post<APIKeyCreated>('/api/v1/api-keys', data),
  revoke: (id: string) => api.delete(`/api/v1/api-keys/${id}`),
};
