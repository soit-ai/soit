""" auth

Auth primitives (JWT/session) used by entrypoints.
"""

import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from app.kernel.commons.errors import UnauthorizedError


class JWTManager:
    """JWT token manager for authentication."""
    
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
    ):
        """Initialize JWT manager.
        
        Args:
            secret_key: Secret key for signing tokens.
            algorithm: JWT algorithm (default: HS256).
            access_token_expire_minutes: Access token expiration in minutes.
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
    
    def create_access_token(
        self,
        user_id: str,
        tenant_id: str,
        workspace_id: Optional[str] = None,
        tenant_role: Optional[str] = None,
        workspace_role: Optional[str] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create JWT access token.
        
        Args:
            user_id: User ID.
            tenant_id: Tenant ID.
            workspace_id: Optional workspace ID.
            tenant_role: Optional tenant role.
            workspace_role: Optional workspace role.
            expires_delta: Optional custom expiration delta.
            
        Returns:
            Encoded JWT token string.
        """
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=self.access_token_expire_minutes
            )
        
        payload: Dict[str, any] = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        
        if workspace_id:
            payload["workspace_id"] = workspace_id
        if tenant_role:
            payload["tenant_role"] = tenant_role
        if workspace_role:
            payload["workspace_role"] = workspace_role
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def decode_token(self, token: str) -> Dict[str, any]:
        """Decode and validate JWT token.
        
        Args:
            token: JWT token string.
            
        Returns:
            Decoded token payload.
            
        Raises:
            UnauthorizedError: If token is invalid or expired.
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True},
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise UnauthorizedError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise UnauthorizedError(f"Invalid token: {str(e)}")
    
    def extract_user_id(self, token: str) -> str:
        """Extract user ID from token.
        
        Args:
            token: JWT token string.
            
        Returns:
            User ID.
            
        Raises:
            UnauthorizedError: If token is invalid.
        """
        payload = self.decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedError("Token missing user ID")
        return str(user_id)
    
    def extract_tenant_id(self, token: str) -> str:
        """Extract tenant ID from token.
        
        Args:
            token: JWT token string.
            
        Returns:
            Tenant ID.
            
        Raises:
            UnauthorizedError: If token is invalid.
        """
        payload = self.decode_token(token)
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise UnauthorizedError("Token missing tenant ID")
        return str(tenant_id)
