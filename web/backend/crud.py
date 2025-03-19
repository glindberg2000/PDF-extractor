from sqlalchemy.orm import Session
from sqlalchemy import and_
import models
import schemas
from datetime import datetime


def get_category(db: Session, category_id: int):
    return db.query(models.Category).filter(models.Category.id == category_id).first()


def get_categories(
    db: Session,
    client_id: int = None,
    type: str = None,
    skip: int = 0,
    limit: int = 100
):
    query = db.query(models.Category)
    
    if client_id is not None:
        query = query.filter(
            models.Category.client_id == client_id
        )
    
    if type is not None:
        query = query.filter(models.Category.type == type)
    
    return query.offset(skip).limit(limit).all()


def create_category(db: Session, category: schemas.CategoryCreate):
    db_category = models.Category(
        name=category.name,
        description=category.description,
        type=category.type,
        is_system_default=category.is_system_default,
        is_auto_generated=category.is_auto_generated,
        parent_id=category.parent_id,
        client_id=category.client_id,
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


def update_category(db: Session, category_id: int, category: schemas.CategoryCreate):
    db_category = get_category(db, category_id=category_id)
    if db_category:
        for key, value in category.model_dump().items():
            setattr(db_category, key, value)
        db.commit()
        db.refresh(db_category)
    return db_category


def delete_category(db: Session, category_id: int):
    db_category = get_category(db, category_id=category_id)
    if db_category:
        db.delete(db_category)
        db.commit()
    return db_category


def get_statement_type(db: Session, statement_type_id: int):
    return db.query(models.StatementType).filter(models.StatementType.id == statement_type_id).first()


def get_statement_types(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.StatementType).offset(skip).limit(limit).all()


def create_statement_type(db: Session, statement_type: schemas.StatementTypeCreate):
    db_statement_type = models.StatementType(**statement_type.model_dump())
    db.add(db_statement_type)
    db.commit()
    db.refresh(db_statement_type)
    return db_statement_type


def update_statement_type(db: Session, statement_type_id: int, statement_type: schemas.StatementTypeCreate):
    db_statement_type = get_statement_type(db, statement_type_id=statement_type_id)
    if db_statement_type:
        for key, value in statement_type.model_dump().items():
            setattr(db_statement_type, key, value)
        db_statement_type.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_statement_type)
    return db_statement_type


def delete_statement_type(db: Session, statement_type_id: int):
    db_statement_type = get_statement_type(db, statement_type_id=statement_type_id)
    if db_statement_type:
        db.delete(db_statement_type)
        db.commit()
    return db_statement_type


def get_client(db: Session, client_id: int):
    return db.query(models.Client).filter(models.Client.id == client_id).first()


def get_clients(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Client).offset(skip).limit(limit).all()


def create_client(db: Session, client: schemas.ClientCreate):
    db_client = models.Client(
        name=client.name,
        description=client.description,
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)

    # Add statement types
    for statement_type_id in client.statement_type_ids:
        statement_type = get_statement_type(db, statement_type_id)
        if statement_type:
            db_client.statement_types.append(statement_type)
    
    db.commit()
    db.refresh(db_client)
    return db_client


def update_client(db: Session, client_id: int, client: schemas.ClientCreate):
    db_client = get_client(db, client_id=client_id)
    if db_client:
        db_client.name = client.name
        db_client.description = client.description
        db_client.updated_at = datetime.utcnow()

        # Update statement types
        db_client.statement_types = []
        for statement_type_id in client.statement_type_ids:
            statement_type = get_statement_type(db, statement_type_id)
            if statement_type:
                db_client.statement_types.append(statement_type)

        db.commit()
        db.refresh(db_client)
    return db_client


def delete_client(db: Session, client_id: int):
    db_client = get_client(db, client_id=client_id)
    if db_client:
        db.delete(db_client)
        db.commit()
    return db_client


def get_client_file(db: Session, client_file_id: int):
    return db.query(models.ClientFile).filter(models.ClientFile.id == client_file_id).first()


def get_client_files(db: Session, client_id: int = None, skip: int = 0, limit: int = 100):
    query = db.query(models.ClientFile)
    if client_id:
        query = query.filter(models.ClientFile.client_id == client_id)
    return query.offset(skip).limit(limit).all()


def create_client_file(db: Session, client_file: schemas.ClientFileCreate):
    db_client_file = models.ClientFile(**client_file.model_dump())
    db.add(db_client_file)
    db.commit()
    db.refresh(db_client_file)
    return db_client_file


def update_client_file(db: Session, client_file_id: int, client_file: schemas.ClientFileCreate):
    db_client_file = get_client_file(db, client_file_id=client_file_id)
    if db_client_file:
        for key, value in client_file.model_dump().items():
            setattr(db_client_file, key, value)
        db_client_file.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_client_file)
    return db_client_file


def delete_client_file(db: Session, client_file_id: int):
    db_client_file = get_client_file(db, client_file_id=client_file_id)
    if db_client_file:
        db.delete(db_client_file)
        db.commit()
    return db_client_file
