from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import current_user_id
from app.db import get_db
from app.services.curriculum import coverage_report

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


@router.get("/coverage")
def get_coverage(db: Session = Depends(get_db),
                 user_id: int = Depends(current_user_id)) -> dict:
    return coverage_report(db, user_id)
