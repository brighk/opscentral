import { useState } from 'react';
import {
  Stack, Title, Paper, Table, Badge, Button, Group, Text,
  Modal, TextInput, Select, NumberInput, Switch, Center, Loader, ActionIcon,
  Timeline,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconPlus, IconTrash, IconPlayerPlay, IconHistory,
  IconCircleCheck, IconCircleX,
} from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { healthchecksApi, type CreateHealthCheck, type HealthCheckLog } from '../api/healthchecks';
import { notifications } from '@mantine/notifications';

const STATUS_COLORS: Record<string, string> = {
  up: 'green',
  down: 'red',
  unknown: 'gray',
};

export default function HealthChecksPage() {
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [logsCheckId, setLogsCheckId] = useState<string | null>(null);
  const [logsCheckName, setLogsCheckName] = useState('');

  const { data: checks, isLoading } = useQuery({
    queryKey: ['healthchecks'],
    queryFn: () => healthchecksApi.list().then(r => r.data),
    refetchInterval: 15000,
  });

  const deleteMutation = useMutation({
    mutationFn: healthchecksApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['healthchecks'] }),
  });

  const testMutation = useMutation({
    mutationFn: healthchecksApi.test,
    onSuccess: () => {
      notifications.show({ title: 'Test sent', message: 'Health check test executed', color: 'green' });
      queryClient.invalidateQueries({ queryKey: ['healthchecks'] });
    },
  });

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Service Health Checks</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={open}>Add Check</Button>
      </Group>

      {isLoading ? (
        <Center h={300}><Loader /></Center>
      ) : (
        <Paper withBorder radius="md">
          {checks && checks.length > 0 ? (
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Target</Table.Th>
                  <Table.Th>Response Time</Table.Th>
                  <Table.Th>Last Checked</Table.Th>
                  <Table.Th>Failures</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {checks.map(check => (
                  <Table.Tr key={check.id}>
                    <Table.Td>
                      <Badge color={STATUS_COLORS[check.status] || 'gray'} variant="filled">
                        {check.status.toUpperCase()}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" fw={500}>{check.name}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge variant="light">{check.check_type.toUpperCase()}</Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" ff="monospace" truncate maw={250}>{check.target}</Text>
                    </Table.Td>
                    <Table.Td>
                      {check.last_response_time_ms != null ? (
                        <Text size="sm" c={check.last_response_time_ms > 1000 ? 'orange' : 'green'}>
                          {check.last_response_time_ms.toFixed(0)} ms
                        </Text>
                      ) : (
                        <Text size="sm" c="dimmed">-</Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs">
                        {check.last_checked_at ? new Date(check.last_checked_at).toLocaleString() : 'Never'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      {check.consecutive_failures > 0 ? (
                        <Badge color="red" variant="light">{check.consecutive_failures}</Badge>
                      ) : (
                        <Text size="sm" c="dimmed">0</Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <ActionIcon variant="light" color="cyan"
                          onClick={() => { setLogsCheckId(check.id); setLogsCheckName(check.name); }}
                          title="View History">
                          <IconHistory size={16} />
                        </ActionIcon>
                        <ActionIcon variant="light" color="blue" onClick={() => testMutation.mutate(check.id)}
                          loading={testMutation.isPending}>
                          <IconPlayerPlay size={16} />
                        </ActionIcon>
                        <ActionIcon variant="light" color="red" onClick={() => deleteMutation.mutate(check.id)}>
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          ) : (
            <Text p="xl" ta="center" c="dimmed">No health checks configured yet. Add one to start monitoring services.</Text>
          )}
        </Paper>
      )}

      <CreateHealthCheckModal opened={opened} onClose={close} />
      <HealthCheckLogsModal
        checkId={logsCheckId}
        checkName={logsCheckName}
        onClose={() => setLogsCheckId(null)}
      />
    </Stack>
  );
}

function HealthCheckLogsModal({
  checkId,
  checkName,
  onClose,
}: {
  checkId: string | null;
  checkName: string;
  onClose: () => void;
}) {
  const { data: logs, isLoading } = useQuery({
    queryKey: ['healthcheckLogs', checkId],
    queryFn: () => healthchecksApi.getLogs(checkId!, 48).then(r => r.data),
    enabled: !!checkId,
    refetchInterval: 30000,
  });

  // Group consecutive same-status logs and show transitions
  const transitions = logs ? getStatusTransitions(logs) : [];

  return (
    <Modal opened={!!checkId} onClose={onClose} title={`Check History — ${checkName}`} size="lg">
      {isLoading ? (
        <Center h={200}><Loader /></Center>
      ) : transitions.length > 0 ? (
        <Stack>
          <Paper withBorder p="md" radius="md">
            <UptimeSummary logs={logs || []} />
          </Paper>
          <Timeline active={0} bulletSize={24} lineWidth={2}>
            {transitions.map((t, i) => (
              <Timeline.Item
                key={i}
                bullet={t.status === 'up'
                  ? <IconCircleCheck size={12} />
                  : <IconCircleX size={12} />
                }
                color={t.status === 'up' ? 'green' : 'red'}
                title={
                  <Group gap="xs">
                    <Badge size="sm" color={t.status === 'up' ? 'green' : 'red'}>
                      {t.status.toUpperCase()}
                    </Badge>
                    <Text size="xs" c="dimmed">
                      {new Date(t.checked_at).toLocaleString()}
                    </Text>
                    {t.response_time_ms != null && (
                      <Text size="xs" c="dimmed">
                        ({t.response_time_ms.toFixed(0)} ms)
                      </Text>
                    )}
                  </Group>
                }
              >
                {t.error && <Text size="sm" c="red" mt={4}>{t.error}</Text>}
                {t.status_code && (
                  <Text size="xs" c="dimmed">HTTP {t.status_code}</Text>
                )}
                {t.count > 1 && (
                  <Text size="xs" c="dimmed" mt={2}>
                    Repeated {t.count} times until {new Date(t.last_at).toLocaleString()}
                  </Text>
                )}
              </Timeline.Item>
            ))}
          </Timeline>
        </Stack>
      ) : (
        <Text ta="center" c="dimmed" py="xl">
          No check results yet. The check will run on its configured interval.
        </Text>
      )}
    </Modal>
  );
}

function UptimeSummary({ logs }: { logs: HealthCheckLog[] }) {
  if (logs.length === 0) return null;
  const upCount = logs.filter(l => l.status === 'up').length;
  const total = logs.length;
  const uptimePercent = ((upCount / total) * 100).toFixed(1);
  const avgResponseTime = logs
    .filter(l => l.response_time_ms != null)
    .reduce((sum, l) => sum + (l.response_time_ms || 0), 0) / (upCount || 1);

  return (
    <Group justify="space-around">
      <div style={{ textAlign: 'center' }}>
        <Text size="xl" fw={700} c={parseFloat(uptimePercent) >= 99 ? 'green' : parseFloat(uptimePercent) >= 95 ? 'yellow' : 'red'}>
          {uptimePercent}%
        </Text>
        <Text size="xs" c="dimmed">Uptime (last 48h)</Text>
      </div>
      <div style={{ textAlign: 'center' }}>
        <Text size="xl" fw={700}>{total}</Text>
        <Text size="xs" c="dimmed">Total Checks</Text>
      </div>
      <div style={{ textAlign: 'center' }}>
        <Text size="xl" fw={700} c={avgResponseTime > 1000 ? 'orange' : 'green'}>
          {avgResponseTime.toFixed(0)} ms
        </Text>
        <Text size="xs" c="dimmed">Avg Response</Text>
      </div>
    </Group>
  );
}

interface StatusTransition {
  status: string;
  checked_at: string;
  last_at: string;
  response_time_ms: number | null;
  status_code: number | null;
  error: string | null;
  count: number;
}

function getStatusTransitions(logs: HealthCheckLog[]): StatusTransition[] {
  if (logs.length === 0) return [];

  const transitions: StatusTransition[] = [];
  let current: StatusTransition | null = null;

  for (const log of logs) {
    if (!current || current.status !== log.status) {
      if (current) transitions.push(current);
      current = {
        status: log.status,
        checked_at: log.checked_at,
        last_at: log.checked_at,
        response_time_ms: log.response_time_ms,
        status_code: log.status_code,
        error: log.error,
        count: 1,
      };
    } else {
      current.count++;
      current.last_at = log.checked_at;
    }
  }
  if (current) transitions.push(current);

  return transitions;
}

function CreateHealthCheckModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [checkType, setCheckType] = useState('http');
  const [target, setTarget] = useState('');
  const [interval, setInterval] = useState<number>(60);
  const [timeout, setTimeout] = useState<number>(10);
  const [expectedStatus, setExpectedStatus] = useState<number>(200);
  const [httpMethod, setHttpMethod] = useState('GET');
  const [alertAfterFailures, setAlertAfterFailures] = useState<number>(3);
  const [notifyChannels, setNotifyChannels] = useState(true);

  const createMutation = useMutation({
    mutationFn: (data: CreateHealthCheck) => healthchecksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['healthchecks'] });
      onClose();
      setName('');
      setTarget('');
    },
  });

  const handleSubmit = () => {
    createMutation.mutate({
      name,
      check_type: checkType,
      target,
      interval_seconds: interval,
      timeout_seconds: timeout,
      expected_status: checkType === 'http' ? expectedStatus : undefined,
      http_method: httpMethod,
      alert_after_failures: alertAfterFailures,
      notify_channels: notifyChannels,
    });
  };

  const placeholders: Record<string, string> = {
    http: 'https://example.com/health',
    tcp: 'db.example.com:5432',
    dns: 'example.com',
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Add Health Check" size="md">
      <Stack>
        <TextInput label="Name" placeholder="e.g., Production API" value={name} onChange={e => setName(e.target.value)} />
        <Select
          label="Check Type"
          data={[
            { value: 'http', label: 'HTTP/HTTPS' },
            { value: 'tcp', label: 'TCP Port' },
            { value: 'dns', label: 'DNS Resolution' },
          ]}
          value={checkType}
          onChange={v => v && setCheckType(v)}
        />
        <TextInput
          label="Target"
          placeholder={placeholders[checkType] || ''}
          value={target}
          onChange={e => setTarget(e.target.value)}
        />
        {checkType === 'http' && (
          <Group grow>
            <Select
              label="HTTP Method"
              data={['GET', 'POST', 'HEAD', 'PUT'].map(m => ({ value: m, label: m }))}
              value={httpMethod}
              onChange={v => v && setHttpMethod(v)}
            />
            <NumberInput label="Expected Status" value={expectedStatus} onChange={v => setExpectedStatus(Number(v))} />
          </Group>
        )}
        <Group grow>
          <NumberInput label="Check Interval (seconds)" value={interval} onChange={v => setInterval(Number(v))} min={10} />
          <NumberInput label="Timeout (seconds)" value={timeout} onChange={v => setTimeout(Number(v))} min={1} max={60} />
        </Group>
        <NumberInput label="Alert after N consecutive failures" value={alertAfterFailures}
          onChange={v => setAlertAfterFailures(Number(v))} min={1} />
        <Switch label="Notify via configured channels" checked={notifyChannels}
          onChange={e => setNotifyChannels(e.currentTarget.checked)} />
        <Button onClick={handleSubmit} loading={createMutation.isPending} disabled={!name || !target}>
          Create Health Check
        </Button>
      </Stack>
    </Modal>
  );
}
