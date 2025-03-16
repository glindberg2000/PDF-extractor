import { useState } from 'react'
import {
    AppShell,
    UnstyledButton,
    Group,
    Text,
    rem,
} from '@mantine/core'
import {
    IconDashboard,
    IconUsers,
    IconFiles,
    IconChartBar,
    IconSettings,
    IconReceipt2,
} from '@tabler/icons-react'
import { useNavigate, useLocation } from 'react-router-dom'

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
            w="100%"
            style={{
                padding: `${rem(8)} ${rem(12)}`,
                borderRadius: rem(8),
                backgroundColor: active ? 'var(--mantine-color-blue-light)' : 'transparent',
            }}
        >
            <Group>
                <Icon size={20} color={color} stroke={1.5} />
                <Text size="sm" c={active ? 'blue' : 'dimmed'}>
                    {label}
                </Text>
            </Group>
        </UnstyledButton>
    )
}

const mainLinks = [
    { icon: IconDashboard, color: 'blue', label: 'Dashboard', view: 'dashboard' },
    { icon: IconUsers, color: 'grape', label: 'Clients', view: 'clients' },
    { icon: IconFiles, color: 'teal', label: 'Files', view: 'files' },
    { icon: IconReceipt2, color: 'violet', label: 'Transactions', view: 'transactions' },
    { icon: IconChartBar, color: 'pink', label: 'Analytics', view: 'analytics' },
    { icon: IconSettings, color: 'gray', label: 'Settings', view: 'settings' },
]

interface LayoutProps {
    children: React.ReactNode
    activeView: string
    onViewChange: (view: string) => void
}

export function Layout({ children, activeView, onViewChange }: LayoutProps) {
    const [opened, setOpened] = useState(false)
    const navigate = useNavigate()
    const location = useLocation()

    const handleNavigation = (view: string) => {
        onViewChange(view)
        navigate(view)
    }

    return (
        <AppShell
            header={{ height: 60 }}
            navbar={{
                width: 300,
                breakpoint: 'sm',
                collapsed: { mobile: !opened }
            }}
            padding="md"
        >
            <AppShell.Header>
                <Group h="100%" px="md">
                    <Text size="lg" fw={700}>PDF Extractor</Text>
                </Group>
            </AppShell.Header>

            <AppShell.Navbar p="md">
                <AppShell.Section grow>
                    {mainLinks.map((link) => (
                        <MainLink
                            key={link.label}
                            {...link}
                            active={activeView === link.view}
                            onClick={() => handleNavigation(link.view)}
                        />
                    ))}
                </AppShell.Section>
            </AppShell.Navbar>

            <AppShell.Main>
                {children}
            </AppShell.Main>
        </AppShell>
    )
} 