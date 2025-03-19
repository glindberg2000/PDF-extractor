import React, { useState } from 'react';
import {
    Stack,
    Button,
    Text,
    Group,
    TextInput,
    MultiSelect,
    Paper,
    Progress,
    Alert,
    ActionIcon,
} from '@mantine/core';
import { IconUpload, IconX, IconCheck } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

interface FileUploadProps {
    clientId: number;
    statementTypeId: number;
    onUploadComplete?: () => void;
}

interface UploadProgress {
    [key: string]: number;
}

export function FileUpload({ clientId, statementTypeId, onUploadComplete }: FileUploadProps) {
    const [files, setFiles] = useState<File[]>([]);
    const [tags, setTags] = useState<string[]>([]);
    const [uploadProgress, setUploadProgress] = useState<UploadProgress>({});
    const [isUploading, setIsUploading] = useState(false);

    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files) {
            setFiles(Array.from(event.target.files));
        }
    };

    const removeFile = (index: number) => {
        setFiles(files.filter((_, i) => i !== index));
    };

    const handleUpload = async () => {
        if (files.length === 0) {
            notifications.show({
                title: 'Error',
                message: 'Please select files to upload',
                color: 'red',
            });
            return;
        }

        setIsUploading(true);
        const formData = new FormData();
        files.forEach(file => formData.append('files', file));
        if (tags.length > 0) {
            formData.append('tags', tags.join(','));
        }

        try {
            const response = await fetch(
                `/api/clients/${clientId}/files/batch-upload?statement_type_id=${statementTypeId}`,
                {
                    method: 'POST',
                    body: formData,
                }
            );

            if (!response.ok) {
                throw new Error('Upload failed');
            }

            const result = await response.json();
            notifications.show({
                title: 'Success',
                message: result.message,
                color: 'green',
            });

            setFiles([]);
            setTags([]);
            setUploadProgress({});
            onUploadComplete?.();
        } catch (error) {
            notifications.show({
                title: 'Error',
                message: 'Failed to upload files',
                color: 'red',
            });
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <Stack spacing="md">
            <Paper p="md" withBorder>
                <Stack spacing="md">
                    <Group position="apart">
                        <Text weight={500}>Upload Files</Text>
                        <Button
                            component="label"
                            leftIcon={<IconUpload size={14} />}
                            disabled={isUploading}
                        >
                            Select Files
                            <input
                                type="file"
                                multiple
                                hidden
                                onChange={handleFileSelect}
                                accept=".pdf"
                            />
                        </Button>
                    </Group>

                    {files.length > 0 && (
                        <Stack spacing="xs">
                            <Text size="sm" weight={500}>Selected Files:</Text>
                            {files.map((file, index) => (
                                <Group key={index} position="apart">
                                    <Text size="sm" truncate>{file.name}</Text>
                                    <ActionIcon
                                        color="red"
                                        onClick={() => removeFile(index)}
                                        disabled={isUploading}
                                    >
                                        <IconX size={14} />
                                    </ActionIcon>
                                </Group>
                            ))}
                        </Stack>
                    )}

                    <MultiSelect
                        label="Tags"
                        placeholder="Add tags (comma-separated)"
                        data={tags}
                        searchable
                        creatable
                        getCreateLabel={(query) => `+ Create ${query}`}
                        onCreate={(query) => {
                            const item = query;
                            setTags((current) => [...current, item]);
                            return item;
                        }}
                        value={tags}
                        onChange={setTags}
                        disabled={isUploading}
                    />

                    {Object.entries(uploadProgress).map(([filename, progress]) => (
                        <Stack key={filename} spacing={4}>
                            <Group position="apart">
                                <Text size="sm">{filename}</Text>
                                <Text size="sm">{progress}%</Text>
                            </Group>
                            <Progress value={progress} />
                        </Stack>
                    ))}

                    {files.length > 0 && (
                        <Button
                            onClick={handleUpload}
                            loading={isUploading}
                            leftIcon={<IconUpload size={14} />}
                        >
                            Upload Files
                        </Button>
                    )}
                </Stack>
            </Paper>
        </Stack>
    );
} 