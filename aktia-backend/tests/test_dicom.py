from io import BytesIO

import numpy as np
import pydicom
import pytest
from fastapi import HTTPException
from PIL import Image
from pydicom.data import get_testdata_file

from app.services import dicom_service
from tests.test_upload_professional import clinics, fake_supabase, png  # noqa: F401  (fixtures reaproveitadas)


# Radiografias reais (CR, 16 bits, MONOCHROME1) que acompanham o pydicom.
RADIOGRAPH = get_testdata_file("RG1_UNCR.dcm")
MULTI_FRAME = get_testdata_file("emri_small.dcm")


def dicom_bytes(path: str = RADIOGRAPH) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def test_conversion_produces_an_8_bit_png_of_the_same_size():
    dataset = pydicom.dcmread(RADIOGRAPH)

    png_bytes, metadata = dicom_service.convert(dicom_bytes())

    image = Image.open(BytesIO(png_bytes))
    assert image.format == "PNG" and image.mode == "L"
    assert image.size == (dataset.Columns, dataset.Rows)
    assert (metadata["width"], metadata["height"]) == (dataset.Columns, dataset.Rows)

    pixels = np.asarray(image)
    # A imagem aproveita a faixa de tons, em vez de sair toda escura ou toda clara.
    assert pixels.min() < 30 and pixels.max() > 225 and 40 < pixels.mean() < 215


def test_monochrome1_is_inverted_to_the_usual_convention():
    dataset = pydicom.dcmread(RADIOGRAPH)
    assert dataset.PhotometricInterpretation == "MONOCHROME1"
    raw = dataset.pixel_array.astype(np.float64)

    png_bytes, _ = dicom_service.convert(dicom_bytes())
    converted = np.asarray(Image.open(BytesIO(png_bytes))).astype(np.float64)

    # Em MONOCHROME1 o valor bruto mais alto é o mais escuro: depois da
    # conversão, a relação entre bruto e convertido tem que ser inversa.
    sample = (slice(None, None, 16), slice(None, None, 16))
    correlation = np.corrcoef(raw[sample].ravel(), converted[sample].ravel())[0, 1]
    assert correlation < -0.9


def test_metadata_keeps_technical_fields_and_no_patient_data():
    dataset = pydicom.dcmread(RADIOGRAPH, stop_before_pixels=True)
    patient_values = {
        str(getattr(dataset, field)) for field in ("PatientName", "PatientID", "PatientBirthDate")
        if str(getattr(dataset, field, "") or "")
    }
    assert patient_values, "o arquivo de teste precisa ter dados de paciente para o teste valer"

    _, metadata = dicom_service.convert(dicom_bytes())

    assert metadata["source_format"] == "dicom"
    assert metadata["modality"] == "CR"
    assert not any(key.startswith("patient") for key in metadata)
    assert not patient_values & {str(value) for value in metadata.values()}
    assert metadata["burned_in_annotation"] is False


def test_detection_of_dicom_files():
    content = dicom_bytes()

    assert dicom_service.is_dicom(content, "application/octet-stream", "exame.bin") is True
    assert dicom_service.is_dicom(b"qualquer coisa", "application/dicom", None) is True
    assert dicom_service.is_dicom(b"qualquer coisa", None, "EXAME.DCM") is True
    assert dicom_service.is_dicom(png(), "image/png", "rx.png") is False


@pytest.mark.parametrize("content", [b"", b"isto nao e um dicom" * 20, png()])
def test_invalid_files_are_rejected(content):
    with pytest.raises(HTTPException) as error:
        dicom_service.convert(content)

    assert error.value.status_code == 400


def test_multi_frame_files_are_rejected():
    with pytest.raises(HTTPException) as error:
        dicom_service.convert(dicom_bytes(MULTI_FRAME))

    assert error.value.status_code == 400
    assert "várias imagens" in error.value.detail


# --- envio pela API -------------------------------------------------------------

def test_upload_of_a_dicom_stores_a_png_and_the_technical_metadata(client, login, clinics, fake_supabase):  # noqa: F811
    clinic_a, (user, _) = clinics["a"]
    login(clinic_a, user)

    response = client.post(
        "/api/v1/analysis/upload",
        data={"patient_code": "P-10"},
        files={"file": ("panoramica.dcm", dicom_bytes(), "application/octet-stream")}
    )

    assert response.status_code == 200
    stored = fake_supabase.tables["radiographs"][0]
    assert stored["file_name"] == "panoramica.dcm"
    assert stored["file_type"] == "image/png"
    assert stored["file_path"].endswith(".png")
    assert stored["patient_code"] == "P-10"
    assert stored["exam_metadata"]["modality"] == "CR"

    saved_file = fake_supabase.files[stored["file_path"]]
    assert saved_file[:8] == b"\x89PNG\r\n\x1a\n"
    assert stored["file_size"] == len(saved_file)
    # O DICOM original (com o nome do paciente) não vai para o storage.
    assert b"DICM" not in saved_file[:200]
    assert len(fake_supabase.files) == 1


def test_upload_of_images_is_unchanged_and_has_no_metadata(client, login, clinics, fake_supabase):  # noqa: F811
    clinic_a, (user, _) = clinics["a"]
    login(clinic_a, user)

    response = client.post("/api/v1/analysis/upload", files={"file": ("rx.png", png(), "image/png")})

    assert response.status_code == 200
    stored = fake_supabase.tables["radiographs"][0]
    assert stored["file_type"] == "image/png"
    assert "exam_metadata" not in stored


def test_upload_rejects_unsupported_formats_and_broken_dicoms(client, login, clinics, fake_supabase):  # noqa: F811
    clinic_a, (user, _) = clinics["a"]
    login(clinic_a, user)

    pdf = client.post("/api/v1/analysis/upload", files={"file": ("laudo.pdf", b"%PDF-1.4", "application/pdf")})
    broken = client.post("/api/v1/analysis/upload", files={"file": ("exame.dcm", b"lixo" * 100, "application/dicom")})

    assert pdf.status_code == 400 and "JPG, PNG ou DICOM" in pdf.json()["detail"]
    assert broken.status_code == 400
    assert fake_supabase.tables["radiographs"] == [] and fake_supabase.files == {}


# --- ida e volta: a conversão devolve a mesma imagem que entrou no DICOM ---------

def make_dicom(gray8: np.ndarray, *, inverted: bool = False, rescale: bool = False, window: bool = True) -> bytes:
    """Embrulha uma imagem de 8 bits num DICOM de 12 bits, como os sensores costumam gravar."""
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1.1"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dataset = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.SOPClassUID, dataset.SOPInstanceUID = meta.MediaStorageSOPClassUID, meta.MediaStorageSOPInstanceUID
    dataset.Modality, dataset.PatientName, dataset.PatientID = "PX", "PACIENTE^TESTE", "123.456.789-00"
    dataset.Rows, dataset.Columns = gray8.shape
    dataset.SamplesPerPixel, dataset.PixelRepresentation = 1, 0
    dataset.BitsAllocated, dataset.BitsStored, dataset.HighBit = 16, 12, 11

    pixels = (gray8.astype(np.uint32) * 4095 // 255).astype(np.uint16)
    if inverted:
        pixels = 4095 - pixels
    if rescale:
        pixels = pixels // 2
        dataset.RescaleSlope, dataset.RescaleIntercept = "2", "0"
    if window:
        dataset.WindowCenter, dataset.WindowWidth = "2047.5", "4096"

    dataset.PhotometricInterpretation = "MONOCHROME1" if inverted else "MONOCHROME2"
    dataset.PixelData = pixels.tobytes()

    buffer = BytesIO()
    dataset.save_as(buffer, enforce_file_format=True)
    return buffer.getvalue()


@pytest.mark.parametrize("options", [
    {},
    {"inverted": True},
    {"rescale": True},
    {"inverted": True, "rescale": True},
])
def test_round_trip_preserves_the_image(options):
    rows, columns = np.mgrid[0:120, 0:200]
    original = ((rows * 2 + columns) % 256).astype(np.uint8)

    png_bytes, metadata = dicom_service.convert(make_dicom(original, **options))
    converted = np.asarray(Image.open(BytesIO(png_bytes))).astype(int)

    assert converted.shape == original.shape
    assert np.abs(converted - original.astype(int)).max() <= 2
    assert metadata["modality"] == "PX"
    assert "TESTE" not in str(metadata) and "123.456" not in str(metadata)
