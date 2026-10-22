import {
  Stack, Title, Paper, Table, Badge, Text, Select, Center, Loader, Group, Progress,
} from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { processesApi } from '../api/processes';
import { useState } from 'react';
import { agentsApi, type Agent } from '../api/agents';

interface AgentOption {
  value: string;
  label: string;
}

const STATUS_COLORS: Record<string, string> = {
  running: 'green',
  sleeping: 'blue',
  stopped: 'orange',
  zombie: 'red',
  idle: 'gray',
};

export default function ProcessesPage() {
  const [agentId, setAgentId] = useState<string | null>(null);

  const { data: agents } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentsApi.list().then(r => r.data.items),
    select: (data: Agent[]): AgentOption[] => data.map(a => ({
      value: a.id,
      label: a.display_name || a.hostname,
    })),
  });

  const { data: processes, isLoading } = useQuery({
    queryKey: ['processes', agentId],
    queryFn: () => processesApi.getProcesses(agentId || undefined).then(r => r.data),
    refetchInterval: 10000,
  });

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Processes</Title>
        <Select
          placeholder="All agents"
          clearable
          data={agents || []}
          value={agentId}
          onChange={setAgentId}
          w={250}
        />
      </Group>

      {isLoading ? (
        <Center h={300}><Loader /></Center>
      ) : (
        <Paper withBorder radius="md">
          {processes && processes.length > 0 ? (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>PID</Table.Th>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>CPU %</Table.Th>
                  <Table.Th>Memory</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>User</Table.Th>
                  <Table.Th>Threads</Table.Th>
                  <Table.Th>Command</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {processes.map((proc, i) => (
                  <Table.Tr key={`${proc.agent_id}-${proc.pid}-${i}`}>
                    <Table.Td><Text size="sm" ff="monospace">{proc.pid}</Text></Table.Td>
                    <Table.Td><Text size="sm" fw={500}>{proc.name}</Text></Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <Progress value={Math.min(proc.cpu_percent, 100)} w={60} size="sm"
                          color={proc.cpu_percent > 80 ? 'red' : proc.cpu_percent > 50 ? 'yellow' : 'blue'} />
                        <Text size="xs">{proc.cpu_percent}%</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <Text size="xs">{proc.memory_percent}%</Text>
                        <Text size="xs" c="dimmed">({proc.memory_mb} MB)</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Badge size="sm" color={STATUS_COLORS[proc.status] || 'gray'}>{proc.status}</Badge>
                    </Table.Td>
                    <Table.Td><Text size="xs">{proc.username || '-'}</Text></Table.Td>
                    <Table.Td><Text size="xs">{proc.num_threads}</Text></Table.Td>
                    <Table.Td>
                      <Text size="xs" ff="monospace" truncate maw={300}>{proc.command}</Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          ) : (
            <Text p="xl" ta="center" c="dimmed">No process data available. Make sure agents are running.</Text>
          )}
        </Paper>
      )}
    </Stack>
  );
}
