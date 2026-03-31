import uuid
import secrets
from typing import Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# HTTP Bearer token认证
security = HTTPBearer(auto_error=False)

class APIKeyManager:
    def __init__(self):
        """
        Initialize the APIKeyManager.
        By default, authentication is disabled.
        """
        self._api_key: Optional[str] = None
        self._auth_enabled = False
    
    def set_api_key(self, api_key: Optional[str]):
        """
        Set the API key for authentication.
        If the key is None, disable authentication.
        """
        self._api_key = api_key
        self._auth_enabled = api_key is not None
    
    def generate_api_key(self) -> str:
        """
        Generate a new API key.
        The key is a random UUID prefixed with "sk-" and suffixed with "-localhost".
        """
        guid = str(uuid.uuid4())
        return f"sk-{guid}-localhost"
    
    def verify_api_key(self, provided_key: Optional[str]) -> bool:
        """
        Verify the provided API key against the stored key.
        If authentication is not enabled, always return True.
        If the key is None, return False.
        Otherwise, use secrets.compare_digest for secure comparison.
        """
        if not self._auth_enabled:
            return True  # 认证未启用，允许访问
        
        if not provided_key:
            return False
        
        # 使用secrets.compare_digest防止时序攻击
        return secrets.compare_digest(provided_key, self._api_key)

# 全局API密钥管理器实例
api_key_manager = APIKeyManager()

def get_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> Optional[str]:
    """
    Extract the API key from the Authorization header.
    If the header is missing or invalid, return None.
    """
    if credentials:
        return credentials.credentials
    return None

def verify_api_key_dependency(api_key: Optional[str] = Depends(get_api_key)):
    """
    Verify the provided API key.
    If the key is invalid or missing, raise an HTTPException with status code 401.
    """
    if not api_key_manager.verify_api_key(api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Expected format: Bearer YOUR_API_KEY",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key