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
} from '@mantine/core'
import { notifications } from '@mantine/notifications'

interface Client {
    id: number
    name: string
}

interface Transaction {
    id: number
    date: string
    description: string
    amount: number
    is_categorized: boolean
    category_id: number | null
    category_name: string | null
}

export function Transactions() {
    const [clients, setClients] = useState<Client[]>([])
    const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
    const [transactions, setTransactions] = useState<Transaction[]>([])

    // Fetch clients on mount
    useEffect(() => {
        fetchClients()
    }, [])

    // Fetch transactions when client selection changes
    useEffect(() => {
        if (selectedClientId) {
            fetchTransactions(parseInt(selectedClientId))
        }
    }, [selectedClientId])

    const fetchClients = async () => {
        try {
            const response = await fetch('http://localhost:8000/clients/')
            const data = await response.json()
            setClients(data)

            // If we have clients but no selection, select the first one
            if (data.length > 0 && !selectedClientId) {
                setSelectedClientId(data[0].id.toString())
            }
        } catch (error) {
            console.error('Error fetching clients:', error)
            notifications.show({
                title: 'Error',
                message: 'Failed to fetch clients',
                color: 'red',
            })
        }
    }

    const fetchTransactions = async (clientId: number) => {
        try {
            const response = await fetch(`http://localhost:8000/clients/${clientId}/transactions/`)
            const data = await response.json()
            setTransactions(data)
        } catch (error) {
            console.error('Error fetching transactions:', error)
            notifications.show({
                title: 'Error',
                message: 'Failed to fetch transactions',
                color: 'red',
            })
        }
    }

    const getAmountColor = (amount: number) => {
        return amount < 0 ? 'red' : 'green'
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

            {transactions.length > 0 ? (
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
                                            {transaction.is_categorized ? (
                                                <Badge color="green">
                                                    {transaction.category_name}
                                                </Badge>
                                            ) : (
                                                <Badge color="yellow">
                                                    Uncategorized
                                                </Badge>
                                            )}
                                        </Table.Td>
                                    </Table.Tr>
                                ))}
                            </Table.Tbody>
                        </Table>
                    </Stack>
                </Paper>
            ) : selectedClientId ? (
                <Text c="dimmed" ta="center" py="xl">
                    No transactions found for this client
                </Text>
            ) : null}
        </Stack>
    )
} 