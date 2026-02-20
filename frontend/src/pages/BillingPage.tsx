import {
  Stack, Title, Paper, Text, Group, Badge, Button, Progress,
  SimpleGrid, Card, List, ThemeIcon, Center, Loader,
} from '@mantine/core';
import { IconCheck, IconCreditCard, IconExternalLink } from '@tabler/icons-react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import { billingApi } from '../api/billing';
import type { Plan } from '../api/billing';

export default function BillingPage() {
  const { data: subscription, isLoading: subLoading } = useQuery({
    queryKey: ['subscription'],
    queryFn: () => billingApi.getSubscription().then(r => r.data),
  });

  const { data: plans, isLoading: plansLoading } = useQuery({
    queryKey: ['plans'],
    queryFn: () => billingApi.getPlans().then(r => r.data),
  });

  const { data: usage } = useQuery({
    queryKey: ['usage'],
    queryFn: () => billingApi.getUsage().then(r => r.data),
  });

  const checkoutMutation = useMutation({
    mutationFn: (plan: string) => billingApi.createCheckout(plan),
    onSuccess: (data) => {
      window.location.href = data.data.checkout_url;
    },
    onError: () => {
      notifications.show({ title: 'Error', message: 'Failed to create checkout session', color: 'red' });
    },
  });

  const portalMutation = useMutation({
    mutationFn: () => billingApi.createPortal(),
    onSuccess: (data) => {
      window.location.href = data.data.portal_url;
    },
  });

  if (subLoading || plansLoading) return <Center h={300}><Loader size="lg" /></Center>;

  const usagePercent = subscription ? (subscription.asset_count / subscription.asset_limit) * 100 : 0;

  return (
    <Stack>
      <Title order={2}>Billing & Subscription</Title>

      {/* Current Plan */}
      <Paper withBorder p="lg" radius="md">
        <Group justify="space-between" mb="md">
          <div>
            <Text fw={600} size="lg">Current Plan</Text>
            <Group gap="xs" mt={4}>
              <Badge size="lg" variant="filled" color="blue">
                {subscription?.plan.toUpperCase()}
              </Badge>
              <Badge color={subscription?.status === 'active' ? 'green' : 'red'}>
                {subscription?.status}
              </Badge>
            </Group>
          </div>
          {subscription?.stripe_customer_id && (
            <Button
              variant="light"
              rightSection={<IconExternalLink size={14} />}
              onClick={() => portalMutation.mutate()}
              loading={portalMutation.isPending}
            >
              Manage Subscription
            </Button>
          )}
        </Group>

        <Text size="sm" c="dimmed" mb={4}>
          Asset Usage: {subscription?.asset_count} / {subscription?.asset_limit}
        </Text>
        <Progress
          value={usagePercent}
          color={usagePercent > 80 ? 'red' : usagePercent > 60 ? 'yellow' : 'blue'}
          size="lg"
          radius="md"
        />

        {usage && (
          <SimpleGrid cols={3} mt="md">
            <div>
              <Text size="xs" c="dimmed">Agents</Text>
              <Text fw={600}>{usage.agent_count}</Text>
            </div>
            <div>
              <Text size="xs" c="dimmed">Alert Rules</Text>
              <Text fw={600}>{usage.alert_rule_count}</Text>
            </div>
            <div>
              <Text size="xs" c="dimmed">Assets</Text>
              <Text fw={600}>{usage.asset_count} / {usage.asset_limit}</Text>
            </div>
          </SimpleGrid>
        )}
      </Paper>

      {/* Plan Comparison */}
      <Title order={3}>Available Plans</Title>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        {plans?.map((plan: Plan) => (
          <Card key={plan.key} withBorder radius="md" padding="lg">
            <Text fw={700} size="lg">{plan.name}</Text>
            <Group gap={4} mt="xs">
              <Text size="xl" fw={800}>${plan.price_monthly}</Text>
              <Text size="sm" c="dimmed">/month</Text>
            </Group>
            <Text size="sm" c="dimmed" mb="sm">
              Up to {plan.asset_limit} assets
            </Text>

            <List spacing="xs" size="sm" mb="md" icon={
              <ThemeIcon color="blue" size={20} radius="xl">
                <IconCheck size={12} />
              </ThemeIcon>
            }>
              {plan.features.map((f, i) => (
                <List.Item key={i}>{f}</List.Item>
              ))}
            </List>

            {subscription?.plan === plan.key ? (
              <Button variant="light" color="green" fullWidth disabled>
                Current Plan
              </Button>
            ) : plan.key === 'free' ? (
              <Button variant="light" fullWidth disabled>
                Free Tier
              </Button>
            ) : (
              <Button
                fullWidth
                onClick={() => checkoutMutation.mutate(plan.key)}
                loading={checkoutMutation.isPending}
              >
                Upgrade to {plan.name}
              </Button>
            )}
          </Card>
        ))}
      </SimpleGrid>
    </Stack>
  );
}
