import React from 'react';
import { Checkbox, FormControlLabel, FormGroup } from '@mui/material';

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
        <FormGroup>
            {statementTypes.map((type) => (
                <FormControlLabel
                    key={type.id}
                    control={
                        <Checkbox
                            checked={selectedTypes.includes(type.id)}
                            onChange={() => handleChange(type.id)}
                            name={type.name}
                        />
                    }
                    label={type.name}
                />
            ))}
        </FormGroup>
    );
}; 