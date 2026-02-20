import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Stack, Title, Group, Button, Badge, Paper, Text, Textarea,
  Select, Tabs, Timeline, Loader, Card,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconArrowLeft, IconCheck } from '@tabler/icons-react';
import { useParams, useNavigate } from 'react-router-dom';
import { incidentsApi } from '../api/incidents';

export default function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [updateMsg, setUpdateMsg] = useState('');
  const [newStatus, setNewStatus] = useState<string | null>(null);
  const [postmortemSummary, setPostmortemSummary] = useState('');
  const [rootCause, setRootCause] = useState('');
  const [impact, setImpact] = useState('');
  const [lessonsLearned, setLessonsLearned] = useState('');
  const [actionItems, setActionItems] = useState('');

  const { data: incident, isLoading } = useQuery({
    queryKey: ['incident', id],
    queryFn: () => incidentsApi.get(id!).then(r => r.data),
    enabled: !!id,
  });

  const { data: updates } = useQuery({
    queryKey: ['incident-updates', id],
    queryFn: () => incidentsApi.listUpdates(id!).then(r => r.data),
    enabled: !!id,
  });

  const { data: postmortem } = useQuery({
    queryKey: ['postmortem', id],
    queryFn: () => incidentsApi.getPostmortem(id!).then(r => r.data).catch(() => null),
    enabled: !!id,
  });

  const addUpdateMutation = useMutation({
    mutationFn: () => incidentsApi.addUpdate(id!, { message: updateMsg, update_type: newStatus ? 'status_change' : 'update', new_status: newStatus || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incident', id] });
      queryClient.invalidateQueries({ queryKey: ['incident-updates', id] });
      setUpdateMsg(''); setNewStatus(null);
      notifications.show({ title: 'Updated', message: 'Update added', color: 'green' });
    },
  });

  const resolveMutation = useMutation({
    mutationFn: () => incidentsApi.resolve(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incident', id] });
      queryClient.invalidateQueries({ queryKey: ['incident-updates', id] });
      notifications.show({ title: 'Resolved', message: 'Incident resolved', color: 'green' });
    },
  });

  const createPostmortemMutation = useMutation({
    mutationFn: () => incidentsApi.createPostmortem(id!, {
      summary: postmortemSummary, root_cause: rootCause || undefined,
      impact: impact || undefined, lessons_learned: lessonsLearned || undefined,
      action_items: actionItems || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['postmortem', id] });
      notifications.show({ title: 'Created', message: 'Postmortem created', color: 'green' });
    },
  });

  const severityColor = (s: string) => {
    switch (s) { case 'critical': case 'major': return 'red'; case 'warning': return 'yellow'; default: return 'blue'; }
  };

  const statusColor = (s: string) => {
    switch (s) { case 'open': return 'red'; case 'investigating': case 'identified': return 'orange'; case 'monitoring': return 'blue'; case 'resolved': return 'green'; case 'closed': return 'gray'; default: return 'blue'; }
  };

  if (isLoading) return <Loader />;
  if (!incident) return <Text>Incident not found</Text>;

  return (
    <Stack>
      <Group>
        <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => navigate('/incidents')}>
          Back
        </Button>
      </Group>

      <Group justify="space-between">
        <Group>
          <Title order={2}>{incident.title}</Title>
          <Badge color={severityColor(incident.severity)} size="lg">{incident.severity}</Badge>
          <Badge color={statusColor(incident.status)} size="lg">{incident.status}</Badge>
        </Group>
        {!['resolved', 'closed'].includes(incident.status) && (
          <Button color="green" leftSection={<IconCheck size={16} />} onClick={() => resolveMutation.mutate()}>
            Resolve
          </Button>
        )}
      </Group>

      {incident.description && (
        <Paper withBorder p="md">
          <Text>{incident.description}</Text>
        </Paper>
      )}

      <Tabs defaultValue="timeline">
        <Tabs.List>
          <Tabs.Tab value="timeline">Timeline</Tabs.Tab>
          <Tabs.Tab value="postmortem">Postmortem</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="timeline" pt="md">
          <Stack>
            <Paper withBorder p="md">
              <Stack>
                <Textarea label="Add Update" value={updateMsg} onChange={e => setUpdateMsg(e.currentTarget.value)} />
                <Select label="Change Status (optional)" clearable
                  data={['investigating', 'identified', 'monitoring', 'resolved', 'closed']}
                  value={newStatus} onChange={setNewStatus} />
                <Button onClick={() => addUpdateMutation.mutate()} disabled={!updateMsg} loading={addUpdateMutation.isPending}>
                  Add Update
                </Button>
              </Stack>
            </Paper>

            <Timeline active={updates?.length || 0} bulletSize={24} lineWidth={2}>
              {updates?.map((u) => (
                <Timeline.Item key={u.id} title={u.update_type}>
                  <Text size="sm">{u.message}</Text>
                  {u.new_status && <Badge size="sm" color={statusColor(u.new_status)}>{u.new_status}</Badge>}
                  <Text size="xs" c="dimmed">{new Date(u.created_at).toLocaleString()}</Text>
                </Timeline.Item>
              ))}
            </Timeline>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="postmortem" pt="md">
          {postmortem ? (
            <Stack>
              <Card withBorder p="md">
                <Text fw={700}>Summary</Text><Text>{postmortem.summary}</Text>
                {postmortem.root_cause && (<><Text fw={700} mt="sm">Root Cause</Text><Text>{postmortem.root_cause}</Text></>)}
                {postmortem.impact && (<><Text fw={700} mt="sm">Impact</Text><Text>{postmortem.impact}</Text></>)}
                {postmortem.lessons_learned && (<><Text fw={700} mt="sm">Lessons Learned</Text><Text>{postmortem.lessons_learned}</Text></>)}
                {postmortem.action_items && (<><Text fw={700} mt="sm">Action Items</Text><Text>{postmortem.action_items}</Text></>)}
              </Card>
            </Stack>
          ) : (
            <Paper withBorder p="md">
              <Stack>
                <Textarea label="Summary" required value={postmortemSummary} onChange={e => setPostmortemSummary(e.currentTarget.value)} />
                <Textarea label="Root Cause" value={rootCause} onChange={e => setRootCause(e.currentTarget.value)} />
                <Textarea label="Impact" value={impact} onChange={e => setImpact(e.currentTarget.value)} />
                <Textarea label="Lessons Learned" value={lessonsLearned} onChange={e => setLessonsLearned(e.currentTarget.value)} />
                <Textarea label="Action Items" value={actionItems} onChange={e => setActionItems(e.currentTarget.value)} />
                <Button onClick={() => createPostmortemMutation.mutate()} disabled={!postmortemSummary} loading={createPostmortemMutation.isPending}>
                  Create Postmortem
                </Button>
              </Stack>
            </Paper>
          )}
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
