from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb


pytestmark = pytest.mark.usefixtures("reports_on_database")

URL = "/api/v1/reports/pre"


def yolo(*class_codes: str, available: bool = True) -> dict:
    return {"yolo": {
        "model": "detector-de-teste",
        "available": available,
        "findings": [
            {"class_code": code, "confidence": 0.5 + i / 100, "bbox": {"x": 0.1 * i, "y": 0.2, "width": 0.05, "height": 0.05}}
            for i, code in enumerate(class_codes)
        ]
    }}


@pytest.fixture
def exam(seed, db):
    """Clínica com um exame de 5 achados (OBT, CAR, OBT, END, OBT), código de paciente e revisão."""
    clinic = seed.clinic("Clínica A")
    dentist = seed.profile(clinic, "Dra. Ana")
    analysis = seed.analysis(clinic, 82, professional_id=dentist, result=yolo("OBT", "CAR", "OBT", "END", "OBT"))
    radiograph = str(db.execute("select radiograph_id from analyses where id = %s", (analysis,)).fetchone()["radiograph_id"])
    db.execute("update radiographs set patient_code = 'PRONT-0042' where id = %s", (radiograph,))
    db.execute("select record_review(%s, %s, %s, 'adequate', false, '{}'::text[], null)", (radiograph, clinic, dentist))

    def validate(decisions: dict[int, str]):
        db.execute(
            "select * from record_finding_validations(%s, %s, %s, %s)",
            (radiograph, clinic, dentist, Jsonb([{"finding_index": i, "decision": d} for i, d in decisions.items()]))
        )

    return {"clinic": clinic, "dentist": dentist, "radiograph": radiograph, "validate": validate}


def test_pre_report_contains_only_confirmed_findings(client, login, exam):
    exam["validate"]({0: "confirmed", 1: "discarded", 2: "confirmed", 3: "confirmed", 4: "discarded"})
    login(exam["clinic"], exam["dentist"])

    response = client.post(URL, json={"radiograph_id": exam["radiograph"], "notes": "  Avaliar o 36.  "})

    assert response.status_code == 201
    report = response.json()
    data = report["data"]

    assert report["title"] == "Pré-laudo — PRONT-0042"
    assert report["notes"] == "Avaliar o 36."
    assert report["radiograph_id"] == exam["radiograph"]
    assert report["issued_by_name"] == "Usuária de Teste"

    assert [(f["number"], f["class_code"], f["label"], f["validated_by_name"]) for f in data["findings"]] == [
        (1, "OBT", "Obturação", "Dra. Ana"),
        (2, "OBT", "Obturação", "Dra. Ana"),
        (3, "END", "Tratamento Endodôntico", "Dra. Ana"),
    ]
    assert data["findings"][1]["bbox"]["x"] == 0.2
    assert data["groups"] == [
        {"class_code": "OBT", "label": "Obturação", "count": 2, "numbers": [1, 2]},
        {"class_code": "END", "label": "Tratamento Endodôntico", "count": 1, "numbers": [3]},
    ]
    assert (data["detected_count"], data["discarded_count"]) == (5, 2)

    assert data["exam"]["patient_code"] == "PRONT-0042"
    assert data["exam"]["professional_name"] == "Dra. Ana"
    assert data["quality"] == {
        "ai_is_adequate": True, "ai_score": 82.0, "model_version": "modelo-de-teste",
        "review_verdict": "adequate", "review_by": "Dra. Ana", "review_reasons": []
    }
    # Sem nada informado na emissão, o documento declara o padrão e deixa o resto em branco.
    assert data["referral"] == {
        "exam_type": "Radiografia panorâmica", "requested_by": None, "clinical_indication": None
    }
    assert data["impression"] is None and data["exam_metadata"] is None
    assert data["detector_model"] == "detector-de-teste"
    assert any("Não é laudo" in line for line in data["disclaimer"])


def test_pre_report_requires_every_finding_to_be_validated(client, login, exam, db):
    exam["validate"]({0: "confirmed", 1: "discarded"})
    login(exam["clinic"], exam["dentist"])

    response = client.post(URL, json={"radiograph_id": exam["radiograph"]})

    assert response.status_code == 400
    assert "Faltam 3 achado(s)" in response.json()["detail"]
    assert db.execute("select count(*) as n from reports").fetchone()["n"] == 0


def test_pre_report_with_everything_discarded_is_valid_and_empty(client, login, exam):
    exam["validate"]({i: "discarded" for i in range(5)})
    login(exam["clinic"], exam["dentist"])

    data = client.post(URL, json={"radiograph_id": exam["radiograph"]}).json()["data"]

    assert (data["findings"], data["groups"], data["discarded_count"]) == ([], [], 5)


def test_issued_pre_report_is_frozen(client, login, exam):
    exam["validate"]({i: "confirmed" for i in range(5)})
    login(exam["clinic"], exam["dentist"])
    issued = client.post(URL, json={"radiograph_id": exam["radiograph"]}).json()

    exam["validate"]({0: "discarded", 1: "discarded"})

    reopened = client.get(f"{URL}/{issued['id']}").json()
    newer = client.post(URL, json={"radiograph_id": exam["radiograph"]}).json()
    listing = client.get(URL, params={"radiograph_id": exam["radiograph"]}).json()

    assert reopened["data"] == issued["data"]
    assert len(reopened["data"]["findings"]) == 5
    assert len(newer["data"]["findings"]) == 3
    assert [item["id"] for item in listing] == [newer["id"], issued["id"]]


def test_exam_without_detection_has_no_pre_report(client, login, seed, db):
    clinic = seed.clinic()
    dentist = seed.profile(clinic)
    not_analyzed = seed.radiograph(clinic)
    old_analysis = seed.analysis(clinic, 80, result=yolo("OBT", available=False))
    old_radiograph = str(db.execute("select radiograph_id from analyses where id = %s", (old_analysis,)).fetchone()["radiograph_id"])
    login(clinic, dentist)

    assert client.post(URL, json={"radiograph_id": not_analyzed}).status_code == 400
    assert client.post(URL, json={"radiograph_id": old_radiograph}).status_code == 400


def test_pre_reports_are_isolated_by_clinic(client, login, exam, seed):
    exam["validate"]({i: "confirmed" for i in range(5)})
    login(exam["clinic"], exam["dentist"])
    issued = client.post(URL, json={"radiograph_id": exam["radiograph"]}).json()

    clinic_b = seed.clinic("Clínica B")
    user_b = seed.profile(clinic_b)
    login(clinic_b, user_b)

    assert client.post(URL, json={"radiograph_id": exam["radiograph"]}).status_code == 404
    assert client.get(f"{URL}/{issued['id']}").status_code == 404
    assert client.get(URL, params={"radiograph_id": exam["radiograph"]}).json() == []


def test_pre_reports_and_quality_reports_do_not_mix(client, login, exam):
    exam["validate"]({i: "confirmed" for i in range(5)})
    login(exam["clinic"], exam["dentist"], "admin")
    pre = client.post(URL, json={"radiograph_id": exam["radiograph"]}).json()

    assert client.get("/api/v1/reports/quality").json() == []
    assert client.get(f"/api/v1/reports/quality/{pre['id']}").status_code == 404


def test_pre_report_routes_require_authentication(client):
    assert client.post(URL, json={"radiograph_id": str(uuid4())}).status_code == 401
    assert client.get(URL, params={"radiograph_id": str(uuid4())}).status_code == 401
    assert client.get(f"{URL}/{uuid4()}").status_code == 401


def test_pre_report_carries_what_the_dentist_informs_and_the_technical_data(client, login, exam, db):
    exam["validate"]({i: "confirmed" for i in range(5)})
    db.execute(
        "update radiographs set exam_metadata = %s where id = %s",
        (Jsonb({"source_format": "dicom", "manufacturer": "Fabricante X", "kvp": 70}), exam["radiograph"])
    )
    login(exam["clinic"], exam["dentist"])

    report = client.post(URL, json={
        "radiograph_id": exam["radiograph"],
        "exam_type": "  Radiografia panorâmica digital ",
        "requested_by": " Dr. Carlos (CRO 1234) ",
        "clinical_indication": " Avaliação pré-ortodôntica. ",
        "impression": " Sem alterações relevantes além das restaurações descritas. ",
        "notes": "   "
    }).json()
    data = report["data"]

    assert data["referral"] == {
        "exam_type": "Radiografia panorâmica digital",
        "requested_by": "Dr. Carlos (CRO 1234)",
        "clinical_indication": "Avaliação pré-ortodôntica."
    }
    assert data["impression"] == "Sem alterações relevantes além das restaurações descritas."
    assert data["exam_metadata"] == {"source_format": "dicom", "manufacturer": "Fabricante X", "kvp": 70}
    assert report["notes"] is None


def test_pre_reports_issued_before_the_standard_structure_still_open(client, login, exam, db):
    exam["validate"]({i: "confirmed" for i in range(5)})
    login(exam["clinic"], exam["dentist"])
    issued = client.post(URL, json={"radiograph_id": exam["radiograph"]}).json()

    # Formato antigo: sem referral, impression, exam_metadata e review_reasons.
    db.execute(
        "update reports set data = (data - 'referral' - 'impression' - 'exam_metadata') "
        "#- '{quality,review_reasons}' where id = %s",
        (issued["id"],)
    )

    reopened = client.get(f"{URL}/{issued['id']}")

    assert reopened.status_code == 200
    assert reopened.json()["data"]["referral"]["exam_type"] == "Radiografia panorâmica"
    assert reopened.json()["data"]["impression"] is None
