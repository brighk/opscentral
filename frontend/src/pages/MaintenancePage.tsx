import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Stack, Title, Group, Button, Table, Badge, Modal, TextInput,
  Textarea, Select, Paper, Text, ActionIcon, Alert as MantineAlert,
  Loader, MultiSelect,
} from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconPlus, IconTrash, IconCalendarOff } from '@tabler/icons-react';
import { maintenanceApi, MaintenanceWindow, MaintenanceWindowCreate } from '../api/maintenance';

import '@mantine/dates/styles.css';

function scopeColor(scope: string) {
  switch (scope) {
    case 'all': return 'red';
    case 'agents': return 'blue';
    case 'health_checks': return 'violet';
    default: return 'gray';
  }
}

function isCurrentlyActive(w: MaintenanceWindow): boolean {
  const now = new Date();
  return w.is_active && new Date(w.start_time) <= now && new Date(w.end_time) >= now;
}

export default function MaintenancePage() {
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [startTime, setStartTime] = useState<Date | null>(null);
  const [endTime, setEndTime] = useState<Date | null>(null);
  const [scope, setScope] = useState<string>('all');
  const [scopeIds, setScopeIds] = useState<string[]>([]);
  const [scopeIdsInput, setScopeIdsInput] = useState('');

  const { data: windows, isLoading } = useQuery({
    queryKey: ['maintenance-windows'],
    queryFn: () => maintenanceApi.list().then(r => r.data),
  });

  const { data: activeWindows } = useQuery({
    queryKey: ['maintenance-windows-active'],
    queryFn: () => maintenanceApi.listActive().then(r => r.data),
    refetchInterval: 60000,
  });

  const createMutation = useMutation({
    mutationFn: (data: MaintenanceWindowCreate) => maintenanceApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['maintenance-windows'] });
      queryClient.invalidateQueries({ queryKey: ['maintenance-windows-active'] });
      closeCreate();
      resetForm();
      notifications.show({ title: 'Created', message: 'Maintenance window created', color: 'green' });
    },
    onError: () =>
      notifications.show({ title: 'Error', message: 'Failed to create maintenance window', color: 'red' }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => maintenanceApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['maintenance-windows'] });
      queryClient.invalidateQueries({ queryKey: ['maintenance-windows-active'] });
      notifications.show({ title: 'Deleted', message: 'Maintenance window deleted', color: 'blue' });
    },
  });

  const resetForm = () => {
    setName('');
    setDescription('');
    setStartTime(null);
    setEndTime(null);
    setScope('all');
    setScopeIds([]);
    setScopeIdsInput('');
  };

  const handleCreate = () => {
    if (!name || !startTime || !endTime) {
      notifications.show({ title: 'Validation', message: 'Name, start time, and end time are required', color: 'orange' });
      return;
    }
    if (endTime <= startTime) {
      notifications.show({ title: 'Validation', message: 'End time must be after start time', color: 'orange' });
      return;
    }
    const ids = scopeIdsInput
      .split(',')
      .map(s => s.trim())
      .filter(Boolean);
    createMutation.mutate({
      name,
      description: description || undefined,
      start_time: startTime.toISOString(),
      end_time: endTime.toISOString(),
      scope,
      scope_ids: ids,
    });
  };

  const activeCount = activeWindows?.length ?? 0;

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Maintenance Windows</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          New Window
        </Button>
      </Group>

      {activeCount > 0 && (
        <MantineAlert
          icon={<IconCalendarOff size={18} />}
          title={`${activeCount} active maintenance window${activeCount > 1 ? 's' : ''}`}
          color="orange"
        >
          Alert suppression is currently active. Alerts will not fire for suppressed resources.
          {activeWindows?.map(w => (
            <Text key={w.id} size="sm" mt={4}>
              <strong>{w.name}</strong> — scope: {w.scope}
              {w.scope_ids.length > 0 && ` (${w.scope_ids.length} resources)`}
              {' '}until {new Date(w.end_time).toLocaleString()}
            </Text>
          ))}
        </MantineAlert>
      )}

      <Paper withBorder p="md">
        {isLoading ? (
          <Loader />
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Start</Table.Th>
                <Table.Th>End</Table.Th>
                <Table.Th>Scope</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {windows?.map((w) => (
                <Table.Tr key={w.id}>
                  <Table.Td>
                    <Text fw={500}>{w.name}</Text>
                    {w.description && <Text size="xs" c="dimmed">{w.description}</Text>}
                  </Table.Td>
                  <Table.Td>{new Date(w.start_time).toLocaleString()}</Table.Td>
                  <Table.Td>{new Date(w.end_time).toLocaleString()}</Table.Td>
                  <Table.Td>
                    <Badge color={scopeColor(w.scope)} variant="light">
                      {w.scope}
                      {w.scope_ids.length > 0 && ` (${w.scope_ids.length})`}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {!w.is_active ? (
                      <Badge color="gray">Disabled</Badge>
                    ) : isCurrentlyActive(w) ? (
                      <Badge color="orange">Active Now</Badge>
                    ) : new Date(w.start_time) > new Date() ? (
                      <Badge color="blue">Scheduled</Badge>
                    ) : (
                      <Badge color="green">Ended</Badge>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <ActionIcon
                      variant="light"
                      color="red"
                      onClick={() => deleteMutation.mutate(w.id)}
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Table.Td>
                </Table.Tr>
              ))}
              {windows?.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={6}>
                    <Text c="dimmed" ta="center">No maintenance windows configured</Text>
                  </Table.Td>
                </Table.Tr>
              )}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={createOpened} onClose={closeCreate} title="New Maintenance Window" size="md">
        <Stack>
          <TextInput
            label="Name"
            required
            placeholder="e.g. Database upgrade"
            value={name}
            onChange={e => setName(e.currentTarget.value)}
          />
          <Textarea
            label="Description"
            placeholder="Optional details"
            value={description}
            onChange={e => setDescription(e.currentTarget.value)}
          />
          <DateTimePicker
            label="Start Time"
            required
            placeholder="Pick start date and time"
            value={startTime}
            onChange={setStartTime}
          />
          <DateTimePicker
            label="End Time"
            required
            placeholder="Pick end date and time"
            value={endTime}
            onChange={setEndTime}
            minDate={startTime ?? undefined}
          />
          <Select
            label="Scope"
            description="Which resources to suppress alerts for"
            data={[
              { value: 'all', label: 'All resources' },
              { value: 'agents', label: 'Specific agents' },
              { value: 'health_checks', label: 'Specific health checks' },
            ]}
            value={scope}
            onChange={v => setScope(v || 'all')}
          />
          {scope !== 'all' && (
            <TextInput
              label="Resource IDs (comma-separated)"
              description="Leave empty to suppress all resources of the selected scope type"
              placeholder="uuid1, uuid2, ..."
              value={scopeIdsInput}
              onChange={e => setScopeIdsInput(e.currentTarget.value)}
            />
          )}
          <Group justify="flex-end" mt="sm">
            <Button variant="subtle" onClick={closeCreate}>Cancel</Button>
            <Button onClick={handleCreate} loading={createMutation.isPending}>Create</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
