import { Grid, Paper, Text, Group, SimpleGrid, Card, RingProgress, Stack, Select, Title, Loader, Alert, Badge, ActionIcon, Table } from '@mantine/core'
import { IconUsers, IconFolders, IconFileCheck, IconChartBar, IconAlertCircle, IconArrowRight } from '@tabler/icons-react'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { notifications } from '@mantine/notifications'

interface Client {
    id: number
    name: string
}

interface Stats {
    statistics: {
        total_files: number
        completed: number
        processing: number
        failed: number
    }
    recent_files: Array<{
        id: number
        filename: string
        status: string
        uploaded_at: string
        client_name: string
        transactions_count: number
        error_message?: string
    }>
}

function StatsCard({ title, value, icon: Icon, color, onClick }: { title: string, value: string | number, icon: any, color: string, onClick?: () => void }) {
    return (
        <Card withBorder shadow="sm" style={{ cursor: onClick ? 'pointer' : 'default' }} onClick={onClick}>
            <Group position="apart">
                <Text size="xs" color="dimmed" weight={700} transform="uppercase">{title}</Text>
                <Icon size={20} color={`var(--mantine-color-${color}-6)`} />
            </Group>
            <Text size="xl" weight={700} mt="sm">{value}</Text>
        </Card>
    )
}

export function Dashboard() {
    const [selectedClient, setSelectedClient] = useState<string | null>(null)
    const [clients, setClients] = useState<Client[]>([])
    const [stats, setStats] = useState<Stats | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const navigate = useNavigate()

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true)
            setError(null)
            try {
                // Fetch clients
                const clientsResponse = await fetch('http://localhost:8000/clients/')
                if (!clientsResponse.ok) {
                    throw new Error(`Failed to fetch clients: ${clientsResponse.statusText}`)
                }
                const clientsData = await clientsResponse.json()
                setClients(clientsData)

                // Fetch processing status
                const statsResponse = await fetch('http://localhost:8000/processing-status/')
                if (!statsResponse.ok) {
                    throw new Error(`Failed to fetch stats: ${statsResponse.statusText}`)
                }
                const statsData = await statsResponse.json()
                setStats(statsData)
            } catch (err) {
                console.error('Error fetching data:', err)
                setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
                notifications.show({
                    title: 'Error',
                    message: err instanceof Error ? err.message : 'Failed to load dashboard data',
                    color: 'red',
                })
            } finally {
                setLoading(false)
            }
        }

        fetchData()
        const interval = setInterval(fetchData, 5000) // Refresh every 5 seconds

        return () => clearInterval(interval)
    }, [])

    if (loading) {
        return (
            <Stack align="center" justify="center" style={{ height: '100%', minHeight: 400 }}>
                <Loader size="xl" />
                <Text>Loading dashboard data...</Text>
            </Stack>
        )
    }

    if (error) {
        return (
            <Alert icon={<IconAlertCircle size="1rem" />} title="Error" color="red">
                {error}
            </Alert>
        )
    }

    if (!stats) {
        return (
            <Alert icon={<IconAlertCircle size="1rem" />} title="No Data" color="yellow">
                No dashboard data available. Please try again later.
            </Alert>
        )
    }

    const successRate = stats.statistics.total_files > 0
        ? ((stats.statistics.completed / stats.statistics.total_files) * 100).toFixed(1)
        : '0.0'

    return (
        <Stack spacing="xl">
            <Title order={2}>Dashboard Overview</Title>

            <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} spacing="md">
                <StatsCard
                    title="Total Clients"
                    value={clients.length}
                    icon={IconUsers}
                    color="blue"
                    onClick={() => navigate('/clients')}
                />
                <StatsCard
                    title="Total Files"
                    value={stats.statistics.total_files}
                    icon={IconFolders}
                    color="teal"
                    onClick={() => navigate('/files')}
                />
                <StatsCard
                    title="Completed Files"
                    value={stats.statistics.completed}
                    icon={IconFileCheck}
                    color="green"
                />
                <StatsCard
                    title="Success Rate"
                    value={`${successRate}%`}
                    icon={IconChartBar}
                    color="grape"
                />
            </SimpleGrid>

            {stats.recent_files.length > 0 && (
                <Card withBorder shadow="sm">
                    <Stack>
                        <Group position="apart">
                            <Text weight={500}>Recent Files</Text>
                            <ActionIcon variant="light" onClick={() => navigate('/files')}>
                                <IconArrowRight size={16} />
                            </ActionIcon>
                        </Group>
                        <Table>
                            <Table.Thead>
                                <Table.Tr>
                                    <Table.Th>File Name</Table.Th>
                                    <Table.Th>Client</Table.Th>
                                    <Table.Th>Status</Table.Th>
                                    <Table.Th>Transactions</Table.Th>
                                    <Table.Th>Uploaded</Table.Th>
                                </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>
                                {stats.recent_files.map((file) => (
                                    <Table.Tr key={file.id}>
                                        <Table.Td>{file.filename}</Table.Td>
                                        <Table.Td>{file.client_name}</Table.Td>
                                        <Table.Td>
                                            <Badge
                                                color={
                                                    file.status === 'completed' ? 'green' :
                                                        file.status === 'processing' ? 'blue' :
                                                            file.status === 'failed' ? 'red' : 'gray'
                                                }
                                                title={file.error_message}
                                            >
                                                {file.status}
                                            </Badge>
                                        </Table.Td>
                                        <Table.Td>{file.transactions_count}</Table.Td>
                                        <Table.Td>{new Date(file.uploaded_at).toLocaleString()}</Table.Td>
                                    </Table.Tr>
                                ))}
                            </Table.Tbody>
                        </Table>
                    </Stack>
                </Card>
            )}
        </Stack>
    )
} 