import { useState } from 'react';
import {
  Stack, Title, Paper, Table, Badge, Button, Group, Tabs, Text,
  Modal, TextInput, Select, NumberInput, Switch, Center, Loader,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconPlus, IconBell, IconList } from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { alertingApi, type AlertRuleCreate } from '../api/alerting';

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'red',
  warning: 'yellow',
  info: 'blue',
};

const STATUS_COLORS: Record<string, string> = {
  firing: 'red',
  acknowledged: 'orange',
  resolved: 'green',
};

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);

  const { data: alerts, isLoading: alertsLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => alertingApi.listAlerts().then(r => r.data),
    refetchInterval: 15000,
  });

  const { data: rules, isLoading: rulesLoading } = useQuery({
    queryKey: ['alertRules'],
    queryFn: () => alertingApi.listRules().then(r => r.data),
  });

  const ackMutation = useMutation({
    mutationFn: alertingApi.acknowledgeAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  });

  const resolveMutation = useMutation({
    mutationFn: alertingApi.resolveAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  });

  const deleteRuleMutation = useMutation({
    mutationFn: alertingApi.deleteRule,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alertRules'] }),
  });

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Alerts</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={open}>New Rule</Button>
      </Group>

      <Tabs defaultValue="alerts">
        <Tabs.List>
          <Tabs.Tab value="alerts" leftSection={<IconBell size={14} />}>Alerts</Tabs.Tab>
          <Tabs.Tab value="rules" leftSection={<IconList size={14} />}>Rules</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="alerts" pt="md">
          {alertsLoading ? <Center h={200}><Loader /></Center> : (
            <Paper withBorder radius="md">
              {alerts && alerts.length > 0 ? (
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Severity</Table.Th>
                      <Table.Th>Title</Table.Th>
                      <Table.Th>Status</Table.Th>
                      <Table.Th>Fired At</Table.Th>
                      <Table.Th>Actions</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {alerts.map(alert => (
                      <Table.Tr key={alert.id}>
                        <Table.Td>
                          <Badge color={SEVERITY_COLORS[alert.severity] || 'gray'}>{alert.severity}</Badge>
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm">{alert.title}</Text>
                          {alert.message && <Text size="xs" c="dimmed">{alert.message}</Text>}
                        </Table.Td>
                        <Table.Td>
                          <Badge variant="light" color={STATUS_COLORS[alert.status] || 'gray'}>{alert.status}</Badge>
                        </Table.Td>
                        <Table.Td>{new Date(alert.fired_at).toLocaleString()}</Table.Td>
                        <Table.Td>
                          <Group gap="xs">
                            {alert.status === 'firing' && (
                              <Button size="xs" variant="light" onClick={() => ackMutation.mutate(alert.id)}>
                                Acknowledge
                              </Button>
                            )}
                            {alert.status !== 'resolved' && (
                              <Button size="xs" variant="light" color="green" onClick={() => resolveMutation.mutate(alert.id)}>
                                Resolve
                              </Button>
                            )}
                          </Group>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              ) : (
                <Text p="xl" ta="center" c="dimmed">No alerts. All systems are healthy!</Text>
              )}
            </Paper>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="rules" pt="md">
          {rulesLoading ? <Center h={200}><Loader /></Center> : (
            <Paper withBorder radius="md">
              {rules && rules.length > 0 ? (
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Name</Table.Th>
                      <Table.Th>Metric</Table.Th>
                      <Table.Th>Condition</Table.Th>
                      <Table.Th>Severity</Table.Th>
                      <Table.Th>Enabled</Table.Th>
                      <Table.Th>Actions</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {rules.map(rule => (
                      <Table.Tr key={rule.id}>
                        <Table.Td>{rule.name}</Table.Td>
                        <Table.Td>{rule.metric_name}</Table.Td>
                        <Table.Td>{rule.condition} {rule.threshold}</Table.Td>
                        <Table.Td>
                          <Badge color={SEVERITY_COLORS[rule.severity] || 'gray'}>{rule.severity}</Badge>
                        </Table.Td>
                        <Table.Td>
                          <Badge color={rule.is_enabled ? 'green' : 'gray'}>{rule.is_enabled ? 'Yes' : 'No'}</Badge>
                        </Table.Td>
                        <Table.Td>
                          <Button size="xs" variant="light" color="red" onClick={() => deleteRuleMutation.mutate(rule.id)}>
                            Delete
                          </Button>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              ) : (
                <Text p="xl" ta="center" c="dimmed">No alert rules configured yet.</Text>
              )}
            </Paper>
          )}
        </Tabs.Panel>
      </Tabs>

      <CreateRuleModal opened={opened} onClose={close} />
    </Stack>
  );
}

function CreateRuleModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [metricName, setMetricName] = useState('cpu_percent');
  const [condition, setCondition] = useState('gt');
  const [threshold, setThreshold] = useState<number>(80);
  const [severity, setSeverity] = useState('warning');
  const [notifyEmail, setNotifyEmail] = useState(true);

  const createMutation = useMutation({
    mutationFn: (data: AlertRuleCreate) => alertingApi.createRule(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alertRules'] });
      onClose();
    },
  });

  const handleSubmit = () => {
    createMutation.mutate({
      name,
      metric_name: metricName,
      condition,
      threshold,
      severity,
      notify_email: notifyEmail,
    });
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Create Alert Rule" size="md">
      <Stack>
        <TextInput label="Rule Name" value={name} onChange={e => setName(e.target.value)} placeholder="e.g., High CPU Alert" />
        <Select
          label="Metric"
          data={[
            { value: 'cpu_percent', label: 'CPU Usage (%)' },
            { value: 'memory_percent', label: 'Memory Usage (%)' },
            { value: 'disk_percent', label: 'Disk Usage (%)' },
            { value: 'load_avg_1m', label: 'Load Average (1m)' },
          ]}
          value={metricName}
          onChange={v => v && setMetricName(v)}
        />
        <Group grow>
          <Select
            label="Condition"
            data={[
              { value: 'gt', label: 'Greater than' },
              { value: 'gte', label: 'Greater or equal' },
              { value: 'lt', label: 'Less than' },
              { value: 'lte', label: 'Less or equal' },
            ]}
            value={condition}
            onChange={v => v && setCondition(v)}
          />
          <NumberInput label="Threshold" value={threshold} onChange={v => setThreshold(Number(v))} />
        </Group>
        <Select
          label="Severity"
          data={[
            { value: 'info', label: 'Info' },
            { value: 'warning', label: 'Warning' },
            { value: 'critical', label: 'Critical' },
          ]}
          value={severity}
          onChange={v => v && setSeverity(v)}
        />
        <Switch label="Email notifications" checked={notifyEmail} onChange={e => setNotifyEmail(e.currentTarget.checked)} />
        <Button onClick={handleSubmit} loading={createMutation.isPending} disabled={!name}>
          Create Rule
        </Button>
      </Stack>
    </Modal>
  );
}
