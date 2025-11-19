"""
Database models and session management for OAuth tokens.
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import uuid

try:
    from ..config.settings import settings
    from ..utils.logger import logger
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from config.settings import settings
    from utils.logger import logger

Base = declarative_base()


class FacebookToken(Base):
    """Model for storing Facebook OAuth tokens."""
    __tablename__ = "facebook_tokens"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True)  # App user ID (if you have user system)
    fb_user_id = Column(String(64), nullable=False)
    encrypted_access_token = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    permissions = Column(JSON, nullable=True)  # List of granted permissions
    accounts = Column(JSON, nullable=True)  # Array of {id, name, role}
    revoked = Column(Boolean, default=False)
    last_refreshed = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class OAuthState(Base):
    """Model for storing OAuth state tokens (CSRF protection)."""
    __tablename__ = "oauth_states"
    
    state = Column(String(128), primary_key=True)
    user_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)


# Database setup
_engine = None
_SessionLocal = None


def init_database() -> None:
    """Initialize database connection and create tables."""
    global _engine, _SessionLocal

    if _engine is not None:
        return

    database_url = settings.database_url

    try:
        # Ensure directory exists for SQLite
        if database_url.startswith("sqlite"):
            db_path = database_url.replace("sqlite:///", "")
            db_dir = Path(db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,   # Recycle connections after 1 hour
        )

        # Test connection
        from sqlalchemy import text
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Create tables
        Base.metadata.create_all(bind=_engine)

        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,  # keep attributes accessible after commit
            bind=_engine,
        )

        logger.info(f"Database initialized successfully: {database_url}")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.error(f"Database URL: {database_url[:50]}...")  # Log partial URL for debugging
        raise  # Re-raise to make the error visible


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    if _SessionLocal is None:
        init_database()
    
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """Get a database session (non-generator version for direct use)."""
    if _SessionLocal is None:
        init_database()
    
    return _SessionLocal()


def reset_database() -> bool:
    """
    Drop all tables and recreate them (clears all data).
    
    WARNING: This will delete all stored OAuth tokens!
    
    Returns:
        True if successful
    """
    global _engine, _SessionLocal
    
    try:
        if _engine is None:
            init_database()
        
        # Drop all tables
        Base.metadata.drop_all(bind=_engine)
        logger.warning("Dropped all database tables")
        
        # Recreate tables
        Base.metadata.create_all(bind=_engine)
        logger.info("Recreated database tables")
        
        return True
    except Exception as e:
        logger.error(f"Failed to reset database: {e}")
        return False


def clear_oauth_tokens() -> int:
    """
    Clear all OAuth tokens from the database (keeps tables).
    
    Returns:
        Number of tokens deleted
    """
    db = get_db_session()
    try:
        count = db.query(FacebookToken).count()
        db.query(FacebookToken).delete()
        db.query(OAuthState).delete()  # Also clear expired states
        db.commit()
        logger.info(f"Cleared {count} OAuth tokens from database")
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear tokens: {e}")
        return 0
    finally:
        db.close()
