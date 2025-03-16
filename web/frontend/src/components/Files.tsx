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
    LoadingOverlay,
} from '@mantine/core'
import { Dropzone } from '@mantine/dropzone'
import { IconUpload, IconX } from '@tabler/icons-react'
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
    const [isUploading, setIsUploading] = useState(false)
    const [ws, setWs] = useState<WebSocket | null>(null)

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
                fetchClientFiles(parseInt(selectedClientId))
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
            fetchClientFiles(parseInt(selectedClientId))
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

    const fetchClientFiles = async (clientId: number) => {
        try {
            const response = await fetch(`http://localhost:8000/clients/${clientId}/files/`)
            const data = await response.json()
            setClientFiles(data)
        } catch (error) {
            console.error('Error fetching client files:', error)
            notifications.show({
                title: 'Error',
                message: 'Failed to fetch client files',
                color: 'red',
            })
        }
    }

    const handleFileUpload = async (files: File[]) => {
        if (!selectedClientId || !files.length) {
            notifications.show({
                title: 'Error',
                message: 'Please select a client and provide a file',
                color: 'red',
            })
            return
        }

        setIsUploading(true)
        const file = files[0]
        const formData = new FormData()
        formData.append('file', file)

        try {
            console.log(`Uploading file for client ${selectedClientId}:`, file.name)
            const response = await fetch(`http://localhost:8000/clients/${selectedClientId}/upload/`, {
                method: 'POST',
                body: formData,
            })

            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || `Upload failed with status ${response.status}`)
            }

            const data = await response.json()
            console.log('Upload response:', data)
            await fetchClientFiles(parseInt(selectedClientId))

            notifications.show({
                title: 'Success',
                message: 'File uploaded successfully and processing started',
                color: 'green',
            })
        } catch (error) {
            console.error('Error uploading file:', error)
            notifications.show({
                title: 'Error',
                message: error instanceof Error ? error.message : 'Failed to upload file. Please try again.',
                color: 'red',
            })
        } finally {
            setIsUploading(false)
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
                return `Processed ${file.total_transactions || 0} transactions`
            case 'processing':
                return 'Processing in progress...'
            case 'pending':
                return 'Queued for processing'
            case 'failed':
                return file.error_message || 'Processing failed'
            default:
                return file.status
        }
    }

    return (
        <Stack spacing="xl">
            <Title order={2}>File Management</Title>

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

            <Paper p="xl" radius="md" withBorder pos="relative">
                <LoadingOverlay visible={isUploading} overlayProps={{ blur: 2 }} />
                <Dropzone
                    onDrop={handleFileUpload}
                    accept={['application/pdf']}
                    maxFiles={1}
                    disabled={!selectedClientId || isUploading}
                >
                    <Group justify="center" style={{ minHeight: 100, pointerEvents: 'none' }}>
                        <Dropzone.Accept>
                            <IconUpload size={32} stroke={1.5} />
                        </Dropzone.Accept>
                        <Dropzone.Reject>
                            <IconX size={32} stroke={1.5} />
                        </Dropzone.Reject>
                        <Dropzone.Idle>
                            <IconUpload size={32} stroke={1.5} />
                        </Dropzone.Idle>
                        <Stack align="center" gap="xs">
                            <Text size="xl">
                                {selectedClientId
                                    ? isUploading
                                        ? 'Uploading...'
                                        : 'Drop PDF here or click to select'
                                    : 'Please select a client first'}
                            </Text>
                            <Text size="sm" c="dimmed">Only PDF files are accepted</Text>
                        </Stack>
                    </Group>
                </Dropzone>
            </Paper>

            {clientFiles.length > 0 && (
                <Paper p="md" radius="md" withBorder>
                    <Stack>
                        <Title order={3}>Uploaded Files</Title>
                        <Table>
                            <Table.Thead>
                                <Table.Tr>
                                    <Table.Th>Name</Table.Th>
                                    <Table.Th>Status</Table.Th>
                                    <Table.Th>Details</Table.Th>
                                    <Table.Th>Uploaded</Table.Th>
                                </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>
                                {clientFiles.map((file) => (
                                    <Table.Tr key={file.id}>
                                        <Table.Td>{file.filename}</Table.Td>
                                        <Table.Td>
                                            <Badge color={getStatusColor(file.status)}>
                                                {file.status}
                                            </Badge>
                                        </Table.Td>
                                        <Table.Td>
                                            {getStatusMessage(file)}
                                        </Table.Td>
                                        <Table.Td>
                                            {new Date(file.uploaded_at).toLocaleString()}
                                        </Table.Td>
                                    </Table.Tr>
                                ))}
                            </Table.Tbody>
                        </Table>
                    </Stack>
                </Paper>
            )}
        </Stack>
    )
} 