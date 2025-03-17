from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String)
    business_description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    categories = relationship(
        "Category", back_populates="client", cascade="all, delete-orphan"
    )
    statement_types = relationship(
        "StatementType", back_populates="client", cascade="all, delete-orphan"
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
    is_auto_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")


class StatementType(Base):
    __tablename__ = "statement_types"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    name = Column(String, index=True)  # e.g., "Wells Fargo Visa", "Chase Visa"
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="statement_types")
    files = relationship("ClientFile", back_populates="statement_type")


class ClientFile(Base):
    __tablename__ = "client_files"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    statement_type_id = Column(Integer, ForeignKey("statement_types.id"))
    filename = Column(String)
    file_path = Column(String)
    status = Column(String)  # pending, processing, completed, error
    error_message = Column(String, nullable=True)
    total_transactions = Column(Integer, nullable=True)
    pages_processed = Column(Integer, nullable=True)
    total_pages = Column(Integer, nullable=True)
    file_hash = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

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

    client_file = relationship("ClientFile", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
