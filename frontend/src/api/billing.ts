import api from './client';

export interface Subscription {
  id: string;
  plan: string;
  status: string;
  asset_limit: number;
  asset_count: number;
  current_period_start: string | null;
  current_period_end: string | null;
  has_billing_portal: boolean;
  created_at: string;
}

export interface Plan {
  key: string;
  name: string;
  price_monthly: number;
  price_yearly: number;
  asset_limit: number;
  features: string[];
}

export interface UsageStats {
  asset_count: number;
  asset_limit: number;
  agent_count: number;
  alert_rule_count: number;
  plan: string;
}

export const billingApi = {
  getSubscription: () => api.get<Subscription>('/api/v1/billing/subscription'),
  getPlans: () => api.get<Plan[]>('/api/v1/billing/plans'),
  getUsage: () => api.get<UsageStats>('/api/v1/billing/usage'),
  createCheckout: (plan: string, billingPeriod: string = 'monthly') =>
    api.post<{ checkout_url: string }>('/api/v1/billing/checkout', { plan, billing_period: billingPeriod }),
  createPortal: () => api.post<{ portal_url: string }>('/api/v1/billing/portal'),
};
