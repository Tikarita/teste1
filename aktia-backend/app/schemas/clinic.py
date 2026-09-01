from pydantic import BaseModel, Field


class ClinicCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=150
    )

    cnpj: str = Field(
        min_length=14,
        max_length=18
    )