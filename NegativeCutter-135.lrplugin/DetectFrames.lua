-- Detect Frames recognition entry with optional live preview.
local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local LrPrefs = import 'LrPrefs'
local LrTasks = import 'LrTasks'
local LrView = import 'LrView'

local pluginPath = _PLUGIN.path
local ProcessAgent = dofile(LrPathUtils.child(pluginPath, "ProcessAgent.lua"))
local CropCleaner = dofile(LrPathUtils.child(pluginPath, "CropCleaner.lua"))
local PreviewAgent = require 'PreviewAgent'
local PreviewRuntime = require 'PreviewRuntime'
local logger = LrLogger('NegativeCutter.DetectFrames'); logger:enable("logfile")
local prefs = LrPrefs.prefsForPlugin()

local FORMAT_OPTIONS = {
  { value = "", display = "自动检测" }, { value = "35mm", display = "135 (35mm)" },
  { value = "645", display = "120 6×4.5" }, { value = "6x6", display = "120 6×6" },
  { value = "6x7", display = "120 6×7" }, { value = "6x8", display = "120 6×8" },
  { value = "6x9", display = "120 6×9" }, { value = "4x5", display = "大画幅 4×5" },
}
local PREVIEW_MODES = {
  { value = "per_photo", display = "逐张预览" },
  { value = "batch_uniform", display = "整批统一" },
  { value = "none", display = "不预览" },
}

local function optionIndex(options, value)
  for index, option in ipairs(options) do if option.value == value then return index end end
  return 1
end

local function menuItems(options)
  local items = {}; for index, option in ipairs(options) do items[index] = { title = option.display, value = index } end
  return items
end

local function chooseSettings(photoCount)
  local f, bind = LrView.osFactory(), LrView.bind
  local filmTypes = CropCleaner.availableTypes()
  local dialogData = {
    expectedFrames = prefs.expectedFrames or 6,
    formatIndex = optionIndex(FORMAT_OPTIONS, prefs.filmFormat or ""),
    filmTypeIndex = optionIndex(filmTypes, prefs.filmType or "negative"),
    previewModeIndex = optionIndex(PREVIEW_MODES, prefs.previewModeDetect or "per_photo"),
  }
  local result = LrDialogs.presentModalDialog {
    title = "NegativeCutter - 开始检测", actionVerb = "开始检测", cancelVerb = "取消",
    contents = f:column {
      bind_to_object = dialogData, spacing = f:control_spacing(),
      f:static_text { title = string.format("将处理 %d 个胶片扫描文件", photoCount) },
      f:row { f:static_text { title = "预期帧数:", width = 90 },
        f:edit_field { value = bind "expectedFrames", width_in_chars = 6, precision = 0 } },
      f:row { f:static_text { title = "胶片格式:", width = 90 },
        f:popup_menu { value = bind "formatIndex", items = menuItems(FORMAT_OPTIONS), width_in_chars = 16 } },
      f:row { f:static_text { title = "胶片类型:", width = 90 },
        f:popup_menu { value = bind "filmTypeIndex", items = menuItems(filmTypes), width_in_chars = 16 } },
      f:row { f:static_text { title = "预览方式:", width = 90 },
        f:popup_menu { value = bind "previewModeIndex", items = menuItems(PREVIEW_MODES), width_in_chars = 16 } },
    },
  }
  if result ~= "ok" then return nil end
  local settings = {
    expectedFrames = tonumber(dialogData.expectedFrames) or 6,
    formatHint = FORMAT_OPTIONS[dialogData.formatIndex].value,
    filmType = filmTypes[dialogData.filmTypeIndex].value,
    previewMode = PREVIEW_MODES[dialogData.previewModeIndex].value,
  }
  if settings.formatHint == "" then settings.formatHint = nil end
  prefs.filmFormat, prefs.filmType, prefs.previewModeDetect = settings.formatHint or "", settings.filmType, settings.previewMode
  return settings
end

local function previewDetection(detection, runtime, title)
  return PreviewAgent.review(nil, {
    frames = detection.frames, thumbnailPath = detection.thumbnailPath,
    sourceWidth = detection.sourceWidth, sourceHeight = detection.sourceHeight, title = title,
  }, runtime)
end

local function runRecognition(catalog, photos, settings, runtime)
  local stats = { total = #photos, terminal = 0, created = 0, errors = {}, canceled = false }
  local sharedOffsets
  for index, photo in ipairs(photos) do
    local detection, detectError = ProcessAgent.detectPhoto(photo, settings)
    if not detection then
      stats.errors[#stats.errors + 1] = tostring(detectError); stats.terminal = stats.terminal + 1
    else
      local selected = detection
      if settings.previewMode == "per_photo" then
        local preview = previewDetection(detection, runtime, string.format("逐张预览 %d/%d · %s", index, #photos, detection.fileName))
        if preview.status == "canceled" then stats.canceled = true; break end
        if preview.status == "error" then
          stats.errors[#stats.errors + 1] = detection.fileName .. ": " .. preview.error; stats.terminal = stats.terminal + 1
          selected = nil
        else
          selected.frames = preview.frames
        end
      elseif settings.previewMode == "batch_uniform" then
        if not sharedOffsets then
          local preview = previewDetection(detection, runtime, "整批统一预览 · " .. detection.fileName)
          if preview.status == "canceled" then stats.canceled = true; break end
          if preview.status == "error" then
            stats.errors[#stats.errors + 1] = detection.fileName .. ": " .. preview.error; stats.canceled = true; break
          end
          sharedOffsets = { topPx = preview.offsets.topPx, bottomPx = preview.offsets.bottomPx,
            leftPx = preview.offsets.leftPx, rightPx = preview.offsets.rightPx }
          selected.frames = preview.frames
        else
          local adjusted, adjustError = ProcessAgent.adjustDetection(detection, sharedOffsets)
          if not adjusted then
            stats.errors[#stats.errors + 1] = detection.fileName .. ": " .. tostring(adjustError); stats.terminal = stats.terminal + 1
            selected = nil
          else selected = adjusted end
        end
      end
      if selected then
        local summary = ProcessAgent.createVirtualCopies(catalog, selected, {})
        stats.created = stats.created + summary.createdCount
        for _, message in ipairs(summary.errors) do stats.errors[#stats.errors + 1] = message end
        stats.terminal = stats.terminal + 1
      end
    end
  end
  return stats
end

LrTasks.startAsyncTask(function()
  local catalog = LrApplication.activeCatalog()
  local photos = catalog:getTargetPhotos()
  if not photos or #photos == 0 then LrDialogs.message("NegativeCutter", "请先选择要处理的胶片扫描文件", "info"); return end
  local settings = chooseSettings(#photos); if not settings then return end
  local runtime = PreviewRuntime.current()
  if not runtime then LrDialogs.message("NegativeCutter", "预览运行时尚未初始化，请重启 Lightroom 后重试", "critical"); return end
  local stats = runRecognition(catalog, photos, settings, runtime)
  local title = stats.canceled and "NegativeCutter - 已取消" or (#stats.errors > 0 and "NegativeCutter - 部分完成" or "NegativeCutter - 完成")
  LrDialogs.message(title, string.format("已完成 %d/%d 个文件，创建 %d 个虚拟副本，错误 %d 个",
    stats.terminal, stats.total, stats.created, #stats.errors), #stats.errors > 0 and "warning" or "info")
end)
