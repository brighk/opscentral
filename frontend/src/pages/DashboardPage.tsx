import { SimpleGrid, Paper, Text, Group, ThemeIcon, Stack, Title, Alert as MantineAlert, Table, Badge, Loader, Center } from '@mantine/core';
import { IconServer, IconRobot, IconBell, IconActivity, IconAlertTriangle } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { monitoringApi } from '../api/monitoring';
import { alertingApi } from '../api/alerting';
import { useWebSocket } from '../hooks/useWebSocket';
import { useCallback } from 'react';

function StatCard({ title, value, icon: Icon, color }: { title: string; value: number | string; icon: typeof IconServer; color: string }) {
  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between">
        <div>
          <Text size="xs" c="dimmed" tt="uppercase" fw={700}>{title}</Text>
          <Text size="xl" fw={700} mt={4}>{value}</Text>
        </div>
        <ThemeIcon color={color} variant="light" size={48} radius="md">
          <Icon size={28} />
        </ThemeIcon>
      </Group>
    </Paper>
  );
}

export default function DashboardPage() {
  const queryClient = useQueryClient();

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['status'],
    queryFn: () => monitoringApi.getStatus().then(r => r.data),
    refetchInterval: 30000,
  });

  const { data: alerts } = useQuery({
    queryKey: ['alerts', 'firing'],
    queryFn: () => alertingApi.listAlerts('firing').then(r => r.data.items),
    refetchInterval: 30000,
  });

  const { data: metrics } = useQuery({
    queryKey: ['metrics', 'cpu'],
    queryFn: () => monitoringApi.getMetrics({ metric_name: 'cpu_percent' }).then(r => r.data),
    refetchInterval: 60000,
  });

  const { data: memMetrics } = useQuery({
    queryKey: ['metrics', 'memory'],
    queryFn: () => monitoringApi.getMetrics({ metric_name: 'memory_percent' }).then(r => r.data),
    refetchInterval: 60000,
  });

  const handleWsMessage = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['status'] });
    queryClient.invalidateQueries({ queryKey: ['metrics'] });
  }, [queryClient]);

  const { connected } = useWebSocket({
    onMessage: handleWsMessage,
    enabled: true,
  });

  if (statusLoading) {
    return <Center h={300}><Loader size="lg" /></Center>;
  }

  const cpuData = (metrics || []).map(m => ({
    time: new Date(m.time_bucket).toLocaleTimeString(),
    value: m.avg_value,
  }));

  const memData = (memMetrics || []).map(m => ({
    time: new Date(m.time_bucket).toLocaleTimeString(),
    value: m.avg_value,
  }));

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Dashboard</Title>
        <Badge variant="dot" color={connected ? 'green' : 'gray'} size="lg">
          {connected ? 'Live' : 'Connecting...'}
        </Badge>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        <StatCard title="Total Agents" value={status?.total_agents ?? 0} icon={IconRobot} color="blue" />
        <StatCard title="Online Agents" value={status?.online_agents ?? 0} icon={IconActivity} color="green" />
        <StatCard title="Total Assets" value={status?.total_assets ?? 0} icon={IconServer} color="violet" />
        <StatCard title="Active Alerts" value={status?.active_alerts ?? 0} icon={IconBell} color={status?.active_alerts ? 'red' : 'gray'} />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Paper withBorder p="md" radius="md">
          <Text fw={600} mb="sm">CPU Usage (%)</Text>
          {cpuData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={cpuData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" fontSize={11} />
                <YAxis domain={[0, 100]} fontSize={11} />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#228be6" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <Center h={250}>
              <Text c="dimmed">No CPU data yet. Install an agent to start monitoring.</Text>
            </Center>
          )}
        </Paper>

        <Paper withBorder p="md" radius="md">
          <Text fw={600} mb="sm">Memory Usage (%)</Text>
          {memData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={memData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" fontSize={11} />
                <YAxis domain={[0, 100]} fontSize={11} />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#40c057" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <Center h={250}>
              <Text c="dimmed">No memory data yet. Install an agent to start monitoring.</Text>
            </Center>
          )}
        </Paper>
      </SimpleGrid>

      <Paper withBorder p="md" radius="md">
        <Text fw={600} mb="sm">Recent Alerts</Text>
        {alerts && alerts.length > 0 ? (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Severity</Table.Th>
                <Table.Th>Title</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Fired At</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {alerts.slice(0, 10).map(alert => (
                <Table.Tr key={alert.id}>
                  <Table.Td>
                    <Badge color={alert.severity === 'critical' ? 'red' : alert.severity === 'warning' ? 'yellow' : 'blue'}>
                      {alert.severity}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{alert.title}</Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={alert.status === 'firing' ? 'red' : 'green'}>
                      {alert.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{new Date(alert.fired_at).toLocaleString()}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        ) : (
          <MantineAlert icon={<IconAlertTriangle size={16} />} color="gray" variant="light">
            No active alerts. Your systems are healthy!
          </MantineAlert>
        )}
      </Paper>
    </Stack>
  );
}
