--[[
  Editor.lua — FilmCrop 帧编辑器启动器（深度集成版）

  工作流程:
  1. 获取缩略图
  2. 使用 ProcessAgent 运行检测
  3. 将检测帧写入临时 JSON
  4. 启动 frame_editor_gui.py（阻塞等待）
  5. 读取编辑后的 JSON
  6. 直接创建虚拟副本并应用裁剪
]]--

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'
local LrPrefs = import 'LrPrefs'

local logger = LrLogger('FilmCrop.Editor')
logger:enable("logfile")

local pluginPath = _PLUGIN.path
local ProcessAgent = dofile(LrPathUtils.child(pluginPath, "ProcessAgent.lua"))
local ApplierAgent = dofile(LrPathUtils.child(pluginPath, "ApplierAgent.lua"))

local prefs = LrPrefs.prefsForPlugin()
if not prefs.expectedFrames then
  prefs.expectedFrames = 6
end

LrTasks.startAsyncTask(function()
  logger:trace("=" .. string.rep("=", 60))
  logger:trace("启动帧编辑器（深度集成版）")
  logger:trace("=" .. string.rep("=", 60))

  local LrApplicationView = import 'LrApplicationView'
  local currentModule = LrApplicationView.getCurrentModuleName()
  if currentModule ~= "develop" then
    LrDialogs.message(
      "FilmCrop - 请在修改照片模块中运行",
      "帧编辑器创建虚拟副本需要在「修改照片」模块中运行。",
      "warning"
    )
    return
  end

  local catalog = LrApplication.activeCatalog()
  local selectedPhotos = catalog:getTargetPhotos()

  if not selectedPhotos or #selectedPhotos == 0 then
    LrDialogs.message("FilmCrop", "请先选择要编辑的照片", "info")
    return
  end

  if #selectedPhotos > 1 then
    LrDialogs.message("FilmCrop", "帧编辑器一次只能处理一张照片", "warning")
    return
  end

  local photo = selectedPhotos[1]
  local fileName = photo:getFormattedMetadata('fileName')
  local baseName = fileName:gsub("%..+$", "")
  logger:trace("编辑文件: " .. fileName)

  -- 步骤1: 获取缩略图
  logger:trace("步骤1: 获取缩略图...")
  local thumbPath, thumbErr = ProcessAgent.extractThumbnail(photo)
  if not thumbPath then
    LrDialogs.message("FilmCrop", "缩略图获取失败: " .. (thumbErr or "未知错误"), "warning")
    return
  end

  -- 步骤2: 使用 ProcessAgent 运行检测
  logger:trace("步骤2: 运行帧检测...")
  local originalPath = photo:getRawMetadata("path")
  local result, analyzeError = ProcessAgent.analyzeWithPython(thumbPath, prefs.expectedFrames, originalPath)

  if not result or not result.frames or #result.frames == 0 then
    LrDialogs.message("FilmCrop", "帧检测失败: " .. (analyzeError or "未检测到帧"), "warning")
    return
  end

  -- 方向对齐
  result = ProcessAgent.directionAlign(result, photo)

  -- 步骤3: 将检测帧写入临时 JSON
  local workDir = LrPathUtils.child(LrPathUtils.getStandardFilePath("temp"), "filmcrop")
  if not LrFileUtils.exists(workDir) then
    LrFileUtils.createAllDirectories(workDir)
  end

  local inputJsonPath = LrPathUtils.child(workDir, "editor_input_" .. baseName .. ".json")
  local outputJsonPath = LrPathUtils.child(workDir, "editor_output_" .. baseName .. ".json")

  -- 构建输入 JSON（与 detect_thumb.py 输出格式一致）
  local inputData = {
    frameCount = result.frameCount,
    sourceWidth = result.sourceWidth,
    sourceHeight = result.sourceHeight,
    cropAngle = result.cropAngle or 0,
    frames = {}
  }
  for _, frame in ipairs(result.frames) do
    table.insert(inputData.frames, {
      index = frame.index,
      top = frame.top or 0,
      bottom = frame.bottom or (result.sourceHeight or 1024),
      left = frame.left or 0,
      right = frame.right or (result.sourceWidth or 1024),
      relativeTop = frame.relativeTop or 0.0,
      relativeBottom = frame.relativeBottom or 1.0,
      relativeLeft = frame.relativeLeft or 0.0,
      relativeRight = frame.relativeRight or 1.0,
    })
  end

  local inputFile = io.open(inputJsonPath, "w")
  if not inputFile then
    LrDialogs.message("FilmCrop", "无法创建临时文件", "warning")
    return
  end
  inputFile:write("{")
  inputFile:write('"frameCount":' .. inputData.frameCount .. ',')
  inputFile:write('"sourceWidth":' .. inputData.sourceWidth .. ',')
  inputFile:write('"sourceHeight":' .. inputData.sourceHeight .. ',')
  inputFile:write('"cropAngle":' .. (inputData.cropAngle or 0) .. ',')
  inputFile:write('"frames":[')
  for i, f in ipairs(inputData.frames) do
    if i > 1 then inputFile:write(",") end
    inputFile:write(string.format(
      '{"index":%d,"top":%d,"bottom":%d,"left":%d,"right":%d,"relativeTop":%.6f,"relativeBottom":%.6f,"relativeLeft":%.6f,"relativeRight":%.6f}',
      f.index, f.top, f.bottom, f.left, f.right, f.relativeTop, f.relativeBottom, f.relativeLeft, f.relativeRight))
  end
  inputFile:write("]}")
  inputFile:close()
  logger:trace("输入JSON已写入: " .. inputJsonPath)

  -- 步骤4: 启动 GUI 编辑器（阻塞等待用户完成编辑）
  logger:trace("步骤4: 启动 GUI 编辑器...")
  local guiScript = LrPathUtils.child(pluginPath, "frame_editor_gui.py")
  if not LrFileUtils.exists(guiScript) then
    LrDialogs.message("FilmCrop", "GUI脚本不存在: " .. guiScript, "warning")
    return
  end

  local pythonCmd = ProcessAgent.findPythonPath()
  local isHorizontal = (result.sourceWidth or 0) >= (result.sourceHeight or 0)
  local horizontalFlag = isHorizontal and " --horizontal" or ""

  local cmd = string.format('"%s" "%s" "%s" --frames-json "%s" --output "%s"%s',
    pythonCmd, guiScript, thumbPath, inputJsonPath, outputJsonPath, horizontalFlag)

  logger:trace("启动命令: " .. cmd)
  LrDialogs.message("FilmCrop", "正在启动帧编辑器...\n编辑完成后点击「确认并应用到 Lightroom」", "info")

  -- 阻塞等待 GUI 完成
  local exitCode = LrTasks.execute(cmd)
  logger:trace("GUI 退出码: " .. tostring(exitCode))

  if exitCode ~= 0 then
    LrDialogs.message("FilmCrop", "帧编辑器异常退出 (代码 " .. exitCode .. ")", "warning")
    return
  end

  -- 检查输出文件
  if not LrFileUtils.exists(outputJsonPath) then
    LrDialogs.message("FilmCrop", "未检测到编辑结果，可能您取消了编辑。", "info")
    return
  end

  -- 步骤5: 读取编辑后的 JSON
  logger:trace("步骤5: 读取编辑结果...")
  local outputFile = io.open(outputJsonPath, "r")
  if not outputFile then
    LrDialogs.message("FilmCrop", "无法读取编辑结果", "warning")
    return
  end
  local outputStr = outputFile:read("*a") or ""
  outputFile:close()

  if #outputStr == 0 then
    LrDialogs.message("FilmCrop", "编辑结果为空", "warning")
    return
  end

  local editedResult = ProcessAgent.parseJSON(outputStr)
  if not editedResult or not editedResult.frames or #editedResult.frames == 0 then
    LrDialogs.message("FilmCrop", "编辑结果解析失败", "warning")
    return
  end

  logger:trace(string.format("编辑结果: %d 帧", #editedResult.frames))

  -- 步骤6: 创建虚拟副本并应用裁剪
  logger:trace("步骤6: 创建虚拟副本...")
  local createdCount = 0

  for frameIdx, frame in ipairs(editedResult.frames) do
    frame.top = frame.top or 0
    frame.bottom = frame.bottom or (editedResult.sourceHeight or 1024)
    frame.left = frame.left or 0
    frame.right = frame.right or (editedResult.sourceWidth or 1024)
    frame.relativeTop = frame.relativeTop or 0.0
    frame.relativeBottom = frame.relativeBottom or 1.0
    frame.relativeLeft = frame.relativeLeft or 0.0
    frame.relativeRight = frame.relativeRight or 1.0

    catalog:setSelectedPhotos(photo, {photo})
    LrTasks.sleep(0.1)

    local virtualCopy = nil
    catalog:withWriteAccessDo("创建虚拟副本", function(context)
      local copies = catalog:createVirtualCopies()
      if copies and #copies > 0 then
        virtualCopy = copies[1]
      end
    end)

    if virtualCopy then
      catalog:setSelectedPhotos(virtualCopy, {virtualCopy})
      LrTasks.sleep(0.2)

      catalog:withWriteAccessDo("重置裁剪", function(context)
        ApplierAgent.resetCrop(virtualCopy)
      end)
      LrTasks.sleep(0.8)

      local sourceW = editedResult.sourceWidth
      local sourceH = editedResult.sourceHeight
      if sourceW and sourceW > 0 and sourceH and sourceH > 0 then
        local applyErr = nil
        catalog:withWriteAccessDo("应用裁剪", function(context)
          local success, err = ApplierAgent.applyCrop(virtualCopy, {
            top = frame.relativeTop,
            bottom = frame.relativeBottom,
            left = frame.relativeLeft or 0,
            right = frame.relativeRight or 1,
            sourceWidth = sourceW,
            sourceHeight = sourceH,
            cropAngle = editedResult.cropAngle or 0
          })
          if not success then applyErr = err end
        end)
        if applyErr then
          logger:error("裁剪应用失败: " .. applyErr)
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

  -- 清理临时文件
  pcall(function()
    if LrFileUtils.exists(inputJsonPath) then LrFileUtils.delete(inputJsonPath) end
    if LrFileUtils.exists(outputJsonPath) then LrFileUtils.delete(outputJsonPath) end
  end)

  logger:trace(string.format("编辑器处理完成: 创建 %d 个虚拟副本", createdCount))
  LrDialogs.message(
    "FilmCrop - 编辑器完成",
    string.format("已根据编辑后的边界创建 %d 个虚拟副本。\n\n请在图库中查看。", createdCount),
    "info"
  )
end)
