from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Client
from app.schemas.directory import ClientDetail, ClientRead, PreferenceRead

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("", response_model=list[ClientRead])
def list_clients(db: Session = Depends(get_db)) -> list[Client]:
    return list(db.scalars(select(Client).order_by(Client.name, Client.id)))


@router.get("/{client_id}", response_model=ClientDetail)
def get_client(client_id: UUID, db: Session = Depends(get_db)) -> ClientDetail:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")

    preferences = sorted(client.preferences, key=lambda p: p.attribute)
    return ClientDetail(
        id=client.id,
        name=client.name,
        preferences=[PreferenceRead.model_validate(p) for p in preferences],
    )
