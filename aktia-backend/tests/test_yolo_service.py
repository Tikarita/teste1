from pathlib import Path

import pytest

# Roda o detector de verdade: só faz sentido onde a IA está instalada
# (requirements.txt) e os pesos foram copiados para app/ml/.
pytest.importorskip("ultralytics")

from app.services import analysis_service, yolo_service  # noqa: E402


REPO_DIR = Path(__file__).resolve().parents[2]
SAMPLE_IMAGES = sorted((REPO_DIR / "dados" / "images" / "test").glob("*.jpg"))[:3]

pytestmark = pytest.mark.skipif(
    not yolo_service.WEIGHTS_PATH.exists() or not SAMPLE_IMAGES,
    reason="pesos do YOLO ou imagens de exemplo ausentes"
)


def test_model_classes_match_the_labels_shown_to_the_user():
    names = yolo_service._get_model().names

    assert set(names.values()) == set(analysis_service.CLASS_LABELS)
    assert analysis_service.LOW_RELIABILITY_CLASSES <= set(names.values())


@pytest.mark.parametrize("image_path", SAMPLE_IMAGES, ids=lambda path: path.name)
def test_detection_result_shape(image_path):
    result = analysis_service.run_yolo_detection(image_path.read_bytes())

    assert result["available"] is True
    assert result["model"] == yolo_service.MODEL_NAME

    confidences = [finding["confidence"] for finding in result["findings"]]
    assert confidences == sorted(confidences, reverse=True)

    for finding in result["findings"]:
        assert finding["label"] == analysis_service.CLASS_LABELS[finding["class_code"]]
        assert finding["low_reliability"] == (
            finding["class_code"] in analysis_service.LOW_RELIABILITY_CLASSES
        )
        assert yolo_service.CONFIDENCE_THRESHOLD <= finding["confidence"] <= 1

        box = finding["bbox"]
        assert 0 <= box["x"] <= 1 and 0 <= box["y"] <= 1
        assert box["width"] > 0 and box["height"] > 0
        assert box["x"] + box["width"] <= 1.001
        assert box["y"] + box["height"] <= 1.001
