from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    JSON,
    func,
    ARRAY,
    Enum,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from database import Base
import enum


class FileStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"

    @classmethod
    def values(cls):
        return [cls.PENDING, cls.PROCESSING, cls.COMPLETED, cls.FAILED, cls.ARCHIVED]


class ClientStatementType(Base):
    __tablename__ = "client_statement_types"

    client_id = Column(Integer, ForeignKey("clients.id"), primary_key=True)
    statement_type_id = Column(
        Integer, ForeignKey("statement_types.id"), primary_key=True
    )


class StatementType(Base):
    __tablename__ = "statement_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    file_pattern = Column(String, nullable=True)
    parser_module = Column(String, nullable=True)
    parser_script = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="1")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    clients = relationship(
        "Client", secondary="client_statement_types", back_populates="statement_types"
    )
    files = relationship("ClientFile", back_populates="statement_type")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String)
    business_description = Column(String)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    categories = relationship(
        "Category", back_populates="client", cascade="all, delete-orphan"
    )
    statement_types = relationship(
        "StatementType", secondary="client_statement_types", back_populates="clients"
    )
    files = relationship(
        "ClientFile", back_populates="client", cascade="all, delete-orphan"
    )


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    type = Column(
        String, nullable=False, server_default="EXPENSE"
    )  # INCOME, EXPENSE, TRANSFER
    is_system_default = Column(Boolean, server_default="0")
    is_auto_generated = Column(Boolean, server_default="0")
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    client = relationship("Client", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")
    parent = relationship("Category", remote_side=[id], backref="subcategories")


class Parser(Base):
    __tablename__ = "parsers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    file_pattern = Column(String)  # Regex pattern to match file names
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Many-to-many relationship with statement types
    statement_types = relationship("StatementType", secondary="parser_statement_types")


class ParserStatementType(Base):
    __tablename__ = "parser_statement_types"

    parser_id = Column(Integer, ForeignKey("parsers.id"), primary_key=True)
    statement_type_id = Column(
        Integer, ForeignKey("statement_types.id"), primary_key=True
    )


class ClientFile(Base):
    __tablename__ = "client_files"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    statement_type_id = Column(Integer, ForeignKey("statement_types.id"))
    filename = Column(String)
    file_path = Column(String)
    status = Column(String, nullable=False, server_default=FileStatus.PENDING)
    error_message = Column(String, nullable=True)
    total_transactions = Column(Integer, nullable=True)
    pages_processed = Column(Integer, nullable=True)
    total_pages = Column(Integer, nullable=True)
    file_hash = Column(String, nullable=True)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)
    tags = Column(JSON, nullable=True)

    # Add CHECK constraint for status
    __table_args__ = (
        CheckConstraint(status.in_(FileStatus.values()), name="status_types"),
    )

    # Relationships
    client = relationship("Client", back_populates="files")
    statement_type = relationship("StatementType", back_populates="files")
    transactions = relationship(
        "Transaction", back_populates="client_file", cascade="all, delete-orphan"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    client_file_id = Column(Integer, ForeignKey("client_files.id"))
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    date = Column(DateTime)
    description = Column(String)
    amount = Column(String)
    raw_text = Column(String, nullable=True)
    is_categorized = Column(Boolean, default=False)
    confidence_score = Column(String, nullable=True)
    categorized_at = Column(DateTime, nullable=True)

    # Relationships
    client_file = relationship("ClientFile", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
