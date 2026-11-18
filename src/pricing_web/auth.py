"""Firebase verification and server-owned workspace capabilities."""
from dataclasses import dataclass
import hashlib
import time

from .config import WebError

CAPABILITIES = {"read", "upload", "train", "compare", "edit", "submit", "review", "publish", "admin"}


def identity_key(issuer, uid):
    return hashlib.sha256((issuer + "\0" + uid).encode()).hexdigest()


@dataclass(frozen=True)
class Principal:
    issuer: str
    uid: str
    auth_time: int
    memberships: dict

    @property
    def actor_id(self): return identity_key(self.issuer, self.uid)

    def require(self, workspace, action, recent_seconds=None):
        member = self.memberships.get(workspace)
        if not member or not member.get("enabled", True) or "read" not in member.get("capabilities", []):
            raise WebError(404, "resource_unavailable")
        if action not in member.get("capabilities", []): raise WebError(403, "forbidden_action")
        if recent_seconds is None and action in {"train", "review", "publish"}: recent_seconds = 3600
        if recent_seconds is None and action == "admin": recent_seconds = 900
        if recent_seconds is not None and time.time() - self.auth_time > recent_seconds:
            raise WebError(401, "recent_auth_required")


class FirebaseVerifier:
    """Public signing certificates are cached; no service-account key is needed.

    Provider account-disable checks are not implied: application membership and
    revoked_before are checked on every request, without caching membership.
    """
    def __init__(self, project_id):
        from cachecontrol import CacheControl
        from google.auth.transport.requests import Request
        import requests
        class BoundedRequest(Request):
            def __call__(self, *args, **kwargs):
                kwargs["timeout"] = 10
                return super().__call__(*args, **kwargs)
        self.project_id = project_id
        self.request = BoundedRequest(session=CacheControl(requests.Session()))

    def verify(self, token):
        from google.oauth2.id_token import verify_firebase_token
        try:
            claims = verify_firebase_token(token, self.request, audience=self.project_id)
        except Exception:
            raise WebError(401, "invalid_identity") from None
        now = time.time()
        if (claims.get("iss") != f"https://securetoken.google.com/{self.project_id}"
                or claims.get("aud") != self.project_id or not isinstance(claims.get("sub"), str)
                or not 1 <= len(claims["sub"]) <= 128
                or any(type(claims.get(k)) is not int for k in ("exp", "iat", "auth_time"))
                or claims["exp"] <= now or claims["iat"] > now or claims["auth_time"] > now
                or claims["auth_time"] > claims["iat"]):
            raise WebError(401, "invalid_identity")
        return claims


class AuthService:
    def __init__(self, store, verifier): self.store, self.verifier = store, verifier

    def authenticate(self, authorization):
        if not authorization or not authorization.startswith("Bearer ") or len(authorization) > 16384:
            raise WebError(401, "identity_required")
        claims = self.verifier.verify(authorization[7:])
        key = identity_key(claims["iss"], claims["sub"])
        member = self.store.get("identity", key, "membership")
        if member is None:
            return Principal(claims["iss"], claims["sub"], claims["auth_time"], {})
        data = member.data
        if not data.get("enabled") or claims["auth_time"] <= data.get("revoked_before", 0):
            raise WebError(401, "membership_revoked")
        # Role labels do not grant access. Only the owner-provisioned capabilities do.
        return Principal(claims["iss"], claims["sub"], claims["auth_time"], data.get("memberships", {}))

    def active_actor(self, actor_id, workspace, capability):
        member = self.store.get("identity", actor_id, "membership")
        if not member or not member.data.get("enabled"): return False
        ws = member.data.get("memberships", {}).get(workspace, {})
        return ws.get("enabled", True) and capability in ws.get("capabilities", []) and "read" in ws.get("capabilities", [])
