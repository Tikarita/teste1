from pathlib import Path

import pytest

# Roda o classificador de verdade: só faz sentido onde a IA está instalada
# (requirements.txt) e os pesos foram copiados para app/ml/.
pytest.importorskip("torch")

from app.services import efficientnet_service  # noqa: E402


REPO_DIR = Path(__file__).resolve().parents[2]
SAMPLE_IMAGES = sorted((REPO_DIR / "dados" / "images" / "test").glob("*.jpg"))[:3]

pytestmark = pytest.mark.skipif(
    not efficientnet_service.WEIGHTS_PATH.exists() or not SAMPLE_IMAGES,
    reason="pesos do EfficientNet ou imagens de exemplo ausentes"
)


@pytest.mark.parametrize("image_path", SAMPLE_IMAGES, ids=lambda path: path.name)
def test_explanation_is_a_normalized_grid_for_the_predicted_class(image_path):
    result = efficientnet_service.classify_adequacy(image_path.read_bytes())
    explanation = result["explanation"]

    assert explanation["method"] == "grad-cam"
    assert explanation["target_class"] == result["label"]

    grid = explanation["grid"]
    cells = [value for row in grid for value in row]
    assert len(grid) == 16 and all(len(row) == 16 for row in grid)
    assert all(0 <= value <= 1 for value in cells)
    assert max(cells) == 1.0


def test_explanation_does_not_change_the_classification():
    image_bytes = SAMPLE_IMAGES[0].read_bytes()

    first = efficientnet_service.classify_adequacy(image_bytes)
    second = efficientnet_service.classify_adequacy(image_bytes)

    assert first == second
