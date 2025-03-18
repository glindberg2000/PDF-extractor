import React from 'react';
import { Checkbox, Stack } from '@mantine/core';

interface StatementType {
    id: number;
    name: string;
    description: string | null;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

interface StatementTypeSelectorProps {
    statementTypes: StatementType[];
    selectedTypes: number[];
    onChange: (selectedTypes: number[]) => void;
}

export const StatementTypeSelector: React.FC<StatementTypeSelectorProps> = ({
    statementTypes,
    selectedTypes,
    onChange,
}) => {
    const handleChange = (typeId: number) => {
        const newSelectedTypes = selectedTypes.includes(typeId)
            ? selectedTypes.filter(id => id !== typeId)
            : [...selectedTypes, typeId];
        onChange(newSelectedTypes);
    };

    return (
        <Stack gap="xs">
            {statementTypes.map((type) => (
                <Checkbox
                    key={type.id}
                    label={type.name}
                    checked={selectedTypes.includes(type.id)}
                    onChange={() => handleChange(type.id)}
                />
            ))}
        </Stack>
    );
}; 