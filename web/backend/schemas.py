from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class StatementTypeBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class StatementTypeCreate(StatementTypeBase):
    pass


class StatementType(StatementTypeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ParserBase(BaseModel):
    name: str
    description: Optional[str] = None
    file_pattern: Optional[str] = None
    is_active: bool = True


class ParserCreate(ParserBase):
    pass


class Parser(ParserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    statement_types: List[StatementType] = []

    class Config:
        from_attributes = True
