from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel

from app.services.supabase_service import execute_with_retry, supabase


INADEQUATE_EXAM = "inadequate_exam"
MAX_LISTED = 30


class Notification(BaseModel):
    id: UUID
    kind: str
    title: str
    message: str
    radiograph_id: UUID | None
    created_at: datetime
    read_at: datetime | None


class NotificationList(BaseModel):
    unread_count: int
    items: list[Notification]


def _insert_notifications(rows: list[dict]) -> None:
    # Já existe aviso deste exame para a pessoa (reanálise): mantém o original.
    supabase.table("notifications").upsert(
        rows,
        on_conflict="radiograph_id,recipient_id,kind",
        ignore_duplicates=True
    ).execute()


def _select_notifications(recipient_id: str, clinic_id: str) -> list[dict]:
    return execute_with_retry(
        supabase
        .table("notifications")
        .select("*")
        .eq("recipient_id", str(recipient_id))
        .eq("clinic_id", str(clinic_id))
        .order("created_at", desc=True)
        .limit(MAX_LISTED)
    ).data or []


def _mark_read(notification_id: str, recipient_id: str) -> list[dict]:
    return (
        supabase
        .table("notifications")
        .update({"read_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", str(notification_id))
        .eq("recipient_id", str(recipient_id))
        .is_("read_at", "null")
        .execute()
    ).data or []


def notify_inadequate_exam(radiograph: dict, quality: dict, current: dict) -> None:
    """
    Avisa em tempo real que a IA classificou o exame como inadequado. Vai para
    o profissional responsável pela captura e para quem pediu a análise, que
    costuma ser quem está com o paciente.

    A IA erra (marca como inadequada cerca de 1 em cada 8 imagens boas), então
    o texto pede para conferir a imagem antes de refazer: repetir uma
    radiografia sem necessidade é exposição à radiação à toa.
    """
    recipients = {
        str(person) for person in (radiograph.get("professional_id"), current["profile"]["id"]) if person
    }

    _insert_notifications([
        {
            "clinic_id": str(current["clinic"]["id"]),
            "recipient_id": recipient,
            "radiograph_id": str(radiograph["id"]),
            "kind": INADEQUATE_EXAM,
            "title": "Exame inadequado: refaça o exame",
            "message": (
                f"A IA classificou a radiografia {radiograph['file_name']} como inadequada para diagnóstico "
                f"(probabilidade de adequação: {quality['score']}/100). Confira a imagem e refaça o exame "
                "enquanto o paciente está na clínica."
            )
        }
        for recipient in sorted(recipients)
    ])


def list_for(current: dict) -> NotificationList:
    rows = _select_notifications(current["profile"]["id"], current["clinic"]["id"])

    return NotificationList(
        unread_count=sum(1 for row in rows if row.get("read_at") is None),
        items=rows
    )


def mark_read(notification_id: UUID, current: dict) -> None:
    """Marca o aviso como lido ("ciente"). Só o destinatário consegue."""
    recipient_id = str(current["profile"]["id"])

    if _mark_read(str(notification_id), recipient_id):
        return

    # Nada atualizado: ou já estava lido, ou não é um aviso desta pessoa.
    own = {str(row["id"]) for row in _select_notifications(recipient_id, current["clinic"]["id"])}
    if str(notification_id) not in own:
        raise HTTPException(
            status_code=404,
            detail="Aviso não encontrado"
        )
