import { MantineProvider, createTheme } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './components/Dashboard'
import { Files } from './components/Files'
import { Clients } from './components/Clients'
import { Transactions } from './components/Transactions'
import { useState, useEffect } from 'react'
import '@mantine/core/styles.css'
import '@mantine/dropzone/styles.css'
import '@mantine/notifications/styles.css'
import { Notifications } from '@mantine/notifications'

const queryClient = new QueryClient()

const theme = createTheme({
  primaryColor: 'blue',
  defaultRadius: 'sm',
})

function AppContent() {
  const [activeView, setActiveView] = useState('Dashboard')
  const location = useLocation()

  // Update activeView based on current route
  useEffect(() => {
    const path = location.pathname.split('/')[1] || 'dashboard'
    setActiveView(path.charAt(0).toUpperCase() + path.slice(1))
  }, [location])

  return (
    <Layout activeView={activeView} onViewChange={setActiveView}>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/files" element={<Files />} />
        <Route path="/clients" element={<Clients />} />
        <Route path="/clients/:clientId/transactions" element={<Transactions />} />
        <Route path="/analytics" element={<div>Analytics View Coming Soon</div>} />
        <Route path="/settings" element={<div>Settings View Coming Soon</div>} />
      </Routes>
    </Layout>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <MantineProvider theme={theme} defaultColorScheme="light">
        <Notifications position="top-right" />
        <Router>
          <AppContent />
        </Router>
      </MantineProvider>
    </QueryClientProvider>
  )
}

export default App
