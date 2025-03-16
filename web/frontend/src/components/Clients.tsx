import { useState, useEffect } from 'react'
import {
    Stack,
    Title,
    Card,
    Text,
    Button,
    Group,
    TextInput,
    Textarea,
    Modal,
    Table,
    ActionIcon,
    Badge,
    Menu,
    SimpleGrid,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconPlus, IconFolder, IconUpload, IconCategory, IconDotsVertical, IconFileUpload, IconTags, IconTable, IconX } from '@tabler/icons-react'
import { Dropzone } from '@mantine/dropzone'
import { useNavigate } from 'react-router-dom'
import { notifications } from '@mantine/notifications'

interface Category {
    id: number
    name: string
    description: string | null
    is_auto_generated: boolean
}

interface Client {
    id: number
    name: string
    address: string | null
    business_description: string | null
    categories: Category[]
}

interface ClientFile {
    id: number
    filename: string
    status: string
    uploaded_at: string
    processed_at: string | null
    error_message: string | null
}

export function Clients() {
    const [clients, setClients] = useState<Client[]>([])
    const [selectedClient, setSelectedClient] = useState<Client | null>(null)
    const [clientFiles, setClientFiles] = useState<ClientFile[]>([])
    const [newClient, setNewClient] = useState({
        name: '',
        address: '',
        business_description: '',
    })
    const [opened, { open, close }] = useDisclosure(false)
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
    const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false)
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
    const [selectedClientForUpload, setSelectedClientForUpload] = useState<Client | null>(null)
    const navigate = useNavigate()

    // Fetch clients on mount
    useEffect(() => {
        fetchClients()
    }, [])

    // Fetch client files when selectedClientForUpload changes
    useEffect(() => {
        if (selectedClientForUpload) {
            fetchClientFiles(selectedClientForUpload.id)
        }
    }, [selectedClientForUpload])

    const fetchClients = async () => {
        try {
            const response = await fetch('http://localhost:8000/clients/')
            const data = await response.json()
            setClients(data)
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

    const handleCreateClient = async () => {
        try {
            const response = await fetch('http://localhost:8000/clients/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(newClient),
            })

            if (!response.ok) {
                throw new Error(`Error: ${response.status}`)
            }

            const data = await response.json()
            setClients([...clients, data])
            setIsCreateModalOpen(false)
            setNewClient({ name: '', address: '', business_description: '' })

            notifications.show({
                title: 'Success',
                message: 'Client created successfully',
                color: 'green',
            })
        } catch (error) {
            console.error('Error creating client:', error)
            notifications.show({
                title: 'Error',
                message: 'Failed to create client. Please try again.',
                color: 'red',
            })
        }
    }

    const handleFileUpload = async (files: File[]) => {
        if (!selectedClientForUpload || !files.length) {
            notifications.show({
                title: 'Error',
                message: 'No client selected or no file provided',
                color: 'red',
            })
            return
        }

        const file = files[0]
        const formData = new FormData()
        formData.append('file', file)

        try {
            console.log(`Uploading file for client ${selectedClientForUpload.id}:`, file.name)
            const response = await fetch(`http://localhost:8000/clients/${selectedClientForUpload.id}/upload/`, {
                method: 'POST',
                body: formData,
                headers: {
                    // Do not set Content-Type header - browser will set it automatically with boundary for multipart/form-data
                    'Accept': 'application/json',
                },
            })

            console.log('Response status:', response.status)
            const responseText = await response.text()
            console.log('Response text:', responseText)

            if (!response.ok) {
                let errorMessage
                try {
                    const errorData = JSON.parse(responseText)
                    errorMessage = errorData.detail || `Upload failed with status ${response.status}`
                } catch {
                    errorMessage = `Upload failed with status ${response.status}: ${responseText}`
                }
                throw new Error(errorMessage)
            }

            const data = JSON.parse(responseText)
            console.log('Upload response:', data)
            await fetchClientFiles(selectedClientForUpload.id)

            notifications.show({
                title: 'Success',
                message: 'File uploaded successfully',
                color: 'green',
            })

            // Close the upload modal after successful upload
            setIsUploadModalOpen(false)
        } catch (error) {
            console.error('Error uploading file:', error)
            notifications.show({
                title: 'Error',
                message: error instanceof Error ? error.message : 'Failed to upload file. Please try again.',
                color: 'red',
            })
        }
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'completed':
                return 'green'
            case 'processing':
                return 'blue'
            case 'failed':
                return 'red'
            default:
                return 'gray'
        }
    }

    return (
        <Stack spacing="md">
            <Group justify="space-between">
                <Title order={2}>Clients</Title>
                <Button onClick={() => setIsCreateModalOpen(true)}>Add Client</Button>
            </Group>

            <SimpleGrid cols={3}>
                {clients.map((client) => (
                    <Card key={client.id} shadow="sm" padding="lg" radius="md" withBorder>
                        <Card.Section withBorder inheritPadding py="xs">
                            <Group justify="space-between">
                                <Text fw={500}>{client.name}</Text>
                                <Menu shadow="md" width={200}>
                                    <Menu.Target>
                                        <ActionIcon variant="subtle">
                                            <IconDotsVertical size={16} />
                                        </ActionIcon>
                                    </Menu.Target>

                                    <Menu.Dropdown>
                                        <Menu.Item
                                            leftSection={<IconFileUpload size={14} />}
                                            onClick={() => {
                                                setSelectedClientForUpload(client)
                                                setIsUploadModalOpen(true)
                                                fetchClientFiles(client.id)
                                            }}
                                        >
                                            Upload Files
                                        </Menu.Item>
                                        <Menu.Item
                                            leftSection={<IconTags size={14} />}
                                            onClick={() => {
                                                setSelectedClient(client)
                                                setIsCategoryModalOpen(true)
                                            }}
                                        >
                                            Manage Categories
                                        </Menu.Item>
                                        <Menu.Item
                                            leftSection={<IconTable size={14} />}
                                            onClick={() => navigate(`/clients/${client.id}/transactions`)}
                                        >
                                            View Transactions
                                        </Menu.Item>
                                    </Menu.Dropdown>
                                </Menu>
                            </Group>
                        </Card.Section>

                        <Stack mt="md" spacing="sm">
                            {client.address && (
                                <Text size="sm" c="dimmed">
                                    {client.address}
                                </Text>
                            )}
                            {client.business_description && (
                                <Text size="sm" c="dimmed">
                                    {client.business_description}
                                </Text>
                            )}

                            <Group mt="md" gap="xs">
                                {client.categories.slice(0, 3).map((category) => (
                                    <Badge
                                        key={category.id}
                                        variant={category.is_auto_generated ? 'light' : 'filled'}
                                        color={category.is_auto_generated ? 'gray' : 'blue'}
                                    >
                                        {category.name}
                                    </Badge>
                                ))}
                                {client.categories.length > 3 && (
                                    <Badge variant="dot">+{client.categories.length - 3} more</Badge>
                                )}
                            </Group>
                        </Stack>

                        {/* Show files directly in the client card */}
                        {selectedClientForUpload?.id === client.id && clientFiles.length > 0 && (
                            <Stack mt="md">
                                <Text fw={500}>Files</Text>
                                <Table>
                                    <Table.Thead>
                                        <Table.Tr>
                                            <Table.Th>Name</Table.Th>
                                            <Table.Th>Status</Table.Th>
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
                                                    {new Date(file.uploaded_at).toLocaleString()}
                                                </Table.Td>
                                            </Table.Tr>
                                        ))}
                                    </Table.Tbody>
                                </Table>
                            </Stack>
                        )}
                    </Card>
                ))}
            </SimpleGrid>

            {/* Create Client Modal */}
            <Modal opened={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} title="Create New Client">
                <Stack gap="md">
                    <TextInput
                        label="Name"
                        placeholder="Enter client name"
                        value={newClient.name}
                        onChange={(e) => setNewClient({ ...newClient, name: e.target.value })}
                        required
                    />
                    <TextInput
                        label="Address"
                        placeholder="Enter client address"
                        value={newClient.address}
                        onChange={(e) => setNewClient({ ...newClient, address: e.target.value })}
                    />
                    <Textarea
                        label="Business Description"
                        placeholder="Describe the client's business"
                        value={newClient.business_description}
                        onChange={(e) =>
                            setNewClient({ ...newClient, business_description: e.target.value })
                        }
                        description="This will be used to auto-generate relevant expense categories"
                    />
                    <Button
                        onClick={handleCreateClient}
                        disabled={!newClient.name}
                    >
                        Create Client
                    </Button>
                </Stack>
            </Modal>

            {/* Upload Files Modal */}
            <Modal opened={isUploadModalOpen} onClose={() => setIsUploadModalOpen(false)} title="Upload Files">
                {selectedClientForUpload && (
                    <Stack gap="md">
                        <Text>Upload files for {selectedClientForUpload.name}</Text>
                        <Dropzone
                            onDrop={async (files) => {
                                await handleFileUpload(files)
                            }}
                            accept={['application/pdf']}
                            maxFiles={1}
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
                                    <Text size="xl">Drop PDF here or click to select</Text>
                                    <Text size="sm" c="dimmed">Only PDF files are accepted</Text>
                                </Stack>
                            </Group>
                        </Dropzone>

                        {/* Show files in the upload modal */}
                        {clientFiles.length > 0 && (
                            <Stack mt="md">
                                <Text fw={500}>Uploaded Files</Text>
                                <Table>
                                    <Table.Thead>
                                        <Table.Tr>
                                            <Table.Th>Name</Table.Th>
                                            <Table.Th>Status</Table.Th>
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
                                                    {new Date(file.uploaded_at).toLocaleString()}
                                                </Table.Td>
                                            </Table.Tr>
                                        ))}
                                    </Table.Tbody>
                                </Table>
                            </Stack>
                        )}
                    </Stack>
                )}
            </Modal>
        </Stack>
    )
} 