from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.auth import ClinicRegister, LoginRequest, RefreshRequest
from app.services.supabase_service import create_auth_client, supabase


router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

bearer_scheme = HTTPBearer(auto_error=False)


def _session_payload(session, profile: dict, clinic: dict) -> dict:
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at,
        "user": profile,
        "clinic": clinic
    }


def _load_profile(user_id: str) -> dict:
    response = (
        supabase
        .table("profiles")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=403,
            detail="Conta sem perfil vinculado a uma clínica. Fale com o administrador."
        )

    return response.data[0]


def _load_clinic(clinic_id: str) -> dict:
    response = (
        supabase
        .table("clinics")
        .select("*")
        .eq("id", clinic_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Clínica vinculada à conta não foi encontrada."
        )

    return response.data[0]


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """
    Valida o access token do Supabase e devolve o perfil + a clínica do usuário.
    Use como dependência nas rotas que precisam de um usuário autenticado.
    """

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária."
        )

    try:
        auth_client = create_auth_client()
        user_response = auth_client.auth.get_user(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Sessão inválida ou expirada."
        )

    if user_response is None or user_response.user is None:
        raise HTTPException(
            status_code=401,
            detail="Sessão inválida ou expirada."
        )

    profile = _load_profile(user_response.user.id)
    clinic = _load_clinic(profile["clinic_id"])

    return {
        "profile": profile,
        "clinic": clinic
    }


@router.post("/register", status_code=201)
def register_clinic(payload: ClinicRegister):
    """
    Cadastra uma clínica e a conta de administrador dela em uma única
    operação: cria a linha em `clinics`, o usuário no Supabase Auth e o
    `profiles` que liga os dois. Se qualquer etapa falhar, o que já foi
    criado é desfeito para não deixar clínica órfã ou usuário sem perfil.
    """

    existing_cnpj = (
        supabase
        .table("clinics")
        .select("id")
        .eq("cnpj", payload.cnpj)
        .limit(1)
        .execute()
    )

    if existing_cnpj.data:
        raise HTTPException(
            status_code=409,
            detail="Já existe uma clínica cadastrada com este CNPJ."
        )

    try:
        clinic_response = (
            supabase
            .table("clinics")
            .insert({
                "name": payload.clinic_name,
                "cnpj": payload.cnpj,
                "email": payload.email
            })
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    clinic = clinic_response.data[0]
    clinic_id = clinic["id"]

    user_id = None

    try:
        auth_response = supabase.auth.admin.create_user({
            "email": payload.email,
            "password": payload.password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": payload.admin_name,
                "clinic_id": str(clinic_id),
                "role": "admin"
            }
        })
        user_id = auth_response.user.id

        supabase.table("profiles").upsert({
            "id": user_id,
            "clinic_id": str(clinic_id),
            "full_name": payload.admin_name,
            "email": payload.email,
            "role": "admin"
        }).execute()

    except Exception as error:
        if user_id:
            try:
                supabase.auth.admin.delete_user(user_id)
            except Exception:
                pass

        try:
            supabase.table("clinics").delete().eq("id", clinic_id).execute()
        except Exception:
            pass

        message = str(error)
        already_registered = (
            "already been registered" in message
            or "already exists" in message
            or "already registered" in message
        )

        raise HTTPException(
            status_code=409 if already_registered else 500,
            detail=(
                "Este e-mail já está em uso por outra conta."
                if already_registered
                else message
            )
        )

    try:
        auth_client = create_auth_client()
        sign_in = auth_client.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    profile = _load_profile(user_id)

    return _session_payload(sign_in.session, profile, clinic)


@router.post("/login")
def login(payload: LoginRequest):

    try:
        auth_client = create_auth_client()
        sign_in = auth_client.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="E-mail ou senha inválidos."
        )

    if sign_in.session is None or sign_in.user is None:
        raise HTTPException(
            status_code=401,
            detail="E-mail ou senha inválidos."
        )

    profile = _load_profile(sign_in.user.id)
    clinic = _load_clinic(profile["clinic_id"])

    return _session_payload(sign_in.session, profile, clinic)


@router.post("/refresh")
def refresh(payload: RefreshRequest):

    try:
        auth_client = create_auth_client()
        refreshed = auth_client.auth.refresh_session(payload.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Sessão expirada. Faça login novamente."
        )

    if refreshed.session is None or refreshed.user is None:
        raise HTTPException(
            status_code=401,
            detail="Sessão expirada. Faça login novamente."
        )

    profile = _load_profile(refreshed.user.id)
    clinic = _load_clinic(profile["clinic_id"])

    return _session_payload(refreshed.session, profile, clinic)


@router.get("/me")
def me(current=Depends(get_current_user)):
    return {
        "user": current["profile"],
        "clinic": current["clinic"]
    }


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    """
    Invalida o refresh token no Supabase. O front descarta a sessão local de
    qualquer forma, então uma falha aqui não impede o logout.
    """

    if credentials is not None:
        try:
            auth_client = create_auth_client()
            auth_client.auth.admin.sign_out(credentials.credentials)
        except Exception:
            pass

    return {"message": "Sessão encerrada"}
