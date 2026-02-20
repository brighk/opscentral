import api from './client';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  company_name: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  is_admin: boolean;
  tenant_id: string;
  tenant_name: string | null;
}

export const authApi = {
  register: (data: RegisterRequest) =>
    api.post<TokenResponse>('/api/v1/auth/register', data),

  login: (data: LoginRequest) =>
    api.post<TokenResponse>('/api/v1/auth/login', data),

  getMe: () =>
    api.get<UserResponse>('/api/v1/auth/me'),

  refresh: (refreshToken: string) =>
    api.post<TokenResponse>('/api/v1/auth/refresh', { refresh_token: refreshToken }),
};
