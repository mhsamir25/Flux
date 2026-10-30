import uuid

from fastapi_users import schemas


# Schema for reading a user (used in responses)
class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


# Schema for creating a user (used during registration)
class UserCreate(schemas.BaseUserCreate):
    pass


# Schema for updating a user (used when modifying profile)
class UserUpdate(schemas.BaseUserUpdate):
    pass
