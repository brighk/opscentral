import { useState } from 'react';
import { Stack, Title, Paper, Text, Select, SimpleGrid, Center, Loader } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { monitoringApi } from '../api/monitoring';
import { agentsApi } from '../api/agents';

const METRIC_OPTIONS = [
  { value: 'cpu_percent', label: 'CPU Usage (%)' },
  { value: 'memory_percent', label: 'Memory Usage (%)' },
  { value: 'disk_percent', label: 'Disk Usage (%)' },
  { value: 'load_avg_1m', label: 'Load Average (1m)' },
  { value: 'load_avg_5m', label: 'Load Average (5m)' },
  { value: 'net_bytes_sent_mb', label: 'Network Sent (MB)' },
  { value: 'net_bytes_recv_mb', label: 'Network Received (MB)' },
];

export default function MonitoringPage() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<string>('cpu_percent');

  const { data: agents } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentsApi.list().then(r => r.data),
  });

  const { data: metrics, isLoading } = useQuery({
    queryKey: ['metrics', selectedMetric, selectedAgent],
    queryFn: () =>
      monitoringApi.getMetrics({
        metric_name: selectedMetric,
        agent_id: selectedAgent || undefined,
      }).then(r => r.data),
    refetchInterval: 30000,
  });

  const agentOptions = (agents || []).map(a => ({
    value: a.id,
    label: a.display_name || a.hostname,
  }));

  // Group by agent for multi-line chart
  const agentGroups: Record<string, { time: string; value: number }[]> = {};
  (metrics || []).forEach(m => {
    const key = m.agent_id;
    if (!agentGroups[key]) agentGroups[key] = [];
    agentGroups[key].push({
      time: new Date(m.time_bucket).toLocaleTimeString(),
      value: m.avg_value,
    });
  });

  // For a single-series view, flatten
  const chartData = (metrics || []).map(m => ({
    time: new Date(m.time_bucket).toLocaleTimeString(),
    value: m.avg_value,
    min: m.min_value,
    max: m.max_value,
  }));

  return (
    <Stack>
      <Title order={2}>Monitoring</Title>

      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <Select
          label="Agent"
          placeholder="All agents"
          data={agentOptions}
          value={selectedAgent}
          onChange={setSelectedAgent}
          clearable
        />
        <Select
          label="Metric"
          data={METRIC_OPTIONS}
          value={selectedMetric}
          onChange={(v) => v && setSelectedMetric(v)}
        />
      </SimpleGrid>

      <Paper withBorder p="md" radius="md">
        <Text fw={600} mb="md">
          {METRIC_OPTIONS.find(m => m.value === selectedMetric)?.label || selectedMetric}
        </Text>
        {isLoading ? (
          <Center h={350}><Loader /></Center>
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" fontSize={11} />
              <YAxis fontSize={11} />
              <Tooltip />
              <Line type="monotone" dataKey="value" stroke="#228be6" strokeWidth={2} name="Average" dot={false} />
              <Line type="monotone" dataKey="min" stroke="#40c057" strokeWidth={1} name="Min" dot={false} strokeDasharray="5 5" />
              <Line type="monotone" dataKey="max" stroke="#fa5252" strokeWidth={1} name="Max" dot={false} strokeDasharray="5 5" />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <Center h={350}>
            <Text c="dimmed">No metric data available. Install an agent to start collecting metrics.</Text>
          </Center>
        )}
      </Paper>
    </Stack>
  );
}
