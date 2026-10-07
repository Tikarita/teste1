from typing import Literal

from pydantic import BaseModel, EmailStr, Field


# Os mesmos valores aceitos pela constraint profiles_role_check do banco.
StaffRole = Literal["admin", "manager", "user"]


class StaffCreate(BaseModel):
    """A clínica não vem no corpo: é sempre a do administrador autenticado."""

    full_name: str = Field(
        min_length=2,
        max_length=150
    )

    email: EmailStr

    role: StaffRole = "user"
