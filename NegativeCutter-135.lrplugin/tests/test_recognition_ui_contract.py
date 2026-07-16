import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]


class RecognitionUIContractTests(unittest.TestCase):
    def setUp(self):
        self.detect = (PLUGIN / "DetectFrames.lua").read_text(encoding="utf-8")
        self.batch = (PLUGIN / "BatchProcess.lua").read_text(encoding="utf-8")
        self.process = (PLUGIN / "ProcessAgent.lua").read_text(encoding="utf-8")

    def test_auto_uses_auto_frame_count_and_explicit_formats_use_defaults(self):
        for source in (self.detect, self.batch):
            self.assertIn("ProcessAgent.defaultExpectedFrames", source)
            self.assertIn("LrBinding.makePropertyTable", source)
            self.assertIn("LrFunctionContext.callWithContext", source)
            self.assertIn("预期帧数（0=自动）:", source)
        for format_hint, expected in (
            ("", 0),
            ("35mm", 6),
            ("645", 4),
            ("6x6", 3),
            ("6x7", 3),
            ("6x8", 2),
            ("6x9", 2),
        ):
            self.assertIn('["%s"] = %d' % (format_hint, expected), self.process)
        self.assertIn("DEFAULT_EXPECTED_FRAMES[formatHint or \"\"]", self.process)

    def test_recognition_dialogs_start_auto_and_do_not_persist_format_state(self):
        for source in (self.detect, self.batch):
            self.assertIn('local initialFormatIndex = 1', source)
            self.assertIn('local initialFormatHint = ""', source)
            self.assertIn('local initialExpectedFrames = ProcessAgent.defaultExpectedFrames("")', source)
            self.assertNotIn('local savedFormatHint = prefs.filmFormat', source)
            self.assertNotIn('prefs.expectedFramesFormat', source)
            self.assertNotIn('prefs.expectedFrames then', source)
            self.assertNotIn('prefs.filmFormat,', source)
            self.assertNotIn('prefs.expectedFrames,', source)
        self.assertIn('prefs.previewModeDetect', self.detect)
        self.assertIn('prefs.previewModeBatch', self.batch)

    def test_format_observer_keeps_auto_and_4x5_fallback_defaults(self):
        for source in (self.detect, self.batch):
            self.assertIn('selectedFormatHint(dialogData.formatIndex)', source)
            self.assertIn('ProcessAgent.defaultExpectedFrames(selectedFormatHint(dialogData.formatIndex))', source)
            self.assertIn('{ value = "", display = "自动检测" }', source)
            self.assertIn('{ value = "4x5", display = "大画幅 4×5" }', source)

    def test_batch_copy_selection_and_orientation_reads_are_yield_safe(self):
        self.assertIn('LrTasks.pcall(function()', self.process)
        self.assertIn('catalog:setSelectedPhotos(detection.photo, { detection.photo })', self.process)
        self.assertIn('catalog:setSelectedPhotos(virtualCopy, { virtualCopy })', self.process)
        self.assertIn('local renamed, renameError = LrTasks.pcall(function()', self.process)
        self.assertNotIn('local renamed, renameError = pcall(function()', self.process)

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
