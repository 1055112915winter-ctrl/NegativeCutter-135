--[[
  FilmCrop 胶片帧检测 - Python分析版本

  工作流程:
  1. 获取缩略图
  2. 调用Python脚本分析帧边界
  3. 方向对齐
  4. 为每帧创建虚拟副本并应用裁剪
]]--

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

--[[
  处理单张照片（自动创建虚拟副本）
]]--
local function processPhotoWithPreview(catalog, photo, i, total, errorMessages, expectedFrames)
  errorMessages = errorMessages or {}
  expectedFrames = expectedFrames or (prefs.expectedFrames or 6)

  local fileName = photo:getFormattedMetadata('fileName')
  logger:trace(string.format("处理文件 %d/%d: %s", i, total, fileName))

  -- 步骤1: 获取缩略图
  local thumbPath, thumbErr = ProcessAgent.extractThumbnail(photo)
  if not thumbPath then
    local msg = fileName .. ": 缩略图获取失败 - " .. (thumbErr or "未知")
    logger:error(msg)
    table.insert(errorMessages, msg)
    return 0
  end

  -- 步骤2: Python 分析
  local originalPath = photo:getRawMetadata("path")
  local result, analyzeError = ProcessAgent.analyzeWithPython(thumbPath, expectedFrames, originalPath)

  if not result or not result.frames or #result.frames == 0 then
    local msg = fileName .. ": 分析失败 - " .. (analyzeError or "未检测到帧")
    logger:error(msg)
    table.insert(errorMessages, msg)
    return 0
  end

  -- 补充 source 尺寸到每帧（供预览对话框使用）
  for _, frame in ipairs(result.frames) do
    frame.sourceHeight = result.sourceHeight
    frame.sourceWidth = result.sourceWidth
  end

  -- 步骤3: 方向对齐
  result = ProcessAgent.directionAlign(result, photo)

  -- 步骤4: 跳过预览，直接使用检测结果
  local frames = result.frames

  -- 补充缺省坐标
  for _, frame in ipairs(frames) do
    frame.top = frame.top or 0
    frame.bottom = frame.bottom or (result.sourceHeight or 1024)
    frame.left = frame.left or 0
    frame.right = frame.right or (result.sourceWidth or 1024)
    frame.relativeTop = frame.relativeTop or 0.0
    frame.relativeBottom = frame.relativeBottom or 1.0
    frame.relativeLeft = frame.relativeLeft or 0.0
    frame.relativeRight = frame.relativeRight or 1.0
  end

  -- 步骤5: 创建虚拟副本并应用裁剪
  local baseName = fileName:gsub("%..+$", "")
  local createdCount = 0

  for frameIdx, frame in ipairs(frames) do
    catalog:setSelectedPhotos(photo, {photo})
    LrTasks.sleep(0.1)

    local virtualCopy = nil
    catalog:withWriteAccessDo(string.format("创建第%d帧虚拟副本", frameIdx), function(context)
      local copies = catalog:createVirtualCopies()
      if copies and #copies > 0 then
        virtualCopy = copies[1]
      end
    end)

    if not virtualCopy then
      table.insert(errorMessages, string.format("%s: 第%d帧虚拟副本创建失败", fileName, frameIdx))
    else
      catalog:setSelectedPhotos(virtualCopy, {virtualCopy})
      LrTasks.sleep(0.2)

      -- 重置持久化裁剪
      catalog:withWriteAccessDo(string.format("重置第%d帧裁剪", frameIdx), function(context)
        ApplierAgent = dofile(LrPathUtils.child(pluginPath, "ApplierAgent.lua"))
        ApplierAgent.resetCrop(virtualCopy)
      end)
      LrTasks.sleep(0.8)

      local sourceW = result.sourceWidth
      local sourceH = result.sourceHeight
      if sourceW and sourceW > 0 and sourceH and sourceH > 0 then
        local applyErr = nil
        catalog:withWriteAccessDo(string.format("应用第%d帧裁剪", frameIdx), function(context)
          local success, err = ApplierAgent.applyCrop(virtualCopy, {
            top = frame.relativeTop,
            bottom = frame.relativeBottom,
            left = frame.relativeLeft or 0,
            right = frame.relativeRight or 1,
            sourceWidth = sourceW,
            sourceHeight = sourceH,
            cropAngle = result.cropAngle or 0
          })
          if not success then applyErr = err or "未知错误" end
        end)

        if applyErr then
          table.insert(errorMessages, string.format("%s: 第%d帧裁剪应用失败 - %s", fileName, frameIdx, applyErr))
        else
          createdCount = createdCount + 1
        end
      end

      local copyName = string.format("%s_帧%02d", baseName, frameIdx)
      pcall(function()
        virtualCopy:setRawMetadata('copyName', copyName)
      end)

      LrTasks.sleep(0.2)
    end
  end

  return createdCount
end

--[[
  主程序
]]--
LrTasks.startAsyncTask(function()
  logger:trace("=" .. string.rep("=", 60))
  logger:trace("FilmCrop Python版检测开始 (v1.5-longedge)")
  logger:trace("=" .. string.rep("=", 60))

  local catalog = LrApplication.activeCatalog()
  local selectedPhotos = catalog:getTargetPhotos()

  if not selectedPhotos or #selectedPhotos == 0 then
    LrDialogs.message("FilmCrop", "请先选择要处理的胶片扫描文件", "info")
    return
  end

  logger:trace(string.format("选中 %d 张照片", #selectedPhotos))

  -- 确认对话框（带预期帧数编辑）
  local f = LrView.osFactory()
  local bind = LrView.bind
  local dialogData = {
    expectedFrames = prefs.expectedFrames or 0
  }

  local messageText = string.format("将对 %d 个文件进行胶片帧检测并创建虚拟副本:", #selectedPhotos)
  for i, photo in ipairs(selectedPhotos) do
    if i <= 3 then
      messageText = messageText .. "\n  • " .. photo:getFormattedMetadata('fileName')
    elseif i == 4 then
      messageText = messageText .. "\n  • ..."
      break
    end
  end

  local contents = f:column {
    spacing = f:control_spacing(),
    bind_to_object = dialogData,
    f:static_text {
      title = messageText,
      height_in_lines = 6,
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
      f:static_text { title = "(填 0 自动检测，或手动指定实际帧数)" },
    },
    f:static_text {
      title = "每帧将创建为一个独立的虚拟副本。",
      height_in_lines = 2,
    },
  }

  local result = LrDialogs.presentModalDialog {
    title = "FilmCrop - 开始检测",
    contents = contents,
    actionVerb = "开始检测",
    cancelVerb = "取消",
  }
  if result ~= "ok" then
    return
  end

  local expectedFrames = tonumber(dialogData.expectedFrames) or (prefs.expectedFrames or 6)
  logger:trace("用户指定的预期帧数: " .. tostring(expectedFrames))

  local processedCount = 0
  local totalVirtualCopies = 0
  local errorMessages = {}

  for i, photo in ipairs(selectedPhotos) do
    local createdCount = processPhotoWithPreview(catalog, photo, i, #selectedPhotos, errorMessages, expectedFrames)
    totalVirtualCopies = totalVirtualCopies + createdCount
    processedCount = processedCount + 1
  end

  logger:trace(string.format("处理完成: %d 个文件, 共创建 %d 个虚拟副本", processedCount, totalVirtualCopies))

  if #errorMessages > 0 then
    local errorMsg = table.concat(errorMessages, "\n")
    if #errorMsg > 500 then
      errorMsg = string.sub(errorMsg, 1, 500) .. "\n... (更多错误)"
    end
    LrDialogs.message(
      "FilmCrop - 处理完成 (部分失败)",
      string.format("成功处理: %d 个文件\n创建虚拟副本: %d\n失败: %d\n\n错误详情:\n%s",
        processedCount, totalVirtualCopies, #errorMessages, errorMsg),
      "warning"
    )
  else
    LrDialogs.message(
      "FilmCrop - 处理完成",
      string.format("成功处理 %d 个文件\n共创建 %d 个虚拟副本\n\n请在图库中查看各个帧的虚拟副本",
        processedCount, totalVirtualCopies),
      "info"
    )
  end
end)
