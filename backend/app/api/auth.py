from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User
from app.services.auth import create_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")
    password: str = Field(min_length=6, max_length=128)


def current_user_id(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> int:
    if authorization and authorization.startswith("Bearer "):
        user_id = decode_token(authorization[7:])
        if user_id is not None and db.get(User, user_id) is not None:
            return user_id
    if not settings.require_auth:
        return 1
    raise HTTPException(status_code=401, detail="请先登录")


@router.post("/register")
def register(body: Credentials, db: Session = Depends(get_db)) -> dict:
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id), "user": {"id": user.id, "username": user.username}}


@router.post("/login")
def login(body: Credentials, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter_by(username=body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": create_token(user.id), "user": {"id": user.id, "username": user.username}}


@router.get("/me")
def me(user_id: int = Depends(current_user_id), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    return {"id": user.id, "username": user.username} if user else {"id": 1, "username": "guest"}
