from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    DateTime,
    Boolean,
    Float,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String, nullable=True)
    business_description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    categories = relationship("Category", back_populates="client")
    files = relationship("ClientFile", back_populates="client")
    transactions = relationship("Transaction", back_populates="client")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    is_auto_generated = Column(Boolean, default=False)
    client_id = Column(Integer, ForeignKey("clients.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")


class ClientFile(Base):
    __tablename__ = "client_files"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    filename = Column(String)
    original_filename = Column(String(255), nullable=True)
    file_path = Column(String(512), nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    total_transactions = Column(Integer, default=0)
    categorized_transactions = Column(Integer, default=0)

    # Relationships
    client = relationship("Client", back_populates="files")
    transactions = relationship("Transaction", back_populates="source_file")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    file_id = Column(Integer, ForeignKey("client_files.id"))
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    date = Column(DateTime)
    description = Column(String)
    amount = Column(Float)
    raw_text = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    is_categorized = Column(Boolean, default=False)
    confidence_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    categorized_at = Column(DateTime, nullable=True)

    # Relationships
    client = relationship("Client", back_populates="transactions")
    source_file = relationship("ClientFile", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")

    @property
    def category_name(self):
        return self.category.name if self.category else None


# Create database engine and tables
engine = create_engine("sqlite:///sql_app.db")
Base.metadata.create_all(bind=engine)
