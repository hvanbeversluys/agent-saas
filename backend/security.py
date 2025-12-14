"""
Module de sécurité - Authentification et autorisation.
Inclut le hashing bcrypt, JWT, et les permissions RBAC.
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets

from passlib.context import CryptContext
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from config import settings

# === Password Hashing avec bcrypt ===
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS
)


def hash_password(password: str) -> str:
    """Hash un mot de passe avec bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe contre son hash"""
    return pwd_context.verify(plain_password, hashed_password)


def generate_api_key() -> str:
    """Génère une clé API sécurisée"""
    return f"ask_{secrets.token_urlsafe(32)}"


def generate_uuid() -> str:
    """Génère un UUID v4"""
    import uuid
    return str(uuid.uuid4())


# === JWT Token Management ===
security = HTTPBearer(auto_error=False)


def create_access_token(user_id: str, tenant_id: str, extra_claims: dict = None) -> str:
    """Crée un JWT access token"""
    expires = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": expires,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Crée un refresh token"""
    expires = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expires,
        "iat": datetime.utcnow(),
        "type": "refresh",
        "jti": generate_uuid()  # Unique ID pour révocation
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Décode et valide un JWT"""
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expiré",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"}
        )


# === RBAC Permissions ===
PERMISSIONS = {
    "agents": ["create", "read", "update", "delete", "execute"],
    "prompts": ["create", "read", "update", "delete"],
    "workflows": ["create", "read", "update", "delete", "execute"],
    "mcp_tools": ["create", "read", "update", "delete", "configure"],
    "users": ["create", "read", "update", "delete", "invite"],
    "billing": ["read", "manage"],
    "settings": ["read", "update"],
    "api_keys": ["create", "read", "delete"],
}

ROLE_PERMISSIONS = {
    "owner": "*",  # Tous les droits
    "admin": [
        "agents:*", "prompts:*", "workflows:*", "mcp_tools:*",
        "users:create", "users:read", "users:update", "users:invite",
        "settings:*", "api_keys:*", "billing:read"
    ],
    "manager": [
        "agents:*", "prompts:*", "workflows:*", 
        "mcp_tools:read", "mcp_tools:configure",
        "users:read", "settings:read"
    ],
    "member": [
        "agents:read", "agents:execute",
        "prompts:read",
        "workflows:read", "workflows:execute",
        "mcp_tools:read"
    ],
    "viewer": [
        "agents:read", "prompts:read", "workflows:read", "mcp_tools:read"
    ],
}


def check_permission(user_role: str, user_permissions: list, resource: str, action: str) -> bool:
    """Vérifie si un utilisateur a la permission requise"""
    role_perms = ROLE_PERMISSIONS.get(user_role, [])
    
    # Owner a tous les droits
    if role_perms == "*":
        return True
    
    # Vérifier permission exacte ou wildcard
    full_perm = f"{resource}:{action}"
    wildcard_perm = f"{resource}:*"
    
    if full_perm in role_perms or wildcard_perm in role_perms:
        return True
    
    # Vérifier permissions additionnelles de l'utilisateur
    if user_permissions and full_perm in user_permissions:
        return True
    
    return False


def require_permission(resource: str, action: str):
    """Dependency Factory pour vérifier les permissions"""
    from database import DBUser, get_db
    
    def permission_checker(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
    ) -> "DBUser":
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Non authentifié",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        payload = decode_token(credentials.credentials)
        
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Type de token invalide"
            )
        
        user = db.query(DBUser).filter(DBUser.id == payload["sub"]).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utilisateur non trouvé"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte désactivé"
            )
        
        if not check_permission(user.role, user.permissions or [], resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission refusée: {resource}:{action}"
            )
        
        return user
    
    return permission_checker


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(lambda: None)  # Sera injecté
) -> "DBUser":
    """Dependency pour récupérer l'utilisateur authentifié"""
    from database import DBUser, get_db
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    payload = decode_token(credentials.credentials)
    
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Type de token invalide"
        )
    
    # Note: db doit être injecté correctement
    return payload


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[dict]:
    """Dependency optionnelle - retourne None si pas authentifié"""
    if not credentials:
        return None
    
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        return payload
    except:
        return None


# === Utility functions ===
def slugify(text: str) -> str:
    """Convertit un texte en slug URL-friendly"""
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')
