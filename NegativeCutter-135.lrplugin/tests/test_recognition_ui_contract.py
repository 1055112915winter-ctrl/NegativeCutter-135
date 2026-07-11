import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]


class RecognitionUIContractTests(unittest.TestCase):
    def setUp(self):
        self.detect = (PLUGIN / "DetectFrames.lua").read_text(encoding="utf-8")
        self.batch = (PLUGIN / "BatchProcess.lua").read_text(encoding="utf-8")

    def test_both_entries_offer_three_preview_modes_with_independent_defaults(self):
        for source in (self.detect, self.batch):
            for label in ("逐张预览", "整批统一", "不预览"):
                self.assertIn(label, source)
        self.assertIn('prefs.previewModeDetect or "per_photo"', self.detect)
        self.assertIn('prefs.previewModeBatch or "batch_uniform"', self.batch)
        self.assertNotIn("previewModeBatch", self.detect)
        self.assertNotIn("previewModeDetect", self.batch)

    def test_both_entries_use_only_the_initialized_runtime_and_explicit_stages(self):
        for source in (self.detect, self.batch):
            for token in (
                "PreviewRuntime.current(ProcessAgent)",
                "ProcessAgent.detectPhoto",
                "PreviewAgent.review",
                "ProcessAgent.adjustDetection",
                "ProcessAgent.createVirtualCopies",
            ):
                self.assertIn(token, source)
            self.assertNotIn("PreviewRuntime.create", source)
            self.assertIn("预览运行时尚未初始化", source)

    def test_batch_uniform_reuses_only_numeric_offsets_not_frames(self):
        for key in ("topPx", "bottomPx", "leftPx", "rightPx"):
            self.assertIn(key, self.batch)
        self.assertIn("ProcessAgent.adjustDetection(detection, sharedOffsets)", self.batch)
        self.assertNotIn("detection.frames = firstDetection.frames", self.batch)

    def test_per_photo_cancel_stops_future_work_without_rollback(self):
        self.assertIn('preview.status == "canceled"', self.detect)
        self.assertIn("break", self.detect)
        self.assertNotIn("deleteVirtual", self.detect)

    def test_http_entry_remains_outside_preview_pipeline(self):
        source = (PLUGIN / "ImportAgent.lua").read_text(encoding="utf-8")
        for forbidden in ("PreviewAgent", "PreviewRuntime", "previewModeDetect", "previewModeBatch"):
            self.assertNotIn(forbidden, source)

    def test_native_progress_and_terminal_accounting_contracts_are_explicit(self):
        for source in (self.detect, self.batch):
            self.assertIn("LrTasks.pcall", source)
            self.assertNotIn("xpcall", source)
            for token in (
                "LrProgressScope",
                "setPortionComplete(terminalPhotos, totalPhotos)",
                "processedPhotos = terminalPhotos",
                "unprocessedPhotos = totalPhotos - terminalPhotos",
                "partialCurrent = true",
                "progress:done()",
                "progress:setCancelable(true)",
                "unexpectedError",
                'stage == "thumbnail"',
                'stage == "recognition"',
                'stage == "frame"',
            ):
                self.assertIn(token, source)
            self.assertIn("progress:isCanceled()", source)


if __name__ == "__main__":
    unittest.main()
