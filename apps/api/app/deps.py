"""FastAPI dependencies that resolve the current user's business."""

from fastapi import Header, HTTPException, status
from supabase import create_client

from app.config import get_settings

_demo_business_id = None


def get_supabase_client():
    """Build a Supabase client from settings; raise 500 if not configured."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Supabase not configured")
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _resolve_business_for_owner(owner_user_id: str) -> str | None:
    """Return the id of the business owned by owner_user_id, or None."""
    client = get_supabase_client()
    response = (
        client.table("businesses")
        .select("id")
        .eq("owner_user_id", owner_user_id)
        .limit(1)
        .execute()
    )
    return response.data[0]["id"] if response.data else None


def resolve_demo_business_id() -> str:
    """Return the demo business id for DEMO_OWNER_USER_ID, cached after first lookup."""
    global _demo_business_id
    if _demo_business_id is not None:
        return _demo_business_id
    settings = get_settings()
    if not settings.demo_owner_user_id:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "DEMO_OWNER_USER_ID not set")
    bid = _resolve_business_for_owner(settings.demo_owner_user_id)
    if bid is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo business not found for owner")
    _demo_business_id = bid
    return bid


def get_current_business_id(authorization: str | None = Header(default=None)) -> str:
    """Return the business id for the caller, using demo mode or the bearer token."""
    settings = get_settings()
    if settings.demo_mode is True:
        return resolve_demo_business_id()

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization[len("Bearer "):].strip()

    try:
        user_resp = get_supabase_client().auth.get_user(token)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    if user_resp.user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    bid = _resolve_business_for_owner(str(user_resp.user.id))
    if bid is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No business for this user")
    return bid
