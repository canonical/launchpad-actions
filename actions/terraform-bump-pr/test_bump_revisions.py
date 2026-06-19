#!/usr/bin/env python3
"""Unit tests for ``bump_revisions``."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bump_revisions import BumpError, bump_file  # noqa: E402


MAIN_TF = """
resource "juju_application" "my-awesome-app" {
  name  = "my-awesome-app"
  model = juju_model.this.name

  charm {
    name     = "commitment-tracker"
    channel  = "latest/beta"
    revision = 27
  }

  resources = {
    app-image = 45 # comment
  }
}
"""


class BumpTerraformTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tf = Path(self._tmp.name) / "main.tf"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, content: str) -> Path:
        self.tf.write_text(content, encoding="utf-8")
        return self.tf

    def test_successful_bump_preserves_formatting_and_comments(self) -> None:
        path = self._write(MAIN_TF)
        changed = bump_file(path, "my-awesome-app", charm_revision=30, resource_revision=50)
        self.assertTrue(changed)

        result = path.read_text(encoding="utf-8")
        self.assertIn("revision = 30", result)
        # The inline comment and surrounding formatting must be preserved.
        self.assertIn("app-image = 50 # comment", result)
        # Only the two numbers changed; nothing else is touched.
        self.assertEqual(result, MAIN_TF.replace("revision = 27", "revision = 30")
                         .replace("app-image = 45", "app-image = 50"))

    def test_no_changes_when_values_match(self) -> None:
        path = self._write(MAIN_TF)
        changed = bump_file(path, "my-awesome-app", charm_revision=27, resource_revision=45)
        self.assertFalse(changed)
        self.assertEqual(path.read_text(encoding="utf-8"), MAIN_TF)

    def test_minimal_block_without_comments(self) -> None:
        content = (
            '\nresource "juju_application" "another-app" {\n'
            "  charm {\n    revision = 27\n  }\n"
            "  resources = {\n    app-image = 45\n  }\n}\n"
        )
        path = self._write(content)
        self.assertTrue(bump_file(path, "another-app", charm_revision=99, resource_revision=7))
        result = path.read_text(encoding="utf-8")
        self.assertIn("revision = 99", result)
        self.assertIn("app-image = 7", result)

    def test_only_targeted_app_is_changed(self) -> None:
        content = (
            '\nresource "juju_application" "other" {\n'
            "  charm {\n    revision = 27\n  }\n"
            "  resources = {\n    app-image = 45\n  }\n}\n"
            + MAIN_TF
        )
        path = self._write(content)
        self.assertTrue(bump_file(path, "my-awesome-app", charm_revision=30, resource_revision=50))
        result = path.read_text(encoding="utf-8")
        # The non-targeted "other" application keeps its original revisions.
        self.assertIn('resource "juju_application" "other" {\n  charm {\n    revision = 27', result)
        self.assertIn("revision = 30", result)
        self.assertIn("app-image = 50 # comment", result)

    def test_quoted_map_key(self) -> None:
        content = (
            '\nresource "juju_application" "q" {\n'
            "  charm {\n    revision = 1\n  }\n"
            '  resources = {\n    "app-image" = 2\n  }\n}\n'
        )
        path = self._write(content)
        self.assertTrue(bump_file(path, "q", charm_revision=10, resource_revision=20))
        result = path.read_text(encoding="utf-8")
        self.assertIn("revision = 10", result)
        self.assertIn('"app-image" = 20', result)

    def test_crlf_line_endings_preserved(self) -> None:
        content = MAIN_TF.replace("\n", "\r\n")
        # Write raw bytes so the CRLF endings are not translated on write.
        self.tf.write_bytes(content.encode("utf-8"))
        self.assertTrue(bump_file(self.tf, "my-awesome-app", charm_revision=30, resource_revision=50))
        raw = self.tf.read_bytes()
        self.assertIn(b"\r\n", raw)
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))  # no bare LF remains
        self.assertIn("revision = 30", raw.decode("utf-8"))
        self.assertIn("app-image = 50 # comment", raw.decode("utf-8"))

    def test_missing_resource_raises(self) -> None:
        content = (
            '\nresource "juju_application" "another-app" {\n'
            "  charm {\n    revision = 27\n  }\n"
            "  resources = {\n    app-image = 45\n  }\n}\n"
        )
        path = self._write(content)
        with self.assertRaises(BumpError) as ctx:
            bump_file(path, "my-awesome-app", charm_revision=1, resource_revision=1)
        self.assertIn("charm revision", str(ctx.exception))
        self.assertIn("resource revision (app-image)", str(ctx.exception))

    def test_missing_charm_revision_only(self) -> None:
        content = (
            '\nresource "juju_application" "app" {\n'
            "  charm {\n    name = \"x\"\n  }\n"
            "  resources = {\n    app-image = 45\n  }\n}\n"
        )
        path = self._write(content)
        with self.assertRaises(BumpError) as ctx:
            bump_file(path, "app", charm_revision=1, resource_revision=1)
        self.assertIn("charm revision", str(ctx.exception))
        self.assertNotIn("resource revision", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
