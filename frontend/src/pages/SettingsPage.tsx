import { useState } from 'react';
import {
  Stack, Title, Paper, Text, TextInput, Button, Switch, Tabs,
  Table, Badge, Group, Modal, Code, CopyButton, ActionIcon,
  Center, Loader,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconSettings, IconKey, IconCopy, IconCheck, IconTrash, IconPlus } from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../store/authStore';
import { apiKeysApi } from '../api/apiKeys';
import type { APIKeyCreated } from '../api/apiKeys';

export default function SettingsPage() {
  const { user } = useAuthStore();

  return (
    <Stack>
      <Title order={2}>Settings</Title>

      <Tabs defaultValue="profile">
        <Tabs.List>
          <Tabs.Tab value="profile" leftSection={<IconSettings size={16} />}>
            Profile
          </Tabs.Tab>
          <Tabs.Tab value="api-keys" leftSection={<IconKey size={16} />}>
            API Keys
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="profile" pt="md">
          <Stack>
            <Paper withBorder p="md" radius="md">
              <Text fw={600} mb="md">Profile</Text>
              <Stack>
                <TextInput label="Full Name" value={user?.full_name || ''} readOnly />
                <TextInput label="Email" value={user?.email || ''} readOnly />
                <TextInput label="Organization" value={user?.tenant_name || ''} readOnly />
              </Stack>
            </Paper>

            <Paper withBorder p="md" radius="md">
              <Text fw={600} mb="md">Notification Preferences</Text>
              <Stack>
                <Switch label="Email notifications for alerts" defaultChecked />
                <Switch label="Email notifications for agent status changes" defaultChecked />
                <Switch label="Weekly summary report" />
              </Stack>
            </Paper>

            <Paper withBorder p="md" radius="md">
              <Text fw={600} mb="md">Agent Configuration Defaults</Text>
              <Stack>
                <TextInput label="Default collection interval (seconds)" defaultValue="60" />
                <TextInput label="Default inventory interval (seconds)" defaultValue="300" />
                <Button w={200}>Save Changes</Button>
              </Stack>
            </Paper>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="api-keys" pt="md">
          <APIKeysTab />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}

function APIKeysTab() {
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [newKey, setNewKey] = useState<APIKeyCreated | null>(null);
  const [keyName, setKeyName] = useState('');

  const { data: keys, isLoading } = useQuery({
    queryKey: ['apiKeys'],
    queryFn: () => apiKeysApi.list().then(r => r.data),
  });

  const createMutation = useMutation({
    mutationFn: () => apiKeysApi.create({ name: keyName }),
    onSuccess: (data) => {
      setNewKey(data.data);
      setKeyName('');
      queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: apiKeysApi.revoke,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['apiKeys'] }),
  });

  if (isLoading) return <Center h={200}><Loader /></Center>;

  return (
    <Stack>
      <Group justify="space-between">
        <Text fw={600}>API Keys</Text>
        <Button leftSection={<IconPlus size={16} />} size="sm" onClick={open}>
          Create API Key
        </Button>
      </Group>

      <Text size="sm" c="dimmed">
        API keys allow third-party integrations to access your OpsCentral data.
      </Text>

      {keys && keys.length > 0 ? (
        <Paper withBorder radius="md">
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Key Prefix</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Last Used</Table.Th>
                <Table.Th>Created</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {keys.map(key => (
                <Table.Tr key={key.id}>
                  <Table.Td>{key.name}</Table.Td>
                  <Table.Td><Code>{key.key_prefix}...</Code></Table.Td>
                  <Table.Td>
                    <Badge color={key.is_active ? 'green' : 'red'}>
                      {key.is_active ? 'Active' : 'Revoked'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never'}
                  </Table.Td>
                  <Table.Td>{new Date(key.created_at).toLocaleDateString()}</Table.Td>
                  <Table.Td>
                    {key.is_active && (
                      <ActionIcon
                        variant="light"
                        color="red"
                        onClick={() => revokeMutation.mutate(key.id)}
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      ) : (
        <Paper withBorder p="lg" radius="md" ta="center">
          <Text c="dimmed">No API keys created yet.</Text>
        </Paper>
      )}

      {/* Create Modal */}
      <Modal opened={opened} onClose={() => { close(); setNewKey(null); }} title="Create API Key">
        {newKey ? (
          <Stack>
            <Text fw={600} c="green">API Key Created</Text>
            <Text size="sm" c="dimmed">
              Copy this key now. You won't be able to see it again.
            </Text>
            <Group>
              <Code block style={{ flex: 1 }}>{newKey.raw_key}</Code>
              <CopyButton value={newKey.raw_key}>
                {({ copied, copy }) => (
                  <ActionIcon color={copied ? 'green' : 'blue'} onClick={copy}>
                    {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                  </ActionIcon>
                )}
              </CopyButton>
            </Group>
            <Button onClick={() => { close(); setNewKey(null); }}>Done</Button>
          </Stack>
        ) : (
          <Stack>
            <TextInput
              label="Key Name"
              placeholder="e.g., CI/CD Pipeline"
              value={keyName}
              onChange={e => setKeyName(e.target.value)}
            />
            <Button
              onClick={() => createMutation.mutate()}
              loading={createMutation.isPending}
              disabled={!keyName}
            >
              Create
            </Button>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
