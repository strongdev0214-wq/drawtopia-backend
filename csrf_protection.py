"""
CSRF protection utilities for FastAPI
"""
from fastapi import HTTPException, Header, Request
from typing import Optional
import secrets
import time
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import os
import logging

logger = logging.getLogger(__name__)

# CSRF token settings
CSRF_SECRET_KEY = os.getenv("CSRF_SECRET_KEY", secrets.token_urlsafe(32))
CSRF_TOKEN_EXPIRY = 3600  # 1 hour in seconds

# Token serializer
serializer = URLSafeTimedSerializer(CSRF_SECRET_KEY)

def generate_csrf_token() -> str:
    """
    Generate a new CSRF token
    
    Returns:
        CSRF token string
    """
    token_data = {
        "timestamp": time.time(),
        "random": secrets.token_urlsafe(16)
    }
    return serializer.dumps(token_data)


def validate_csrf_token(token: str) -> bool:
    """
    Validate a CSRF token
    
    Args:
        token: CSRF token to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        serializer.loads(token, max_age=CSRF_TOKEN_EXPIRY)
        return True
    except (BadSignature, SignatureExpired) as e:
        logger.warning(f"Invalid CSRF token: {e}")
        return False


async def verify_csrf_token(
    request: Request,
    x_csrf_token: Optional[str] = Header(None)
):
    """
    Dependency to verify CSRF token in requests
    
    Args:
        request: FastAPI request object
        x_csrf_token: CSRF token from header
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    # Skip CSRF for GET, HEAD, OPTIONS (safe methods)
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return
    
    if not x_csrf_token:
        raise HTTPException(
            status_code=403,
            detail="CSRF token missing"
        )
    
    if not validate_csrf_token(x_csrf_token):
        raise HTTPException(
            status_code=403,
            detail="Invalid or expired CSRF token"
        )
    
    return True


class CSRFProtection:
    """
    CSRF Protection middleware
    """
    
    def __init__(self, exempt_paths: Optional[list] = None):
        """
        Initialize CSRF protection
        
        Args:
            exempt_paths: List of paths to exempt from CSRF protection
        """
        self.exempt_paths = exempt_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json"
        ]
    
    def is_exempt(self, path: str) -> bool:
        """Check if path is exempt from CSRF protection"""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)

