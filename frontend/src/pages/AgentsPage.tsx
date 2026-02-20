import { useState } from 'react';
import {
  Stack, Title, Paper, Table, Badge, Button, Group, Text,
  Modal, Code, CopyButton, Stepper, TextInput, Select, Center, Loader, ActionIcon,
  Timeline,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconPlus, IconRobot, IconCopy, IconCheck, IconTrash, IconHistory,
  IconCircleCheck, IconCircleX, IconTerminal,
} from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { agentsApi } from '../api/agents';

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return 'Never';
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function AgentsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [opened, { open, close }] = useDisclosure(false);
  const [historyAgentId, setHistoryAgentId] = useState<string | null>(null);
  const [historyAgentName, setHistoryAgentName] = useState('');

  const { data: agentsData, isLoading } = useQuery({
    queryKey: ['agents'],
    queryFn: () => agentsApi.list().then(r => r.data),
    refetchInterval: 15000,
  });
  const agents = (agentsData as any)?.items ?? agentsData ?? [];

  const deactivateMutation = useMutation({
    mutationFn: agentsApi.deactivate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agents'] }),
  });

  if (isLoading) return <Center h={300}><Loader size="lg" /></Center>;

  const isOnline = (lastSeen: string | null) => {
    if (!lastSeen) return false;
    return Date.now() - new Date(lastSeen).getTime() < 180000; // 3 minutes
  };

  const openHistory = (agentId: string, name: string) => {
    setHistoryAgentId(agentId);
    setHistoryAgentName(name);
  };

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Agents</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={open}>Install Agent</Button>
      </Group>

      {agents.length > 0 ? (
        <Paper withBorder radius="md">
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Hostname</Table.Th>
                <Table.Th>OS</Table.Th>
                <Table.Th>Version</Table.Th>
                <Table.Th>IP</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Last Seen</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {agents.map(agent => (
                <Table.Tr key={agent.id}>
                  <Table.Td>
                    <Group gap="xs">
                      <IconRobot size={16} />
                      <Text fw={500}>{agent.display_name || agent.hostname}</Text>
                    </Group>
                  </Table.Td>
                  <Table.Td>{agent.os_version || agent.os_type || '-'}</Table.Td>
                  <Table.Td>{agent.agent_version || '-'}</Table.Td>
                  <Table.Td>{agent.ip_address || '-'}</Table.Td>
                  <Table.Td>
                    <Badge color={isOnline(agent.last_seen) ? 'green' : 'red'} variant="dot">
                      {isOnline(agent.last_seen) ? 'Online' : 'Offline'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{timeAgo(agent.last_seen)}</Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <ActionIcon
                        variant="light"
                        color="teal"
                        onClick={() => navigate(`/remote-actions?agent=${agent.id}`)}
                        title="Run Action"
                      >
                        <IconTerminal size={14} />
                      </ActionIcon>
                      <ActionIcon
                        variant="light"
                        color="blue"
                        onClick={() => openHistory(agent.id, agent.display_name || agent.hostname)}
                        title="Status History"
                      >
                        <IconHistory size={14} />
                      </ActionIcon>
                      <ActionIcon
                        variant="light"
                        color="red"
                        onClick={() => deactivateMutation.mutate(agent.id)}
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
      ) : (
        <Paper withBorder p="xl" radius="md" ta="center">
          <IconRobot size={48} color="gray" />
          <Title order={4} mt="md">No agents installed</Title>
          <Text c="dimmed" mt="sm" mb="md">
            Install the OpsCentral agent on your servers to start monitoring.
          </Text>
          <Button onClick={open}>Install Your First Agent</Button>
        </Paper>
      )}

      <InstallWizard opened={opened} onClose={close} />
      <StatusHistoryModal
        agentId={historyAgentId}
        agentName={historyAgentName}
        onClose={() => setHistoryAgentId(null)}
      />
    </Stack>
  );
}

function StatusHistoryModal({
  agentId,
  agentName,
  onClose,
}: {
  agentId: string | null;
  agentName: string;
  onClose: () => void;
}) {
  const { data: logs, isLoading } = useQuery({
    queryKey: ['agentStatusHistory', agentId],
    queryFn: () => agentsApi.getStatusHistory(agentId!, 30).then(r => r.data),
    enabled: !!agentId,
  });

  return (
    <Modal opened={!!agentId} onClose={onClose} title={`Status History — ${agentName}`} size="lg">
      {isLoading ? (
        <Center h={200}><Loader /></Center>
      ) : logs && logs.length > 0 ? (
        <Timeline active={0} bulletSize={24} lineWidth={2}>
          {logs.map(log => (
            <Timeline.Item
              key={log.id}
              bullet={log.status === 'online'
                ? <IconCircleCheck size={12} />
                : <IconCircleX size={12} />
              }
              color={log.status === 'online' ? 'green' : 'red'}
              title={
                <Group gap="xs">
                  <Badge size="sm" color={log.status === 'online' ? 'green' : 'red'}>
                    {log.status.toUpperCase()}
                  </Badge>
                  <Text size="xs" c="dimmed">
                    {new Date(log.recorded_at).toLocaleString()}
                  </Text>
                </Group>
              }
            >
              <Text size="sm" c="dimmed" mt={4}>{log.message}</Text>
            </Timeline.Item>
          ))}
        </Timeline>
      ) : (
        <Text ta="center" c="dimmed" py="xl">
          No status transitions recorded yet. History is tracked when agents go online or offline.
        </Text>
      )}
    </Modal>
  );
}

function InstallWizard({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const [step, setStep] = useState(0);
  const [hostname, setHostname] = useState('');
  const [osType, setOsType] = useState('linux');
  const [result, setResult] = useState<{ agent_id: string; api_key: string } | null>(null);
  const queryClient = useQueryClient();

  const registerMutation = useMutation({
    mutationFn: () => agentsApi.register({ hostname, os_type: osType }).then(r => r.data),
    onSuccess: (data) => {
      setResult(data);
      setStep(2);
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });

  const linuxCommand = result
    ? `curl -sSL https://get.opscentral.io/agent | sudo bash -s -- --api-key ${result.api_key} --server ${window.location.origin}`
    : '';
  const windowsCommand = result
    ? `powershell -ExecutionPolicy Bypass -Command "irm https://get.opscentral.io/agent.ps1 | iex" -ApiKey ${result.api_key} -ServerUrl ${window.location.origin}`
    : '';
  const installCommand = osType === 'windows' ? windowsCommand : linuxCommand;

  const handleClose = () => {
    setStep(0);
    setHostname('');
    setResult(null);
    onClose();
  };

  return (
    <Modal opened={opened} onClose={handleClose} title="Install Agent" size="lg">
      <Stepper active={step} onStepClick={setStep}>
        <Stepper.Step label="Configure" description="Server details">
          <Stack mt="md">
            <TextInput
              label="Hostname"
              placeholder="e.g., web-server-01"
              value={hostname}
              onChange={e => setHostname(e.target.value)}
            />
            <Select
              label="Operating System"
              data={[
                { value: 'linux', label: 'Linux (Ubuntu/Debian/RHEL/CentOS)' },
                { value: 'windows', label: 'Windows' },
                { value: 'macos', label: 'macOS' },
              ]}
              value={osType}
              onChange={v => v && setOsType(v)}
            />
            <Button onClick={() => { registerMutation.mutate(); setStep(1); }} disabled={!hostname} loading={registerMutation.isPending}>
              Register Agent
            </Button>
          </Stack>
        </Stepper.Step>

        <Stepper.Step label="Registering" description="Creating agent">
          <Center h={100}><Loader /></Center>
        </Stepper.Step>

        <Stepper.Step label="Install" description="Run on server">
          <Stack mt="md">
            <Text size="sm">Run this command on your server to install the agent:</Text>
            <Group>
              <Code block style={{ flex: 1, fontSize: 12 }}>{installCommand}</Code>
              <CopyButton value={installCommand}>
                {({ copied, copy }) => (
                  <ActionIcon color={copied ? 'green' : 'blue'} onClick={copy}>
                    {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                  </ActionIcon>
                )}
              </CopyButton>
            </Group>
            <Text size="sm" c="dimmed">
              Or manually configure: set OC_API_KEY={result?.api_key} and OC_SERVER_URL={window.location.origin}
            </Text>
            <Button onClick={handleClose}>Done</Button>
          </Stack>
        </Stepper.Step>
      </Stepper>
    </Modal>
  );
}
