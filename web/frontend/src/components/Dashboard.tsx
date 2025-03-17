import { useEffect, useState } from 'react'
import { Container, Text, Paper, SimpleGrid, Card } from '@mantine/core'
import { IconUsers, IconFiles } from '@tabler/icons-react'

interface Client {
    name: string
    categories: any[]
}

function StatsCard({ title, value, icon: Icon, color }: { title: string, value: string | number, icon: any, color: string }) {
    return (
        <Card withBorder p="md">
            <Text size="xs" c="dimmed" tt="uppercase" fw={700}>{title}</Text>
            <Text size="xl" fw={700} mt="sm">{value}</Text>
            <Icon size={20} color={`var(--mantine-color-${color}-6)`} style={{ position: 'absolute', top: 20, right: 20 }} />
        </Card>
    )
}

export function Dashboard() {
    const [clients, setClients] = useState<Client[]>([])
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        fetch('/api/clients/')
            .then(res => res.json())
            .then(data => {
                console.log('Fetched data:', data)
                setClients(data)
            })
            .catch(err => {
                console.error('Error:', err)
                setError(err.message)
            })
    }, [])

    return (
        <Container size="xl" py="xl">
            <Text size="xl" weight={700} mb="xl">Dashboard</Text>

            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                <StatsCard
                    title="Total Clients"
                    value={clients.length}
                    icon={IconUsers}
                    color="blue"
                />
                <StatsCard
                    title="Total Categories"
                    value={clients.reduce((acc, client) => acc + client.categories.length, 0)}
                    icon={IconFiles}
                    color="teal"
                />
            </SimpleGrid>

            {error && (
                <Paper mt="md" p="md" withBorder bg="red.0">
                    <Text c="red">Error: {error}</Text>
                </Paper>
            )}
        </Container>
    )
} 