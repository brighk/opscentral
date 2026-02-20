import { useState } from 'react';
import {
  Title, Group, Stack, Card, SimpleGrid, Text, Badge, Paper,
  Select, Table, Progress, Tooltip, Modal,
} from '@mantine/core';
import {
  IconWorldWww, IconLock, IconAlertTriangle, IconCheck, IconX,
} from '@tabler/icons-react';
import { useDisclosure } from '@mantine/hooks';
import { useQuery } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { uptimeApi, type UptimeStat, type ResponseTimePoint } from '../api/uptime';

const statusColor: Record<string, string> = {
  up: 'green',
  down: 'red',
  unknown: 'gray',
};

export default function UptimePage() {
  const [period, setPeriod] = useState('24h');
  const [selectedCheck, setSelectedCheck] = useState<UptimeStat | null>(null);
  const [detailOpened, { open: openDetail, close: closeDetail }] = useDisclosure(false);

  const { data: stats = [], isLoading } = useQuery({
    queryKey: ['uptime-stats', period],
    queryFn: () => uptimeApi.stats({ period }),
  });

  const { data: responseTimes = [] } = useQuery<ResponseTimePoint[]>({
    queryKey: ['response-times', selectedCheck?.check_id, period],
    queryFn: () => uptimeApi.responseTimes(selectedCheck!.check_id, period),
    enabled: !!selectedCheck,
  });

  const allUp = stats.every((s: UptimeStat) => s.status === 'up');
  const anyDown = stats.some((s: UptimeStat) => s.status === 'down');
  const avgUptime = stats.length > 0
    ? stats.reduce((sum: number, s: UptimeStat) => sum + (s.uptime_percent || 0), 0) / stats.length
    : 0;

  const openCheckDetail = (stat: UptimeStat) => {
    setSelectedCheck(stat);
    openDetail();
  };

  return (
    <Stack>
      <Group justify="space-between">
        <Group>
          <IconWorldWww size={28} />
          <Title order={2}>Uptime Monitoring</Title>
        </Group>
        <Select
          w={150}
          value={period}
          onChange={(v) => v && setPeriod(v)}
          data={[
            { value: '1h', label: 'Last hour' },
            { value: '6h', label: 'Last 6 hours' },
            { value: '24h', label: 'Last 24 hours' },
            { value: '7d', label: 'Last 7 days' },
            { value: '30d', label: 'Last 30 days' },
          ]}
        />
      </Group>

      {/* Overall Status */}
      <Card shadow="xs" p="md">
        <Group>
          {allUp ? (
            <IconCheck size={24} color="green" />
          ) : anyDown ? (
            <IconX size={24} color="red" />
          ) : (
            <IconAlertTriangle size={24} color="orange" />
          )}
          <div>
            <Text fw={600}>
              {allUp ? 'All Systems Operational' : anyDown ? 'Outage Detected' : 'Some Issues'}
            </Text>
            <Text size="sm" c="dimmed">
              {stats.length} services monitored | Average uptime: {avgUptime.toFixed(2)}%
            </Text>
          </div>
        </Group>
      </Card>

      {isLoading ? (
        <Text c="dimmed">Loading...</Text>
      ) : stats.length === 0 ? (
        <Paper shadow="xs" p="xl" ta="center">
          <Stack align="center">
            <IconWorldWww size={48} color="gray" />
            <Text c="dimmed">No health checks configured</Text>
            <Text size="sm" c="dimmed">Create health checks to start monitoring uptime</Text>
          </Stack>
        </Paper>
      ) : (
        <Paper shadow="xs" p="md">
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Service</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Uptime</Table.Th>
                <Table.Th>Avg Response</Table.Th>
                <Table.Th>SSL</Table.Th>
                <Table.Th>Last Check</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {stats.map((s: UptimeStat) => (
                <Table.Tr
                  key={s.check_id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => openCheckDetail(s)}
                >
                  <Table.Td>
                    <Text size="sm" fw={500}>{s.name}</Text>
                    <Text size="xs" c="dimmed">{s.target}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge color={statusColor[s.status] || 'gray'} size="sm">
                      {s.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {s.uptime_percent !== null ? (
                      <Group gap="xs">
                        <Progress
                          value={s.uptime_percent}
                          color={s.uptime_percent >= 99.5 ? 'green' : s.uptime_percent >= 95 ? 'yellow' : 'red'}
                          size="sm"
                          w={60}
                        />
                        <Text size="sm">{s.uptime_percent}%</Text>
                      </Group>
                    ) : (
                      <Text size="sm" c="dimmed">—</Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">
                      {s.avg_response_time_ms ? `${s.avg_response_time_ms}ms` : '—'}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    {s.ssl_certificate ? (
                      s.ssl_certificate.error ? (
                        <Tooltip label={s.ssl_certificate.error}>
                          <Badge color="red" size="sm" leftSection={<IconAlertTriangle size={10} />}>
                            Error
                          </Badge>
                        </Tooltip>
                      ) : s.ssl_certificate.is_expired ? (
                        <Badge color="red" size="sm">Expired</Badge>
                      ) : s.ssl_certificate.is_expiring_soon ? (
                        <Tooltip label={`Expires in ${s.ssl_certificate.days_until_expiry} days`}>
                          <Badge color="yellow" size="sm" leftSection={<IconLock size={10} />}>
                            {s.ssl_certificate.days_until_expiry}d
                          </Badge>
                        </Tooltip>
                      ) : (
                        <Tooltip label={`Valid for ${s.ssl_certificate.days_until_expiry} days`}>
                          <Badge color="green" size="sm" leftSection={<IconLock size={10} />}>
                            OK
                          </Badge>
                        </Tooltip>
                      )
                    ) : (
                      <Text size="sm" c="dimmed">—</Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {s.last_checked_at ? new Date(s.last_checked_at).toLocaleTimeString() : 'Never'}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}

      {/* Detail Modal */}
      <Modal
        opened={detailOpened}
        onClose={closeDetail}
        title={selectedCheck?.name || 'Service Details'}
        size="lg"
      >
        {selectedCheck && (
          <Stack>
            <SimpleGrid cols={3}>
              <Card shadow="xs" p="sm">
                <Text size="xs" c="dimmed">Uptime</Text>
                <Text size="lg" fw={700}>
                  {selectedCheck.uptime_percent !== null ? `${selectedCheck.uptime_percent}%` : '—'}
                </Text>
              </Card>
              <Card shadow="xs" p="sm">
                <Text size="xs" c="dimmed">Avg Response</Text>
                <Text size="lg" fw={700}>
                  {selectedCheck.avg_response_time_ms ? `${selectedCheck.avg_response_time_ms}ms` : '—'}
                </Text>
              </Card>
              <Card shadow="xs" p="sm">
                <Text size="xs" c="dimmed">Checks</Text>
                <Text size="lg" fw={700}>
                  {selectedCheck.successful_checks}/{selectedCheck.total_checks}
                </Text>
              </Card>
            </SimpleGrid>

            {/* SSL Certificate Info */}
            {selectedCheck.ssl_certificate && !selectedCheck.ssl_certificate.error && (
              <Card shadow="xs" p="sm">
                <Group gap="xs" mb="xs">
                  <IconLock size={16} />
                  <Text size="sm" fw={600}>SSL Certificate</Text>
                </Group>
                <SimpleGrid cols={2}>
                  <div>
                    <Text size="xs" c="dimmed">Issuer</Text>
                    <Text size="sm">{selectedCheck.ssl_certificate.issuer}</Text>
                  </div>
                  <div>
                    <Text size="xs" c="dimmed">Expires</Text>
                    <Text size="sm">
                      {selectedCheck.ssl_certificate.not_after
                        ? new Date(selectedCheck.ssl_certificate.not_after).toLocaleDateString()
                        : '—'
                      }
                      {selectedCheck.ssl_certificate.days_until_expiry !== null && (
                        <Text span size="xs" c="dimmed"> ({selectedCheck.ssl_certificate.days_until_expiry} days)</Text>
                      )}
                    </Text>
                  </div>
                </SimpleGrid>
              </Card>
            )}

            {/* Response Time Chart */}
            <Text fw={600} size="sm">Response Time</Text>
            {responseTimes.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={responseTimes}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="timestamp"
                    tickFormatter={(v) => new Date(v).toLocaleTimeString()}
                    fontSize={11}
                  />
                  <YAxis unit="ms" fontSize={11} />
                  <RechartsTooltip
                    labelFormatter={(v) => new Date(v as string).toLocaleString()}
                    formatter={(v: number) => [`${v}ms`, 'Response Time']}
                  />
                  <Line
                    type="monotone"
                    dataKey="response_time_ms"
                    stroke="#228be6"
                    dot={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <Text size="sm" c="dimmed" ta="center" py="md">No response time data yet</Text>
            )}
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
