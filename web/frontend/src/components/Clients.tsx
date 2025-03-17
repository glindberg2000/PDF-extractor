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
import { IconPlus, IconFolder, IconUpload, IconCategory, IconDotsVertical, IconFileUpload, IconTags, IconX, IconChevronRight, IconEdit, IconTrash, IconAlertCircle } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useNavigate } from 'react-router-dom'
import { useForm } from '@mantine/form'

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
    const [modalOpen, setModalOpen] = useState(false)
    const [editingClient, setEditingClient] = useState<Client | null>(null)

    const form = useForm({
        initialValues: {
            name: '',
            address: '',
            business_description: ''
        },
        validate: {
            name: (value) => !value.trim() ? 'Name is required' : null,
            address: (value) => !value.trim() ? 'Address is required' : null,
            business_description: (value) => !value.trim() ? 'Business description is required' : null
        }
    })

    useEffect(() => {
        fetchClients()
    }, [])

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

    const handleSubmit = async (values: typeof form.values) => {
        try {
            const url = editingClient
                ? `/api/clients/${editingClient.id}`
                : '/api/clients/'

            const response = await fetch(url, {
                method: editingClient ? 'PUT' : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(values)
            })

            if (!response.ok) throw new Error('Failed to save client')

            notifications.show({
                title: 'Success',
                message: `Client ${editingClient ? 'updated' : 'created'} successfully`,
                color: 'green'
            })

            setModalOpen(false)
            form.reset()
            setEditingClient(null)
            fetchClients()
        } catch (err) {
            console.error('Error saving client:', err)
            notifications.show({
                title: 'Error',
                message: err instanceof Error ? err.message : 'Failed to save client',
                color: 'red'
            })
        }
    }

    const handleEdit = (client: Client) => {
        setEditingClient(client)
        form.setValues({
            name: client.name,
            address: client.address || '',
            business_description: client.business_description || ''
        })
        setModalOpen(true)
    }

    const handleDelete = async (id: number) => {
        if (!confirm('Are you sure you want to delete this client?')) return

        try {
            const response = await fetch(`/api/clients/${id}`, {
                method: 'DELETE'
            })

            if (!response.ok) throw new Error('Failed to delete client')

            notifications.show({
                title: 'Success',
                message: 'Client deleted successfully',
                color: 'green'
            })

            fetchClients()
        } catch (err) {
            console.error('Error deleting client:', err)
            notifications.show({
                title: 'Error',
                message: err instanceof Error ? err.message : 'Failed to delete client',
                color: 'red'
            })
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
        <Container size="xl" py="xl">
            <Group justify="space-between" mb="xl">
                <Title order={2}>Clients</Title>
                <Button onClick={() => {
                    setEditingClient(null)
                    form.reset()
                    setModalOpen(true)
                }}>
                    Add Client
                </Button>
            </Group>

            {clients.length === 0 ? (
                <Paper p="xl" ta="center">
                    <Text c="dimmed">No clients yet. Add your first client to get started!</Text>
                </Paper>
            ) : (
                <Table>
                    <Table.Thead>
                        <Table.Tr>
                            <Table.Th>Name</Table.Th>
                            <Table.Th>Address</Table.Th>
                            <Table.Th>Business Description</Table.Th>
                            <Table.Th>Created At</Table.Th>
                            <Table.Th>Actions</Table.Th>
                        </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                        {clients.map((client) => (
                            <Table.Tr key={client.id}>
                                <Table.Td>{client.name}</Table.Td>
                                <Table.Td>{client.address}</Table.Td>
                                <Table.Td>{client.business_description}</Table.Td>
                                <Table.Td>{new Date(client.created_at).toLocaleDateString()}</Table.Td>
                                <Table.Td>
                                    <Group gap="xs">
                                        <ActionIcon
                                            variant="light"
                                            color="blue"
                                            onClick={() => handleEdit(client)}
                                        >
                                            <IconEdit size={16} />
                                        </ActionIcon>
                                        <ActionIcon
                                            variant="light"
                                            color="red"
                                            onClick={() => handleDelete(client.id)}
                                        >
                                            <IconTrash size={16} />
                                        </ActionIcon>
                                    </Group>
                                </Table.Td>
                            </Table.Tr>
                        ))}
                    </Table.Tbody>
                </Table>
            )}

            <Modal
                opened={modalOpen}
                onClose={() => setModalOpen(false)}
                title={editingClient ? 'Edit Client' : 'Add Client'}
            >
                <form onSubmit={form.onSubmit(handleSubmit)}>
                    <Stack>
                        <TextInput
                            label="Name"
                            placeholder="Enter client name"
                            required
                            {...form.getInputProps('name')}
                        />
                        <TextInput
                            label="Address"
                            placeholder="Enter client address"
                            required
                            {...form.getInputProps('address')}
                        />
                        <Textarea
                            label="Business Description"
                            placeholder="Enter business description"
                            required
                            {...form.getInputProps('business_description')}
                        />
                        <Group justify="flex-end">
                            <Button variant="light" onClick={() => setModalOpen(false)}>Cancel</Button>
                            <Button type="submit">{editingClient ? 'Save Changes' : 'Add Client'}</Button>
                        </Group>
                    </Stack>
                </form>
            </Modal>
        </Container>
    )
} 