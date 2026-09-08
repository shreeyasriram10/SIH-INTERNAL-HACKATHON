from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db

router = APIRouter()


def _client_ip(request: Request) -> str:
    """Behind Vercel the socket peer is the edge, so prefer the forwarded chain."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _issue_session(request: Request, response: Response, user: models.User) -> str:
    """Mint the token and park it in an httpOnly cookie.

    The cookie is what the dashboard uses. It is unreadable from JavaScript, so
    injected script cannot lift the session the way it could from localStorage,
    and SameSite=strict keeps it off cross-site requests.
    """
    token = auth.create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response.set_cookie(
        key=auth.SESSION_COOKIE,
        value=token,
        max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=auth.cookie_is_secure(request),
        samesite="strict",
        path="/",
    )
    return token


@router.post("/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, request: Request, db: Session = Depends(get_db)):
    """Self-service sign-up, restricted to approved domains.

    This used to be open to anyone and granted the Analyst role outright, which
    unlocked every authenticated endpoint - cargo requests and recommendation
    history included - to any passer-by who filled in the form.
    """
    email = user.email.strip().lower()

    if not auth.signup_allowed(email):
        db.add(models.AuditLog(
            action="REGISTER_REJECTED",
            user_email=email,
            details="Address outside the permitted sign-up domains",
            ip_address=_client_ip(request),
        ))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-registration is not open. Ask an administrator to create your account.",
        )

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
        ip_address=_client_ip(request),
    ))
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(
    request: Request, response: Response, db: Session = Depends(get_db)
):
    """Accepts JSON or an OAuth2 form body, so the pages and Swagger both work."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        body = await request.form()

    username = (body.get("username") or body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    ip = _client_ip(request)
    throttle_key = f"{ip}|{username}"

    if auth.login_is_throttled(throttle_key):
        db.add(models.AuditLog(
            action="LOGIN_THROTTLED",
            user_email=username or "unknown",
            details=f"Too many failed attempts within {auth.LOGIN_WINDOW_SEC}s",
            ip_address=ip,
        ))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Try again shortly.",
        )

    user = db.query(models.User).filter(models.User.email == username).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        auth.register_login_failure(throttle_key)
        db.add(models.AuditLog(
            action="LOGIN_FAILED",
            user_email=username or "unknown",
            details="Incorrect email or password",
            ip_address=ip,
        ))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password. Please verify credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth.clear_login_failures(throttle_key)
    access_token = _issue_session(request, response, user)

    db.add(models.AuditLog(
        action="USER_LOGIN",
        user_email=user.email,
        details=f"Successful sign-in as {user.role}",
        ip_address=ip,
    ))
    db.commit()
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(auth.get_optional_user),
):
    """Clear the session cookie.

    The token itself stays valid until it expires - revoking it would need a
    server-side deny list, which is Tier 1 work.
    """
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    if user is not None:
        db.add(models.AuditLog(
            action="USER_LOGOUT",
            user_email=user.email,
            details="Session cookie cleared",
            ip_address=_client_ip(request),
        ))
        db.commit()
    return {"status": "SUCCESS"}


@router.get("/me", response_model=schemas.User)
def read_current_user(current_user: models.User = Depends(auth.get_current_user)):
    """Lets the front end confirm it still has a session without reading the
    token, which it can no longer do."""
    return current_user
