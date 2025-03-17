import { useState } from 'react'
import { AppShell, UnstyledButton, Group, Text, Burger, Title, Box } from '@mantine/core'
import {
    IconDashboard,
    IconUsers,
    IconFiles,
    IconReceipt2,
} from '@tabler/icons-react'
import { useNavigate, useLocation, Routes, Route, Navigate } from 'react-router-dom'
import { Dashboard } from './Dashboard'
import { Files } from './Files'
import { Clients } from './Clients'
import { Transactions } from './Transactions'

interface MainLinkProps {
    icon: typeof IconDashboard
    color: string
    label: string
    active?: boolean
    onClick?: () => void
}

function MainLink({ icon: Icon, color, label, active, onClick }: MainLinkProps) {
    return (
        <UnstyledButton
            onClick={onClick}
            sx={(theme) => ({
                display: 'block',
                width: '100%',
                padding: theme.spacing.md,
                borderRadius: theme.radius.sm,
                color: active ? theme.colors[color][7] : theme.colors.gray[7],
                backgroundColor: active ? theme.colors[color][0] : 'transparent',
                '&:hover': {
                    backgroundColor: theme.colors[color][0],
                },
                '& + &': {
                    marginTop: theme.spacing.sm,
                },
            })}
        >
            <Group>
                <Box style={{ width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Icon size={24} stroke={1.5} color={active ? `var(--mantine-color-${color}-7)` : undefined} />
                </Box>
                <Text size="sm" fw={active ? 500 : 400}>{label}</Text>
            </Group>
        </UnstyledButton>
    )
}

const mainLinks = [
    { icon: IconDashboard, color: 'blue', label: 'Dashboard', path: '/dashboard' },
    { icon: IconUsers, color: 'grape', label: 'Clients', path: '/clients' },
    { icon: IconFiles, color: 'teal', label: 'Files', path: '/files' },
    { icon: IconReceipt2, color: 'violet', label: 'Transactions', path: '/transactions' },
]

export default function Layout() {
    const [opened, setOpened] = useState(false)
    const navigate = useNavigate()
    const location = useLocation()
    const currentPath = location.pathname.split('/')[1] || 'dashboard'

    return (
        <AppShell
            header={{ height: 60 }}
            navbar={{
                width: 300,
                breakpoint: 'sm',
                collapsed: { desktop: false, mobile: !opened }
            }}
            padding="md"
        >
            <AppShell.Header>
                <Group h="100%" px="md" justify="space-between">
                    <Group>
                        <Burger
                            opened={opened}
                            onClick={() => setOpened((o) => !o)}
                            hiddenFrom="sm"
                            size="sm"
                        />
                        <Title order={3}>PDF Extractor</Title>
                    </Group>
                </Group>
            </AppShell.Header>

            <AppShell.Navbar p="md">
                <AppShell.Section>
                    {mainLinks.map((link) => (
                        <MainLink
                            key={link.path}
                            {...link}
                            active={currentPath === link.path.substring(1)}
                            onClick={() => {
                                navigate(link.path)
                                setOpened(false)
                            }}
                        />
                    ))}
                </AppShell.Section>
            </AppShell.Navbar>

            <AppShell.Main>
                <Routes>
                    <Route path="/" element={<Navigate to="/dashboard" replace />} />
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/clients" element={<Clients />} />
                    <Route path="/files" element={<Files />} />
                    <Route path="/transactions" element={<Transactions />} />
                </Routes>
            </AppShell.Main>
        </AppShell>
    )
} 