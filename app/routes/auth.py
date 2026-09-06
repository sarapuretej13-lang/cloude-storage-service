import os
import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from google_auth_oauthlib.flow import Flow

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
FRONTEND_URL         = os.getenv("FRONTEND_URL", "http://localhost:5500")

def get_google_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI],
            }
        },
        scopes=["openid", "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile"],
        redirect_uri=GOOGLE_REDIRECT_URI,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):

    # Check duplicate
    try:
        existing = db.query(User).filter(User.email == body.email.lower().strip()).first()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB query failed: {str(e)}")

    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=body.name.strip(),
        email=body.email.lower().strip(),
        hashed_password=hash_password(body.password)
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database not ready: {str(e)}")

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# =========================================================
# GOOGLE OAUTH
# =========================================================

@router.get("/google/login")
def google_login():
    """Redirect browser to Google's consent screen."""
    flow = get_google_flow()
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account"
    )
    return RedirectResponse(authorization_url)


@router.get("/google/callback")
def google_callback(code: str, db: Session = Depends(get_db)):
    """Google redirects here after user consents."""
    try:
        flow = get_google_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Fetch user info from Google
        user_info_resp = http_requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"}
        )
        if not user_info_resp.ok:
            raise HTTPException(status_code=400, detail="Failed to fetch Google user info")

        user_info = user_info_resp.json()
        email = user_info.get("email", "").lower().strip()
        name  = user_info.get("name", email.split("@")[0])

        if not email:
            raise HTTPException(status_code=400, detail="Google did not return an email")

        # Find or create user
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(name=name, email=email, hashed_password=None)
            db.add(user)
            db.commit()
            db.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        # Redirect to frontend with token in query param
        # Frontend reads it from URL and stores in localStorage
        return RedirectResponse(
            url=f"{FRONTEND_URL}/index.html?token={token}&name={name}"
        )

    except HTTPException:
        raise
    except Exception as e:
        return RedirectResponse(url=f"{FRONTEND_URL}/index.html?error=google_auth_failed")
