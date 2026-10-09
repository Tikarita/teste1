from pathlib import Path

from app.core.config import settings


def ensure_model_file(path: Path) -> Path:
    """
    Garante que o arquivo de pesos existe no disco. Os .pt ficam fora do Git;
    em produção são baixados, na primeira análise, do bucket privado de
    modelos no Supabase Storage (settings.MODELS_BUCKET), onde cada arquivo
    tem o mesmo nome do arquivo local.
    """
    if path.exists():
        return path

    # Import tardio: quem só usa os modelos locais não precisa do cliente.
    from app.services.supabase_service import supabase

    try:
        content = supabase.storage.from_(settings.MODELS_BUCKET).download(path.name)
    except Exception as error:
        raise FileNotFoundError(
            f"Pesos do modelo não encontrados em {path} nem no bucket "
            f"'{settings.MODELS_BUCKET}' do Supabase ({error})."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    # Grava num temporário e renomeia: um download interrompido não deixa um
    # arquivo pela metade com o nome final.
    partial = path.with_suffix(path.suffix + ".baixando")
    partial.write_bytes(content)
    partial.replace(path)

    return path
