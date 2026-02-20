import { AppShell, Burger, Group, NavLink, Text, UnstyledButton, Menu, Avatar } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconDashboard,
  IconServer,
  IconDeviceDesktopAnalytics,
  IconBell,
  IconRobot,
  IconSettings,
  IconLogout,
  IconChevronDown,
  IconActivity,
  IconActivityHeartbeat,
  IconBellRinging,
  IconShieldCheck,
  IconUsers,
  IconLayoutDashboard,
  IconWorldWww,
  IconCreditCard,
  IconReport,
  IconTerminal,
  IconPlugConnected,
  IconBook2,
  IconUrgent,
  IconPhoneCall,
  IconCalendarOff,
} from '@tabler/icons-react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

const navItems = [
  { label: 'Dashboard', icon: IconDashboard, path: '/' },
  { label: 'Monitoring', icon: IconDeviceDesktopAnalytics, path: '/monitoring' },
  { label: 'Processes', icon: IconActivity, path: '/processes' },
  { label: 'Assets', icon: IconServer, path: '/assets' },
  { label: 'Alerts', icon: IconBell, path: '/alerts' },
  { label: 'Health Checks', icon: IconActivityHeartbeat, path: '/health-checks' },
  { label: 'Agents', icon: IconRobot, path: '/agents' },
  { label: 'Notifications', icon: IconBellRinging, path: '/notifications' },
  { label: 'Vulnerabilities', icon: IconShieldCheck, path: '/vulnerabilities' },
  { label: 'Uptime', icon: IconWorldWww, path: '/uptime' },
  { label: 'Remote Actions', icon: IconTerminal, path: '/remote-actions' },
  { label: 'Integrations', icon: IconPlugConnected, path: '/integrations' },
  { label: 'Runbooks', icon: IconBook2, path: '/runbooks' },
  { label: 'Incidents', icon: IconUrgent, path: '/incidents' },
  { label: 'On-Call', icon: IconPhoneCall, path: '/oncall' },
  { label: 'Maintenance', icon: IconCalendarOff, path: '/maintenance' },
  { label: 'Reports', icon: IconReport, path: '/reports' },
  { label: 'Dashboards', icon: IconLayoutDashboard, path: '/custom-dashboards' },
  { label: 'Billing', icon: IconCreditCard, path: '/billing' },
  { label: 'Users', icon: IconUsers, path: '/users' },
  { label: 'Settings', icon: IconSettings, path: '/settings' },
];

export default function AppLayout() {
  const [opened, { toggle }] = useDisclosure();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 250, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Text size="xl" fw={700} c="blue">OpsCentral</Text>
          </Group>
          <Menu shadow="md" width={200}>
            <Menu.Target>
              <UnstyledButton>
                <Group gap="xs">
                  <Avatar size="sm" radius="xl" color="blue">
                    {user?.full_name?.charAt(0) || 'U'}
                  </Avatar>
                  <Text size="sm" visibleFrom="sm">{user?.full_name}</Text>
                  <IconChevronDown size={14} />
                </Group>
              </UnstyledButton>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Label>{user?.email}</Menu.Label>
              <Menu.Item leftSection={<IconSettings size={14} />} onClick={() => navigate('/settings')}>
                Settings
              </Menu.Item>
              <Menu.Divider />
              <Menu.Item color="red" leftSection={<IconLogout size={14} />} onClick={handleLogout}>
                Logout
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            label={item.label}
            leftSection={<item.icon size={20} />}
            active={
              item.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.path)
            }
            onClick={() => {
              navigate(item.path);
              toggle();
            }}
            mb={4}
          />
        ))}
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
