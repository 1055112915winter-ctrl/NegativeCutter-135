--[[
  ProcessAgent.lua — FilmCrop 共享处理核心
  提供 Python 检测 + 方向对齐 + 虚拟副本创建的通用流程，
  被 DetectFrames.lua（带预览）和 BatchProcess.lua（无预览）共享。
]]

local LrApplication = import 'LrApplication'
local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'
local LrPrefs = import 'LrPrefs'

local pluginPath = _PLUGIN.path
local WORK_DIR = LrPathUtils.child(LrPathUtils.getStandardFilePath("temp"), "filmcrop")

local ThumbnailAgent = dofile(LrPathUtils.child(pluginPath, "ThumbnailAgent.lua"))
local ApplierAgent = dofile(LrPathUtils.child(pluginPath, "ApplierAgent.lua"))

local logger = LrLogger('FilmCrop.ProcessAgent')
logger:enable("logfile")

local prefs = LrPrefs.prefsForPlugin()

if not prefs.expectedFrames then
  prefs.expectedFrames = 6
end

local ProcessAgent = {}

-- ------------------------------------------------------------------
-- findPythonPath — 统一查找 Python 3 解释器
-- ------------------------------------------------------------------
local _cachedPythonPath = nil

function ProcessAgent.findPythonPath()
  if _cachedPythonPath then
    return _cachedPythonPath
  end

  local possiblePythons = {"/Library/Frameworks/Python.framework/Versions/3.14/bin/python3", "/usr/bin/python3", "/usr/local/bin/python3", "/opt/homebrew/bin/python3"}
  for _, pyPath in ipairs(possiblePythons) do
    if LrFileUtils.exists(pyPath) then
      _cachedPythonPath = pyPath
      return pyPath
    end
  end

  _cachedPythonPath = "python3"  -- fallback
  return "python3"
end

-- ------------------------------------------------------------------
-- parseJSON — 解析 detect_thumb.py 的 stdout JSON
-- ------------------------------------------------------------------
function ProcessAgent.parseJSON(jsonStr)
  local result = {}
  local cleanStr = jsonStr:gsub("%s+", " ")

  result.frameCount = tonumber(cleanStr:match('"frameCount"%s*:%s*(%d+)')) or 0
  result.sourceWidth = tonumber(cleanStr:match('"sourceWidth"%s*:%s*(%d+)')) or 0
  result.sourceHeight = tonumber(cleanStr:match('"sourceHeight"%s*:%s*(%d+)')) or 0
  result.cropAngle = tonumber(cleanStr:match('"cropAngle"%s*:%s*([%-%d%.]+)')) or 0.0

  local debugSection = cleanStr:match('"debug"%s*:%s*(%b{})')
  if debugSection then
    local isH = debugSection:match('"isHorizontal"%s*:%s*(true|false)')
    if isH == "true" then
      result.isHorizontal = true
    elseif isH == "false" then
      result.isHorizontal = false
    end
  end
  if result.isHorizontal == nil then
    result.isHorizontal = (result.sourceWidth or 0) >= (result.sourceHeight or 0)
  end

  result.frames = {}
  local framesSection = cleanStr:match('"frames"%s*:%s*(%[.-%])')
  if framesSection then
    for frameStr in framesSection:gmatch('%b{}') do
      local frame = {}
      frame.index = tonumber(frameStr:match('"index"%s*:%s*(%d+)'))
      frame.top = tonumber(frameStr:match('"top"%s*:%s*(%d+)'))
      frame.bottom = tonumber(frameStr:match('"bottom"%s*:%s*(%d+)'))
      frame.left = tonumber(frameStr:match('"left"%s*:%s*(%d+)'))
      frame.right = tonumber(frameStr:match('"right"%s*:%s*(%d+)'))
      frame.relativeTop = tonumber(frameStr:match('"relativeTop"%s*:%s*([%d%.]+)')) or 0.0
      frame.relativeBottom = tonumber(frameStr:match('"relativeBottom"%s*:%s*([%d%.]+)')) or 1.0
      frame.relativeLeft = tonumber(frameStr:match('"relativeLeft"%s*:%s*([%d%.]+)'))
      frame.relativeRight = tonumber(frameStr:match('"relativeRight"%s*:%s*([%d%.]+)'))

      if not frame.relativeLeft then
        frame.relativeLeft = (frame.left or 0) / (result.sourceWidth > 0 and result.sourceWidth or 1)
      end
      if not frame.relativeRight then
        frame.relativeRight = (frame.right or (result.sourceWidth or 1024)) / (result.sourceWidth > 0 and result.sourceWidth or 1)
      end

      if frame.index and frame.top and frame.bottom then
        table.insert(result.frames, frame)
      end
    end
  end

  return result
end

-- ------------------------------------------------------------------
-- analyzeWithPython — 调用 detect_thumb.py 并返回解析结果
-- ------------------------------------------------------------------
function ProcessAgent.analyzeWithPython(thumbPath, expectedFrames, originalPath)
  -- 确保工作目录存在（可能被独立调用，ThumbnailAgent 尚未初始化）
  if not LrFileUtils.exists(WORK_DIR) then
    LrFileUtils.createAllDirectories(WORK_DIR)
  end

  local pythonScript = LrPathUtils.child(pluginPath, "detect_thumb.py")

  if not LrFileUtils.exists(pythonScript) then
    return nil, "Python脚本不存在: " .. pythonScript
  end

  -- 优先使用缩略图；若缩略图不可用且原图存在，则 fallback 到原图直接检测
  local inputPath = thumbPath
  if not LrFileUtils.exists(thumbPath) then
    if originalPath and LrFileUtils.exists(originalPath) then
      logger:trace("缩略图不可用，fallback 到原图: " .. originalPath)
      inputPath = originalPath
    else
      return nil, "缩略图不存在且无原图 fallback: " .. (thumbPath or "nil")
    end
  end

  local pythonCmd = ProcessAgent.findPythonPath()
  local cmd = string.format('"%s" "%s" "%s" --frames %d --cleanup-scale 0.50',
    pythonCmd, pythonScript, inputPath, expectedFrames)

  if originalPath and LrFileUtils.exists(originalPath) then
    cmd = cmd .. ' --original "' .. originalPath .. '"'
  end

  local tempOutputFile = LrPathUtils.child(WORK_DIR, "output_" .. tostring(math.random(10000)) .. ".txt")
  -- 同时捕获 stderr，便于诊断 Python 异常
  -- PYTHONDONTWRITEBYTECODE=1 防止 Python 缓存旧的字节码导致代码修改不生效
  local shellCmd = 'PYTHONDONTWRITEBYTECODE=1 ' .. cmd .. ' > "' .. tempOutputFile .. '" 2>&1'
  local exitCode = LrTasks.execute(shellCmd)

  local output = ""
  local file = io.open(tempOutputFile, "r")
  if file then
    output = file:read("*a") or ""
    file:close()
    LrFileUtils.delete(tempOutputFile)
  end

  logger:trace(string.format("analyzeWithPython exit=%d, len=%d", exitCode, #output))
  logger:trace("analyzeWithPython output: " .. string.sub(output, 1, 3000))

  if exitCode ~= 0 then
    local err = string.format("Python执行失败 (路径: %s, 退出码: %d)", pythonCmd, exitCode)
    if #output > 0 then err = err .. ": " .. string.sub(output, 1, 2000) end
    return nil, err
  end

  if #output == 0 then
    return nil, "Python无输出 (路径: " .. pythonCmd .. ")"
  end

  local result = ProcessAgent.parseJSON(output)
  if not result then return nil, "无法解析JSON输出" end
  if result.error then return nil, "Python错误: " .. result.error end
  if not result.frames or #result.frames == 0 then return nil, "未检测到帧" end

  -- Log diagnostic info if available
  if result._diag then
    logger:trace(string.format("Python诊断: exe=%s, ver=%s, mtime=%s",
      result._diag.pythonExecutable or "?",
      result._diag.pythonVersion or "?",
      result._diag.detectorMtime or "?"))
  end

  return result, nil
end

-- ------------------------------------------------------------------
-- directionAlign — EXIF 方向不一致时旋转坐标
-- ------------------------------------------------------------------
function ProcessAgent.directionAlign(result, photo)
  local photoDimensions = photo:getRawMetadata("dimensions")
  local lrWidth = (photoDimensions and photoDimensions.width) or result.sourceWidth or 1024
  local lrHeight = (photoDimensions and photoDimensions.height) or result.sourceHeight or 1024
  local isPyHorizontal = result.isHorizontal
  local isLrHorizontal = lrWidth >= lrHeight

  logger:trace(string.format("directionAlign: pyH=%s, lrH=%s, lrW=%d, lrH=%d, srcW=%d, srcH=%d",
    tostring(isPyHorizontal), tostring(isLrHorizontal), lrWidth, lrHeight, result.sourceWidth or 0, result.sourceHeight or 0))

  if isPyHorizontal ~= isLrHorizontal then
    logger:trace("方向不一致，旋转坐标...")
    for _, frame in ipairs(result.frames) do
      local origRelTop = frame.relativeTop or 0.0
      local origRelBottom = frame.relativeBottom or 1.0
      local origRelLeft = frame.relativeLeft or 0.0
      local origRelRight = frame.relativeRight or 1.0

      frame.relativeTop = origRelLeft
      frame.relativeBottom = origRelRight
      frame.relativeLeft = origRelTop
      frame.relativeRight = origRelBottom

      frame.top = math.floor(frame.relativeTop * lrHeight)
      frame.bottom = math.floor(frame.relativeBottom * lrHeight)
      frame.left = math.floor(frame.relativeLeft * lrWidth)
      frame.right = math.floor(frame.relativeRight * lrWidth)
    end
    result.sourceWidth = lrWidth
    result.sourceHeight = lrHeight
    -- When coordinates are rotated 90°, the crop angle axis is also rotated.
    -- Negate the angle so the correction is applied in the new orientation.
    result.cropAngle = -(result.cropAngle or 0)
    for _, frame in ipairs(result.frames) do
      frame.sourceWidth = lrWidth
      frame.sourceHeight = lrHeight
    end
  end

  return result
end

-- ------------------------------------------------------------------
-- extractThumbnail — 获取缩略图（带等待）
-- ------------------------------------------------------------------
function ProcessAgent.extractThumbnail(photo)
  local thumbSuccess, thumbPath, thumbError = nil, nil, nil

  ThumbnailAgent.extract(photo, 8192, function(success, path, err)
    thumbSuccess = success
    thumbPath = path
    thumbError = err
  end)

  local waitCount = 0
  while thumbSuccess == nil and waitCount < 100 do
    LrTasks.sleep(0.1)
    waitCount = waitCount + 1
  end

  if not thumbSuccess then
    return nil, thumbError or "缩略图获取超时"
  end

  return thumbPath, nil
end

-- ------------------------------------------------------------------
-- detectAndCrop — 完整检测+裁剪流程（不含预览对话框）
-- 返回: createdCount, errorMessage (nil on success)
-- ------------------------------------------------------------------
function ProcessAgent.detectAndCrop(catalog, photo, expectedFrames, fileName)
  local baseName = fileName:gsub("%..+$", "")

  -- 步骤1: 获取缩略图
  local thumbPath, thumbErr = ProcessAgent.extractThumbnail(photo)
  if not thumbPath then
    logger:trace("缩略图获取失败: " .. (thumbErr or "未知") .. "，尝试原图 fallback")
  end

  -- 步骤2: Python 分析（缩略图失败时 fallback 到原图）
  local originalPath = photo:getRawMetadata("path")
  local result, analyzeError = ProcessAgent.analyzeWithPython(thumbPath, expectedFrames, originalPath)
  if not result then
    return 0, "分析失败 - " .. (analyzeError or "未知")
  end

  -- 步骤3: 方向对齐
  result = ProcessAgent.directionAlign(result, photo)

  -- 步骤4: 为每帧创建虚拟副本并应用裁剪
  local frames = result.frames
  local createdCount = 0

  if #frames > 0 then
    local f0 = frames[1]
    logger:trace(string.format("detectAndCrop frame1 coords: top=%.6f bottom=%.6f left=%.6f right=%.6f",
      f0.relativeTop or 0, f0.relativeBottom or 0, f0.relativeLeft or 0, f0.relativeRight or 0))
  end

  for _, frame in ipairs(frames) do
    frame.top = frame.top or 0
    frame.bottom = frame.bottom or (result.sourceHeight or 1024)
    frame.left = frame.left or 0
    frame.right = frame.right or (result.sourceWidth or 1024)
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

      local sourceW = result.sourceWidth
      local sourceH = result.sourceHeight
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
            cropAngle = result.cropAngle or 0
          })
          if not success then applyErr = err end
        end)
        if applyErr then
          logger:error("裁剪应用失败: " .. applyErr)
        end
      end

      pcall(function()
        virtualCopy:setRawMetadata('copyName', copyName)
      end)

      createdCount = createdCount + 1
      LrTasks.sleep(0.2)
    end
  end

  return createdCount, nil
end

return ProcessAgent
