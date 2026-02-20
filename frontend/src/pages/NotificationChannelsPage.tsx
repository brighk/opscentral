import { useState } from 'react';
import {
  Stack, Title, Paper, Table, Badge, Button, Group, Text,
  Modal, TextInput, Select, Switch, Center, Loader, ActionIcon,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconPlus, IconTrash, IconPlayerPlay } from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notificationsApi, type CreateNotificationChannel } from '../api/notifications';
import { notifications } from '@mantine/notifications';

const CHANNEL_TYPE_LABELS: Record<string, string> = {
  slack: 'Slack',
  teams: 'Microsoft Teams',
  discord: 'Discord',
  webhook: 'Custom Webhook',
  email: 'Email',
};

const CHANNEL_TYPE_COLORS: Record<string, string> = {
  slack: 'grape',
  teams: 'blue',
  discord: 'indigo',
  webhook: 'orange',
  email: 'teal',
};

export default function NotificationChannelsPage() {
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);

  const { data: channels, isLoading } = useQuery({
    queryKey: ['notificationChannels'],
    queryFn: () => notificationsApi.listChannels().then(r => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: notificationsApi.deleteChannel,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notificationChannels'] }),
  });

  const testMutation = useMutation({
    mutationFn: notificationsApi.testChannel,
    onSuccess: () => {
      notifications.show({ title: 'Test sent', message: 'Test notification dispatched', color: 'green' });
    },
    onError: () => {
      notifications.show({ title: 'Test failed', message: 'Failed to send test notification', color: 'red' });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      notificationsApi.updateChannel(id, { is_enabled: enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notificationChannels'] }),
  });

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Notification Channels</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={open}>Add Channel</Button>
      </Group>

      {isLoading ? (
        <Center h={300}><Loader /></Center>
      ) : (
        <Paper withBorder radius="md">
          {channels && channels.length > 0 ? (
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Enabled</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {channels.map(channel => (
                  <Table.Tr key={channel.id}>
                    <Table.Td><Text size="sm" fw={500}>{channel.name}</Text></Table.Td>
                    <Table.Td>
                      <Badge color={CHANNEL_TYPE_COLORS[channel.channel_type] || 'gray'}>
                        {CHANNEL_TYPE_LABELS[channel.channel_type] || channel.channel_type}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Switch
                        checked={channel.is_enabled}
                        onChange={e => toggleMutation.mutate({
                          id: channel.id,
                          enabled: e.currentTarget.checked,
                        })}
                      />
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs">{new Date(channel.created_at).toLocaleDateString()}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <ActionIcon variant="light" color="blue" onClick={() => testMutation.mutate(channel.id)}
                          loading={testMutation.isPending}>
                          <IconPlayerPlay size={16} />
                        </ActionIcon>
                        <ActionIcon variant="light" color="red" onClick={() => deleteMutation.mutate(channel.id)}>
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          ) : (
            <Text p="xl" ta="center" c="dimmed">
              No notification channels configured. Add Slack, Teams, Discord, or webhook integrations.
            </Text>
          )}
        </Paper>
      )}

      <CreateChannelModal opened={opened} onClose={close} />
    </Stack>
  );
}

function CreateChannelModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [channelType, setChannelType] = useState('slack');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [emailRecipients, setEmailRecipients] = useState('');

  const createMutation = useMutation({
    mutationFn: (data: CreateNotificationChannel) => notificationsApi.createChannel(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationChannels'] });
      onClose();
      setName('');
      setWebhookUrl('');
      setEmailRecipients('');
    },
  });

  const handleSubmit = () => {
    let config: Record<string, unknown> = {};
    if (channelType === 'email') {
      config = { recipients: emailRecipients.split(',').map(e => e.trim()).filter(Boolean) };
    } else if (channelType === 'webhook') {
      config = { url: webhookUrl, method: 'POST' };
    } else {
      config = { webhook_url: webhookUrl };
    }

    createMutation.mutate({ name, channel_type: channelType, config });
  };

  const urlPlaceholders: Record<string, string> = {
    slack: 'https://hooks.slack.com/services/...',
    teams: 'https://outlook.office.com/webhook/...',
    discord: 'https://discord.com/api/webhooks/...',
    webhook: 'https://your-service.com/webhook',
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Add Notification Channel" size="md">
      <Stack>
        <TextInput label="Channel Name" placeholder="e.g., #ops-alerts" value={name}
          onChange={e => setName(e.target.value)} />
        <Select
          label="Channel Type"
          data={[
            { value: 'slack', label: 'Slack' },
            { value: 'teams', label: 'Microsoft Teams' },
            { value: 'discord', label: 'Discord' },
            { value: 'webhook', label: 'Custom Webhook' },
            { value: 'email', label: 'Email' },
          ]}
          value={channelType}
          onChange={v => v && setChannelType(v)}
        />
        {channelType === 'email' ? (
          <TextInput
            label="Recipients"
            placeholder="email1@company.com, email2@company.com"
            value={emailRecipients}
            onChange={e => setEmailRecipients(e.target.value)}
            description="Comma-separated list of email addresses"
          />
        ) : (
          <TextInput
            label="Webhook URL"
            placeholder={urlPlaceholders[channelType] || ''}
            value={webhookUrl}
            onChange={e => setWebhookUrl(e.target.value)}
          />
        )}
        <Button onClick={handleSubmit} loading={createMutation.isPending}
          disabled={!name || (channelType === 'email' ? !emailRecipients : !webhookUrl)}>
          Add Channel
        </Button>
      </Stack>
    </Modal>
  );
}
