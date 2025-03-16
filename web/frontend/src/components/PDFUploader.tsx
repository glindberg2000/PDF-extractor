import { useState } from 'react'
import { Paper, Text, Group, Stack, Table, Button } from '@mantine/core'
import { Dropzone } from '@mantine/dropzone'
import { useMutation } from '@tanstack/react-query'
import axios from 'axios'
import { IconUpload, IconFileAnalytics, IconDownload } from '@tabler/icons-react'

interface Transaction {
    date: string
    description: string
    amount: number
    category?: string
}

export function PDFUploader() {
    const [file, setFile] = useState<File | null>(null)
    const [transactions, setTransactions] = useState<Transaction[]>([])
    const [error, setError] = useState<string | null>(null)

    const uploadMutation = useMutation({
        mutationFn: async (file: File) => {
            const formData = new FormData()
            formData.append('file', file)
            const response = await axios.post('http://localhost:8000/upload/', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            })
            return response.data
        },
        onSuccess: (data) => {
            setTransactions(data.transactions)
            setError(null)
        },
        onError: (error: any) => {
            setError(error.response?.data?.detail || 'An error occurred while processing the file')
        },
    })

    const handleDrop = (files: File[]) => {
        const pdf = files[0]
        setFile(pdf)
        uploadMutation.mutate(pdf)
    }

    return (
        <Stack spacing="xl">
            <Paper p="xl" radius="md" withBorder>
                <Dropzone
                    onDrop={handleDrop}
                    accept={['application/pdf']}
                    maxSize={20 * 1024 ** 2}
                    loading={uploadMutation.isPending}
                    style={{ borderRadius: '8px' }}
                >
                    <Group position="center" spacing="xl" style={{ minHeight: 220, pointerEvents: 'none' }}>
                        <Stack align="center" spacing="xs">
                            {uploadMutation.isPending ? (
                                <IconFileAnalytics size={50} stroke={1.5} />
                            ) : (
                                <IconUpload size={50} stroke={1.5} />
                            )}
                            <Text size="xl" inline weight={500}>
                                {uploadMutation.isPending
                                    ? 'Processing your statement...'
                                    : 'Drag your PDF statement here or click to select'}
                            </Text>
                            <Text size="sm" color="dimmed" inline mt={7}>
                                Upload your bank statement to extract transactions
                            </Text>
                        </Stack>
                    </Group>
                </Dropzone>
            </Paper>

            {error && (
                <Paper p="md" radius="md" withBorder bg="red.0">
                    <Text color="red.7" weight={500}>{error}</Text>
                </Paper>
            )}

            {transactions.length > 0 && (
                <Paper p="xl" radius="md" withBorder>
                    <Group position="apart" mb="xl">
                        <Text size="lg" weight={700}>Extracted Transactions</Text>
                        <Button
                            leftIcon={<IconDownload size={20} />}
                            onClick={() => {
                                const csv = [
                                    ['Date', 'Description', 'Amount', 'Category'],
                                    ...transactions.map(t => [
                                        t.date,
                                        t.description,
                                        t.amount.toString(),
                                        t.category || 'Uncategorized'
                                    ])
                                ].map(row => row.join(',')).join('\n')

                                const blob = new Blob([csv], { type: 'text/csv' })
                                const url = window.URL.createObjectURL(blob)
                                const a = document.createElement('a')
                                a.href = url
                                a.download = 'transactions.csv'
                                a.click()
                                window.URL.revokeObjectURL(url)
                            }}
                        >
                            Download CSV
                        </Button>
                    </Group>

                    <Table striped highlightOnHover>
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th>Date</Table.Th>
                                <Table.Th>Description</Table.Th>
                                <Table.Th>Amount</Table.Th>
                                <Table.Th>Category</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {transactions.map((transaction, index) => (
                                <Table.Tr key={index}>
                                    <Table.Td>{transaction.date}</Table.Td>
                                    <Table.Td>{transaction.description}</Table.Td>
                                    <Table.Td style={{ color: transaction.amount < 0 ? 'red' : 'green' }}>
                                        ${Math.abs(transaction.amount).toFixed(2)}
                                    </Table.Td>
                                    <Table.Td>{transaction.category || 'Uncategorized'}</Table.Td>
                                </Table.Tr>
                            ))}
                        </Table.Tbody>
                    </Table>
                </Paper>
            )}
        </Stack>
    )
} 