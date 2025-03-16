import { Grid, Paper, Text, Group, SimpleGrid, Card, RingProgress, Stack, Select, Title } from '@mantine/core'
import { IconUsers, IconFolders, IconFileCheck, IconChartBar } from '@tabler/icons-react'
import { useState, useEffect } from 'react'
import { ProcessingStatus } from './ProcessingStatus'

interface Client {
    id: number
    name: string
}

interface StatsCardProps {
    title: string
    value: string
    icon: typeof IconUsers
    color: string
}

function StatsCard({ title, value, icon: Icon, color }: StatsCardProps) {
    return (
        <Card withBorder radius="md" p="md">
            <Group position="apart">
                <div>
                    <Text size="xs" color="dimmed" transform="uppercase" weight={700}>
                        {title}
                    </Text>
                    <Text weight={700} size="xl">
                        {value}
                    </Text>
                </div>
                <Icon size={32} color={color} />
            </Group>
        </Card>
    )
}

export function Dashboard() {
    const [selectedClient, setSelectedClient] = useState<string | null>(null)
    const [clients, setClients] = useState<Client[]>([])

    useEffect(() => {
        // Fetch clients
        fetch('http://localhost:8000/clients/')
            .then(res => res.json())
            .then(data => setClients(data))
            .catch(console.error)
    }, [])

    return (
        <Stack gap="md">
            <Title order={2}>Dashboard Overview</Title>
            <ProcessingStatus />
            <Group position="apart" align="flex-end">
                <Select
                    label="Select Client"
                    placeholder="Choose client"
                    data={clients.map(client => ({ value: client.id.toString(), label: client.name }))}
                    value={selectedClient}
                    onChange={setSelectedClient}
                    style={{ width: 200 }}
                />
            </Group>

            <SimpleGrid cols={4}>
                <StatsCard
                    title="Total Clients"
                    value="12"
                    icon={IconUsers}
                    color="blue"
                />
                <StatsCard
                    title="Processed Files"
                    value="156"
                    icon={IconFileCheck}
                    color="teal"
                />
                <StatsCard
                    title="Pending Files"
                    value="3"
                    icon={IconFolders}
                    color="orange"
                />
                <StatsCard
                    title="Success Rate"
                    value="98%"
                    icon={IconChartBar}
                    color="grape"
                />
            </SimpleGrid>

            <Grid>
                <Grid.Col span={8}>
                    <Paper withBorder radius="md" p="md">
                        <Text size="lg" weight={700} mb="md">Recent Files</Text>
                        <Stack spacing="xs">
                            {mockRecentFiles.map((file, index) => (
                                <Card key={index} withBorder padding="xs">
                                    <Group position="apart">
                                        <div>
                                            <Text weight={500}>{file.name}</Text>
                                            <Text size="xs" color="dimmed">{file.date}</Text>
                                        </div>
                                        <Text
                                            size="sm"
                                            weight={500}
                                            color={
                                                file.status === 'Processed'
                                                    ? 'teal'
                                                    : file.status === 'Processing'
                                                        ? 'blue'
                                                        : 'red'
                                            }
                                        >
                                            {file.status}
                                        </Text>
                                    </Group>
                                </Card>
                            ))}
                        </Stack>
                    </Paper>
                </Grid.Col>

                <Grid.Col span={4}>
                    <Paper withBorder radius="md" p="md" h="100%">
                        <Text size="lg" weight={700} mb="md">Processing Status</Text>
                        <Stack align="center" spacing="md">
                            <RingProgress
                                sections={[{ value: 87, color: 'teal' }]}
                                label={
                                    <Text size="xl" align="center" weight={700}>
                                        87%
                                    </Text>
                                }
                                size={150}
                            />
                            <Text size="sm" color="dimmed" align="center">
                                Overall Success Rate
                            </Text>
                        </Stack>
                    </Paper>
                </Grid.Col>
            </Grid>
        </Stack>
    )
} 