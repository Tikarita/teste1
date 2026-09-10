from pydantic import BaseModel, EmailStr, Field


class ClinicRegister(BaseModel):
    """Cadastro de uma clínica junto com a conta do seu administrador."""

    clinic_name: str = Field(
        min_length=2,
        max_length=150
    )

    cnpj: str = Field(
        min_length=14,
        max_length=18
    )

    admin_name: str = Field(
        min_length=2,
        max_length=150
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=72
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
