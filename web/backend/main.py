from sqlalchemy.orm import Session
from fastapi import (
    FastAPI,
    File,
    UploadFile,
    HTTPException,
    BackgroundTasks,
    WebSocket,
    Depends,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import os
from datetime import datetime
import json
import aiofiles
from typing import List, Optional
import asyncio
from sqlalchemy.sql import func

from database import SessionLocal, engine, get_db
from models import Base, Client, Category, ClientFile, Transaction
from ai_utils import generate_categories
from dataextractai_vision import VisionExtractor

# Initialize FastAPI app
app = FastAPI(
    title="PDF Extractor API",
    description="API for extracting transaction data from PDF statements",
    version="1.0.0",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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


class ClientBase(BaseModel):
    name: str
    address: Optional[str] = None
    business_description: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientResponse(ClientBase):
    id: int
    created_at: datetime
    categories: List[CategoryResponse] = []

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
    return {"message": "PDF Extractor API is running"}


@app.post("/clients/", response_model=ClientResponse)
async def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    db_client = Client(**client.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)

    # Auto-generate categories based on business description
    if client.business_description:
        try:
            categories_json = await generate_categories(client.business_description)
            categories = json.loads(categories_json)

            for category_name in categories:
                db_category = Category(
                    name=category_name,
                    description=f"Auto-generated category for {client.name}",
                    is_auto_generated=True,
                    client_id=db_client.id,
                )
                db.add(db_category)

            db.commit()
            db.refresh(db_client)
        except Exception as e:
            print(f"Error generating categories: {e}")
            # Add some default categories
            default_categories = ["Income", "Expenses", "Transfers", "Other"]
            for category_name in default_categories:
                db_category = Category(
                    name=category_name,
                    description=f"Default category for {client.name}",
                    is_auto_generated=True,
                    client_id=db_client.id,
                )
                db.add(db_category)
            db.commit()
            db.refresh(db_client)

    return db_client


@app.get("/clients/", response_model=List[ClientResponse])
async def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).all()


@app.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


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
    return db.query(ClientFile).filter(ClientFile.client_id == client_id).all()


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
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            active_connections.remove(connection)


async def process_pdf_background(
    file_path: str, client_id: int, file_id: int, db: Session
):
    """Process a PDF file in the background"""
    print(f"Starting background processing for file: {file_path}")
    try:
        # Update file status to processing
        db_file = db.query(ClientFile).filter(ClientFile.id == file_id).first()
        if not db_file:
            print(f"Error: File record {file_id} not found in database")
            return

        print(f"Updating status to processing for file ID: {file_id}")
        db_file.status = "processing"
        db.commit()

        await broadcast_status(
            {
                "type": "status_update",
                "file": os.path.basename(file_path),
                "status": "processing",
                "message": "Processing started",
            }
        )

        print("Processing PDF file...")
        # Process the PDF using the extractor
        extractor = VisionExtractor()
        # Run the synchronous process_pdf in a thread pool
        csv_path = await asyncio.to_thread(extractor.process_pdf, file_path)
        if not csv_path:
            raise Exception("Failed to process PDF file")

        print(f"Reading transactions from CSV: {csv_path}")
        # Read transactions from CSV
        df = pd.read_csv(csv_path)

        print(f"Found {len(df)} transactions")
        # Store transactions in database
        transactions = []
        for _, row in df.iterrows():
            transaction = Transaction(
                client_id=client_id,
                file_id=file_id,
                date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                description=row["description"],
                amount=float(row["amount"]),
                raw_text=row["raw_text"],
                is_categorized=False,
                notes=None,
                confidence_score=None,
                categorized_at=None,
            )
            transactions.append(transaction)

        print(f"Saving {len(transactions)} transactions to database...")
        db.bulk_save_objects(transactions)

        # Update file status and transaction counts
        print("Updating file status to completed...")
        db_file.status = "completed"
        db_file.transaction_count = len(transactions)
        db_file.processed_at = datetime.utcnow()
        db.commit()

        await broadcast_status(
            {
                "type": "status_update",
                "file": os.path.basename(file_path),
                "status": "completed",
                "message": f"Successfully extracted {len(transactions)} transactions",
            }
        )

        # Clean up temporary files
        if csv_path and os.path.exists(csv_path):
            os.remove(csv_path)

    except Exception as e:
        print(f"Error processing file: {str(e)}")
        if db_file:
            db_file.status = "error"
            db_file.error_message = str(e)
            db.commit()

        await broadcast_status(
            {
                "type": "status_update",
                "file": os.path.basename(file_path),
                "status": "error",
                "message": f"Error processing file: {str(e)}",
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
    query = db.query(Transaction).filter(Transaction.client_id == client_id)

    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)
    if category_id is not None:
        query = query.filter(Transaction.category_id == category_id)
    if is_categorized is not None:
        query = query.filter(Transaction.is_categorized == is_categorized)

    return query.all()


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
