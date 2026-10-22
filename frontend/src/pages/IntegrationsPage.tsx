import { useState } from 'react';
import {
  Stack, Title, Paper, Text, Group, Badge, Button, Table, Tabs,
  Modal, TextInput, MultiSelect, JsonInput, Center, Loader, ActionIcon,
  Card, SimpleGrid, Drawer,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconPlus, IconTrash, IconTestPipe, IconEye, IconWebhook,
  IconPlugConnected,
} from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import { integrationsApi } from '../api/integrations';
import { apiErrorMessage } from '../api/client';
import type { WebhookEndpoint } from '../api/integrations';

const PROVIDERS = [
  { value: 'pagerduty', label: 'PagerDuty', color: 'green' },
  { value: 'jira', label: 'Jira', color: 'blue' },
  { value: 'opsgenie', label: 'OpsGenie', color: 'violet' },
  { value: 'servicenow', label: 'ServiceNow', color: 'teal' },
];

export default function IntegrationsPage() {
  return (
    <Stack>
      <Title order={2}>Integrations</Title>
      <Tabs defaultValue="webhooks">
        <Tabs.List>
          <Tabs.Tab value="webhooks" leftSection={<IconWebhook size={16} />}>
            Webhooks
          </Tabs.Tab>
          <Tabs.Tab value="integrations" leftSection={<IconPlugConnected size={16} />}>
            External Integrations
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="webhooks" pt="md">
          <WebhooksTab />
        </Tabs.Panel>
        <Tabs.Panel value="integrations" pt="md">
          <ExternalIntegrationsTab />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}

function WebhooksTab() {
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [deliveryEndpoint, setDeliveryEndpoint] = useState<WebhookEndpoint | null>(null);
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);

  const { data: webhooks, isLoading } = useQuery({
    queryKey: ['webhooks'],
    queryFn: () => integrationsApi.listWebhooks().then(r => r.data),
  });

  const { data: eventTypes } = useQuery({
    queryKey: ['eventTypes'],
    queryFn: () => integrationsApi.getEventTypes().then(r => r.data),
  });

  const { data: deliveries } = useQuery({
    queryKey: ['deliveries', deliveryEndpoint?.id],
    queryFn: () => deliveryEndpoint ? integrationsApi.getDeliveries(deliveryEndpoint.id).then(r => r.data) : Promise.resolve([]),
    enabled: !!deliveryEndpoint,
  });

  const createMutation = useMutation({
    mutationFn: () => integrationsApi.createWebhook({ name, url, event_types: selectedEvents }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      closeCreate();
      setName(''); setUrl(''); setSelectedEvents([]);
      notifications.show({ title: 'Webhook Created', message: 'Webhook endpoint created', color: 'blue' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: integrationsApi.deleteWebhook,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['webhooks'] }),
  });

  const testMutation = useMutation({
    mutationFn: integrationsApi.testWebhook,
    onSuccess: () => notifications.show({ title: 'Test Sent', message: 'Test webhook delivered', color: 'green' }),
  });

  if (isLoading) return <Center h={200}><Loader /></Center>;

  return (
    <Stack>
      <Group justify="space-between">
        <Text fw={600}>Webhook Endpoints</Text>
        <Button leftSection={<IconPlus size={16} />} size="sm" onClick={openCreate}>
          Add Webhook
        </Button>
      </Group>

      {webhooks && webhooks.length > 0 ? (
        <Paper withBorder radius="md">
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>URL</Table.Th>
                <Table.Th>Events</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Last Status</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {webhooks.map(wh => (
                <Table.Tr key={wh.id}>
                  <Table.Td>{wh.name}</Table.Td>
                  <Table.Td><Text size="sm" truncate style={{ maxWidth: 200 }}>{wh.url}</Text></Table.Td>
                  <Table.Td><Badge>{wh.event_types.length} events</Badge></Table.Td>
                  <Table.Td>
                    <Badge color={wh.is_active ? 'green' : 'red'}>
                      {wh.is_active ? 'Active' : 'Disabled'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {wh.last_status_code ? (
                      <Badge color={wh.last_status_code < 400 ? 'green' : 'red'}>
                        {wh.last_status_code}
                      </Badge>
                    ) : '-'}
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <ActionIcon variant="light" color="blue" onClick={() => setDeliveryEndpoint(wh)}>
                        <IconEye size={14} />
                      </ActionIcon>
                      <ActionIcon variant="light" color="green" onClick={() => testMutation.mutate(wh.id)}>
                        <IconTestPipe size={14} />
                      </ActionIcon>
                      <ActionIcon variant="light" color="red" onClick={() => deleteMutation.mutate(wh.id)}>
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      ) : (
        <Paper withBorder p="xl" radius="md" ta="center">
          <Title order={4}>No webhooks configured</Title>
          <Text c="dimmed" mt="sm">Add a webhook endpoint to receive event notifications.</Text>
        </Paper>
      )}

      {/* Create Modal */}
      <Modal opened={createOpened} onClose={closeCreate} title="Create Webhook Endpoint" size="md">
        <Stack>
          <TextInput label="Name" placeholder="e.g., Slack Notifications" value={name} onChange={e => setName(e.target.value)} />
          <TextInput label="URL" placeholder="https://example.com/webhook" value={url} onChange={e => setUrl(e.target.value)} />
          <MultiSelect
            label="Event Types"
            placeholder="Select events to subscribe"
            data={eventTypes?.map(et => ({ value: et.key, label: et.key })) || []}
            value={selectedEvents}
            onChange={setSelectedEvents}
            searchable
          />
          <Button onClick={() => createMutation.mutate()} loading={createMutation.isPending} disabled={!name || !url || selectedEvents.length === 0}>
            Create
          </Button>
        </Stack>
      </Modal>

      {/* Delivery Drawer */}
      <Drawer
        opened={!!deliveryEndpoint}
        onClose={() => setDeliveryEndpoint(null)}
        title={`Deliveries — ${deliveryEndpoint?.name}`}
        position="right"
        size="lg"
      >
        {deliveries && deliveries.length > 0 ? (
          <Stack>
            {deliveries.map(d => (
              <Paper key={d.id} withBorder p="sm" radius="sm">
                <Group justify="space-between" mb="xs">
                  <Badge>{d.event_type}</Badge>
                  <Group gap="xs">
                    <Badge color={d.status_code && d.status_code < 400 ? 'green' : 'red'}>
                      {d.status_code || 'Error'}
                    </Badge>
                    {d.duration_ms && <Text size="xs" c="dimmed">{d.duration_ms}ms</Text>}
                  </Group>
                </Group>
                <Text size="xs" c="dimmed">{new Date(d.created_at).toLocaleString()}</Text>
              </Paper>
            ))}
          </Stack>
        ) : (
          <Text c="dimmed" ta="center" mt="xl">No deliveries yet.</Text>
        )}
      </Drawer>
    </Stack>
  );
}

function ExternalIntegrationsTab() {
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [integrationName, setIntegrationName] = useState('');
  const [config, setConfig] = useState('{}');

  const { data: integrations, isLoading } = useQuery({
    queryKey: ['externalIntegrations'],
    queryFn: () => integrationsApi.listIntegrations().then(r => r.data),
  });

  const createMutation = useMutation({
    mutationFn: () => {
      let parsedConfig: Record<string, unknown> = {};
      try { parsedConfig = JSON.parse(config); } catch { /* ignore */ }
      return integrationsApi.createIntegration({
        provider: selectedProvider,
        name: integrationName,
        config: parsedConfig,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['externalIntegrations'] });
      closeCreate();
      setSelectedProvider(''); setIntegrationName(''); setConfig('{}');
      notifications.show({ title: 'Integration Created', message: 'External integration configured', color: 'blue' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: integrationsApi.deleteIntegration,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['externalIntegrations'] }),
  });

  const testMutation = useMutation({
    mutationFn: integrationsApi.testIntegration,
    onSuccess: (res) => notifications.show({ title: 'Test Passed', message: res.data.detail, color: 'green' }),
    onError: (err) => notifications.show({ title: 'Test Failed', message: apiErrorMessage(err, 'Connection test failed'), color: 'red' }),
  });

  if (isLoading) return <Center h={200}><Loader /></Center>;

  return (
    <Stack>
      <Group justify="space-between">
        <Text fw={600}>External Integrations</Text>
        <Button leftSection={<IconPlus size={16} />} size="sm" onClick={openCreate}>
          Add Integration
        </Button>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        {PROVIDERS.map(p => {
          const existing = integrations?.filter(i => i.provider === p.value) || [];
          return (
            <Card key={p.value} withBorder radius="md" padding="md">
              <Group mb="xs">
                <IconPlugConnected size={24} />
                <Text fw={500}>{p.label}</Text>
              </Group>
              {existing.length > 0 ? (
                existing.map(i => (
                  <Group key={i.id} justify="space-between" mt="xs">
                    <Group gap="xs">
                      <Badge color={i.is_active ? 'green' : 'red'} size="sm">
                        {i.is_active ? 'Active' : 'Disabled'}
                      </Badge>
                      <Text size="sm">{i.name}</Text>
                    </Group>
                    <Group gap="xs">
                      <ActionIcon size="sm" variant="light" color="green" onClick={() => testMutation.mutate(i.id)}>
                        <IconTestPipe size={12} />
                      </ActionIcon>
                      <ActionIcon size="sm" variant="light" color="red" onClick={() => deleteMutation.mutate(i.id)}>
                        <IconTrash size={12} />
                      </ActionIcon>
                    </Group>
                  </Group>
                ))
              ) : (
                <Text size="sm" c="dimmed">Not configured</Text>
              )}
            </Card>
          );
        })}
      </SimpleGrid>

      <Modal opened={createOpened} onClose={closeCreate} title="Add External Integration" size="md">
        <Stack>
          <TextInput label="Provider" placeholder="Select provider" value={selectedProvider} onChange={e => setSelectedProvider(e.target.value)} />
          <TextInput label="Name" placeholder="e.g., Production PagerDuty" value={integrationName} onChange={e => setIntegrationName(e.target.value)} />
          <JsonInput
            label="Configuration (JSON)"
            placeholder='{"api_key": "..."}'
            value={config}
            onChange={setConfig}
            minRows={4}
          />
          <Button
            onClick={() => createMutation.mutate()}
            loading={createMutation.isPending}
            disabled={!selectedProvider || !integrationName}
          >
            Create Integration
          </Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
