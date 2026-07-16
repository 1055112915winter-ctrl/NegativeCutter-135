-- Detect Frames recognition entry with per-photo preview by default.
local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrPathUtils = import 'LrPathUtils'
local LrPrefs = import 'LrPrefs'
local LrProgressScope = import 'LrProgressScope'
local LrTasks = import 'LrTasks'

local pluginPath = _PLUGIN.path
local ProcessAgent = dofile(LrPathUtils.child(pluginPath, "ProcessAgent.lua"))
local CropCleaner = dofile(LrPathUtils.child(pluginPath, "CropCleaner.lua"))
local RecognitionWorkflow = dofile(LrPathUtils.child(pluginPath, "RecognitionWorkflow.lua"))
local PreviewAgent = require 'PreviewAgent'
local PreviewRuntime = require 'PreviewRuntime'
local prefs = LrPrefs.prefsForPlugin()

local workflow = RecognitionWorkflow.new {
  ProcessAgent = ProcessAgent,
  CropCleaner = CropCleaner,
  PreviewAgent = PreviewAgent,
  prefs = prefs,
}

local function chooseSettings(photoCount)
  return workflow.chooseSettings {
    contextName = "NegativeCutter.DetectFrames.chooseSettings",
    photoCount = photoCount,
    dialogTitle = "NegativeCutter - 开始检测",
    actionVerb = "开始检测",
    introFormat = "将处理 %d 个胶片扫描文件",
    previewPreferenceKey = "previewModeDetect",
    defaultPreviewMode = "per_photo",
  }
end

local function runRecognition(catalog, photos, settings, runtime, adapters)
  return workflow.runRecognition(catalog, photos, settings, runtime, adapters)
end

LrTasks.startAsyncTask(function()
  local catalog = LrApplication.activeCatalog()
  local photos = catalog:getTargetPhotos()
  if not photos or #photos == 0 then
    LrDialogs.message("NegativeCutter", "请先选择要处理的胶片扫描文件", "info")
    return
  end

  local settings = chooseSettings(#photos)
  if not settings then return end
  local runtime = PreviewRuntime.current(ProcessAgent)
  if not runtime then
    LrDialogs.message("NegativeCutter", "预览运行时尚未初始化，请重启 Lightroom 后重试", "critical")
    return
  end

  local progress = LrProgressScope { title = "NegativeCutter - 检测帧", caption = "准备处理" }
  progress:setCancelable(true)
  local stats = runRecognition(catalog, photos, settings, runtime, { progress = progress })
  local title, body, severity = workflow.outcomePresentation(stats, false)
  LrDialogs.message(title, body, severity)
end)

return { runRecognition = runRecognition }
