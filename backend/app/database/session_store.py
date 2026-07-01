"""
Session Store - Use MySQL instead of Redis for session caching.
Stores workflow state, tokens, and temporary data.
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, DateTime, Text, select, delete
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession
import json

Base = declarative_base()


class SessionCache(Base):
    """Simple session cache table to replace Redis."""
    __tablename__ = "session_cache"
    
    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SessionStore:
    """MySQL-backed session store (replaces Redis)."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get(self, key: str) -> str | None:
        """Get a value from session store."""
        result = await self.db.execute(
            select(SessionCache).where(SessionCache.key == key)
        )
        session_obj = result.scalar_one_or_none()
        
        if session_obj is None:
            return None
        
        # Check if expired
        if session_obj.expires_at and session_obj.expires_at < datetime.now(timezone.utc):
            await self.db.delete(session_obj)
            await self.db.commit()
            return None
        
        return session_obj.value
    
    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Set a value in session store. ex is expiry in seconds."""
        expires_at = None
        if ex:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ex)
        
        # Delete existing
        await self.db.execute(delete(SessionCache).where(SessionCache.key == key))
        
        session_obj = SessionCache(key=key, value=value, expires_at=expires_at)
        self.db.add(session_obj)
        await self.db.commit()
    
    async def delete(self, key: str) -> None:
        """Delete a key from session store."""
        await self.db.execute(delete(SessionCache).where(SessionCache.key == key))
        await self.db.commit()
    
    async def get_json(self, key: str) -> dict | None:
        """Get and parse JSON from session store."""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None
    
    async def set_json(self, key: str, value: dict, ex: int | None = None) -> None:
        """Set JSON value in session store."""
        await self.set(key, json.dumps(value), ex=ex)
    
    async def cleanup_expired(self) -> None:
        """Clean up expired sessions."""
        await self.db.execute(
            delete(SessionCache).where(
                SessionCache.expires_at < datetime.now(timezone.utc)
            )
        )
        await self.db.commit()
