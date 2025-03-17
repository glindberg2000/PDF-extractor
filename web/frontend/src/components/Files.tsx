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
    Paper,
    Grid,
    useMantineTheme,
    ScrollArea,
} from '@mantine/core'
import { IconDownload, IconEye, IconAlertCircle, IconUpload, IconFolder, IconFile } from '@tabler/icons-react'
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
    path?: string
}

interface StatusUpdate {
    type: 'status_update'
    file: string
    status: string
    message: string
}

interface FolderStructure {
    name: string
    type: 'folder' | 'file'
    children?: FolderStructure[]
    file?: ClientFile
}

export function Files() {
    const [clients, setClients] = useState<Client[]>([])
    const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
    const [clientFiles, setClientFiles] = useState<ClientFile[]>([])
    const [folderStructure, setFolderStructure] = useState<FolderStructure[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [ws, setWs] = useState<WebSocket | null>(null)
    const [uploading, setUploading] = useState(false)
    const theme = useMantineTheme()

    // WebSocket connection
    useEffect(() => {
        const websocket = new WebSocket('ws://localhost:5173/ws')

        websocket.onopen = () => {
            console.log('WebSocket connected')
        }

        websocket.onmessage = (event) => {
            const data: StatusUpdate = JSON.parse(event.data)
            if (data.type === 'status_update' && selectedClientId) {
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
        } else {
            setClientFiles([])
            setFolderStructure([])
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

    const fetchClientFiles = async (clientId: string) => {
        setLoading(true)
        try {
            const response = await fetch(`/api/clients/${clientId}/files/`)
            if (!response.ok) {
                throw new Error('Failed to fetch client files')
            }
            const data: ClientFile[] = await response.json()
            setClientFiles(data)

            // Build folder structure
            const structure = buildFolderStructure(data)
            setFolderStructure(structure)
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

    const buildFolderStructure = (files: ClientFile[]): FolderStructure[] => {
        const structure: { [key: string]: FolderStructure } = {}

        files.forEach(file => {
            const path = file.path || file.filename
            const parts = path.split('/')
            let current = structure

            parts.forEach((part, index) => {
                if (index === parts.length - 1) {
                    // File
                    current[part] = {
                        name: part,
                        type: 'file',
                        file
                    }
                } else {
                    // Folder
                    if (!current[part]) {
                        current[part] = {
                            name: part,
                            type: 'folder',
                            children: []
                        }
                    }
                    current = current[part].children as { [key: string]: FolderStructure }
                }
            })
        })

        return Object.values(structure)
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
            const response = await fetch(`/api/clients/${selectedClientId}/files/`, {
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

    const renderFolderStructure = (items: FolderStructure[], level = 0) => {
        return items.map((item, index) => (
            <div key={item.name + index} style={{ marginLeft: level * 20 }}>
                {item.type === 'folder' ? (
                    <Paper
                        p="xs"
                        mb="xs"
                        style={{
                            backgroundColor: theme.colors.blue[0],
                            borderLeft: `3px solid ${theme.colors.blue[6]}`
                        }}
                    >
                        <Group>
                            <IconFolder size={20} color={theme.colors.blue[6]} />
                            <Text fw={500}>{item.name}</Text>
                        </Group>
                        {item.children && renderFolderStructure(item.children, level + 1)}
                    </Paper>
                ) : (
                    <Paper
                        p="xs"
                        mb="xs"
                        style={{
                            backgroundColor: theme.white,
                            borderLeft: `3px solid ${theme.colors.gray[3]}`
                        }}
                    >
                        <Group position="apart">
                            <Group>
                                <IconFile size={20} color={theme.colors.gray[6]} />
                                <Stack spacing={0}>
                                    <Text size="sm">{item.name}</Text>
                                    {item.file && (
                                        <Text size="xs" color="dimmed">
                                            {new Date(item.file.uploaded_at).toLocaleDateString()}
                                        </Text>
                                    )}
                                </Stack>
                            </Group>
                            {item.file && (
                                <Group spacing="xs">
                                    <Badge color={getStatusColor(item.file.status)}>
                                        {item.file.status}
                                    </Badge>
                                    <ActionIcon
                                        variant="light"
                                        color="blue"
                                        onClick={() => window.open(`http://localhost:8000/files/${item.file.id}/download`)}
                                    >
                                        <IconDownload size={16} />
                                    </ActionIcon>
                                </Group>
                            )}
                        </Group>
                    </Paper>
                )}
            </div>
        ))
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
            <Card>
                <Group position="apart" mb="md">
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
                                        variant="light"
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
                        <Stack align="center" py="xl">
                            <Loader />
                            <Text>Loading files...</Text>
                        </Stack>
                    ) : clientFiles.length === 0 ? (
                        <Alert icon={<IconAlertCircle size="1rem" />} color="blue">
                            No files uploaded yet. Upload a PDF to get started.
                        </Alert>
                    ) : (
                        <ScrollArea h={500}>
                            {renderFolderStructure(folderStructure)}
                        </ScrollArea>
                    )
                ) : (
                    <Alert icon={<IconAlertCircle size="1rem" />} color="blue">
                        Select a client to view and manage their files.
                    </Alert>
                )}
            </Card>
        </Stack>
    )
} 