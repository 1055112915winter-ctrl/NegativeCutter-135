import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]


class RecognitionUIContractTests(unittest.TestCase):
    def setUp(self):
        self.detect = (PLUGIN / "DetectFrames.lua").read_text(encoding="utf-8")
        self.batch = (PLUGIN / "BatchProcess.lua").read_text(encoding="utf-8")
        self.process = (PLUGIN / "ProcessAgent.lua").read_text(encoding="utf-8")
        self.workflow = (PLUGIN / "RecognitionWorkflow.lua").read_text(encoding="utf-8")

    def test_auto_uses_auto_frame_count_and_explicit_formats_use_defaults(self):
        self.assertIn("ProcessAgent.defaultExpectedFrames", self.workflow)
        self.assertIn("LrBinding.makePropertyTable", self.workflow)
        self.assertIn("LrFunctionContext.callWithContext", self.workflow)
        self.assertIn("预期帧数（0=自动）:", self.workflow)
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
        self.assertIn('local initialFormatIndex = 1', self.workflow)
        self.assertIn('local initialFormatHint = ""', self.workflow)
        self.assertIn('local initialExpectedFrames = ProcessAgent.defaultExpectedFrames("")', self.workflow)
        self.assertNotIn('local savedFormatHint = prefs.filmFormat', self.workflow)
        self.assertNotIn('prefs.expectedFramesFormat', self.workflow)
        self.assertNotIn('prefs.expectedFrames then', self.workflow)
        self.assertNotIn('prefs.filmFormat,', self.workflow)
        self.assertNotIn('prefs.expectedFrames,', self.workflow)
        self.assertIn('previewPreferenceKey = "previewModeDetect"', self.detect)
        self.assertIn('previewPreferenceKey = "previewModeBatch"', self.batch)

    def test_format_observer_keeps_auto_and_4x5_fallback_defaults(self):
        self.assertIn('selectedFormatHint(dialogData.formatIndex)', self.workflow)
        self.assertIn('ProcessAgent.defaultExpectedFrames(selectedFormatHint(dialogData.formatIndex))', self.workflow)
        self.assertIn('{ value = "", display = "自动检测" }', self.workflow)
        self.assertIn('{ value = "4x5", display = "大画幅 4×5" }', self.workflow)

    def test_batch_copy_selection_and_orientation_reads_are_yield_safe(self):
        self.assertIn('LrTasks.pcall(function()', self.process)
        self.assertIn('catalog:setSelectedPhotos(detection.photo, { detection.photo })', self.process)
        self.assertIn('catalog:setSelectedPhotos(virtualCopy, { virtualCopy })', self.process)
        self.assertIn('local renamed, renameError = LrTasks.pcall(function()', self.process)
        self.assertNotIn('local renamed, renameError = pcall(function()', self.process)

    def test_both_entries_offer_three_preview_modes_with_independent_defaults(self):
        for label in ("逐张预览", "整批统一", "不预览"):
            self.assertIn(label, self.workflow)
        self.assertIn('defaultPreviewMode = "per_photo"', self.detect)
        self.assertIn('defaultPreviewMode = "batch_uniform"', self.batch)
        self.assertNotIn("previewModeBatch", self.detect)
        self.assertNotIn("previewModeDetect", self.batch)

    def test_both_entries_use_only_the_initialized_runtime_and_explicit_stages(self):
        for source in (self.detect, self.batch):
            self.assertIn("PreviewRuntime.current(ProcessAgent)", source)
            self.assertIn("workflow.runRecognition", source)
            self.assertNotIn("PreviewRuntime.create", source)
            self.assertIn("预览运行时尚未初始化", source)
        for token in (
            "ProcessAgent.detectPhoto",
            "PreviewAgent.review",
            "ProcessAgent.previewPayload",
            "ProcessAgent.alignPreviewFrames",
            "ProcessAgent.adjustPreviewDetection",
            "ProcessAgent.createVirtualCopies",
        ):
            self.assertIn(token, self.workflow)

    def test_batch_uniform_reuses_only_numeric_offsets_not_frames(self):
        for key in ("topPx", "bottomPx", "leftPx", "rightPx"):
            self.assertIn(key, self.workflow)
        self.assertIn("ProcessAgent.adjustPreviewDetection(detection, sharedOffsets)", self.workflow)
        self.assertNotIn("detection.frames = firstDetection.frames", self.workflow)

    def test_preview_uses_thumbnail_coordinates_then_aligns_only_after_confirmation(self):
        self.assertIn("local preview, previewError = ProcessAgent.previewPayload(detection)", self.workflow)
        self.assertIn("frames = preview.frames", self.workflow)
        self.assertIn("sourceWidth = preview.sourceWidth", self.workflow)
        self.assertIn("sourceHeight = preview.sourceHeight", self.workflow)
        self.assertIn("ProcessAgent.alignPreviewFrames(detection, preview.frames)", self.workflow)

    def test_per_photo_cancel_stops_future_work_without_rollback(self):
        self.assertIn('preview.status == "canceled"', self.workflow)
        self.assertIn("break", self.workflow)
        self.assertNotIn("deleteVirtual", self.workflow)

    def test_http_entry_remains_outside_preview_pipeline(self):
        source = (PLUGIN / "ImportAgent.lua").read_text(encoding="utf-8")
        for forbidden in ("PreviewAgent", "PreviewRuntime", "previewModeDetect", "previewModeBatch"):
            self.assertNotIn(forbidden, source)

    def test_native_progress_and_terminal_accounting_contracts_are_explicit(self):
        self.assertIn("LrTasks.pcall", self.workflow)
        self.assertNotIn("xpcall", self.workflow)
        for token in (
            "setPortionComplete(terminalPhotos, totalPhotos)",
            "processedPhotos = terminalPhotos",
            "unprocessedPhotos = totalPhotos - terminalPhotos",
            "partialCurrent = true",
            "progress:done()",
            "unexpectedError",
            'stage == "thumbnail"',
            'stage == "recognition"',
            'stage == "frame"',
        ):
            self.assertIn(token, self.workflow)
        self.assertIn("progress:isCanceled()", self.workflow)
        for source in (self.detect, self.batch):
            self.assertIn("LrProgressScope", source)
            self.assertIn("progress:setCancelable(true)", source)

    def test_menu_entries_delegate_to_one_shared_workflow(self):
        for source in (self.detect, self.batch):
            self.assertIn('dofile(LrPathUtils.child(pluginPath, "RecognitionWorkflow.lua"))', source)
            self.assertIn("RecognitionWorkflow.new", source)
            self.assertLess(len(source.splitlines()), 100)
        self.assertGreater(len(self.workflow.splitlines()), 200)


if __name__ == "__main__":
    unittest.main()
