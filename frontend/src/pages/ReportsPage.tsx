import { useState } from 'react';
import {
  Stack, Title, Paper, Text, Group, Badge, Button, Table,
  SimpleGrid, Card, RingProgress, Center, Loader, Modal, Select,
  ActionIcon,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconFileAnalytics, IconDownload, IconTrash, IconPlus, IconCalendar,
} from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import { reportsApi } from '../api/reports';

const REPORT_TYPES = [
  { value: 'security_posture', label: 'Security Posture' },
  { value: 'asset_inventory', label: 'Asset Inventory' },
  { value: 'uptime_summary', label: 'Uptime Summary' },
  { value: 'vulnerability_report', label: 'Vulnerability Report' },
];

function scoreColor(score: number): string {
  if (score >= 80) return 'green';
  if (score >= 60) return 'yellow';
  return 'red';
}

export default function ReportsPage() {
  const queryClient = useQueryClient();
  const [genOpened, { open: openGen, close: closeGen }] = useDisclosure(false);
  const [schedOpened, { open: openSched, close: closeSched }] = useDisclosure(false);
  const [selectedType, setSelectedType] = useState('security_posture');
  const [schedFreq, setSchedFreq] = useState('weekly');

  const { data: compliance, isLoading: compLoading } = useQuery({
    queryKey: ['compliance'],
    queryFn: () => reportsApi.getCompliance().then(r => r.data),
  });

  const { data: reports, isLoading: reportsLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => reportsApi.list().then(r => r.data),
  });

  const { data: schedules } = useQuery({
    queryKey: ['reportSchedules'],
    queryFn: () => reportsApi.listSchedules().then(r => r.data),
  });

  const generateMutation = useMutation({
    mutationFn: (type: string) => reportsApi.generate(type),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] });
      closeGen();
      notifications.show({ title: 'Report Queued', message: 'Report generation started', color: 'blue' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: reportsApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reports'] }),
  });

  const createScheduleMutation = useMutation({
    mutationFn: () => reportsApi.createSchedule({ report_type: selectedType, frequency: schedFreq }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reportSchedules'] });
      closeSched();
    },
  });

  const deleteScheduleMutation = useMutation({
    mutationFn: reportsApi.deleteSchedule,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reportSchedules'] }),
  });

  if (compLoading || reportsLoading) return <Center h={300}><Loader size="lg" /></Center>;

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Reports & Compliance</Title>
        <Group>
          <Button leftSection={<IconCalendar size={16} />} variant="light" onClick={openSched}>
            Schedule
          </Button>
          <Button leftSection={<IconPlus size={16} />} onClick={openGen}>
            Generate Report
          </Button>
        </Group>
      </Group>

      {/* Compliance Score */}
      {compliance ? (
        <Paper withBorder p="lg" radius="md">
          <Text fw={600} size="lg" mb="md">Compliance Score</Text>
          <Group>
            <RingProgress
              size={120}
              thickness={12}
              roundCaps
              sections={[{ value: compliance.overall_score, color: scoreColor(compliance.overall_score) }]}
              label={
                <Text ta="center" fw={700} size="lg">
                  {compliance.overall_score}
                </Text>
              }
            />
            <SimpleGrid cols={2} spacing="md" style={{ flex: 1 }}>
              {[
                { label: 'Patching', score: compliance.patching_score },
                { label: 'Uptime', score: compliance.uptime_score },
                { label: 'Vulnerability', score: compliance.vulnerability_score },
                { label: 'Agent Coverage', score: compliance.agent_coverage_score },
              ].map(s => (
                <Card key={s.label} withBorder p="sm">
                  <Text size="xs" c="dimmed">{s.label}</Text>
                  <Text fw={600} c={scoreColor(s.score)}>{s.score}/100</Text>
                </Card>
              ))}
            </SimpleGrid>
          </Group>
        </Paper>
      ) : (
        <Paper withBorder p="lg" radius="md" ta="center">
          <Text c="dimmed">No compliance scores calculated yet. Scores are computed daily.</Text>
        </Paper>
      )}

      {/* Report Types */}
      <Title order={3}>Quick Generate</Title>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        {REPORT_TYPES.map(rt => (
          <Card key={rt.value} withBorder radius="md" padding="md">
            <Group>
              <IconFileAnalytics size={24} />
              <Text fw={500}>{rt.label}</Text>
            </Group>
            <Button
              variant="light"
              fullWidth
              mt="sm"
              onClick={() => generateMutation.mutate(rt.value)}
              loading={generateMutation.isPending}
            >
              Generate
            </Button>
          </Card>
        ))}
      </SimpleGrid>

      {/* Generated Reports */}
      {reports && reports.length > 0 && (
        <>
          <Title order={3}>Generated Reports</Title>
          <Paper withBorder radius="md">
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Format</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {reports.map(report => (
                  <Table.Tr key={report.id}>
                    <Table.Td>{report.report_type.replace(/_/g, ' ')}</Table.Td>
                    <Table.Td>{report.format.toUpperCase()}</Table.Td>
                    <Table.Td>
                      <Badge color={
                        report.status === 'ready' ? 'green' :
                        report.status === 'failed' ? 'red' : 'yellow'
                      }>
                        {report.status}
                      </Badge>
                    </Table.Td>
                    <Table.Td>{new Date(report.created_at).toLocaleDateString()}</Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        {report.status === 'ready' && (
                          <ActionIcon variant="light" color="blue">
                            <IconDownload size={14} />
                          </ActionIcon>
                        )}
                        <ActionIcon
                          variant="light"
                          color="red"
                          onClick={() => deleteMutation.mutate(report.id)}
                        >
                          <IconTrash size={14} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Paper>
        </>
      )}

      {/* Schedules */}
      {schedules && schedules.length > 0 && (
        <>
          <Title order={3}>Scheduled Reports</Title>
          <Paper withBorder radius="md">
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Report Type</Table.Th>
                  <Table.Th>Frequency</Table.Th>
                  <Table.Th>Next Run</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {schedules.map(s => (
                  <Table.Tr key={s.id}>
                    <Table.Td>{s.report_type.replace(/_/g, ' ')}</Table.Td>
                    <Table.Td><Badge>{s.frequency}</Badge></Table.Td>
                    <Table.Td>{s.next_run_at ? new Date(s.next_run_at).toLocaleDateString() : '-'}</Table.Td>
                    <Table.Td>
                      <ActionIcon
                        variant="light"
                        color="red"
                        onClick={() => deleteScheduleMutation.mutate(s.id)}
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Paper>
        </>
      )}

      {/* Generate Modal */}
      <Modal opened={genOpened} onClose={closeGen} title="Generate Report">
        <Stack>
          <Select
            label="Report Type"
            data={REPORT_TYPES}
            value={selectedType}
            onChange={v => v && setSelectedType(v)}
          />
          <Button onClick={() => generateMutation.mutate(selectedType)} loading={generateMutation.isPending}>
            Generate
          </Button>
        </Stack>
      </Modal>

      {/* Schedule Modal */}
      <Modal opened={schedOpened} onClose={closeSched} title="Create Report Schedule">
        <Stack>
          <Select
            label="Report Type"
            data={REPORT_TYPES}
            value={selectedType}
            onChange={v => v && setSelectedType(v)}
          />
          <Select
            label="Frequency"
            data={[
              { value: 'weekly', label: 'Weekly' },
              { value: 'monthly', label: 'Monthly' },
            ]}
            value={schedFreq}
            onChange={v => v && setSchedFreq(v)}
          />
          <Button onClick={() => createScheduleMutation.mutate()} loading={createScheduleMutation.isPending}>
            Create Schedule
          </Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
