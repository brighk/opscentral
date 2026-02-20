import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Stack, Title, Group, Button, Table, Badge, Modal, TextInput,
  Textarea, Select, Paper, Text, SimpleGrid, Card, Loader,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconPlus, IconCheck } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { incidentsApi, Incident, IncidentStats } from '../api/incidents';

export default function IncidentsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  // Form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState('warning');

  const { data: incidents, isLoading } = useQuery({
    queryKey: ['incidents', statusFilter],
    queryFn: () => incidentsApi.list(statusFilter || undefined).then(r => r.data),
    refetchInterval: 10000,
  });

  const { data: stats } = useQuery({
    queryKey: ['incident-stats'],
    queryFn: () => incidentsApi.getStats().then(r => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: { title: string; description?: string; severity: string }) =>
      incidentsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      queryClient.invalidateQueries({ queryKey: ['incident-stats'] });
      closeCreate();
      setTitle(''); setDescription(''); setSeverity('warning');
      notifications.show({ title: 'Created', message: 'Incident created', color: 'green' });
    },
  });

  const resolveMutation = useMutation({
    mutationFn: (id: string) => incidentsApi.resolve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      queryClient.invalidateQueries({ queryKey: ['incident-stats'] });
      notifications.show({ title: 'Resolved', message: 'Incident resolved', color: 'green' });
    },
  });

  const severityColor = (s: string) => {
    switch (s) { case 'critical': case 'major': return 'red'; case 'warning': return 'yellow'; default: return 'blue'; }
  };

  const statusColor = (s: string) => {
    switch (s) { case 'open': return 'red'; case 'investigating': case 'identified': return 'orange'; case 'monitoring': return 'blue'; case 'resolved': return 'green'; case 'closed': return 'gray'; default: return 'blue'; }
  };

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Incidents</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>Create Incident</Button>
      </Group>

      {stats && (
        <SimpleGrid cols={{ base: 2, sm: 3, md: 6 }}>
          <Card withBorder p="sm"><Text size="xs" c="dimmed">Total</Text><Text size="xl" fw={700}>{stats.total}</Text></Card>
          <Card withBorder p="sm"><Text size="xs" c="dimmed">Open</Text><Text size="xl" fw={700} c="red">{stats.open}</Text></Card>
          <Card withBorder p="sm"><Text size="xs" c="dimmed">Investigating</Text><Text size="xl" fw={700} c="orange">{stats.investigating}</Text></Card>
          <Card withBorder p="sm"><Text size="xs" c="dimmed">Resolved</Text><Text size="xl" fw={700} c="green">{stats.resolved}</Text></Card>
          <Card withBorder p="sm"><Text size="xs" c="dimmed">Closed</Text><Text size="xl" fw={700} c="gray">{stats.closed}</Text></Card>
          <Card withBorder p="sm"><Text size="xs" c="dimmed">MTTR</Text><Text size="xl" fw={700}>{stats.mttr_hours != null ? `${stats.mttr_hours}h` : 'N/A'}</Text></Card>
        </SimpleGrid>
      )}

      <Group>
        <Select
          placeholder="Filter by status"
          clearable
          data={['open', 'investigating', 'identified', 'monitoring', 'resolved', 'closed']}
          value={statusFilter}
          onChange={setStatusFilter}
          w={200}
        />
      </Group>

      <Paper withBorder p="md">
        {isLoading ? <Loader /> : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Severity</Table.Th>
                <Table.Th>Title</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Source</Table.Th>
                <Table.Th>Created</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {incidents?.map((inc) => (
                <Table.Tr key={inc.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/incidents/${inc.id}`)}>
                  <Table.Td><Badge color={severityColor(inc.severity)}>{inc.severity}</Badge></Table.Td>
                  <Table.Td>{inc.title}</Table.Td>
                  <Table.Td><Badge color={statusColor(inc.status)}>{inc.status}</Badge></Table.Td>
                  <Table.Td><Badge variant="light">{inc.source}</Badge></Table.Td>
                  <Table.Td>{new Date(inc.created_at).toLocaleString()}</Table.Td>
                  <Table.Td onClick={(e) => e.stopPropagation()}>
                    {!['resolved', 'closed'].includes(inc.status) && (
                      <Button size="xs" variant="light" color="green" leftSection={<IconCheck size={14} />}
                        onClick={() => resolveMutation.mutate(inc.id)}>
                        Resolve
                      </Button>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={createOpened} onClose={closeCreate} title="Create Incident">
        <Stack>
          <TextInput label="Title" required value={title} onChange={e => setTitle(e.currentTarget.value)} />
          <Textarea label="Description" value={description} onChange={e => setDescription(e.currentTarget.value)} />
          <Select label="Severity" data={['info', 'warning', 'critical', 'major']} value={severity} onChange={v => setSeverity(v || 'warning')} />
          <Button onClick={() => createMutation.mutate({ title, description: description || undefined, severity })} loading={createMutation.isPending}>
            Create
          </Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
