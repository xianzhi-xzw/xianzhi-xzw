import tempfile
import unittest
from pathlib import Path

from generate_language_stats import refresh_readme_images, render_language_svg


class RefreshReadmeImagesTest(unittest.TestCase):
    def test_replaces_missing_and_existing_cache_versions(self):
        content = (
            "![language](./assets/language-stats.svg)\n"
            "![activity](./assets/code-activity.svg?v=old)\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            readme = Path(temp_dir) / "README.md"
            readme.write_text(content, encoding="utf-8")
            refresh_readme_images(readme, "202607301234")
            self.assertEqual(
                readme.read_text(encoding="utf-8"),
                "![language](./assets/language-stats.svg?v=202607301234)\n"
                "![activity](./assets/code-activity.svg?v=202607301234)\n",
            )


class RenderLanguageSvgTest(unittest.TestCase):
    def test_bar_widths_represent_share_of_total_not_share_of_top_language(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "languages.svg"
            render_language_svg({"Python": 40, "C++": 60}, output)
            svg = output.read_text(encoding="utf-8")
            self.assertIn(
                'width="321" height="10" rx="5" fill="#f34b7d"', svg
            )
            self.assertIn(
                'width="214" height="10" rx="5" fill="#3572A5"', svg
            )


if __name__ == "__main__":
    unittest.main()
