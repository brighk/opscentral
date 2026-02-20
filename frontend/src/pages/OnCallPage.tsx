import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Stack, Title, Group, Button, Table, Badge, Modal, TextInput,
  Textarea, Select, Paper, Text, Tabs, NumberInput, JsonInput,
  Card, ActionIcon, Loader, Alert,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconPlus, IconTrash, IconPhoneCall } from '@tabler/icons-react';
import { oncallApi, OnCallSchedule, EscalationPolicy } from '../api/oncall';

export default function OnCallPage() {
  const queryClient = useQueryClient();

  // Whoami
  const { data: whoami } = useQuery({
    queryKey: ['oncall-whoami'],
    queryFn: () => oncallApi.whoami().then(r => r.data),
  });

  return (
    <Stack>
      <Title order={2}>On-Call Management</Title>

      {whoami && whoami.length > 0 && (
        <Alert color="blue" icon={<IconPhoneCall size={16} />} title="You are currently on call">
          {whoami.map(w => w.schedule_name).join(', ')}
        </Alert>
      )}

      <Tabs defaultValue="schedules">
        <Tabs.List>
          <Tabs.Tab value="schedules">Schedules</Tabs.Tab>
          <Tabs.Tab value="policies">Escalation Policies</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="schedules" pt="md">
          <SchedulesTab />
        </Tabs.Panel>

        <Tabs.Panel value="policies" pt="md">
          <PoliciesTab />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}

function SchedulesTab() {
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [rotationType, setRotationType] = useState('weekly');
  const [participantsInput, setParticipantsInput] = useState('');
  const [handoffTime, setHandoffTime] = useState('09:00');

  const { data: schedules, isLoading } = useQuery({
    queryKey: ['oncall-schedules'],
    queryFn: () => oncallApi.listSchedules().then(r => r.data),
  });

  const createMutation = useMutation({
    mutationFn: () => {
      const participants = participantsInput.split(',').map(p => p.trim()).filter(Boolean);
      return oncallApi.createSchedule({ name, description: description || undefined, rotation_type: rotationType, participants, handoff_time: handoffTime });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oncall-schedules'] });
      closeCreate();
      setName(''); setDescription(''); setParticipantsInput('');
      notifications.show({ title: 'Created', message: 'Schedule created', color: 'green' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => oncallApi.deleteSchedule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oncall-schedules'] });
      notifications.show({ title: 'Deleted', message: 'Schedule deleted', color: 'blue' });
    },
  });

  return (
    <Stack>
      <Group justify="flex-end">
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>Create Schedule</Button>
      </Group>

      <Paper withBorder p="md">
        {isLoading ? <Loader /> : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Rotation</Table.Th>
                <Table.Th>Participants</Table.Th>
                <Table.Th>Handoff</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {schedules?.map((s) => (
                <Table.Tr key={s.id}>
                  <Table.Td>{s.name}</Table.Td>
                  <Table.Td><Badge variant="light">{s.rotation_type}</Badge></Table.Td>
                  <Table.Td>{s.participants.length}</Table.Td>
                  <Table.Td>{s.handoff_time}</Table.Td>
                  <Table.Td><Badge color={s.is_active ? 'green' : 'gray'}>{s.is_active ? 'Active' : 'Inactive'}</Badge></Table.Td>
                  <Table.Td>
                    <ActionIcon variant="light" color="red" onClick={() => deleteMutation.mutate(s.id)}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={createOpened} onClose={closeCreate} title="Create Schedule">
        <Stack>
          <TextInput label="Name" required value={name} onChange={e => setName(e.currentTarget.value)} />
          <Textarea label="Description" value={description} onChange={e => setDescription(e.currentTarget.value)} />
          <Select label="Rotation Type" data={['daily', 'weekly', 'biweekly', 'custom']} value={rotationType} onChange={v => setRotationType(v || 'weekly')} />
          <TextInput label="Participants (comma-separated user IDs)" value={participantsInput} onChange={e => setParticipantsInput(e.currentTarget.value)} />
          <TextInput label="Handoff Time (HH:MM)" value={handoffTime} onChange={e => setHandoffTime(e.currentTarget.value)} />
          <Button onClick={() => createMutation.mutate()} loading={createMutation.isPending}>Create</Button>
        </Stack>
      </Modal>
    </Stack>
  );
}

function PoliciesTab() {
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [stepsJson, setStepsJson] = useState('[\n  {\n    "delay_minutes": 5,\n    "targets": []\n  }\n]');

  const { data: policies, isLoading } = useQuery({
    queryKey: ['escalation-policies'],
    queryFn: () => oncallApi.listPolicies().then(r => r.data),
  });

  const createMutation = useMutation({
    mutationFn: () => {
      const steps = JSON.parse(stepsJson);
      return oncallApi.createPolicy({ name, description: description || undefined, steps });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['escalation-policies'] });
      closeCreate();
      setName(''); setDescription('');
      notifications.show({ title: 'Created', message: 'Policy created', color: 'green' });
    },
    onError: () => notifications.show({ title: 'Error', message: 'Invalid steps JSON', color: 'red' }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => oncallApi.deletePolicy(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['escalation-policies'] });
      notifications.show({ title: 'Deleted', message: 'Policy deleted', color: 'blue' });
    },
  });

  return (
    <Stack>
      <Group justify="flex-end">
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>Create Policy</Button>
      </Group>

      <Paper withBorder p="md">
        {isLoading ? <Loader /> : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Steps</Table.Th>
                <Table.Th>Repeat</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {policies?.map((p) => (
                <Table.Tr key={p.id}>
                  <Table.Td>{p.name}</Table.Td>
                  <Table.Td>{p.steps.length}</Table.Td>
                  <Table.Td>{p.repeat_count}x</Table.Td>
                  <Table.Td><Badge color={p.is_active ? 'green' : 'gray'}>{p.is_active ? 'Active' : 'Inactive'}</Badge></Table.Td>
                  <Table.Td>
                    <ActionIcon variant="light" color="red" onClick={() => deleteMutation.mutate(p.id)}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={createOpened} onClose={closeCreate} title="Create Escalation Policy" size="lg">
        <Stack>
          <TextInput label="Name" required value={name} onChange={e => setName(e.currentTarget.value)} />
          <Textarea label="Description" value={description} onChange={e => setDescription(e.currentTarget.value)} />
          <JsonInput label="Steps (JSON)" value={stepsJson} onChange={setStepsJson} minRows={6} formatOnBlur validationError="Invalid JSON" />
          <Button onClick={() => createMutation.mutate()} loading={createMutation.isPending}>Create</Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
