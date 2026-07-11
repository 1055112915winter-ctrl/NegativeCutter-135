-- Batch Process recognition entry with batch-uniform preview by default.
local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local LrPrefs = import 'LrPrefs'
local LrProgressScope = import 'LrProgressScope'
local LrTasks = import 'LrTasks'
local LrView = import 'LrView'

local pluginPath = _PLUGIN.path
local ProcessAgent = dofile(LrPathUtils.child(pluginPath, "ProcessAgent.lua"))
local CropCleaner = dofile(LrPathUtils.child(pluginPath, "CropCleaner.lua"))
local PreviewAgent = require 'PreviewAgent'
local PreviewRuntime = require 'PreviewRuntime'
local logger = LrLogger('NegativeCutter.BatchProcess'); logger:enable("logfile")
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
local function optionIndex(options, value) for index, option in ipairs(options) do if option.value == value then return index end end; return 1 end
local function menuItems(options) local items = {}; for index, option in ipairs(options) do items[index] = { title = option.display, value = index } end; return items end

local function chooseSettings(photoCount)
  local f, bind, filmTypes = LrView.osFactory(), LrView.bind, CropCleaner.availableTypes()
  local dialogData = {
    expectedFrames = prefs.expectedFrames or 6,
    formatIndex = optionIndex(FORMAT_OPTIONS, prefs.filmFormat or ""),
    filmTypeIndex = optionIndex(filmTypes, prefs.filmType or "negative"),
    previewModeIndex = optionIndex(PREVIEW_MODES, prefs.previewModeBatch or "batch_uniform"),
  }
  local result = LrDialogs.presentModalDialog {
    title = "NegativeCutter - 批量处理", actionVerb = "开始批量处理", cancelVerb = "取消",
    contents = f:column { bind_to_object = dialogData, spacing = f:control_spacing(),
      f:static_text { title = string.format("将批量处理 %d 个胶片扫描文件", photoCount) },
      f:row { f:static_text { title = "预期帧数:", width = 90 }, f:edit_field { value = bind "expectedFrames", width_in_chars = 6, precision = 0 } },
      f:row { f:static_text { title = "胶片格式:", width = 90 }, f:popup_menu { value = bind "formatIndex", items = menuItems(FORMAT_OPTIONS), width_in_chars = 16 } },
      f:row { f:static_text { title = "胶片类型:", width = 90 }, f:popup_menu { value = bind "filmTypeIndex", items = menuItems(filmTypes), width_in_chars = 16 } },
      f:row { f:static_text { title = "预览方式:", width = 90 }, f:popup_menu { value = bind "previewModeIndex", items = menuItems(PREVIEW_MODES), width_in_chars = 16 } },
    },
  }
  if result ~= "ok" then return nil end
  local settings = { expectedFrames = tonumber(dialogData.expectedFrames) or 6,
    formatHint = FORMAT_OPTIONS[dialogData.formatIndex].value, filmType = filmTypes[dialogData.filmTypeIndex].value,
    previewMode = PREVIEW_MODES[dialogData.previewModeIndex].value }
  if settings.formatHint == "" then settings.formatHint = nil end
  prefs.filmFormat, prefs.filmType, prefs.previewModeBatch = settings.formatHint or "", settings.filmType, settings.previewMode
  return settings
end

local function previewDetection(detection, runtime, title)
  return PreviewAgent.review(nil, { frames = detection.frames, thumbnailPath = detection.thumbnailPath,
    sourceWidth = detection.sourceWidth, sourceHeight = detection.sourceHeight, title = title }, runtime)
end

local function runRecognition(catalog, photos, settings, runtime, adapters)
  adapters = adapters or {}
  local progress = assert(adapters.progress, "progress adapter is required")
  local totalPhotos, terminalPhotos = #photos, 0
  local stats = { total = totalPhotos, created = 0, errors = {}, canceled = false, partialCurrent = false }
  local sharedOffsets
  local function updateCaption(stage, fileName, photoIndex, frameIndex, frameTotal)
    local caption
    if stage == "thumbnail" then caption = string.format("%d/%d · 生成缩略图 · %s", photoIndex, totalPhotos, fileName)
    elseif stage == "recognition" then caption = string.format("%d/%d · 识别边界 · %s", photoIndex, totalPhotos, fileName)
    elseif stage == "preview" then caption = string.format("%d/%d · 预览确认 · %s", photoIndex, totalPhotos, fileName)
    elseif stage == "frame" then caption = string.format("%d/%d · 创建帧 %d/%d · %s", photoIndex, totalPhotos, frameIndex, frameTotal, fileName)
    else caption = string.format("%d/%d · %s", photoIndex, totalPhotos, fileName) end
    progress:setCaption(caption)
  end
  local function markTerminal()
    terminalPhotos = terminalPhotos + 1
    progress:setPortionComplete(terminalPhotos, totalPhotos)
  end
  local ok, unexpected = LrTasks.pcall(function()
    for index, photo in ipairs(photos) do
      if progress:isCanceled() then stats.canceled = true; break end
      local fallbackName = photo.getFormattedMetadata and photo:getFormattedMetadata("fileName") or "scan"
      local detectOptions = { expectedFrames = settings.expectedFrames, formatHint = settings.formatHint,
        filmType = settings.filmType, thumbnailWidth = settings.thumbnailWidth,
        onStage = function(stage) updateCaption(stage, fallbackName, index) end }
      local detection, detectError = ProcessAgent.detectPhoto(photo, detectOptions)
      if progress:isCanceled() then stats.canceled = true; break end
      if not detection then
        stats.errors[#stats.errors + 1] = fallbackName .. ": " .. tostring(detectError); markTerminal()
      else
        local selected = detection
        if settings.previewMode == "per_photo" then
          updateCaption("preview", detection.fileName, index)
          local preview = previewDetection(detection, runtime, string.format("逐张预览 %d/%d · %s", index, totalPhotos, detection.fileName))
          if progress:isCanceled() or preview.status == "canceled" then stats.canceled = true; break end
          if preview.status == "error" then stats.errors[#stats.errors + 1] = detection.fileName .. ": " .. preview.error; markTerminal(); selected = nil
          else selected.frames = preview.frames end
        elseif settings.previewMode == "batch_uniform" then
          if not sharedOffsets then
            updateCaption("preview", detection.fileName, index)
            local preview = previewDetection(detection, runtime, "整批统一预览 · " .. detection.fileName)
            if progress:isCanceled() or preview.status == "canceled" then stats.canceled = true; break end
            if preview.status == "error" then stats.errors[#stats.errors + 1] = detection.fileName .. ": " .. preview.error; markTerminal(); selected = nil
            else
              sharedOffsets = { topPx = preview.offsets.topPx, bottomPx = preview.offsets.bottomPx,
                leftPx = preview.offsets.leftPx, rightPx = preview.offsets.rightPx }
              selected.frames = preview.frames
            end
          else
            local adjusted, adjustError = ProcessAgent.adjustDetection(detection, sharedOffsets)
            if not adjusted then stats.errors[#stats.errors + 1] = detection.fileName .. ": " .. tostring(adjustError); markTerminal(); selected = nil
            else selected = adjusted end
          end
        end
        if selected then
          if progress:isCanceled() then stats.canceled = true; break end
          local summary = ProcessAgent.createVirtualCopies(catalog, selected, {
            isCanceled = function() return progress:isCanceled() end,
            onStage = function(stage, frameIndex, frameTotal) updateCaption(stage, detection.fileName, index, frameIndex, frameTotal) end,
          })
          stats.created = stats.created + summary.createdCount
          for _, message in ipairs(summary.errors) do stats.errors[#stats.errors + 1] = message end
          if summary.status == "canceled" or progress:isCanceled() then
            stats.canceled = true
            if summary.attemptedFrames > 0 or summary.createdCount > 0 then stats.partialCurrent = true end
            break
          end
          markTerminal()
        end
      end
    end
  end)
  progress:done()
  if not ok then stats.unexpectedError = tostring(unexpected) end
  stats.processedPhotos = terminalPhotos
  stats.unprocessedPhotos = totalPhotos - terminalPhotos
  stats.terminal = terminalPhotos
  return stats
end

LrTasks.startAsyncTask(function()
  local catalog = LrApplication.activeCatalog(); local photos = catalog:getTargetPhotos()
  if not photos or #photos == 0 then LrDialogs.message("NegativeCutter - 批量处理", "请先选择要处理的胶片扫描文件", "info"); return end
  local settings = chooseSettings(#photos); if not settings then return end
  local runtime = PreviewRuntime.current(ProcessAgent)
  if not runtime then LrDialogs.message("NegativeCutter", "预览运行时尚未初始化，请重启 Lightroom 后重试", "critical"); return end
  local progress = LrProgressScope { title = "NegativeCutter - 批量处理", caption = "准备处理" }
  progress:setCancelable(true)
  local stats = runRecognition(catalog, photos, settings, runtime, { progress = progress })
  local body = string.format("已处理 %d 个，未处理 %d 个，创建 %d 个虚拟副本，错误 %d 个",
    stats.processedPhotos, stats.unprocessedPhotos, stats.created, #stats.errors)
  if stats.unexpectedError then LrDialogs.message("NegativeCutter - 未预期错误", body .. "\n\n" .. stats.unexpectedError, "critical")
  elseif stats.canceled then LrDialogs.message("NegativeCutter - 已取消", body .. (stats.partialCurrent and "\n当前照片已保留部分成功副本。" or ""), "info")
  elseif #stats.errors > 0 then LrDialogs.message("NegativeCutter - 部分完成", body, "warning")
  else LrDialogs.message("NegativeCutter - 完成", body, "info") end
end)

return { runRecognition = runRecognition }
