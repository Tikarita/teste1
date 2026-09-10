import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client


# A rede corporativa faz inspeção TLS (FortiGate), então o certificado que
# chega do Supabase é reemitido pela CA do firewall. Essa CA está no
# repositório de certificados do Windows, mas o Python usa o bundle do
# `certifi` — daí o "CERTIFICATE_VERIFY_FAILED". O truststore faz o ssl
# padrão consultar o repositório do sistema operacional, resolvendo isso
# sem desligar a verificação de certificado.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        f"SUPABASE_URL ou SUPABASE_KEY não foram configurados. "
        f"Arquivo esperado em: {BASE_DIR / '.env'}"
    )


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


def create_auth_client() -> Client:
    """
    Cliente novo e descartável para operações de autenticação.

    `sign_in_with_password` e `get_user` gravam a sessão do usuário no
    cliente que as executa. Se isso acontecesse no `supabase` global, as
    consultas seguintes passariam a usar o token daquele usuário em vez da
    service key — então cada login/validação usa um cliente próprio.
    """
    return create_client(SUPABASE_URL, SUPABASE_KEY)
