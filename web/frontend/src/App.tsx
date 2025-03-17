import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter as Router } from 'react-router-dom'
import { Notifications } from '@mantine/notifications'
import Layout from './components/Layout'
import './App.css'

// Import Mantine styles
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'

const queryClient = new QueryClient()

function App() {
  return (
    <MantineProvider
      theme={{
        primaryColor: 'blue',
        components: {
          AppShell: {
            styles: {
              root: { minHeight: '100vh' },
              main: { backgroundColor: 'var(--mantine-color-gray-0)' }
            }
          }
        }
      }}
    >
      <Notifications />
      <QueryClientProvider client={queryClient}>
        <Router>
          <Layout />
        </Router>
      </QueryClientProvider>
    </MantineProvider>
  )
}

export default App
