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
    Paper,
    Loader,
    Alert,
    Container,
} from '@mantine/core'
import { IconPlus, IconFolder, IconUpload, IconCategory, IconDotsVertical, IconFileUpload, IconTags, IconTable, IconX, IconChevronRight, IconEdit, IconTrash, IconAlertCircle } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useNavigate } from 'react-router-dom'

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
    created_at: string
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
    const navigate = useNavigate()
    const [clients, setClients] = useState<Client[]>([])
    const [selectedClient, setSelectedClient] = useState<Client | null>(null)
    const [clientFiles, setClientFiles] = useState<ClientFile[]>([])
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [formData, setFormData] = useState({
        name: '',
        address: '',
        business_description: '',
    })

    useEffect(() => {
        fetchClients()
    }, [])

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

    const handleCreateClient = async () => {
        if (!formData.name.trim()) {
            notifications.show({
                title: 'Error',
                message: 'Client name is required',
                color: 'red',
            })
            return
        }

        setLoading(true)
        try {
            const response = await fetch('http://localhost:8000/clients/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData),
            })

            if (!response.ok) {
                throw new Error('Failed to create client')
            }

            const newClient = await response.json()
            setClients([...clients, newClient])
            setIsCreateModalOpen(false)
            setFormData({ name: '', address: '', business_description: '' })
            notifications.show({
                title: 'Success',
                message: 'Client created successfully',
                color: 'green',
            })
            fetchClients() // Refresh the list
        } catch (error) {
            console.error('Error creating client:', error)
            notifications.show({
                title: 'Error',
                message: 'Failed to create client. Please try again.',
                color: 'red',
            })
        } finally {
            setLoading(false)
        }
    }

    if (loading && clients.length === 0) {
        return (
            <Container size="xl">
                <Stack align="center" justify="center" style={{ height: '70vh' }}>
                    <Loader size="xl" />
                    <Text>Loading clients...</Text>
                </Stack>
            </Container>
        )
    }

    if (error) {
        return (
            <Container size="xl">
                <Alert icon={<IconAlertCircle size="1rem" />} title="Error" color="red">
                    {error}
                </Alert>
            </Container>
        )
    }

    return (
        <Container size="xl">
            <Stack gap="md">
                <Group position="apart">
                    <Title order={2}>Clients</Title>
                    <Button
                        leftIcon={<IconPlus size={16} />}
                        onClick={() => {
                            setSelectedClient(null)
                            setFormData({ name: '', address: '', business_description: '' })
                            setIsCreateModalOpen(true)
                        }}
                    >
                        Add Client
                    </Button>
                </Group>

                {clients.length === 0 ? (
                    <Card withBorder shadow="sm" p="xl">
                        <Stack align="center" spacing="md">
                            <IconFolder size={48} color="var(--mantine-color-blue-6)" />
                            <Text size="lg" weight={500}>No Clients Yet</Text>
                            <Text color="dimmed" size="sm" align="center">
                                Get started by adding your first client using the "Add Client" button above.
                            </Text>
                            <Button
                                variant="light"
                                onClick={() => {
                                    setSelectedClient(null)
                                    setFormData({ name: '', address: '', business_description: '' })
                                    setIsCreateModalOpen(true)
                                }}
                                leftIcon={<IconPlus size={16} />}
                            >
                                Add Your First Client
                            </Button>
                        </Stack>
                    </Card>
                ) : (
                    <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
                        {clients.map((client) => (
                            <Card key={client.id} withBorder shadow="sm">
                                <Stack>
                                    <Group position="apart">
                                        <Group>
                                            <IconFolder size={24} color="var(--mantine-color-blue-6)" />
                                            <div>
                                                <Text weight={500}>{client.name}</Text>
                                                {client.address && (
                                                    <Text size="sm" color="dimmed">
                                                        {client.address}
                                                    </Text>
                                                )}
                                            </div>
                                        </Group>
                                        <Menu shadow="md" width={200}>
                                            <Menu.Target>
                                                <ActionIcon variant="light">
                                                    <IconDotsVertical size={16} />
                                                </ActionIcon>
                                            </Menu.Target>
                                            <Menu.Dropdown>
                                                <Menu.Item
                                                    icon={<IconEdit size={16} />}
                                                    onClick={() => {
                                                        setSelectedClient(client)
                                                        setFormData({
                                                            name: client.name,
                                                            address: client.address || '',
                                                            business_description: client.business_description || '',
                                                        })
                                                        setIsCreateModalOpen(true)
                                                    }}
                                                >
                                                    Edit Details
                                                </Menu.Item>
                                                <Menu.Item
                                                    icon={<IconFileUpload size={16} />}
                                                    onClick={() => navigate('/files')}
                                                >
                                                    Upload Files
                                                </Menu.Item>
                                                <Menu.Item
                                                    icon={<IconTable size={16} />}
                                                    onClick={() => navigate('/transactions')}
                                                >
                                                    View Transactions
                                                </Menu.Item>
                                            </Menu.Dropdown>
                                        </Menu>
                                    </Group>
                                    {client.business_description && (
                                        <Text size="sm" color="dimmed" lineClamp={2}>
                                            {client.business_description}
                                        </Text>
                                    )}
                                    <Group position="apart" mt="auto">
                                        <Badge color="blue">
                                            Created: {new Date(client.created_at).toLocaleDateString()}
                                        </Badge>
                                        <Badge color="grape">
                                            {client.categories?.length || 0} Categories
                                        </Badge>
                                    </Group>
                                </Stack>
                            </Card>
                        ))}
                    </SimpleGrid>
                )}

                <Modal
                    opened={isCreateModalOpen}
                    onClose={() => {
                        setIsCreateModalOpen(false)
                        setSelectedClient(null)
                        setFormData({ name: '', address: '', business_description: '' })
                    }}
                    title={selectedClient ? "Edit Client" : "Create New Client"}
                    size="md"
                    centered
                >
                    <Stack spacing="md">
                        <TextInput
                            label="Client Name"
                            placeholder="Enter client name"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            required
                        />
                        <TextInput
                            label="Address"
                            placeholder="Enter client address"
                            value={formData.address}
                            onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                        />
                        <Textarea
                            label="Business Description"
                            placeholder="Enter business description"
                            value={formData.business_description}
                            onChange={(e) =>
                                setFormData({ ...formData, business_description: e.target.value })
                            }
                            minRows={3}
                        />
                        <Button
                            onClick={handleCreateClient}
                            loading={loading}
                            disabled={!formData.name.trim()}
                            fullWidth
                        >
                            {selectedClient ? "Update Client" : "Create Client"}
                        </Button>
                    </Stack>
                </Modal>
            </Stack>
        </Container>
    )
} 