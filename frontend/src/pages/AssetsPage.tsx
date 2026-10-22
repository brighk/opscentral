import { Stack, Title, Paper, Table, Badge, Text, Group, Center, Loader } from '@mantine/core';
import { IconServer } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { assetsApi } from '../api/assets';

export default function AssetsPage() {
  const navigate = useNavigate();

  const { data: assets, isLoading } = useQuery({
    queryKey: ['assets'],
    queryFn: () => assetsApi.list().then(r => r.data.items),
    refetchInterval: 30000,
  });

  if (isLoading) return <Center h={300}><Loader size="lg" /></Center>;

  return (
    <Stack>
      <Title order={2}>Assets</Title>

      {assets && assets.length > 0 ? (
        <Paper withBorder radius="md">
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Hostname</Table.Th>
                <Table.Th>OS</Table.Th>
                <Table.Th>CPU</Table.Th>
                <Table.Th>RAM</Table.Th>
                <Table.Th>Disk</Table.Th>
                <Table.Th>IP</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {assets.map(asset => (
                <Table.Tr
                  key={asset.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/assets/${asset.id}`)}
                >
                  <Table.Td>
                    <Group gap="xs">
                      <IconServer size={16} />
                      <Text fw={500}>{asset.hostname}</Text>
                    </Group>
                  </Table.Td>
                  <Table.Td>{asset.os_version || asset.os_type || '-'}</Table.Td>
                  <Table.Td>{asset.cpu_cores ? `${asset.cpu_cores} cores` : '-'}</Table.Td>
                  <Table.Td>{asset.ram_total_gb ? `${asset.ram_total_gb} GB` : '-'}</Table.Td>
                  <Table.Td>{asset.disk_total_gb ? `${asset.disk_total_gb} GB` : '-'}</Table.Td>
                  <Table.Td>{asset.ip_addresses?.[0] || '-'}</Table.Td>
                  <Table.Td>
                    <Badge color={asset.status === 'active' ? 'green' : 'gray'}>{asset.status}</Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      ) : (
        <Paper withBorder p="xl" radius="md" ta="center">
          <IconServer size={48} color="gray" />
          <Title order={4} mt="md">No assets discovered yet</Title>
          <Text c="dimmed" mt="sm">
            Assets are automatically created when agents send their first inventory report.
            Install an agent on your servers to get started.
          </Text>
        </Paper>
      )}
    </Stack>
  );
}
