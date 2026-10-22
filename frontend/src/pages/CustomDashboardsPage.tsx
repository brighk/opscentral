import { useState } from 'react';
import {
  Title, Group, Stack, Button, Modal, TextInput, Textarea, Card, SimpleGrid,
  Text, Badge, ActionIcon, Tooltip, Paper, Menu,
} from '@mantine/core';
import {
  IconLayoutDashboard, IconPlus, IconTrash, IconStar, IconStarFilled,
  IconDotsVertical, IconEye,
} from '@tabler/icons-react';
import { useDisclosure } from '@mantine/hooks';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import { dashboardsApi, type DashboardSummary, type Dashboard, type DashboardWidget } from '../api/dashboards';

const widgetTypes = [
  { value: 'metric_chart', label: 'Metric Chart' },
  { value: 'status_card', label: 'Status Card' },
  { value: 'alert_feed', label: 'Alert Feed' },
  { value: 'asset_summary', label: 'Asset Summary' },
  { value: 'process_list', label: 'Process List' },
  { value: 'health_check_status', label: 'Health Check Status' },
  { value: 'vuln_summary', label: 'Vulnerability Summary' },
];

export default function CustomDashboardsPage() {
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [viewDashboard, setViewDashboard] = useState<Dashboard | null>(null);
  const [viewOpened, { open: openView, close: closeView }] = useDisclosure(false);
  const [createForm, setCreateForm] = useState({ name: '', description: '' });

  const { data: dashboards = [], isLoading } = useQuery({
    queryKey: ['custom-dashboards'],
    queryFn: dashboardsApi.list,
  });

  const createMutation = useMutation({
    mutationFn: () => dashboardsApi.create({ name: createForm.name, description: createForm.description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-dashboards'] });
      notifications.show({ title: 'Dashboard created', message: `"${createForm.name}" has been created`, color: 'green' });
      closeCreate();
      setCreateForm({ name: '', description: '' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => dashboardsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-dashboards'] });
      notifications.show({ title: 'Deleted', message: 'Dashboard deleted', color: 'orange' });
    },
  });

  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => dashboardsApi.setDefault(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-dashboards'] });
    },
  });

  const viewDetail = async (id: string) => {
    const data = await dashboardsApi.get(id);
    setViewDashboard(data);
    openView();
  };

  const addWidgetMutation = useMutation({
    mutationFn: ({ dashboardId, widget }: { dashboardId: string; widget: Partial<DashboardWidget> }) =>
      dashboardsApi.addWidget(dashboardId, widget),
    onSuccess: async () => {
      if (viewDashboard) {
        const updated = await dashboardsApi.get(viewDashboard.id);
        setViewDashboard(updated);
      }
    },
  });

  const removeWidgetMutation = useMutation({
    mutationFn: ({ dashboardId, widgetId }: { dashboardId: string; widgetId: string }) =>
      dashboardsApi.removeWidget(dashboardId, widgetId),
    onSuccess: async () => {
      if (viewDashboard) {
        const updated = await dashboardsApi.get(viewDashboard.id);
        setViewDashboard(updated);
      }
    },
  });

  return (
    <Stack>
      <Group justify="space-between">
        <Group>
          <IconLayoutDashboard size={28} />
          <Title order={2}>Custom Dashboards</Title>
        </Group>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          New Dashboard
        </Button>
      </Group>

      {isLoading ? (
        <Text c="dimmed">Loading...</Text>
      ) : dashboards.length === 0 ? (
        <Paper shadow="xs" p="xl" ta="center">
          <Stack align="center">
            <IconLayoutDashboard size={48} color="gray" />
            <Text c="dimmed">No custom dashboards yet</Text>
            <Button onClick={openCreate}>Create your first dashboard</Button>
          </Stack>
        </Paper>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
          {dashboards.map((d: DashboardSummary) => (
            <Card key={d.id} shadow="xs" p="md" withBorder>
              <Group justify="space-between" mb="xs">
                <Group gap="xs">
                  <Text fw={600}>{d.name}</Text>
                  {d.is_default && (
                    <Badge color="yellow" size="xs" leftSection={<IconStarFilled size={10} />}>
                      Default
                    </Badge>
                  )}
                </Group>
                <Menu shadow="md">
                  <Menu.Target>
                    <ActionIcon variant="subtle"><IconDotsVertical size={16} /></ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown>
                    <Menu.Item leftSection={<IconEye size={14} />} onClick={() => viewDetail(d.id)}>
                      View & Edit
                    </Menu.Item>
                    {!d.is_default && (
                      <Menu.Item
                        leftSection={<IconStar size={14} />}
                        onClick={() => setDefaultMutation.mutate(d.id)}
                      >
                        Set as Default
                      </Menu.Item>
                    )}
                    <Menu.Divider />
                    <Menu.Item
                      color="red"
                      leftSection={<IconTrash size={14} />}
                      onClick={() => deleteMutation.mutate(d.id)}
                    >
                      Delete
                    </Menu.Item>
                  </Menu.Dropdown>
                </Menu>
              </Group>
              <Text size="sm" c="dimmed" lineClamp={2}>
                {d.description || 'No description'}
              </Text>
              <Text size="xs" c="dimmed" mt="sm">
                Created {new Date(d.created_at).toLocaleDateString()}
              </Text>
            </Card>
          ))}
        </SimpleGrid>
      )}

      {/* Create Dashboard Modal */}
      <Modal opened={createOpened} onClose={closeCreate} title="Create Dashboard">
        <Stack>
          <TextInput
            label="Name"
            placeholder="My Dashboard"
            required
            value={createForm.name}
            onChange={(e) => setCreateForm({ ...createForm, name: e.currentTarget.value })}
          />
          <Textarea
            label="Description"
            placeholder="What this dashboard shows..."
            value={createForm.description}
            onChange={(e) => setCreateForm({ ...createForm, description: e.currentTarget.value })}
          />
          <Button
            onClick={() => createMutation.mutate()}
            loading={createMutation.isPending}
            disabled={!createForm.name}
          >
            Create
          </Button>
        </Stack>
      </Modal>

      {/* View/Edit Dashboard Modal */}
      <Modal
        opened={viewOpened}
        onClose={closeView}
        title={viewDashboard?.name || 'Dashboard'}
        size="lg"
      >
        {viewDashboard && (
          <Stack>
            <Text size="sm" c="dimmed">{viewDashboard.description || 'No description'}</Text>

            <Group justify="space-between">
              <Text fw={600}>Widgets ({viewDashboard.widgets.length})</Text>
              <Menu shadow="md">
                <Menu.Target>
                  <Button size="xs" leftSection={<IconPlus size={14} />}>Add Widget</Button>
                </Menu.Target>
                <Menu.Dropdown>
                  {widgetTypes.map((wt) => (
                    <Menu.Item
                      key={wt.value}
                      onClick={() =>
                        addWidgetMutation.mutate({
                          dashboardId: viewDashboard.id,
                          widget: { widget_type: wt.value, title: wt.label },
                        })
                      }
                    >
                      {wt.label}
                    </Menu.Item>
                  ))}
                </Menu.Dropdown>
              </Menu>
            </Group>

            {viewDashboard.widgets.length === 0 ? (
              <Text c="dimmed" size="sm" ta="center" py="md">
                No widgets yet. Add one to get started.
              </Text>
            ) : (
              <Stack gap="xs">
                {viewDashboard.widgets.map((w: DashboardWidget) => (
                  <Paper key={w.id} shadow="xs" p="sm" withBorder>
                    <Group justify="space-between">
                      <Group gap="xs">
                        <Badge size="sm" variant="light">
                          {w.widget_type.replace('_', ' ')}
                        </Badge>
                        <Text size="sm" fw={500}>{w.title}</Text>
                      </Group>
                      <Group gap="xs">
                        <Text size="xs" c="dimmed">
                          {w.width}x{w.height} at ({w.position_x},{w.position_y})
                        </Text>
                        <Tooltip label="Remove widget">
                          <ActionIcon
                            size="sm"
                            color="red"
                            variant="light"
                            onClick={() =>
                              removeWidgetMutation.mutate({
                                dashboardId: viewDashboard.id,
                                widgetId: w.id,
                              })
                            }
                          >
                            <IconTrash size={14} />
                          </ActionIcon>
                        </Tooltip>
                      </Group>
                    </Group>
                  </Paper>
                ))}
              </Stack>
            )}
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
