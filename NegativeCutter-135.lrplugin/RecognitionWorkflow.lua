-- Shared recognition dialog and orchestration for Lightroom menu entries.
-- Product-specific titles, defaults, and outcome policy stay in the entry files.

local LrBinding = import 'LrBinding'
local LrDialogs = import 'LrDialogs'
local LrFunctionContext = import 'LrFunctionContext'
local LrTasks = import 'LrTasks'
local LrView = import 'LrView'

local RecognitionWorkflow = {}

local FORMAT_OPTIONS = {
  { value = "", display = "自动检测" },
  { value = "35mm", display = "135 (35mm)" },
  { value = "645", display = "120 6×4.5" },
  { value = "6x6", display = "120 6×6" },
  { value = "6x7", display = "120 6×7" },
  { value = "6x8", display = "120 6×8" },
  { value = "6x9", display = "120 6×9" },
  { value = "4x5", display = "大画幅 4×5" },
}

local PREVIEW_MODES = {
  { value = "per_photo", display = "逐张预览" },
  { value = "batch_uniform", display = "整批统一" },
  { value = "none", display = "不预览" },
}

local function optionIndex(options, value)
  for index, option in ipairs(options) do
    if option.value == value then return index end
  end
  return 1
end

local function menuItems(options)
  local items = {}
  for index, option in ipairs(options) do
    items[index] = { title = option.display, value = index }
  end
  return items
end

local function selectedFormatHint(formatIndex)
  return FORMAT_OPTIONS[formatIndex] and FORMAT_OPTIONS[formatIndex].value or ""
end

function RecognitionWorkflow.new(dependencies)
  dependencies = dependencies or {}
  local ProcessAgent = assert(dependencies.ProcessAgent, "ProcessAgent is required")
  local CropCleaner = assert(dependencies.CropCleaner, "CropCleaner is required")
  local PreviewAgent = assert(dependencies.PreviewAgent, "PreviewAgent is required")
  local prefs = assert(dependencies.prefs, "plugin preferences are required")
  local workflow = {}

  function workflow.chooseSettings(config)
    config = config or {}
    return LrFunctionContext.callWithContext(config.contextName or "NegativeCutter.chooseSettings", function(context)
      local f, bind = LrView.osFactory(), LrView.bind
      local filmTypes = CropCleaner.availableTypes()
      local initialFormatIndex = 1
      local initialFormatHint = ""
      local initialExpectedFrames = ProcessAgent.defaultExpectedFrames("")
      local dialogData = LrBinding.makePropertyTable(context)
      dialogData.expectedFrames = initialExpectedFrames
      dialogData.formatIndex = initialFormatIndex
      dialogData.filmTypeIndex = optionIndex(filmTypes, prefs.filmType or "negative")
      dialogData.previewModeIndex = optionIndex(
        PREVIEW_MODES,
        prefs[config.previewPreferenceKey] or config.defaultPreviewMode
      )
      dialogData:addObserver("formatIndex", function()
        dialogData.expectedFrames = ProcessAgent.defaultExpectedFrames(selectedFormatHint(dialogData.formatIndex))
      end)

      local result = LrDialogs.presentModalDialog {
        title = config.dialogTitle,
        actionVerb = config.actionVerb,
        cancelVerb = "取消",
        contents = f:column {
          bind_to_object = dialogData,
          spacing = f:control_spacing(),
          f:static_text { title = string.format(config.introFormat, config.photoCount) },
          f:row {
            f:static_text { title = "预期帧数（0=自动）:", width = 145 },
            f:edit_field { value = bind "expectedFrames", width_in_chars = 6, precision = 0 },
          },
          f:row {
            f:static_text { title = "胶片格式:", width = 90 },
            f:popup_menu { value = bind "formatIndex", items = menuItems(FORMAT_OPTIONS), width_in_chars = 16 },
          },
          f:row {
            f:static_text { title = "胶片类型:", width = 90 },
            f:popup_menu { value = bind "filmTypeIndex", items = menuItems(filmTypes), width_in_chars = 16 },
          },
          f:row {
            f:static_text { title = "预览方式:", width = 90 },
            f:popup_menu { value = bind "previewModeIndex", items = menuItems(PREVIEW_MODES), width_in_chars = 16 },
          },
        },
      }
      if result ~= "ok" then return nil end

      local settings = {
        expectedFrames = tonumber(dialogData.expectedFrames)
          or ProcessAgent.defaultExpectedFrames(selectedFormatHint(dialogData.formatIndex)),
        formatHint = selectedFormatHint(dialogData.formatIndex),
        filmType = filmTypes[dialogData.filmTypeIndex].value,
        previewMode = PREVIEW_MODES[dialogData.previewModeIndex].value,
      }
      if settings.formatHint == "" then settings.formatHint = nil end
      prefs.filmType = settings.filmType
      prefs[config.previewPreferenceKey] = settings.previewMode
      return settings
    end)
  end

  local function previewDetection(detection, runtime, title)
    local preview, previewError = ProcessAgent.previewPayload(detection)
    if not preview then return { status = "error", error = previewError } end
    return PreviewAgent.review(nil, {
      frames = preview.frames,
      thumbnailPath = detection.thumbnailPath,
      sourceWidth = preview.sourceWidth,
      sourceHeight = preview.sourceHeight,
      title = title,
    }, runtime)
  end

  function workflow.runRecognition(catalog, photos, settings, runtime, adapters)
    adapters = adapters or {}
    local progress = assert(adapters.progress, "progress adapter is required")
    local totalPhotos, terminalPhotos = #photos, 0
    local stats = {
      total = totalPhotos,
      created = 0,
      errors = {},
      canceled = false,
      partialCurrent = false,
    }
    local sharedOffsets

    local function updateCaption(stage, fileName, photoIndex, frameIndex, frameTotal)
      local caption
      if stage == "thumbnail" then
        caption = string.format("%d/%d · 生成缩略图 · %s", photoIndex, totalPhotos, fileName)
      elseif stage == "recognition" then
        caption = string.format("%d/%d · 识别边界 · %s", photoIndex, totalPhotos, fileName)
      elseif stage == "preview" then
        caption = string.format("%d/%d · 预览确认 · %s", photoIndex, totalPhotos, fileName)
      elseif stage == "frame" then
        caption = string.format("%d/%d · 创建帧 %d/%d · %s", photoIndex, totalPhotos, frameIndex, frameTotal, fileName)
      else
        caption = string.format("%d/%d · %s", photoIndex, totalPhotos, fileName)
      end
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
        local detection, detectError = ProcessAgent.detectPhoto(photo, {
          expectedFrames = settings.expectedFrames,
          formatHint = settings.formatHint,
          filmType = settings.filmType,
          thumbnailWidth = settings.thumbnailWidth,
          onStage = function(stage) updateCaption(stage, fallbackName, index) end,
        })
        if progress:isCanceled() then stats.canceled = true; break end

        if not detection then
          stats.errors[#stats.errors + 1] = fallbackName .. ": " .. tostring(detectError)
          markTerminal()
        else
          local selected = detection
          if settings.previewMode == "per_photo" then
            updateCaption("preview", detection.fileName, index)
            local preview = previewDetection(
              detection,
              runtime,
              string.format("逐张预览 %d/%d · %s", index, totalPhotos, detection.fileName)
            )
            if progress:isCanceled() or preview.status == "canceled" then
              stats.canceled = true
              break
            elseif preview.status == "error" then
              stats.errors[#stats.errors + 1] = detection.fileName .. ": " .. preview.error
              markTerminal()
              selected = nil
            else
              local aligned, alignError = ProcessAgent.alignPreviewFrames(detection, preview.frames)
              if not aligned then
                stats.errors[#stats.errors + 1] = detection.fileName .. ": " .. tostring(alignError)
                markTerminal()
                selected = nil
              else
                selected = aligned
              end
            end
          elseif settings.previewMode == "batch_uniform" then
            if not sharedOffsets then
              updateCaption("preview", detection.fileName, index)
              local preview = previewDetection(detection, runtime, "整批统一预览 · " .. detection.fileName)
              if progress:isCanceled() or preview.status == "canceled" then
                stats.canceled = true
                break
              elseif preview.status == "error" then
                stats.errors[#stats.errors + 1] = detection.fileName .. ": " .. preview.error
                markTerminal()
                selected = nil
              else
                sharedOffsets = {
                  topPx = preview.offsets.topPx,
                  bottomPx = preview.offsets.bottomPx,
                  leftPx = preview.offsets.leftPx,
                  rightPx = preview.offsets.rightPx,
                }
                local aligned, alignError = ProcessAgent.alignPreviewFrames(detection, preview.frames)
                if not aligned then
                  stats.errors[#stats.errors + 1] = detection.fileName .. ": " .. tostring(alignError)
                  markTerminal()
                  selected = nil
                else
                  selected = aligned
                end
              end
            else
              local adjusted, adjustError = ProcessAgent.adjustPreviewDetection(detection, sharedOffsets)
              if not adjusted then
                stats.errors[#stats.errors + 1] = detection.fileName .. ": " .. tostring(adjustError)
                markTerminal()
                selected = nil
              else
                selected = adjusted
              end
            end
          end

          if selected then
            if progress:isCanceled() then stats.canceled = true; break end
            local summary = ProcessAgent.createVirtualCopies(catalog, selected, {
              isCanceled = function() return progress:isCanceled() end,
              onStage = function(stage, frameIndex, frameTotal)
                updateCaption(stage, detection.fileName, index, frameIndex, frameTotal)
              end,
            })
            stats.created = stats.created + summary.createdCount
            for _, message in ipairs(summary.errors) do
              stats.errors[#stats.errors + 1] = message
            end
            if summary.status == "canceled" or progress:isCanceled() then
              stats.canceled = true
              if summary.attemptedFrames > 0 or summary.createdCount > 0 then
                stats.partialCurrent = true
              end
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

  function workflow.outcomePresentation(stats, zeroSuccessIsFailure)
    local body = string.format(
      "已处理 %d 个，未处理 %d 个，创建 %d 个虚拟副本，错误 %d 个",
      stats.processedPhotos,
      stats.unprocessedPhotos,
      stats.created,
      #stats.errors
    )
    if #stats.errors > 0 then
      body = body .. "\n首个错误: " .. tostring(stats.errors[1]) ..
        "\n日志: ~/Library/Logs/Adobe/Lightroom/LrClassicLogs/NegativeCutter.log"
    end
    if stats.unexpectedError then
      return "NegativeCutter - 未预期错误", body .. "\n\n" .. stats.unexpectedError, "critical"
    elseif stats.canceled then
      return "NegativeCutter - 已取消",
        body .. (stats.partialCurrent and "\n当前照片已保留部分成功副本。" or ""),
        "info"
    elseif #stats.errors > 0 and zeroSuccessIsFailure and stats.created == 0 then
      return "NegativeCutter - 失败", body, "critical"
    elseif #stats.errors > 0 then
      return "NegativeCutter - 部分完成", body, "warning"
    end
    return "NegativeCutter - 完成", body, "info"
  end

  return workflow
end

return RecognitionWorkflow
