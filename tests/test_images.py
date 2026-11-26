import numpy as np
from PIL import Image

from promptgen.core.images import load_image_arrays
from promptgen.core.textfiles import list_image_files


def test_load_rgb_and_alpha(tmp_path):
    img = Image.new("RGBA", (2, 1))
    img.putpixel((0, 0), (255, 255, 255, 255))
    img.putpixel((1, 0), (0, 0, 0, 0))
    img.save(tmp_path / "x.png")
    rgb, mask = load_image_arrays(str(tmp_path / "x.png"))
    assert rgb.shape == (1, 2, 3) and rgb.dtype == np.float32
    assert np.allclose(rgb[0, 0], 1.0)
    assert mask.tolist() == [[0.0, 1.0]]


def test_jpeg_has_empty_mask_and_listing(tmp_path):
    Image.new("RGB", (5, 4), (10, 20, 30)).save(tmp_path / "B.jpg")
    Image.new("RGB", (1, 1)).save(tmp_path / "a.webp")
    (tmp_path / "c.txt").write_text("x")
    assert list_image_files(str(tmp_path)) == ["a.webp", "B.jpg"]
    rgb, mask = load_image_arrays(str(tmp_path / "B.jpg"))
    assert rgb.shape == (4, 5, 3) and mask.shape == (4, 5) and not mask.any()
