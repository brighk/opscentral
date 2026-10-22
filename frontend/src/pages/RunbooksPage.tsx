import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Stack, Title, Group, Button, Table, Badge, Modal, TextInput,
  Textarea, Select, Switch, Paper, Text, ActionIcon, JsonInput,
  Loader,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconPlus, IconTrash, IconPlayerPlay, IconCheck, IconX } from '@tabler/icons-react';
import { runbooksApi, type Runbook, type RunbookStep } from '../api/runbooks';
import { apiErrorMessage } from '../api/client';

const DEFAULT_STEPS = JSON.stringify(
  [
    {
      name: 'Restart nginx',
      action_type: 'remote_action',
      parameters: { agent_id: '<agent id>', action: 'restart_service', parameters: { service_name: 'nginx' } },
      on_failure: 'stop',
    },
    { name: 'Wait for startup', action_type: 'delay', parameters: { seconds: 10 }, on_failure: 'stop' },
    {
      name: 'Check health endpoint',
      action_type: 'webhook',
      parameters: { url: 'https://example.com/health', method: 'GET' },
      on_failure: 'stop',
    },
    {
      name: 'Health returned 200',
      action_type: 'condition',
      parameters: { step: 2, path: 'status_code', operator: 'eq', value: 200 },
      on_failure: 'stop',
    },
  ],
  null,
  2,
);

const STEPS_HELP =
  'Step types: remote_action (agent_id, action, parameters, timeout_seconds), ' +
  'webhook (url, method, headers, body), delay (seconds), ' +
  'condition (step, path, operator, value). on_failure: stop or continue.';

export default function RunbooksPage() {
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [selectedRunbook, setSelectedRunbook] = useState<Runbook | null>(null);
  const [executionsOpened, { open: openExecutions, close: closeExecutions }] = useDisclosure(false);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [triggerType, setTriggerType] = useState('manual');
  const [requiresApproval, setRequiresApproval] = useState(false);
  const [stepsJson, setStepsJson] = useState(DEFAULT_STEPS);

  const { data: runbooks, isLoading } = useQuery({
    queryKey: ['runbooks'],
    queryFn: () => runbooksApi.list().then(r => r.data),
  });

  const { data: executions } = useQuery({
    queryKey: ['runbook-executions', selectedRunbook?.id],
    queryFn: () => selectedRunbook ? runbooksApi.listExecutions(selectedRunbook.id).then(r => r.data) : Promise.resolve([]),
    enabled: !!selectedRunbook && executionsOpened,
    refetchInterval: 5000,
  });

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string; steps: RunbookStep[]; trigger_type: string; requires_approval: boolean }) =>
      runbooksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runbooks'] });
      closeCreate();
      resetForm();
      notifications.show({ title: 'Success', message: 'Runbook created', color: 'green' });
    },
    onError: (err) => notifications.show({ title: 'Error', message: apiErrorMessage(err, 'Failed to create runbook'), color: 'red' }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => runbooksApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runbooks'] });
      notifications.show({ title: 'Deleted', message: 'Runbook deleted', color: 'blue' });
    },
  });

  const executeMutation = useMutation({
    mutationFn: (id: string) => runbooksApi.execute(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runbook-executions'] });
      notifications.show({ title: 'Queued', message: 'Runbook execution queued', color: 'blue' });
    },
    onError: (err) => notifications.show({ title: 'Error', message: apiErrorMessage(err, 'Failed to execute runbook'), color: 'red' }),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => runbooksApi.approve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runbook-executions'] });
      notifications.show({ title: 'Approved', message: 'Execution approved', color: 'green' });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => runbooksApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runbook-executions'] });
      notifications.show({ title: 'Cancelled', message: 'Execution cancelled', color: 'orange' });
    },
  });

  const resetForm = () => {
    setName('');
    setDescription('');
    setTriggerType('manual');
    setRequiresApproval(false);
    setStepsJson(DEFAULT_STEPS);
  };

  const handleCreate = () => {
    try {
      const steps = JSON.parse(stepsJson);
      createMutation.mutate({ name, description: description || undefined, steps, trigger_type: triggerType, requires_approval: requiresApproval });
    } catch {
      notifications.show({ title: 'Error', message: 'Invalid steps JSON', color: 'red' });
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'green';
      case 'failed': return 'red';
      case 'running': return 'blue';
      case 'pending_approval': return 'yellow';
      case 'cancelled': return 'gray';
      default: return 'blue';
    }
  };

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Runbooks</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>Create Runbook</Button>
      </Group>

      <Paper withBorder p="md">
        {isLoading ? (
          <Loader />
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Trigger</Table.Th>
                <Table.Th>Steps</Table.Th>
                <Table.Th>Approval</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {runbooks?.map((rb) => (
                <Table.Tr key={rb.id}>
                  <Table.Td>{rb.name}</Table.Td>
                  <Table.Td><Badge variant="light">{rb.trigger_type}</Badge></Table.Td>
                  <Table.Td>{rb.steps.length}</Table.Td>
                  <Table.Td>{rb.requires_approval ? <Badge color="yellow">Required</Badge> : <Badge color="gray">No</Badge>}</Table.Td>
                  <Table.Td><Badge color={rb.is_enabled ? 'green' : 'gray'}>{rb.is_enabled ? 'Enabled' : 'Disabled'}</Badge></Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <ActionIcon variant="light" color="blue" onClick={() => { executeMutation.mutate(rb.id); }}>
                        <IconPlayerPlay size={16} />
                      </ActionIcon>
                      <Button size="xs" variant="light" onClick={() => { setSelectedRunbook(rb); openExecutions(); }}>
                        History
                      </Button>
                      <ActionIcon variant="light" color="red" onClick={() => deleteMutation.mutate(rb.id)}>
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      {/* Create Modal */}
      <Modal opened={createOpened} onClose={closeCreate} title="Create Runbook" size="lg">
        <Stack>
          <TextInput label="Name" required value={name} onChange={e => setName(e.currentTarget.value)} />
          <Textarea label="Description" value={description} onChange={e => setDescription(e.currentTarget.value)} />
          <Select
            label="Trigger Type"
            data={[
              { value: 'manual', label: 'Manual' },
              { value: 'alert', label: 'Alert' },
              { value: 'scheduled', label: 'Scheduled' },
            ]}
            value={triggerType}
            onChange={v => setTriggerType(v || 'manual')}
          />
          <Switch label="Requires Approval" checked={requiresApproval} onChange={e => setRequiresApproval(e.currentTarget.checked)} />
          <JsonInput
            label="Steps (JSON)"
            description={STEPS_HELP}
            value={stepsJson}
            onChange={setStepsJson}
            minRows={6}
            formatOnBlur
            validationError="Invalid JSON"
          />
          <Button onClick={handleCreate} loading={createMutation.isPending}>Create</Button>
        </Stack>
      </Modal>

      {/* Executions Modal */}
      <Modal opened={executionsOpened} onClose={closeExecutions} title={`Executions: ${selectedRunbook?.name}`} size="lg">
        <Stack>
          {executions?.map((exec) => (
            <Paper key={exec.id} withBorder p="sm">
              <Group justify="space-between">
                <Group>
                  <Badge color={statusColor(exec.status)}>{exec.status}</Badge>
                  <Text size="sm" c="dimmed">{new Date(exec.created_at).toLocaleString()}</Text>
                </Group>
                <Group gap="xs">
                  {exec.status === 'pending_approval' && (
                    <>
                      <ActionIcon variant="light" color="green" onClick={() => approveMutation.mutate(exec.id)}>
                        <IconCheck size={16} />
                      </ActionIcon>
                      <ActionIcon variant="light" color="red" onClick={() => cancelMutation.mutate(exec.id)}>
                        <IconX size={16} />
                      </ActionIcon>
                    </>
                  )}
                </Group>
              </Group>
              {exec.error && <Text size="sm" c="red" mt="xs">{exec.error}</Text>}
            </Paper>
          ))}
          {executions?.length === 0 && <Text c="dimmed">No executions yet</Text>}
        </Stack>
      </Modal>
    </Stack>
  );
}
