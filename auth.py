import uuid
import secrets
from typing import Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# HTTP Bearer token认证
security = HTTPBearer(auto_error=False)

class APIKeyManager:
    def __init__(self):
        self._api_key: Optional[str] = None
        self._auth_enabled = False
    
    def set_api_key(self, api_key: Optional[str]):
        self._api_key = api_key
        self._auth_enabled = api_key is not None
    
    def generate_api_key(self) -> str:
        guid = str(uuid.uuid4())
        return f"sk-{guid}-localhost"
    
    def verify_api_key(self, provided_key: Optional[str]) -> bool:
        if not self._auth_enabled:
            return True  # 认证未启用，允许访问
        
        if not provided_key:
            return False
        
        # 使用secrets.compare_digest防止时序攻击
        return secrets.compare_digest(provided_key, self._api_key)

# 全局API密钥管理器实例
api_key_manager = APIKeyManager()

def get_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> Optional[str]:
    if credentials:
        return credentials.credentials
    return None

def verify_api_key_dependency(api_key: Optional[str] = Depends(get_api_key)):
    if not api_key_manager.verify_api_key(api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Expected format: Bearer YOUR_API_KEY",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key