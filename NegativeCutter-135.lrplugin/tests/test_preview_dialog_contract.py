import re
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]


class PreviewDialogContractTests(unittest.TestCase):
    def setUp(self):
        self.agent = (PLUGIN / "PreviewAgent.lua").read_text(encoding="utf-8")
        self.runtime = (PLUGIN / "PreviewRuntime.lua").read_text(encoding="utf-8")

    def test_review_accepts_complete_request_and_returns_only_approved_schemas(self):
        for key in ("frames", "thumbnailPath", "sourceWidth", "sourceHeight", "title"):
            self.assertRegex(self.agent, rf"request\.{key}\b")
        for schema in (
            'status = "confirmed", frames =',
            'status = "canceled"',
            'status = "error", error =',
        ):
            self.assertIn(schema, self.agent)

    def test_runtime_owns_lightroom_binding_view_and_modal_adapters(self):
        for sdk_name in ("LrBinding", "LrView", "LrDialogs"):
            self.assertIn(sdk_name, self.runtime)
        for adapter in (
            "makePropertyTable",
            "addObserver",
            "viewFactory",
            "presentModalDialog",
        ):
            self.assertIn(adapter, self.runtime)

    def test_dialog_has_one_picture_four_numeric_controls_and_actions(self):
        self.assertEqual(self.agent.count("f:picture"), 1)
        self.assertEqual(self.agent.count("f:edit_field"), 4)
        self.assertEqual(self.agent.count("immediate = true"), 4)
        for token in (
            'bind "previewPath"',
            'precision = 0',
            'title = "向外增加"',
            'title = "重置"',
            'actionVerb = "确认"',
            'cancelVerb = "取消"',
            'bind "failureText"',
        ):
            self.assertIn(token, self.agent)
        self.assertIn("actionBinding = {", self.agent)
        self.assertIn("enabled = { bind_to_object = props, key = \"confirmEnabled\" }", self.agent)

    def test_dialog_never_mutates_lightroom_or_reruns_detection(self):
        for forbidden in ("applyDevelopSettings", "createVirtualCopies", "analyzeWithPython", "detectPhoto", 'text_color = "red"'):
            self.assertNotIn(forbidden, self.agent)

    def test_harness_is_source_only_and_not_registered_or_packaged(self):
        harness = "manual_preview_harness.lua"
        self.assertTrue((PLUGIN / "tests" / harness).is_file())
        for path in (PLUGIN / "Info.lua", PLUGIN / "build.sh"):
            self.assertNotIn(harness, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
