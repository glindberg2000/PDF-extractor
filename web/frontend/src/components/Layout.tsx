import { useState, useEffect } from 'react'
import { AppShell, UnstyledButton, Group, Text, Burger, Title, Box, MediaQuery, useMantineTheme } from '@mantine/core'
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
    const theme = useMantineTheme()

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
                transition: 'all 0.2s ease',
                '&:hover': {
                    backgroundColor: theme.colors[color][0],
                    transform: 'translateX(4px)',
                },
                '& + &': {
                    marginTop: theme.spacing.sm,
                },
            })}
        >
            <Group>
                <Box style={{
                    width: 24,
                    height: 24,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'transform 0.2s ease'
                }}>
                    <Icon
                        size={24}
                        stroke={1.5}
                        style={{
                            transform: active ? 'scale(1.1)' : 'scale(1)',
                            transition: 'transform 0.2s ease'
                        }}
                        color={active ? `var(--mantine-color-${color}-7)` : undefined}
                    />
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
    const theme = useMantineTheme()
    const currentPath = location.pathname.split('/')[1] || 'dashboard'

    // Close mobile nav when route changes
    useEffect(() => {
        setOpened(false)
    }, [location.pathname])

    return (
        <AppShell
            header={{ height: 60 }}
            navbar={{
                width: { base: 300 },
                breakpoint: 'sm',
                collapsed: { desktop: false, mobile: !opened }
            }}
            padding="md"
        >
            <AppShell.Header>
                <Group h="100%" px="md" justify="space-between">
                    <Group>
                        <MediaQuery largerThan="sm" styles={{ display: 'none' }}>
                            <Burger
                                opened={opened}
                                onClick={() => setOpened((o) => !o)}
                                size="sm"
                                color={theme.colors.gray[6]}
                                mr="xl"
                            />
                        </MediaQuery>
                        <Title order={3} style={{
                            background: 'linear-gradient(45deg, #4FACFE 0%, #00F2FE 100%)',
                            WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent'
                        }}>
                            PDF Extractor
                        </Title>
                    </Group>
                </Group>
            </AppShell.Header>

            <AppShell.Navbar
                p="md"
                style={{
                    borderRight: `1px solid ${theme.colors.gray[2]}`,
                    backgroundColor: theme.white
                }}
            >
                <AppShell.Section grow>
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

            <AppShell.Main style={{ backgroundColor: theme.colors.gray[0] }}>
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