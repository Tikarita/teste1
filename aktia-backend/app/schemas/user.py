from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):

    clinic_id: UUID

    name: str = Field(
        min_length=2,
        max_length=150
    )

    email: EmailStr

    role: str = Field(
        default="user"
    )