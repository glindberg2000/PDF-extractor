import { useEffect, useState } from 'react'
import { Container, Text, Paper } from '@mantine/core'

export function Test() {
    const [data, setData] = useState<any>(null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        fetch('/api/clients/')
            .then(res => res.json())
            .then(data => {
                console.log('Fetched data:', data)
                setData(data)
            })
            .catch(err => {
                console.error('Error:', err)
                setError(err.message)
            })
    }, [])

    return (
        <Container size="sm" py="xl">
            <Paper p="md" withBorder>
                <Text size="xl" weight={700} mb="md">Test Component</Text>
                <Text>If you can see this, React is working!</Text>

                {error && (
                    <Text color="red" mt="md">Error: {error}</Text>
                )}

                {data && (
                    <Text mt="md">
                        Backend data: {JSON.stringify(data, null, 2)}
                    </Text>
                )}
            </Paper>
        </Container>
    )
} 