import { useEffect, useState } from 'react'
import { Card, Text, Group, Stack, RingProgress, Table, Loader, Alert } from '@mantine/core'
import { IconFile, IconCheck, IconX, IconLoader, IconAlertCircle } from '@tabler/icons-react'

interface ProcessingStats {
    total_files: number
    completed: number
    processing: number
    failed: number
    total_transactions: number
}

interface RecentFile {
    file_path: string
    status: string
    last_processed: string
    pages_processed: number
    total_transactions: number
}

interface ProcessingStatus {
    statistics: ProcessingStats
    recent_files: RecentFile[]
}

export function ProcessingStatus() {
    const [status, setStatus] = useState<ProcessingStatus | null>(null)
    const [socket, setSocket] = useState<WebSocket | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    // Fetch initial status
    useEffect(() => {
        const fetchStatus = () => {
            setLoading(true)
            setError(null)
            fetch('http://localhost:8000/processing-status/')
                .then(res => {
                    if (!res.ok) {
                        throw new Error(`Failed to fetch status: ${res.statusText}`)
                    }
                    return res.json()
                })
                .then(data => {
                    setStatus(data)
                    setError(null)
                })
                .catch(err => {
                    console.error('Error fetching status:', err)
                    setError(err.message)
                })
                .finally(() => setLoading(false))
        }

        fetchStatus()
    }, [])

    // Setup WebSocket connection
    useEffect(() => {
        const ws = new WebSocket('ws://localhost:8000/ws')

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data)
            if (data.type === 'status_update') {
                // Refresh status after update
                fetch('http://localhost:8000/processing-status/')
                    .then(res => {
                        if (!res.ok) {
                            throw new Error(`Failed to fetch status: ${res.statusText}`)
                        }
                        return res.json()
                    })
                    .then(data => {
                        setStatus(data)
                        setError(null)
                    })
                    .catch(err => {
                        console.error('Error fetching status:', err)
                        setError(err.message)
                    })
            }
        }

        ws.onerror = (error) => {
            console.error('WebSocket error:', error)
            setError('WebSocket connection error')
        }

        setSocket(ws)

        return () => {
            ws.close()
        }
    }, [])

    if (loading) {
        return (
            <Stack align="center" spacing="md" py="xl">
                <Loader size="lg" />
                <Text>Loading processing status...</Text>
            </Stack>
        )
    }

    if (error) {
        return (
            <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
                {error}
            </Alert>
        )
    }

    if (!status) {
        return (
            <Alert icon={<IconAlertCircle size={16} />} title="No Data" color="gray">
                No processing status data available.
            </Alert>
        )
    }

    const { statistics, recent_files } = status

    const successRate = statistics.total_files > 0
        ? (statistics.completed / statistics.total_files) * 100
        : 0

    return (
        <Stack gap="md">
            <Group grow>
                <Card withBorder>
                    <Group justify="space-between">
                        <div>
                            <Text size="xs" c="dimmed">Total Files</Text>
                            <Text fw={700} size="xl">{statistics.total_files}</Text>
                        </div>
                        <IconFile size={32} color="gray" />
                    </Group>
                </Card>

                <Card withBorder>
                    <Group justify="space-between">
                        <div>
                            <Text size="xs" c="dimmed">Success Rate</Text>
                            <Text fw={700} size="xl">{successRate.toFixed(1)}%</Text>
                        </div>
                        <RingProgress
                            size={32}
                            thickness={4}
                            sections={[{ value: successRate, color: 'blue' }]}
                        />
                    </Group>
                </Card>

                <Card withBorder>
                    <Group justify="space-between">
                        <div>
                            <Text size="xs" c="dimmed">Total Transactions</Text>
                            <Text fw={700} size="xl">{statistics.total_transactions}</Text>
                        </div>
                        <IconCheck size={32} color="green" />
                    </Group>
                </Card>
            </Group>

            <Card withBorder>
                <Text fw={700} mb="md">Recent Files</Text>
                {recent_files.length > 0 ? (
                    <Table>
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th>File</Table.Th>
                                <Table.Th>Status</Table.Th>
                                <Table.Th>Processed</Table.Th>
                                <Table.Th>Pages</Table.Th>
                                <Table.Th>Transactions</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {recent_files.map((file) => (
                                <Table.Tr key={file.file_path}>
                                    <Table.Td>{file.file_path.split('/').pop()}</Table.Td>
                                    <Table.Td>
                                        <Group gap="xs">
                                            {file.status === 'completed' && <IconCheck size={16} color="green" />}
                                            {file.status === 'processing' && <IconLoader size={16} color="blue" />}
                                            {file.status === 'failed' && <IconX size={16} color="red" />}
                                            <Text>{file.status}</Text>
                                        </Group>
                                    </Table.Td>
                                    <Table.Td>{new Date(file.last_processed).toLocaleString()}</Table.Td>
                                    <Table.Td>{file.pages_processed}</Table.Td>
                                    <Table.Td>{file.total_transactions}</Table.Td>
                                </Table.Tr>
                            ))}
                        </Table.Tbody>
                    </Table>
                ) : (
                    <Text c="dimmed" ta="center" py="md">No recent files to display.</Text>
                )}
            </Card>
        </Stack>
    )
} 