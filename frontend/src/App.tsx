import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { useEffect } from 'react';

import { theme } from './styles/theme';
import { useAuthStore } from './store/authStore';
import AppLayout from './layouts/AppLayout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import MonitoringPage from './pages/MonitoringPage';
import AssetsPage from './pages/AssetsPage';
import AssetDetailPage from './pages/AssetDetailPage';
import AlertsPage from './pages/AlertsPage';
import AgentsPage from './pages/AgentsPage';
import SettingsPage from './pages/SettingsPage';
import ProcessesPage from './pages/ProcessesPage';
import HealthChecksPage from './pages/HealthChecksPage';
import NotificationChannelsPage from './pages/NotificationChannelsPage';
import VulnerabilitiesPage from './pages/VulnerabilitiesPage';
import UserManagementPage from './pages/UserManagementPage';
import CustomDashboardsPage from './pages/CustomDashboardsPage';
import UptimePage from './pages/UptimePage';
import BillingPage from './pages/BillingPage';
import ReportsPage from './pages/ReportsPage';
import RemoteActionsPage from './pages/RemoteActionsPage';
import IntegrationsPage from './pages/IntegrationsPage';
import RunbooksPage from './pages/RunbooksPage';
import IncidentsPage from './pages/IncidentsPage';
import IncidentDetailPage from './pages/IncidentDetailPage';
import OnCallPage from './pages/OnCallPage';
import MaintenancePage from './pages/MaintenancePage';

import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30000,
    },
  },
});

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
}

function AuthRedirect({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? <Navigate to="/" /> : <>{children}</>;
}

export default function App() {
  const { loadUser } = useAuthStore();

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  return (
    <QueryClientProvider client={queryClient}>
      <MantineProvider theme={theme}>
        <Notifications position="top-right" />
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<AuthRedirect><LoginPage /></AuthRedirect>} />
            <Route path="/register" element={<AuthRedirect><RegisterPage /></AuthRedirect>} />
            <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
              <Route index element={<DashboardPage />} />
              <Route path="monitoring" element={<MonitoringPage />} />
              <Route path="processes" element={<ProcessesPage />} />
              <Route path="assets" element={<AssetsPage />} />
              <Route path="assets/:id" element={<AssetDetailPage />} />
              <Route path="alerts" element={<AlertsPage />} />
              <Route path="health-checks" element={<HealthChecksPage />} />
              <Route path="agents" element={<AgentsPage />} />
              <Route path="notifications" element={<NotificationChannelsPage />} />
              <Route path="vulnerabilities" element={<VulnerabilitiesPage />} />
              <Route path="users" element={<UserManagementPage />} />
              <Route path="custom-dashboards" element={<CustomDashboardsPage />} />
              <Route path="uptime" element={<UptimePage />} />
              <Route path="billing" element={<BillingPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="remote-actions" element={<RemoteActionsPage />} />
              <Route path="integrations" element={<IntegrationsPage />} />
              <Route path="runbooks" element={<RunbooksPage />} />
              <Route path="incidents" element={<IncidentsPage />} />
              <Route path="incidents/:id" element={<IncidentDetailPage />} />
              <Route path="oncall" element={<OnCallPage />} />
              <Route path="maintenance" element={<MaintenancePage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </BrowserRouter>
      </MantineProvider>
    </QueryClientProvider>
  );
}
