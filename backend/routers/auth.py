from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from datetime import timedelta

from database import get_db
import models
import schemas
import auth

router = APIRouter()


@router.post("/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    email = user.email.strip().lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(
        name=user.name.strip(),
        email=email,
        hashed_password=auth.get_password_hash(user.password),
        role="Analyst",
    )
    db.add(new_user)
    db.add(models.AuditLog(
        action="USER_REGISTER",
        user_email=email,
        details=f"New analyst account created: {new_user.name}",
    ))
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(request: Request, db: Session = Depends(get_db)):
    """Accepts either JSON or an OAuth2 form body, so both the static pages and
    Swagger's Authorize dialog can authenticate."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        body = await request.form()

    username = (body.get("username") or body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    user = db.query(models.User).filter(models.User.email == username).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password. Please verify credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    db.add(models.AuditLog(
        action="USER_LOGIN",
        user_email=user.email,
        details=f"Successful sign-in as {user.role}",
        ip_address=request.client.host if request.client else "unknown",
    ))
    db.commit()
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}


@router.get("/me", response_model=schemas.User)
def read_current_user(current_user: models.User = Depends(auth.get_current_user)):
    """Lets the front end validate a stored token on page load instead of
    trusting whatever is in localStorage."""
    return current_user
