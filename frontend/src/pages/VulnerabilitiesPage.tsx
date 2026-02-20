import { useState } from 'react';
import {
  Title, Table, Badge, Group, Select, Card, SimpleGrid, Text,
  Stack, Button, ActionIcon, Tooltip, Paper, RingProgress, Center,
} from '@mantine/core';
import { IconShieldCheck, IconRefresh, IconCheck } from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import { vulnerabilitiesApi, type Vulnerability, type VulnSummary } from '../api/vulnerabilities';

const severityColor: Record<string, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'yellow',
  low: 'blue',
};

export default function VulnerabilitiesPage() {
  const queryClient = useQueryClient();
  const [severityFilter, setSeverityFilter] = useState<string | null>(null);
  const [showResolved, setShowResolved] = useState(false);

  const { data: vulns = [], isLoading } = useQuery({
    queryKey: ['vulnerabilities', severityFilter, showResolved],
    queryFn: () => vulnerabilitiesApi.list({
      severity: severityFilter || undefined,
      resolved: showResolved || undefined,
    }),
  });

  const { data: summary } = useQuery<VulnSummary>({
    queryKey: ['vuln-summary'],
    queryFn: vulnerabilitiesApi.summary,
  });

  const scanMutation = useMutation({
    mutationFn: vulnerabilitiesApi.triggerScan,
    onSuccess: () => {
      notifications.show({ title: 'Scan started', message: 'Vulnerability scan triggered in background', color: 'blue' });
    },
  });

  const resolveMutation = useMutation({
    mutationFn: (id: string) => vulnerabilitiesApi.resolve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vulnerabilities'] });
      queryClient.invalidateQueries({ queryKey: ['vuln-summary'] });
    },
  });

  const total = summary?.total || 0;
  const critical = summary?.critical || 0;
  const high = summary?.high || 0;

  return (
    <Stack>
      <Group justify="space-between">
        <Group>
          <IconShieldCheck size={28} />
          <Title order={2}>Vulnerabilities</Title>
        </Group>
        <Button
          leftSection={<IconRefresh size={16} />}
          onClick={() => scanMutation.mutate()}
          loading={scanMutation.isPending}
        >
          Scan Now
        </Button>
      </Group>

      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <Card shadow="xs" p="md">
          <Text size="xs" c="dimmed">Critical</Text>
          <Text size="xl" fw={700} c="red">{critical}</Text>
        </Card>
        <Card shadow="xs" p="md">
          <Text size="xs" c="dimmed">High</Text>
          <Text size="xl" fw={700} c="orange">{high}</Text>
        </Card>
        <Card shadow="xs" p="md">
          <Text size="xs" c="dimmed">Medium</Text>
          <Text size="xl" fw={700} c="yellow.7">{summary?.medium || 0}</Text>
        </Card>
        <Card shadow="xs" p="md">
          <Text size="xs" c="dimmed">Total</Text>
          <Text size="xl" fw={700}>{total}</Text>
        </Card>
      </SimpleGrid>

      <Group>
        <Select
          placeholder="Filter by severity"
          clearable
          data={['critical', 'high', 'medium', 'low']}
          value={severityFilter}
          onChange={setSeverityFilter}
          w={200}
        />
        <Button
          variant={showResolved ? 'filled' : 'light'}
          size="sm"
          onClick={() => setShowResolved(!showResolved)}
        >
          {showResolved ? 'Showing resolved' : 'Show resolved'}
        </Button>
      </Group>

      <Paper shadow="xs" p="md">
        {isLoading ? (
          <Text c="dimmed">Loading...</Text>
        ) : vulns.length === 0 ? (
          <Center py="xl">
            <Stack align="center">
              <RingProgress sections={[{ value: 100, color: 'green' }]} label={<Center><IconShieldCheck size={28} color="green" /></Center>} />
              <Text c="dimmed">No vulnerabilities found</Text>
            </Stack>
          </Center>
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Severity</Table.Th>
                <Table.Th>CVE</Table.Th>
                <Table.Th>Package</Table.Th>
                <Table.Th>Asset</Table.Th>
                <Table.Th>Summary</Table.Th>
                <Table.Th>Fix</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {vulns.map((v: Vulnerability) => (
                <Table.Tr key={v.id}>
                  <Table.Td>
                    <Badge color={severityColor[v.severity] || 'gray'} variant="filled" size="sm">
                      {v.severity}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" ff="monospace">{v.cve_id || '—'}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{v.software_name}</Text>
                    <Text size="xs" c="dimmed">{v.installed_version}</Text>
                  </Table.Td>
                  <Table.Td><Text size="sm">{v.asset_hostname}</Text></Table.Td>
                  <Table.Td><Text size="sm" lineClamp={2}>{v.summary}</Text></Table.Td>
                  <Table.Td>
                    <Text size="sm" c="green">{v.fixed_version || '—'}</Text>
                  </Table.Td>
                  <Table.Td>
                    {!v.is_resolved && (
                      <Tooltip label="Mark resolved">
                        <ActionIcon
                          color="green"
                          variant="light"
                          onClick={() => resolveMutation.mutate(v.id)}
                        >
                          <IconCheck size={16} />
                        </ActionIcon>
                      </Tooltip>
                    )}
                    {v.is_resolved && <Badge color="green" size="sm">Resolved</Badge>}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>
    </Stack>
  );
}
