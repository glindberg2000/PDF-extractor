import React, { useState, useEffect } from 'react'
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
    MultiSelect,
    Tooltip,
} from '@mantine/core'
import { IconPlus, IconFolder, IconUpload, IconCategory, IconDotsVertical, IconFileUpload, IconTags, IconX, IconChevronRight, IconEdit, IconTrash, IconAlertCircle } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useNavigate } from 'react-router-dom'
import { useForm } from '@mantine/form'
import { StatementTypeSelector } from './StatementTypeSelector'

interface Category {
    id: number
    name: string
    description: string | null
    is_auto_generated: boolean
}

interface StatementType {
    id: number
    name: string
    description: string | null
    is_active: boolean
    created_at: string
    updated_at: string
}

interface Client {
    id: number
    name: string
    address: string | null
    business_description: string | null
    categories: Category[]
    created_at: string
    updated_at: string
    statement_types?: StatementType[]
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
    const [statementTypes, setStatementTypes] = useState<StatementType[]>([])
    const [formData, setFormData] = useState({
        name: '',
        address: '',
        business_description: '',
        statement_types: [] as number[]
    })

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

    const statementTypeForm = useForm({
        initialValues: {
            name: '',
            description: '',
        },
        validate: {
            name: (value) => !value ? 'Name is required' : null,
        },
    })

    useEffect(() => {
        fetchClients()
        fetchStatementTypes()
    }, [])

    const fetchClients = async () => {
        setLoading(true)
        setError(null)
        try {
            console.log('Fetching clients...')
            const response = await fetch('/api/clients/')
            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || 'Failed to fetch clients')
            }
            const data = await response.json()
            console.log('Received clients:', data)
            setClients(data)
        } catch (err) {
            console.error('Error fetching clients:', err)
            setError(err instanceof Error ? err.message : 'Failed to fetch clients')
            notifications.show({
                title: 'Error',
                message: 'Failed to fetch clients. Please try again.',
                color: 'red',
            })
        } finally {
            setLoading(false)
        }
    }

    const fetchStatementTypes = async () => {
        try {
            console.log('Fetching statement types...')
            const response = await fetch('/api/statement-types/')
            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || 'Failed to fetch statement types')
            }
            const data = await response.json()
            console.log('Received statement types:', data)
            setStatementTypes(data)
        } catch (err) {
            console.error('Error fetching statement types:', err)
            setError(err instanceof Error ? err.message : 'Failed to load statement types')
            notifications.show({
                title: 'Error',
                message: 'Failed to load statement types. Please try again.',
                color: 'red',
            })
        }
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        try {
            const url = editingClient
                ? `/api/clients/${editingClient.id}`
                : '/api/clients/'
            const method = editingClient ? 'PUT' : 'POST'

            console.log('Submitting form data:', formData)
            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: formData.name,
                    address: formData.address,
                    business_description: formData.business_description,
                    statement_type_ids: formData.statement_types
                })
            })

            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || 'Failed to save client')
            }

            await fetchClients()
            setModalOpen(false)
            setEditingClient(null)
            setFormData({
                name: '',
                address: '',
                business_description: '',
                statement_types: []
            })
            notifications.show({
                title: 'Success',
                message: `Client ${editingClient ? 'updated' : 'created'} successfully`,
                color: 'green'
            })
        } catch (err) {
            console.error('Error submitting form:', err)
            notifications.show({
                title: 'Error',
                message: err instanceof Error ? err.message : 'Failed to save client',
                color: 'red'
            })
        }
    }

    const handleEdit = (client: Client) => {
        setEditingClient(client)
        setFormData({
            name: client.name,
            address: client.address || '',
            business_description: client.business_description || '',
            statement_types: client.statement_types?.map(type => type.id) || []
        })
        setModalOpen(true)
    }

    const handleDelete = async (id: number) => {
        if (!confirm('Are you sure you want to delete this client?')) return

        try {
            const response = await fetch(`/api/clients/${id}`, {
                method: 'DELETE'
            })

            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || 'Failed to delete client')
            }

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

    const handleClientSelect = (client: Client) => {
        setSelectedClient(client)
    }

    const handleStatementTypeSelect = (typeId: number) => {
        // Implementation of handleStatementTypeSelect
    }

    const handleUploadComplete = (file: File) => {
        // Implementation of handleUploadComplete
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

            <SimpleGrid cols={2} spacing="xl">
                <Stack>
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
                                    <Table.Th>Statement Types</Table.Th>
                                    <Table.Th>Actions</Table.Th>
                                </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>
                                {clients.map((client) => (
                                    <Table.Tr
                                        key={client.id}
                                        style={{
                                            cursor: 'pointer',
                                            backgroundColor: selectedClient?.id === client.id ? 'var(--mantine-color-gray-0)' : undefined
                                        }}
                                        onClick={() => handleClientSelect(client)}
                                    >
                                        <Table.Td>{client.name}</Table.Td>
                                        <Table.Td>{client.address}</Table.Td>
                                        <Table.Td>
                                            <Group spacing="xs">
                                                {client.statement_types?.map((type) => (
                                                    <Badge
                                                        key={type.id}
                                                        variant="light"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleStatementTypeSelect(type.id);
                                                        }}
                                                    >
                                                        {type.name}
                                                    </Badge>
                                                ))}
                                            </Group>
                                        </Table.Td>
                                        <Table.Td>
                                            <Group gap="xs">
                                                <Tooltip label="Edit">
                                                    <ActionIcon
                                                        variant="light"
                                                        color="blue"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleEdit(client);
                                                        }}
                                                    >
                                                        <IconEdit size={16} />
                                                    </ActionIcon>
                                                </Tooltip>
                                                <Tooltip label="Delete">
                                                    <ActionIcon
                                                        variant="light"
                                                        color="red"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleDelete(client.id);
                                                        }}
                                                    >
                                                        <IconTrash size={16} />
                                                    </ActionIcon>
                                                </Tooltip>
                                            </Group>
                                        </Table.Td>
                                    </Table.Tr>
                                ))}
                            </Table.Tbody>
                        </Table>
                    )}
                </Stack>

                <Stack>
                    {selectedClient ? (
                        <>
                            <Title order={3}>{selectedClient.name}</Title>
                            {/* ... existing file upload and file listing UI ... */}
                        </>
                    ) : (
                        <Paper p="xl" ta="center">
                            <Text c="dimmed">Select a client to view details</Text>
                        </Paper>
                    )}
                </Stack>
            </SimpleGrid>

            <Modal
                opened={modalOpen}
                onClose={() => setModalOpen(false)}
                title={editingClient ? 'Edit Client' : 'Add Client'}
            >
                <form onSubmit={handleSubmit}>
                    <Stack>
                        <TextInput
                            label="Name"
                            placeholder="Enter client name"
                            required
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            error={form.errors.name}
                        />
                        <TextInput
                            label="Address"
                            placeholder="Enter client address"
                            required
                            value={formData.address}
                            onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                            error={form.errors.address}
                        />
                        <Textarea
                            label="Business Description"
                            placeholder="Enter business description"
                            required
                            value={formData.business_description}
                            onChange={(e) => setFormData({ ...formData, business_description: e.target.value })}
                            error={form.errors.business_description}
                        />
                        <Stack spacing="xs">
                            <Text weight={500}>Statement Types</Text>
                            <StatementTypeSelector
                                statementTypes={statementTypes}
                                selectedTypes={formData.statement_types}
                                onChange={(selectedTypes) => setFormData({ ...formData, statement_types: selectedTypes })}
                            />
                        </Stack>
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