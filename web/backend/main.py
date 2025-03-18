"""
PDF Extractor API
"""

import os
import logging
from datetime import datetime
import json
import aiofiles
from typing import List, Optional
import asyncio
from sqlalchemy.sql import func
from dotenv import load_dotenv
import fitz
import sqlite3
import pandas as pd
from sqlalchemy.orm import Session
from fastapi import (
    FastAPI,
    File,
    UploadFile,
    HTTPException,
    BackgroundTasks,
    WebSocket,
    Depends,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("pdf_extractor.log")],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Check for required environment variables
if not os.getenv("OPENAI_API_KEY"):
    print("Warning: OPENAI_API_KEY not set. Some features will be disabled.")

from database import SessionLocal, engine, get_db
from models import (
    Base,
    Client,
    Category,
    ClientFile,
    Transaction,
    StatementType,
    Parser,
)
from schemas import (
    StatementType as StatementTypeSchema,
    Parser as ParserSchema,
)
from ai_utils import generate_categories
from dataextractai_vision.extractor import process_pdf_file

# Initialize FastAPI app
app = FastAPI(
    title="PDF Extractor API",
    description="API for extracting transaction data from PDF statements",
    version="1.0.0",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Create uploads directory
os.makedirs("uploads", exist_ok=True)


# Pydantic models for request/response
class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int
    is_auto_generated: bool
    client_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class StatementTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None


class StatementTypeResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ClientBase(BaseModel):
    name: str
    address: Optional[str] = None
    business_description: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(ClientBase):
    pass


class ClientResponse(ClientBase):
    id: int
    created_at: datetime
    categories: List[CategoryResponse] = []
    statement_types: List[StatementTypeResponse] = []

    class Config:
        from_attributes = True


class FileResponse(BaseModel):
    id: int
    filename: str
    status: str
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    total_transactions: Optional[int] = None
    pages_processed: Optional[int] = None
    total_pages: Optional[int] = None
    file_hash: Optional[str] = None

    class Config:
        from_attributes = True


# Add new Pydantic models for transactions
class TransactionResponse(BaseModel):
    id: int
    date: datetime
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


# Store active WebSocket connections
active_connections: set = set()


@app.get("/")
async def root():
    return {"message": "Welcome to PDF Extractor API"}


@app.post("/clients/", response_model=ClientResponse)
async def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    """Create a new client."""
    try:
        logger.info(f"Creating new client: {client.name}")

        # Create client
        db_client = Client(**client.model_dump())
        db.add(db_client)
        db.commit()
        db.refresh(db_client)

        return db_client
    except Exception as e:
        logger.error(f"Error creating client: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/clients/", response_model=List[ClientResponse])
async def list_clients(db: Session = Depends(get_db)):
    try:
        logger.info("Fetching all clients")
        clients = db.query(Client).all()
        return clients
    except Exception as e:
        logger.error(f"Error fetching clients: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, db: Session = Depends(get_db)):
    try:
        logger.info(f"Fetching client with ID: {client_id}")
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        return client
    except Exception as e:
        logger.error(f"Error fetching client {client_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clients/{client_id}/categories/", response_model=CategoryResponse)
async def create_category(
    client_id: int, category: CategoryCreate, db: Session = Depends(get_db)
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    db_category = Category(**category.dict(), client_id=client_id)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@app.get("/clients/{client_id}/files/", response_model=List[FileResponse])
async def list_client_files(client_id: int, db: Session = Depends(get_db)):
    try:
        files = db.query(ClientFile).filter(ClientFile.client_id == client_id).all()
        return files
    except Exception as e:
        print(f"Error fetching files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching files: {str(e)}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except:
        active_connections.remove(websocket)


async def broadcast_status(message: dict):
    """Broadcast status update to all connected clients"""
    # Ensure we have all required fields
    if "file_id" in message:
        message.update(
            {
                "type": "status_update",
                "timestamp": datetime.now().isoformat(),
                "pages_processed": message.get("pages_processed", 0),
                "total_pages": message.get("total_pages", 0),
                "total_transactions": message.get("total_transactions", 0),
            }
        )

    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            print(f"Error broadcasting status: {e}")
            active_connections.remove(connection)


async def process_pdf_background(
    file_path: str, client_id: int, file_id: int, db: Session
):
    """Process a PDF file in the background"""
    logger.info(f"Starting background processing for file: {file_path}")
    try:
        # Update file status to processing
        db_file = db.query(ClientFile).filter(ClientFile.id == file_id).first()
        if not db_file:
            logger.error(f"Error: File record {file_id} not found in database")
            return

        db_file.status = "processing"
        db.commit()
        await broadcast_status(
            {
                "type": "status_update",
                "file_id": file_id,
                "status": "processing",
                "message": "Starting PDF processing...",
            }
        )

        # Process the PDF using our new parser system
        logger.info("Calling process_pdf_file...")
        result = process_pdf_file(file_path)
        logger.info(f"Process result: {result}")

        if result.transactions:
            logger.info(f"Found {len(result.transactions)} transactions")
            # Update file record
            db_file.status = "completed"
            db_file.processed_at = datetime.now()
            db_file.total_transactions = len(result.transactions)
            db_file.pages_processed = result.pages_processed
            db_file.total_pages = result.total_pages
            db.commit()

            # Add transactions to database
            for transaction in result.transactions:
                logger.debug(f"Adding transaction: {transaction}")
                db_transaction = Transaction(
                    client_file_id=file_id,
                    date=pd.to_datetime(transaction.date),
                    description=transaction.description,
                    amount=transaction.amount,
                    raw_text=transaction.category,  # Store the parser-suggested category
                    is_categorized=False,
                )
                db.add(db_transaction)

            db.commit()
            logger.info("Successfully committed transactions to database")

            await broadcast_status(
                {
                    "type": "status_update",
                    "file_id": file_id,
                    "status": "completed",
                    "total_transactions": len(result.transactions),
                    "pages_processed": result.pages_processed,
                    "total_pages": result.total_pages,
                    "processing_details": result.processing_details,
                }
            )
        else:
            error_message = result.error_message or "No transactions found"
            logger.error(f"Processing failed: {error_message}")
            db_file.status = "error"
            db_file.error_message = error_message
            db_file.processed_at = datetime.now()
            db_file.pages_processed = result.pages_processed
            db_file.total_pages = result.total_pages
            db.commit()

            await broadcast_status(
                {
                    "type": "status_update",
                    "file_id": file_id,
                    "status": "error",
                    "error_message": error_message,
                    "pages_processed": result.pages_processed,
                    "total_pages": result.total_pages,
                    "processing_details": result.processing_details,
                }
            )

    except Exception as e:
        logger.exception(f"Error processing file: {str(e)}")
        if db_file:
            db_file.status = "error"
            db_file.error_message = str(e)
            db_file.processed_at = datetime.now()
            db.commit()

        await broadcast_status(
            {
                "type": "status_update",
                "file_id": file_id,
                "status": "error",
                "error_message": str(e),
            }
        )


@app.post("/clients/{client_id}/files/", response_model=FileResponse)
async def upload_file(
    client_id: int,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    print(f"Starting file upload for client {client_id}: {file.filename}")

    # Validate client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Create unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join("uploads", unique_filename)

    try:
        # Save file
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # Create file record
        db_file = ClientFile(
            client_id=client_id,
            filename=file.filename,
            file_path=file_path,
            status="pending",
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)

        # Send initial status update
        await broadcast_status(
            {
                "type": "status_update",
                "file_id": db_file.id,
                "status": "pending",
                "filename": file.filename,
                "message": "File uploaded, starting processing...",
            }
        )

        # Start background processing
        background_tasks.add_task(
            process_pdf_background,
            file_path=file_path,
            client_id=client_id,
            file_id=db_file.id,
            db=db,
        )

        return db_file

    except Exception as e:
        # Clean up file if upload fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/clients/{client_id}/transactions/", response_model=List[TransactionResponse])
async def list_client_transactions(
    client_id: int,
    db: Session = Depends(get_db),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category_id: Optional[int] = None,
    is_categorized: Optional[bool] = None,
):
    """List transactions for a client with optional filters"""
    try:
        # Start with a query that joins ClientFile to get transactions for this client
        query = (
            db.query(Transaction)
            .join(ClientFile)
            .filter(ClientFile.client_id == client_id)
        )

        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)
        if category_id is not None:
            query = query.filter(Transaction.category_id == category_id)
        if is_categorized is not None:
            query = query.filter(Transaction.is_categorized == is_categorized)

        transactions = query.all()
        return transactions
    except Exception as e:
        print(f"Error fetching transactions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching transactions: {str(e)}"
        )


@app.post("/transactions/{transaction_id}/categorize")
async def categorize_transaction(
    transaction_id: int,
    category_id: int,
    confidence_score: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """Categorize a transaction"""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    transaction.category_id = category_id
    transaction.is_categorized = True
    transaction.confidence_score = confidence_score
    transaction.categorized_at = datetime.utcnow()

    db.commit()
    return {"status": "success"}


@app.get("/processing-status/")
async def get_processing_status(db: Session = Depends(get_db)):
    """Get the status of all processed files"""
    try:
        # Get statistics
        total_files = db.query(func.count(ClientFile.id)).scalar()
        completed_files = (
            db.query(func.count(ClientFile.id))
            .filter(ClientFile.status == "completed")
            .scalar()
        )
        processing_files = (
            db.query(func.count(ClientFile.id))
            .filter(ClientFile.status == "processing")
            .scalar()
        )
        failed_files = (
            db.query(func.count(ClientFile.id))
            .filter(ClientFile.status == "failed")
            .scalar()
        )
        total_transactions = (
            db.query(func.sum(ClientFile.total_transactions)).scalar() or 0
        )

        # Get recent files
        recent_files = (
            db.query(ClientFile).order_by(ClientFile.uploaded_at.desc()).limit(5).all()
        )

        return {
            "statistics": {
                "total_files": total_files,
                "completed": completed_files,
                "processing": processing_files,
                "failed": failed_files,
                "total_transactions": total_transactions,
            },
            "recent_files": [
                {
                    "file_path": file.file_path,
                    "status": file.status,
                    "last_processed": (
                        file.processed_at.isoformat()
                        if file.processed_at
                        else file.uploaded_at.isoformat()
                    ),
                    "pages_processed": 0,  # TODO: Add pages_processed to ClientFile model
                    "total_transactions": file.total_transactions or 0,
                }
                for file in recent_files
            ],
        }
    except Exception as e:
        print(f"Error getting processing status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int, client: ClientUpdate, db: Session = Depends(get_db)
):
    try:
        logger.info(f"Updating client with ID: {client_id}")
        db_client = db.query(Client).filter(Client.id == client_id).first()
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")

        for key, value in client.dict().items():
            setattr(db_client, key, value)

        db.commit()
        db.refresh(db_client)
        return db_client
    except Exception as e:
        logger.error(f"Error updating client {client_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/clients/{client_id}")
async def delete_client(client_id: int, db: Session = Depends(get_db)):
    try:
        logger.info(f"Deleting client with ID: {client_id}")
        db_client = db.query(Client).filter(Client.id == client_id).first()
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Delete associated categories first (due to foreign key constraint)
        db.query(Category).filter(Category.client_id == client_id).delete()

        # Delete the client
        db.delete(db_client)
        db.commit()
        return {"message": "Client deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting client {client_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clients/{client_id}/statement-types", response_model=StatementTypeResponse)
async def create_statement_type(
    client_id: int, statement_type: StatementTypeCreate, db: Session = Depends(get_db)
):
    db_statement_type = StatementType(
        client_id=client_id,
        name=statement_type.name,
        description=statement_type.description,
    )
    db.add(db_statement_type)
    db.commit()
    db.refresh(db_statement_type)
    return db_statement_type


@app.get(
    "/clients/{client_id}/statement-types", response_model=List[StatementTypeResponse]
)
async def list_statement_types(client_id: int, db: Session = Depends(get_db)):
    return db.query(StatementType).filter(StatementType.client_id == client_id).all()


@app.delete("/clients/{client_id}/statement-types/{statement_type_id}")
async def delete_statement_type(
    client_id: int, statement_type_id: int, db: Session = Depends(get_db)
):
    db_statement_type = (
        db.query(StatementType)
        .filter(
            StatementType.id == statement_type_id, StatementType.client_id == client_id
        )
        .first()
    )
    if not db_statement_type:
        raise HTTPException(status_code=404, detail="Statement type not found")

    db.delete(db_statement_type)
    db.commit()
    return {"message": "Statement type deleted successfully"}


# Parser and Statement Type endpoints
@app.get("/parsers/", response_model=List[ParserSchema])
def get_parsers(db: Session = Depends(get_db)):
    return db.query(Parser).filter(Parser.is_active == True).all()


@app.get("/statement-types/", response_model=List[StatementTypeSchema])
def get_statement_types(db: Session = Depends(get_db)):
    return db.query(StatementType).filter(StatementType.is_active == True).all()


@app.get(
    "/parsers/{parser_id}/statement-types/", response_model=List[StatementTypeSchema]
)
def get_parser_statement_types(parser_id: int, db: Session = Depends(get_db)):
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")
    return parser.statement_types


@app.post("/parsers/{parser_id}/statement-types/{statement_type_id}/")
def add_statement_type_to_parser(
    parser_id: int, statement_type_id: int, db: Session = Depends(get_db)
):
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")

    statement_type = (
        db.query(StatementType).filter(StatementType.id == statement_type_id).first()
    )
    if not statement_type:
        raise HTTPException(status_code=404, detail="Statement type not found")

    if statement_type not in parser.statement_types:
        parser.statement_types.append(statement_type)
        db.commit()

    return {"message": "Statement type added to parser"}


@app.delete("/parsers/{parser_id}/statement-types/{statement_type_id}/")
def remove_statement_type_from_parser(
    parser_id: int, statement_type_id: int, db: Session = Depends(get_db)
):
    parser = db.query(Parser).filter(Parser.id == parser_id).first()
    if not parser:
        raise HTTPException(status_code=404, detail="Parser not found")

    statement_type = (
        db.query(StatementType).filter(StatementType.id == statement_type_id).first()
    )
    if not statement_type:
        raise HTTPException(status_code=404, detail="Statement type not found")

    if statement_type in parser.statement_types:
        parser.statement_types.remove(statement_type)
        db.commit()

    return {"message": "Statement type removed from parser"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
