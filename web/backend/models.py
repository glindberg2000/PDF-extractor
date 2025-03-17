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
    file_path = Column(String)  # Path to the uploaded file
    status = Column(String)  # pending, processing, completed, error
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    total_transactions = Column(Integer, nullable=True)
    pages_processed = Column(Integer, nullable=True)
    total_pages = Column(Integer, nullable=True)
    file_hash = Column(String, nullable=True)  # To link with processing history

    # Relationships
    client = relationship("Client", back_populates="files")
    transactions = relationship(
        "Transaction", back_populates="client_file", cascade="all, delete-orphan"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    client_file_id = Column(Integer, ForeignKey("client_files.id"))
    date = Column(DateTime, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_categorized = Column(Boolean, default=False)
    raw_text = Column(String, nullable=True)  # For storing AI-suggested category
    confidence_score = Column(Float, nullable=True)
    categorized_at = Column(DateTime, nullable=True)
    page_number = Column(Integer, nullable=True)

    # Relationships
    client_file = relationship("ClientFile", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")

    @property
    def category_name(self):
        return self.category.name if self.category else None


# Create database engine and tables
engine = create_engine("sqlite:///sql_app.db")
Base.metadata.create_all(bind=engine)
