import { useState, useEffect } from 'react'
import {
    Stack,
    Title,
    Text,
    Select,
    Paper,
    Table,
    Badge,
    Group,
    NumberFormatter,
    Loader,
    Alert,
    Button,
} from '@mantine/core'
import { IconAlertCircle, IconFileUpload } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useNavigate } from 'react-router-dom'

interface Client {
    id: number
    name: string
}

interface Transaction {
    id: number
    date: string
    description: string
    amount: number
    category: string | null
}

export function Transactions() {
    const [clients, setClients] = useState<Client[]>([])
    const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
    const [transactions, setTransactions] = useState<Transaction[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const navigate = useNavigate()

    useEffect(() => {
        fetchClients()
    }, [])

    useEffect(() => {
        if (selectedClientId) {
            fetchTransactions(selectedClientId)
        } else {
            setTransactions([])
        }
    }, [selectedClientId])

    const fetchClients = async () => {
        setLoading(true)
        setError(null)
        try {
            const response = await fetch('/api/clients/')
            if (!response.ok) {
                throw new Error('Failed to fetch clients')
            }
            const data = await response.json()
            setClients(data)
        } catch (error) {
            console.error('Error fetching clients:', error)
            setError(error instanceof Error ? error.message : 'Failed to load clients')
            notifications.show({
                title: 'Error',
                message: 'Failed to load clients. Please try again.',
                color: 'red',
            })
        } finally {
            setLoading(false)
        }
    }

    const fetchTransactions = async (clientId: string) => {
        setLoading(true)
        try {
            const response = await fetch(`/api/clients/${clientId}/transactions/`)
            if (!response.ok) {
                throw new Error('Failed to fetch transactions')
            }
            const data = await response.json()
            setTransactions(data)
        } catch (error) {
            console.error('Error fetching transactions:', error)
            notifications.show({
                title: 'Error',
                message: 'Failed to fetch transactions',
                color: 'red',
            })
        } finally {
            setLoading(false)
        }
    }

    const getAmountColor = (amount: number) => {
        return amount < 0 ? 'red' : 'green'
    }

    if (loading && !selectedClientId) {
        return (
            <Stack align="center" justify="center" style={{ height: '100%', minHeight: 400 }}>
                <Loader size="xl" />
                <Text>Loading clients...</Text>
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

    if (!clients.length) {
        return (
            <Alert icon={<IconAlertCircle size="1rem" />} title="No Clients" color="blue">
                Please create a client first to view transactions.
            </Alert>
        )
    }

    return (
        <Stack spacing="xl">
            <Title order={2}>Transactions</Title>

            <Select
                label="Select Client"
                placeholder="Choose client"
                data={clients.map(client => ({
                    value: client.id.toString(),
                    label: client.name
                }))}
                value={selectedClientId}
                onChange={setSelectedClientId}
                searchable
            />

            {selectedClientId && (
                loading ? (
                    <Stack align="center" p="xl">
                        <Loader size="sm" />
                        <Text size="sm">Loading transactions...</Text>
                    </Stack>
                ) : transactions.length > 0 ? (
                    <Paper p="md" radius="md" withBorder>
                        <Stack>
                            <Group justify="space-between" align="center">
                                <Title order={3}>Transaction History</Title>
                                <Text size="sm" c="dimmed">
                                    {transactions.length} transactions found
                                </Text>
                            </Group>
                            <Table>
                                <Table.Thead>
                                    <Table.Tr>
                                        <Table.Th>Date</Table.Th>
                                        <Table.Th>Description</Table.Th>
                                        <Table.Th>Amount</Table.Th>
                                        <Table.Th>Category</Table.Th>
                                    </Table.Tr>
                                </Table.Thead>
                                <Table.Tbody>
                                    {transactions.map((transaction) => (
                                        <Table.Tr key={transaction.id}>
                                            <Table.Td>
                                                {new Date(transaction.date).toLocaleDateString()}
                                            </Table.Td>
                                            <Table.Td>{transaction.description}</Table.Td>
                                            <Table.Td>
                                                <Text c={getAmountColor(transaction.amount)}>
                                                    <NumberFormatter
                                                        value={Math.abs(transaction.amount)}
                                                        prefix={transaction.amount < 0 ? "-$" : "$"}
                                                        thousandSeparator=","
                                                        decimalScale={2}
                                                        fixedDecimalScale
                                                    />
                                                </Text>
                                            </Table.Td>
                                            <Table.Td>
                                                {transaction.category ? (
                                                    <Badge color="blue">
                                                        {transaction.category}
                                                    </Badge>
                                                ) : (
                                                    <Text size="sm" c="dimmed">Uncategorized</Text>
                                                )}
                                            </Table.Td>
                                        </Table.Tr>
                                    ))}
                                </Table.Tbody>
                            </Table>
                        </Stack>
                    </Paper>
                ) : (
                    <Stack align="center" p="xl" spacing="md">
                        <Text c="dimmed">No transactions found for this client</Text>
                        <Button
                            leftIcon={<IconFileUpload size={16} />}
                            variant="light"
                            onClick={() => navigate('/files')}
                        >
                            Upload PDF to Extract Transactions
                        </Button>
                    </Stack>
                )
            )}
        </Stack>
    )
} 