import { Stack, Title, Paper, Text, Group, Badge, SimpleGrid, Table, Loader, Center, Button } from '@mantine/core';
import { IconArrowLeft } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { assetsApi } from '../api/assets';

function InfoItem({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>{label}</Text>
      <Text size="sm" fw={500}>{value ?? '-'}</Text>
    </div>
  );
}

export default function AssetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: asset, isLoading } = useQuery({
    queryKey: ['asset', id],
    queryFn: () => assetsApi.get(id!).then(r => r.data),
    enabled: !!id,
  });

  if (isLoading) return <Center h={300}><Loader size="lg" /></Center>;
  if (!asset) return <Text>Asset not found</Text>;

  return (
    <Stack>
      <Group>
        <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => navigate('/assets')}>
          Back
        </Button>
        <Title order={2}>{asset.hostname}</Title>
        <Badge color={asset.status === 'active' ? 'green' : 'gray'}>{asset.status}</Badge>
      </Group>

      <Paper withBorder p="md" radius="md">
        <Text fw={600} mb="md">System Information</Text>
        <SimpleGrid cols={{ base: 2, md: 4 }}>
          <InfoItem label="OS" value={asset.os_version || asset.os_type} />
          <InfoItem label="CPU" value={asset.cpu_model} />
          <InfoItem label="CPU Cores" value={asset.cpu_cores} />
          <InfoItem label="RAM" value={asset.ram_total_gb ? `${asset.ram_total_gb} GB` : null} />
          <InfoItem label="Disk" value={asset.disk_total_gb ? `${asset.disk_total_gb} GB` : null} />
          <InfoItem label="IP Addresses" value={asset.ip_addresses?.join(', ')} />
          <InfoItem label="MAC Addresses" value={asset.mac_addresses?.join(', ')} />
          <InfoItem label="Type" value={asset.asset_type} />
        </SimpleGrid>
      </Paper>

      <Paper withBorder p="md" radius="md">
        <Text fw={600} mb="md">Installed Software ({asset.software?.length || 0})</Text>
        {asset.software && asset.software.length > 0 ? (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Version</Table.Th>
                <Table.Th>Publisher</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {asset.software.map(sw => (
                <Table.Tr key={sw.id}>
                  <Table.Td>{sw.name}</Table.Td>
                  <Table.Td>{sw.version || '-'}</Table.Td>
                  <Table.Td>{sw.publisher || '-'}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        ) : (
          <Text c="dimmed">No software inventory available</Text>
        )}
      </Paper>
    </Stack>
  );
}
