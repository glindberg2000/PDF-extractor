from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: str = "EXPENSE"  # INCOME, EXPENSE, TRANSFER
    is_system_default: bool = False
    is_auto_generated: bool = False
    parent_id: Optional[int] = None
    client_id: Optional[int] = None


class CategoryCreate(CategoryBase):
    pass


class Category(CategoryBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatementTypeBase(BaseModel):
    name: str
    description: Optional[str] = None
    file_pattern: Optional[str] = None
    parser_module: Optional[str] = None
    is_active: bool = True


class StatementTypeCreate(StatementTypeBase):
    pass


class StatementType(StatementTypeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    file_pattern: Optional[str] = None
    parser_module: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class StatementTypeResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    file_pattern: Optional[str] = None
    parser_module: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ClientBase(BaseModel):
    name: str
    address: Optional[str] = None
    business_description: Optional[str] = None


class ClientCreate(ClientBase):
    statement_type_ids: List[int] = []


class ClientUpdate(ClientBase):
    statement_type_ids: List[int] = []


class ClientResponse(ClientBase):
    id: int
    created_at: Optional[datetime] = None
    categories: List[Category] = []
    statement_types: List[StatementType] = []

    class Config:
        from_attributes = True


class ClientFileBase(BaseModel):
    client_id: int
    statement_type_id: int
    file_path: str
    file_name: str
    file_size: int
    file_type: str
    status: str = "PENDING"  # PENDING, PROCESSING, COMPLETED, ERROR
    error_message: Optional[str] = None


class ClientFileCreate(ClientFileBase):
    pass


class ClientFile(ClientFileBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FileResponse(BaseModel):
    id: int
    filename: str
    status: str
    uploaded_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    total_transactions: Optional[int] = None
    pages_processed: Optional[int] = None
    total_pages: Optional[int] = None
    file_hash: Optional[str] = None

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    id: int
    date: Optional[datetime] = None
    description: str
    amount: float
    is_categorized: bool
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    raw_text: Optional[str] = None

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    message: str
    file_id: int
