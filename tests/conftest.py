"""
Pytest global configuration and environment setup.
"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base

# Ensure test BOT_TOKEN and JWT_SECRET are set prior to importing bot modules
os.environ.setdefault("BOT_TOKEN", "123456789:TestBotTokenMockForPytestSuite")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_key_for_unit_testing_123")


@pytest.fixture
def db():
    """In-memory SQLite session for tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
