import { useState } from 'react';
import {
  Title, Table, Badge, Group, Stack, Button, Modal, TextInput,
  Select, Text, Paper, Tabs, ActionIcon, Tooltip,
} from '@mantine/core';
import { IconUsers, IconPlus, IconTrash } from '@tabler/icons-react';
import { useDisclosure } from '@mantine/hooks';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import { usersApi, type ManagedUser, type AuditLogEntry } from '../api/users';

export default function UserManagementPage() {
  const queryClient = useQueryClient();
  const [inviteOpened, { open: openInvite, close: closeInvite }] = useDisclosure(false);
  const [inviteForm, setInviteForm] = useState({ email: '', full_name: '', role: 'viewer', password: '' });

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['managed-users'],
    queryFn: usersApi.list,
  });

  const { data: auditLogs = [] } = useQuery({
    queryKey: ['audit-log'],
    queryFn: () => usersApi.auditLog({ limit: 50 }),
  });

  const inviteMutation = useMutation({
    mutationFn: () => usersApi.invite(inviteForm),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['managed-users'] });
      queryClient.invalidateQueries({ queryKey: ['audit-log'] });
      notifications.show({ title: 'User invited', message: `Invitation sent to ${inviteForm.email}`, color: 'green' });
      closeInvite();
      setInviteForm({ email: '', full_name: '', role: 'viewer', password: '' });
    },
    onError: () => {
      notifications.show({ title: 'Error', message: 'Failed to invite user', color: 'red' });
    },
  });

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      usersApi.updateRole(userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['managed-users'] });
      queryClient.invalidateQueries({ queryKey: ['audit-log'] });
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (userId: string) => usersApi.deactivate(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['managed-users'] });
      notifications.show({ title: 'User deactivated', message: 'User has been deactivated', color: 'orange' });
    },
  });

  return (
    <Stack>
      <Group justify="space-between">
        <Group>
          <IconUsers size={28} />
          <Title order={2}>User Management</Title>
        </Group>
        <Button leftSection={<IconPlus size={16} />} onClick={openInvite}>
          Invite User
        </Button>
      </Group>

      <Tabs defaultValue="users">
        <Tabs.List>
          <Tabs.Tab value="users">Users ({users.length})</Tabs.Tab>
          <Tabs.Tab value="audit">Audit Log</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="users" pt="md">
          <Paper shadow="xs" p="md">
            {isLoading ? (
              <Text c="dimmed">Loading...</Text>
            ) : (
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Name</Table.Th>
                    <Table.Th>Email</Table.Th>
                    <Table.Th>Role</Table.Th>
                    <Table.Th>Status</Table.Th>
                    <Table.Th>Joined</Table.Th>
                    <Table.Th>Actions</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {users.map((u: ManagedUser) => (
                    <Table.Tr key={u.id}>
                      <Table.Td><Text size="sm" fw={500}>{u.full_name}</Text></Table.Td>
                      <Table.Td><Text size="sm">{u.email}</Text></Table.Td>
                      <Table.Td>
                        <Select
                          size="xs"
                          w={120}
                          value={u.role}
                          data={['admin', 'operator', 'viewer']}
                          onChange={(role) => role && roleMutation.mutate({ userId: u.id, role })}
                        />
                      </Table.Td>
                      <Table.Td>
                        <Badge color={u.is_active ? 'green' : 'gray'} size="sm">
                          {u.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" c="dimmed">
                          {new Date(u.created_at).toLocaleDateString()}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        {u.is_active && (
                          <Tooltip label="Deactivate">
                            <ActionIcon
                              color="red"
                              variant="light"
                              onClick={() => deactivateMutation.mutate(u.id)}
                            >
                              <IconTrash size={16} />
                            </ActionIcon>
                          </Tooltip>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Paper>
        </Tabs.Panel>

        <Tabs.Panel value="audit" pt="md">
          <Paper shadow="xs" p="md">
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>When</Table.Th>
                  <Table.Th>User</Table.Th>
                  <Table.Th>Action</Table.Th>
                  <Table.Th>Resource</Table.Th>
                  <Table.Th>Details</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {auditLogs.map((log: AuditLogEntry) => (
                  <Table.Tr key={log.id}>
                    <Table.Td>
                      <Text size="sm" c="dimmed">
                        {new Date(log.performed_at).toLocaleString()}
                      </Text>
                    </Table.Td>
                    <Table.Td><Text size="sm">{log.user_email}</Text></Table.Td>
                    <Table.Td>
                      <Badge variant="light" size="sm">{log.action}</Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{log.resource_type}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed" lineClamp={1}>
                        {JSON.stringify(log.details)}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Paper>
        </Tabs.Panel>
      </Tabs>

      {/* Invite User Modal */}
      <Modal opened={inviteOpened} onClose={closeInvite} title="Invite User">
        <Stack>
          <TextInput
            label="Email"
            placeholder="user@company.com"
            required
            value={inviteForm.email}
            onChange={(e) => setInviteForm({ ...inviteForm, email: e.currentTarget.value })}
          />
          <TextInput
            label="Full Name"
            placeholder="John Doe"
            required
            value={inviteForm.full_name}
            onChange={(e) => setInviteForm({ ...inviteForm, full_name: e.currentTarget.value })}
          />
          <Select
            label="Role"
            data={[
              { value: 'admin', label: 'Admin — Full access' },
              { value: 'operator', label: 'Operator — Manage, no admin' },
              { value: 'viewer', label: 'Viewer — Read-only' },
            ]}
            value={inviteForm.role}
            onChange={(v) => v && setInviteForm({ ...inviteForm, role: v })}
          />
          <TextInput
            label="Temporary Password"
            placeholder="Set a temporary password"
            required
            value={inviteForm.password}
            onChange={(e) => setInviteForm({ ...inviteForm, password: e.currentTarget.value })}
          />
          <Button
            onClick={() => inviteMutation.mutate()}
            loading={inviteMutation.isPending}
            disabled={!inviteForm.email || !inviteForm.full_name || !inviteForm.password}
          >
            Send Invitation
          </Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
