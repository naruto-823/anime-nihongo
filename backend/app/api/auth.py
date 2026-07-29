from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
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


def _native_session(user: User) -> dict:
    return {
        "access_token": create_token(user.id),
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username},
    }


def current_user_id(request: Request, authorization: str | None = Header(default=None),
                    db: Session = Depends(get_db)) -> int:
    # Cookie is the primary transport. Bearer remains temporarily supported so
    # existing logged-in clients can migrate without losing their session.
    token = request.cookies.get(settings.auth_cookie_name)
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if token:
        user_id = decode_token(token)
        if user_id is not None and db.get(User, user_id) is not None:
            return user_id
    if not settings.require_auth:
        return 1
    raise HTTPException(status_code=401, detail="请先登录")


def _set_session(response: Response, user_id: int) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=create_token(user_id),
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register")
def register(body: Credentials, response: Response, db: Session = Depends(get_db)) -> dict:
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    _set_session(response, user.id)
    return {"user": {"id": user.id, "username": user.username}}


@router.post("/login")
def login(body: Credentials, response: Response, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter_by(username=body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    _set_session(response, user.id)
    return {"user": {"id": user.id, "username": user.username}}


@router.post("/native/register")
def native_register(body: Credentials, db: Session = Depends(get_db)) -> dict:
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _native_session(user)


@router.post("/native/login")
def native_login(body: Credentials, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter_by(username=body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return _native_session(user)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(settings.auth_cookie_name, path="/")


@router.get("/me")
def me(response: Response, user_id: int = Depends(current_user_id), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user:
        # Also upgrades a legacy Bearer session to the HttpOnly cookie.
        _set_session(response, user.id)
    return {"id": user.id, "username": user.username} if user else {"id": 1, "username": "guest"}
