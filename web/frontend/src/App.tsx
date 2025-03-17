import { MantineProvider } from '@mantine/core'
import { AppShell, Title, NavLink } from '@mantine/core'
import { IconDashboard, IconUsers, IconFiles, IconReceipt2 } from '@tabler/icons-react'
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { Dashboard } from './components/Dashboard'
import { Clients } from './components/Clients'
import { Notifications } from '@mantine/notifications'

// Import Mantine styles
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'

const navItems = [
  { icon: IconDashboard, label: 'Dashboard', color: 'blue', path: '/' },
  { icon: IconUsers, label: 'Clients', color: 'grape', path: '/clients' },
  { icon: IconFiles, label: 'Files', color: 'teal', path: '/files' },
  { icon: IconReceipt2, label: 'Transactions', color: 'violet', path: '/transactions' }
]

function Layout() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{
        width: 300,
        breakpoint: 'sm'
      }}
      padding="md"
    >
      <AppShell.Header p="md">
        <Title order={3}
          style={{
            background: 'linear-gradient(45deg, #4FACFE 0%, #00F2FE 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}
        >
          PDF Extractor
        </Title>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        {navItems.map((item) => (
          <NavLink
            key={item.label}
            label={item.label}
            leftSection={<item.icon size={20} color={`var(--mantine-color-${item.color}-6)`} />}
            variant="light"
            active={location.pathname === item.path}
            onClick={() => navigate(item.path)}
            mb="sm"
          />
        ))}
      </AppShell.Navbar>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/clients" element={<Clients />} />
          <Route path="/files" element={<div>Files Page</div>} />
          <Route path="/transactions" element={<div>Transactions Page</div>} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  )
}

function App() {
  return (
    <MantineProvider>
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    </MantineProvider>
  )
}

export default App
