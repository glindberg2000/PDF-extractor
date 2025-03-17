import { useState, useEffect } from 'react'
import {
    Card,
    Text,
    Group,
    Stack,
    Select,
    Title,
    Badge,
    Table,
    ActionIcon,
    Loader,
    Alert,
    Button,
    FileButton,
} from '@mantine/core'
import { IconDownload, IconEye, IconAlertCircle, IconUpload } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'

interface Client {
    id: number
    name: string
}

interface ClientFile {
    id: number
    filename: string
    status: string
    uploaded_at: string
    processed_at: string | null
    error_message: string | null
    total_transactions?: number
    pages_processed?: number
    total_pages?: number
    processing_details?: string[]
}

interface StatusUpdate {
    type: 'status_update'
    file: string
    status: string
    message: string
}

export function Files() {
    const [clients, setClients] = useState<Client[]>([])
    const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
    const [clientFiles, setClientFiles] = useState<ClientFile[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [ws, setWs] = useState<WebSocket | null>(null)
    const [uploading, setUploading] = useState(false)

    // WebSocket connection
    useEffect(() => {
        const websocket = new WebSocket('ws://localhost:8000/ws')

        websocket.onopen = () => {
            console.log('WebSocket connected')
        }

        websocket.onmessage = (event) => {
            const data: StatusUpdate = JSON.parse(event.data)
            if (data.type === 'status_update' && selectedClientId) {
                // Refresh file list when we get a status update
                fetchClientFiles(selectedClientId)
            }
        }

        websocket.onerror = (error) => {
            console.error('WebSocket error:', error)
        }

        setWs(websocket)

        return () => {
            websocket.close()
        }
    }, [selectedClientId])

    // Fetch clients on mount
    useEffect(() => {
        fetchClients()
    }, [])

    // Fetch client files when client selection changes
    useEffect(() => {
        if (selectedClientId) {
            fetchClientFiles(selectedClientId)
        }
    }, [selectedClientId])

    const fetchClients = async () => {
        setLoading(true)
        setError(null)
        try {
            const response = await fetch('http://localhost:8000/clients/')
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

    const fetchClientFiles = async (clientId: string) => {
        setLoading(true)
        try {
            const response = await fetch(`http://localhost:8000/clients/${clientId}/files/`)
            if (!response.ok) {
                throw new Error('Failed to fetch client files')
            }
            const data = await response.json()
            setClientFiles(data)
        } catch (error) {
            console.error('Error fetching client files:', error)
            notifications.show({
                title: 'Error',
                message: 'Failed to fetch client files',
                color: 'red',
            })
        } finally {
            setLoading(false)
        }
    }

    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'completed':
                return 'green'
            case 'processing':
                return 'blue'
            case 'pending':
                return 'yellow'
            case 'failed':
                return 'red'
            default:
                return 'gray'
        }
    }

    const getStatusMessage = (file: ClientFile) => {
        switch (file.status.toLowerCase()) {
            case 'completed':
                return `Processed ${file.total_transactions || 0} transactions from ${file.pages_processed || 0} pages`
            case 'processing':
                return `Processing page ${file.pages_processed || 0} of ${file.total_pages || '?'}`
            case 'pending':
                return 'Queued for processing'
            case 'failed':
                return file.error_message || 'Processing failed'
            default:
                return file.status
        }
    }

    const handleFileUpload = async (file: File | null) => {
        if (!file || !selectedClientId) return

        setUploading(true)
        const formData = new FormData()
        formData.append('file', file)

        try {
            const response = await fetch(`http://localhost:8000/clients/${selectedClientId}/files/`, {
                method: 'POST',
                body: formData,
            })

            if (!response.ok) {
                throw new Error('Failed to upload file')
            }

            notifications.show({
                title: 'Success',
                message: 'File uploaded successfully',
                color: 'green',
            })

            // Refresh file list
            fetchClientFiles(selectedClientId)
        } catch (error) {
            console.error('Error uploading file:', error)
            notifications.show({
                title: 'Error',
                message: 'Failed to upload file',
                color: 'red',
            })
        } finally {
            setUploading(false)
        }
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
                Please create a client first before uploading files.
            </Alert>
        )
    }

    return (
        <Stack gap="md">
            <Group position="apart" align="flex-end">
                <Title order={2}>Files</Title>
                <Group>
                    <Select
                        label="Select Client"
                        placeholder="Choose client"
                        data={clients.map(client => ({ value: client.id.toString(), label: client.name }))}
                        value={selectedClientId}
                        onChange={setSelectedClientId}
                        style={{ width: 200 }}
                    />
                    {selectedClientId && (
                        <FileButton onChange={handleFileUpload} accept="application/pdf">
                            {(props) => (
                                <Button
                                    {...props}
                                    leftIcon={<IconUpload size={16} />}
                                    loading={uploading}
                                >
                                    Upload PDF
                                </Button>
                            )}
                        </FileButton>
                    )}
                </Group>
            </Group>

            {selectedClientId ? (
                loading ? (
                    <Stack align="center" justify="center" style={{ height: '100%', minHeight: 400 }}>
                        <Loader size="xl" />
                        <Text>Loading files...</Text>
                    </Stack>
                ) : clientFiles.length === 0 ? (
                    <Card withBorder p="xl">
                        <Stack align="center" spacing="md">
                            <IconUpload size={48} color="var(--mantine-color-blue-6)" />
                            <Text size="lg" weight={500}>No Files Yet</Text>
                            <Text color="dimmed" size="sm" align="center">
                                Upload your first PDF file using the button above.
                            </Text>
                        </Stack>
                    </Card>
                ) : (
                    <Table>
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th>File Name</Table.Th>
                                <Table.Th>Status</Table.Th>
                                <Table.Th>Progress</Table.Th>
                                <Table.Th>Transactions</Table.Th>
                                <Table.Th>Uploaded</Table.Th>
                                <Table.Th>Actions</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {clientFiles.map((file) => (
                                <Table.Tr key={file.id}>
                                    <Table.Td>{file.filename}</Table.Td>
                                    <Table.Td>
                                        <Badge
                                            color={getStatusColor(file.status)}
                                            title={file.error_message}
                                        >
                                            {file.status}
                                        </Badge>
                                    </Table.Td>
                                    <Table.Td>
                                        <Text size="sm" color="dimmed">
                                            {getStatusMessage(file)}
                                        </Text>
                                        {file.processing_details && file.processing_details.length > 0 && (
                                            <Text size="xs" color="dimmed" mt={4}>
                                                {file.processing_details.join(', ')}
                                            </Text>
                                        )}
                                    </Table.Td>
                                    <Table.Td>{file.total_transactions || 0}</Table.Td>
                                    <Table.Td>{new Date(file.uploaded_at).toLocaleString()}</Table.Td>
                                    <Table.Td>
                                        <Group spacing={4}>
                                            <ActionIcon
                                                variant="light"
                                                color="blue"
                                                onClick={() => window.open(`http://localhost:8000/clients/${selectedClientId}/files/${file.id}/view`, '_blank')}
                                                title="View PDF"
                                            >
                                                <IconEye size={16} />
                                            </ActionIcon>
                                            <ActionIcon
                                                variant="light"
                                                color="green"
                                                onClick={() => window.open(`http://localhost:8000/clients/${selectedClientId}/files/${file.id}/download`, '_blank')}
                                                title="Download PDF"
                                            >
                                                <IconDownload size={16} />
                                            </ActionIcon>
                                        </Group>
                                    </Table.Td>
                                </Table.Tr>
                            ))}
                        </Table.Tbody>
                    </Table>
                )
            ) : (
                <Alert icon={<IconAlertCircle size="1rem" />} title="Select a Client" color="blue">
                    Please select a client to view their files.
                </Alert>
            )}
        </Stack>
    )
} 