import uuid
from fastapi import APIRouter, Depends, Response, Cookie, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from app.db.session import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.services.auth_service import register_user, login_user, get_user_by_id, get_or_create_oauth_user
from app.api.deps import get_current_user
from app.models.user import User
from app.core.security import decode_token, create_access_token, create_refresh_token
from app.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user, access, refresh = await register_user(db, req.email, req.password, req.display_name)
    response.set_cookie(
        key="refresh_token", value=refresh, httponly=True, secure=False,
        samesite="lax", max_age=settings.jwt_refresh_expire_days * 86400, path="/api/v1/auth",
    )
    return TokenResponse(access_token=access)

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user, access, refresh = await login_user(db, req.email, req.password)
    response.set_cookie(
        key="refresh_token", value=refresh, httponly=True, secure=False,
        samesite="lax", max_age=settings.jwt_refresh_expire_days * 86400, path="/api/v1/auth",
    )
    return TokenResponse(access_token=access)

@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user

@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(None),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    new_access = create_access_token(str(user.id))
    new_refresh = create_refresh_token(str(user.id))
    response.set_cookie(
        key="refresh_token", value=new_refresh, httponly=True, secure=False,
        samesite="lax", max_age=settings.jwt_refresh_expire_days * 86400, path="/api/v1/auth",
    )
    return TokenResponse(access_token=new_access)

OAUTH_CONFIGS = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": "openid email profile",
    },
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scopes": "read:user user:email",
    },
}

def _get_oauth_settings(provider: str):
    if provider == "google":
        return settings.oauth_google_client_id, settings.oauth_google_client_secret
    elif provider == "github":
        return settings.oauth_github_client_id, settings.oauth_github_client_secret
    return "", ""

@router.get("/oauth/{provider}")
async def oauth_redirect(provider: str):
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    cfg = OAUTH_CONFIGS[provider]
    client_id, _ = _get_oauth_settings(provider)
    redirect_uri = f"{settings.backend_url}/api/v1/auth/oauth/{provider}/callback"
    url = f"{cfg['auth_url']}?client_id={client_id}&redirect_uri={redirect_uri}&scope={cfg['scopes']}&response_type=code"
    return RedirectResponse(url=url)

@router.get("/oauth/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    response: Response = ...,
    db: AsyncSession = Depends(get_db),
):
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    cfg = OAUTH_CONFIGS[provider]
    client_id, client_secret = _get_oauth_settings(provider)
    redirect_uri = f"{settings.backend_url}/api/v1/auth/oauth/{provider}/callback"

    async with httpx.AsyncClient() as http:
        token_resp = await http.post(cfg["token_url"], data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }, headers={"Accept": "application/json"})
        token_data = token_resp.json()
        oauth_token = token_data.get("access_token")
        if not oauth_token:
            raise HTTPException(status_code=400, detail="OAuth token exchange failed")

        userinfo_resp = await http.get(cfg["userinfo_url"], headers={"Authorization": f"Bearer {oauth_token}"})
        userinfo = userinfo_resp.json()

    if provider == "google":
        email = userinfo.get("email")
        name = userinfo.get("name", email)
        oauth_id = userinfo.get("id")
    elif provider == "github":
        email = userinfo.get("email")
        if not email:
            async with httpx.AsyncClient() as http:
                emails_resp = await http.get("https://api.github.com/user/emails", headers={"Authorization": f"Bearer {oauth_token}"})
                emails = emails_resp.json()
                primary = next((e for e in emails if e.get("primary")), None)
                email = primary["email"] if primary else None
        name = userinfo.get("name") or userinfo.get("login", "")
        oauth_id = str(userinfo.get("id"))

    if not email:
        raise HTTPException(status_code=400, detail="Could not get email from provider")

    user, access, refresh_tok = await get_or_create_oauth_user(db, email, name, provider, oauth_id)
    response.set_cookie(
        key="refresh_token", value=refresh_tok, httponly=True, secure=False,
        samesite="lax", max_age=settings.jwt_refresh_expire_days * 86400, path="/api/v1/auth",
    )
    return TokenResponse(access_token=access)
