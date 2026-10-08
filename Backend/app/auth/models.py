"""Defines the User ORM table used for authentication.
- Inherits SQLAlchemyBaseUserTableUUID which provides standard auth columns (id, email, hashed_password, etc.).
- Inherits Base from app.db so SQLAlchemy knows the declarative mapping.
- The primary key (UUID) is used by PipelineTemplate.owner_id as a foreign key.
"""
from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from app.db import Base


# User table with built-in auth columns; UUID primary key for cross-database compatibility
class User(SQLAlchemyBaseUserTableUUID, Base):
    pass
