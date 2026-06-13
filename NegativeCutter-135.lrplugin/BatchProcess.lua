--[[
  BatchProcess.lua
  批量处理多个胶片扫描文件（无预览，直接创建虚拟副本）
  使用 ProcessAgent 共享检测管线，与 DetectFrames.lua 一致。
]]

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local LrTasks = import 'LrTasks'
local LrPrefs = import 'LrPrefs'
local LrView = import 'LrView'

local pluginPath = _PLUGIN.path
local ProcessAgent = dofile(LrPathUtils.child(pluginPath, "ProcessAgent.lua"))
local CropCleaner = dofile(LrPathUtils.child(pluginPath, "CropCleaner.lua"))

local logger = LrLogger('NegativeCutter')
logger:enable("logfile")

local prefs = LrPrefs.prefsForPlugin()

if not prefs.expectedFrames then
  prefs.expectedFrames = 6
end

-- 批量处理主函数
LrTasks.startAsyncTask(function()
  logger:trace("=" .. string.rep("=", 60))
  logger:trace("NegativeCutter 批量处理开始 (v2.4.3)")
  logger:trace("=" .. string.rep("=", 60))

  local catalog = LrApplication.activeCatalog()
  local selectedPhotos = catalog:getTargetPhotos()

  if not selectedPhotos or #selectedPhotos == 0 then
    LrDialogs.message("NegativeCutter - 批量处理", "请先选择要处理的胶片扫描文件", "info")
    return
  end

  -- 确认对话框
  local f = LrView.osFactory()
  local bind = LrView.bind
  local _FORMAT_OPTIONS = {
    { value = "",    display = "自动检测" },
    { value = "35mm", display = "135 (35mm)" },
    { value = "645",  display = "120 6×4.5" },
    { value = "6x6",  display = "120 6×6" },
    { value = "6x7",  display = "120 6×7" },
    { value = "6x8",  display = "120 6×8" },
    { value = "6x9",  display = "120 6×9" },
    { value = "4x5",  display = "大画幅 4×5" },
  }

  local formatMenuItems = {}
  for i, opt in ipairs(_FORMAT_OPTIONS) do
    table.insert(formatMenuItems, { title = opt.display, value = i })
  end

  -- Film type options
  local filmTypeOptions = CropCleaner.availableTypes()
  local filmTypeMenuItems = {}
  for i, opt in ipairs(filmTypeOptions) do
    table.insert(filmTypeMenuItems, { title = opt.display, value = i })
  end

  local currentFormat = prefs.filmFormat or ""
  local formatIndex = 1
  for i, opt in ipairs(_FORMAT_OPTIONS) do
    if opt.value == currentFormat then
      formatIndex = i
      break
    end
  end

  local currentFilmType = prefs.filmType or "negative"
  local filmTypeIndex = 1
  for i, opt in ipairs(filmTypeOptions) do
    if opt.value == currentFilmType then
      filmTypeIndex = i
      break
    end
  end

  local dialogData = {
    expectedFrames = prefs.expectedFrames or 0,
    formatIndex    = formatIndex,
    filmTypeIndex  = filmTypeIndex,
  }

  local contents = f:column {
    spacing = f:control_spacing(),
    bind_to_object = dialogData,
    f:static_text {
      title = string.format("将对 %d 个文件进行批量检测并创建虚拟副本", #selectedPhotos),
      height_in_lines = 3,
    },
    f:separator {},
    f:row {
      spacing = f:label_spacing(),
      f:static_text { title = "预期帧数:", width = 80 },
      f:edit_field {
        value = bind "expectedFrames",
        width_in_chars = 5,
        precision = 0,
      },
      f:static_text { title = "(填 0 自动检测，所有文件使用相同帧数)" },
    },
    f:row {
      spacing = f:label_spacing(),
      f:static_text { title = "胶片格式:", width = 80 },
      f:popup_menu {
        items = formatMenuItems,
        value = bind "formatIndex",
        width_in_chars = 14,
      },
      f:static_text { title = "(选自动时由引擎推断宽高比)" },
    },
    f:row {
      spacing = f:label_spacing(),
      f:static_text { title = "胶片类型:", width = 80 },
      f:popup_menu {
        items = filmTypeMenuItems,
        value = bind "filmTypeIndex",
        width_in_chars = 18,
      },
      f:static_text { title = "(决定边界清理强度)" },
    },
    f:static_text {
      title = "批量处理将跳过预览，直接为每个文件创建虚拟副本。",
      height_in_lines = 2,
    },
  }

  local dlgResult = LrDialogs.presentModalDialog {
    title = "NegativeCutter - 批量处理",
    contents = contents,
    actionVerb = "开始批量处理",
    cancelVerb = "取消",
  }
  if dlgResult ~= "ok" then return end

  local expectedFrames = tonumber(dialogData.expectedFrames) or (prefs.expectedFrames or 6)
  local chosenFormat = _FORMAT_OPTIONS[dialogData.formatIndex].value
  local chosenFilmType = filmTypeOptions[dialogData.filmTypeIndex].value
  prefs.filmFormat = chosenFormat
  prefs.filmType = chosenFilmType
  logger:trace("批量处理预期帧数: " .. tostring(expectedFrames))
  logger:trace("批量处理胶片格式: " .. tostring(chosenFormat))
  logger:trace("批量处理胶片类型: " .. tostring(chosenFilmType))

  local stats = {
    total = #selectedPhotos,
    success = 0,
    framesCreated = 0,
    errors = {}
  }

  local formatHint = chosenFormat ~= "" and chosenFormat or nil

  for i, photo in ipairs(selectedPhotos) do
    local fileName = photo:getFormattedMetadata('fileName')
    logger:trace(string.format("批量处理 [%d/%d]: %s", i, #selectedPhotos, fileName))

    local createdCount, errMsg = ProcessAgent.detectAndCrop(catalog, photo, expectedFrames, fileName, formatHint)
    if errMsg then
      table.insert(stats.errors, fileName .. ": " .. errMsg)
    else
      stats.success = stats.success + 1
      stats.framesCreated = stats.framesCreated + (createdCount or 0)
    end
  end

  logger:trace(string.format("批量处理完成: 成功 %d/%d, 创建 %d 个虚拟副本",
    stats.success, stats.total, stats.framesCreated))

  local report = string.format(
    "总文件 %d · 成功 %d · 失败 %d\n创建虚拟副本 %d",
    stats.total, stats.success, stats.total - stats.success, stats.framesCreated)

  if #stats.errors > 0 then
    local errorDetail = table.concat(stats.errors, "\n  • ", 1, math.min(5, #stats.errors))
    if #stats.errors > 5 then
      errorDetail = errorDetail .. "\n  ... 等 " .. (#stats.errors - 5) .. " 个错误"
    end
    local failResult = LrDialogs.confirm(
      "⚠️  批量处理完成（部分失败）",
      report .. "\n\n错误详情:\n  • " .. errorDetail,
      "🐛 反馈问题",
      "关闭"
    )
    if failResult == "ok" then
      dofile(LrPathUtils.child(pluginPath, "Feedback.lua"))
    end
  else
    local donateResult = LrDialogs.confirm(
      "✅ 批量处理完成",
      report .. "\n\n所有文件已成功处理。",
      "☕ 请作者喝咖啡",
      "关闭"
    )
    if donateResult == "ok" then
      ProcessAgent.openSponsorImage()
    end
  end
end)
