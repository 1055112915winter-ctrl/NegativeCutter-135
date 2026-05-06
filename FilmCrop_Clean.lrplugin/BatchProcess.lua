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

local logger = LrLogger('FilmCrop')
logger:enable("logfile")

local prefs = LrPrefs.prefsForPlugin()

if not prefs.expectedFrames then
  prefs.expectedFrames = 6
end

-- 批量处理主函数
LrTasks.startAsyncTask(function()
  logger:trace("=" .. string.rep("=", 60))
  logger:trace("FilmCrop 批量处理开始 (v1.5)")
  logger:trace("=" .. string.rep("=", 60))

  local catalog = LrApplication.activeCatalog()
  local selectedPhotos = catalog:getTargetPhotos()

  if not selectedPhotos or #selectedPhotos == 0 then
    LrDialogs.message("FilmCrop - 批量处理", "请先选择要处理的胶片扫描文件", "info")
    return
  end

  -- 确认对话框
  local f = LrView.osFactory()
  local bind = LrView.bind
  local dialogData = { expectedFrames = prefs.expectedFrames or 0 }

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
    f:static_text {
      title = "批量处理将跳过预览，直接为每个文件创建虚拟副本。",
      height_in_lines = 2,
    },
  }

  local dlgResult = LrDialogs.presentModalDialog {
    title = "FilmCrop - 批量处理",
    contents = contents,
    actionVerb = "开始批量处理",
    cancelVerb = "取消",
  }
  if dlgResult ~= "ok" then return end

  local expectedFrames = tonumber(dialogData.expectedFrames) or (prefs.expectedFrames or 6)
  logger:trace("批量处理预期帧数: " .. tostring(expectedFrames))

  local stats = {
    total = #selectedPhotos,
    success = 0,
    framesCreated = 0,
    errors = {}
  }

  for i, photo in ipairs(selectedPhotos) do
    local fileName = photo:getFormattedMetadata('fileName')
    logger:trace(string.format("批量处理 [%d/%d]: %s", i, #selectedPhotos, fileName))

    local createdCount, errMsg = ProcessAgent.detectAndCrop(catalog, photo, expectedFrames, fileName)
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
    "处理统计:\n  • 总文件: %d\n  • 成功: %d\n  • 失败: %d\n  • 创建虚拟副本: %d",
    stats.total, stats.success, stats.total - stats.success, stats.framesCreated)

  if #stats.errors > 0 then
    local errorDetail = table.concat(stats.errors, "\n  • ", 1, math.min(5, #stats.errors))
    if #stats.errors > 5 then
      errorDetail = errorDetail .. "\n  ... 等 " .. (#stats.errors - 5) .. " 个错误"
    end
    LrDialogs.message("FilmCrop - 批量处理完成", report .. "\n\n错误详情:\n  • " .. errorDetail, "warning")
  else
    LrDialogs.message("FilmCrop - 批量处理完成", report, "info")
  end
end)
