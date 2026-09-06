import base64
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from myai.studio import preprocess_image


class StudioImageTests(unittest.TestCase):
    def data_url(self, size=(900, 500), image_format="PNG"):
        stream = io.BytesIO()
        Image.new("RGB", size, (10, 20, 30)).save(stream, format=image_format)
        encoded = base64.b64encode(stream.getvalue()).decode("ascii")
        mime = "jpeg" if image_format == "JPEG" else image_format.lower()
        return f"data:image/{mime};base64,{encoded}"

    def test_preprocess_crops_to_diffusion_size(self):
        with tempfile.TemporaryDirectory() as directory:
            result = preprocess_image(self.data_url(), Path(directory) / "source.png", 512)
            self.assertEqual((result["normalized_width"], result["normalized_height"]), (512, 512))
            with Image.open(result["path"]) as image:
                self.assertEqual(image.size, (512, 512))

    def test_rejects_invalid_image(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                preprocess_image("data:image/png;base64,ZmFrZQ==", Path(directory) / "source.png")


if __name__ == "__main__":
    unittest.main()
