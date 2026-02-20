import { useState } from 'react';
import {
  Stack, Title, Paper, Text, Group, Badge, Button, Table,
  Modal, Select, TextInput, JsonInput, Center, Loader, ActionIcon,
  Code,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconPlus, IconPlayerStop, IconEye } from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import { remoteActionsApi } from '../api/remoteActions';
import type { RemoteAction } from '../api/remoteActions';
import { agentsApi } from '../api/agents';

function statusColor(status: string): string {
  switch (status) {
    case 'completed': return 'green';
    case 'failed': case 'expired': return 'red';
    case 'running': case 'dispatched': return 'blue';
    case 'pending': return 'yellow';
    default: return 'gray';
  }
}

export default function RemoteActionsPage() {
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [detailAction, setDetailAction] = useState<RemoteAction | null>(null);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [selectedType, setSelectedType] = useState('');
  const [params, setParams] = useState('{}');

  const { data: actions, isLoading } = useQuery({
    queryKey: ['remoteActions'],
    queryFn: () => remoteActionsApi.list().then(r => r.data),
    refetchInterval: 5000,
  });

  const { data: actionTypes } = useQuery({
    queryKey: ['actionTypes'],
    queryFn: () => remoteActionsApi.getTypes().then(r => r.data),
  });

  const { data: agentsData } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentsApi.list().then(r => r.data),
  });
  const agents = agentsData?.items ?? agentsData ?? [];

  const createMutation = useMutation({
    mutationFn: () => {
      let parsedParams: Record<string, unknown> | undefined;
      try {
        const p = JSON.parse(params);
        if (Object.keys(p).length > 0) parsedParams = p;
      } catch { /* ignore */ }
      return remoteActionsApi.create({
        agent_id: selectedAgent,
        action_type: selectedType,
        parameters: parsedParams,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['remoteActions'] });
      closeCreate();
      setParams('{}');
      notifications.show({ title: 'Action Created', message: 'Remote action has been queued', color: 'blue' });
    },
    onError: () => {
      notifications.show({ title: 'Error', message: 'Failed to create action', color: 'red' });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: remoteActionsApi.cancel,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['remoteActions'] }),
  });

  if (isLoading) return <Center h={300}><Loader size="lg" /></Center>;

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Remote Actions</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          New Action
        </Button>
      </Group>

      {actions && actions.length > 0 ? (
        <Paper withBorder radius="md">
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Action Type</Table.Th>
                <Table.Th>Agent</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Created</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {actions.map(action => (
                <Table.Tr key={action.id}>
                  <Table.Td>{action.action_type.replace(/_/g, ' ')}</Table.Td>
                  <Table.Td><Text size="sm">{action.agent_id.slice(0, 8)}...</Text></Table.Td>
                  <Table.Td>
                    <Badge color={statusColor(action.status)}>{action.status}</Badge>
                  </Table.Td>
                  <Table.Td>{new Date(action.created_at).toLocaleString()}</Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <ActionIcon
                        variant="light"
                        color="blue"
                        onClick={() => setDetailAction(action)}
                      >
                        <IconEye size={14} />
                      </ActionIcon>
                      {['pending', 'dispatched'].includes(action.status) && (
                        <ActionIcon
                          variant="light"
                          color="red"
                          onClick={() => cancelMutation.mutate(action.id)}
                        >
                          <IconPlayerStop size={14} />
                        </ActionIcon>
                      )}
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      ) : (
        <Paper withBorder p="xl" radius="md" ta="center">
          <Title order={4}>No remote actions</Title>
          <Text c="dimmed" mt="sm">
            Create a remote action to run commands on your agents.
          </Text>
        </Paper>
      )}

      {/* Create Modal */}
      <Modal opened={createOpened} onClose={closeCreate} title="Create Remote Action" size="md">
        <Stack>
          <Select
            label="Agent"
            placeholder="Select agent"
            data={Array.isArray(agents) ? agents.map((a: any) => ({
              value: a.id,
              label: a.display_name || a.hostname,
            })) : []}
            value={selectedAgent}
            onChange={v => v && setSelectedAgent(v)}
          />
          <Select
            label="Action Type"
            placeholder="Select action"
            data={actionTypes?.map(t => ({
              value: t.key,
              label: `${t.name} (${t.min_role})`,
            })) || []}
            value={selectedType}
            onChange={v => v && setSelectedType(v)}
          />
          <JsonInput
            label="Parameters (JSON)"
            placeholder='{"service_name": "nginx"}'
            value={params}
            onChange={setParams}
            minRows={3}
          />
          <Button
            onClick={() => createMutation.mutate()}
            loading={createMutation.isPending}
            disabled={!selectedAgent || !selectedType}
          >
            Execute Action
          </Button>
        </Stack>
      </Modal>

      {/* Detail Modal */}
      <Modal
        opened={!!detailAction}
        onClose={() => setDetailAction(null)}
        title="Action Details"
        size="lg"
      >
        {detailAction && (
          <Stack>
            <Group>
              <Text fw={600}>Type:</Text>
              <Text>{detailAction.action_type}</Text>
            </Group>
            <Group>
              <Text fw={600}>Status:</Text>
              <Badge color={statusColor(detailAction.status)}>{detailAction.status}</Badge>
            </Group>
            {detailAction.parameters && (
              <>
                <Text fw={600}>Parameters:</Text>
                <Code block>{JSON.stringify(detailAction.parameters, null, 2)}</Code>
              </>
            )}
            {detailAction.result && (
              <>
                <Text fw={600}>Result:</Text>
                <Code block>{JSON.stringify(detailAction.result, null, 2)}</Code>
              </>
            )}
            {detailAction.error && (
              <>
                <Text fw={600} c="red">Error:</Text>
                <Code block color="red">{detailAction.error}</Code>
              </>
            )}
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
