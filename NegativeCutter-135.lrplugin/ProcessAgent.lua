--[[
  ProcessAgent.lua — NegativeCutter 共享处理核心
  提供 Python 检测 + 方向对齐 + 虚拟副本创建的通用流程，
  被 DetectFrames.lua（带预览）和 BatchProcess.lua（无预览）共享。
]]

local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'
local LrPrefs = import 'LrPrefs'

local pluginPath = _PLUGIN.path
local WORK_DIR = LrPathUtils.child(LrPathUtils.getStandardFilePath("temp"), "negativecutter")

-- Lr Lua sandbox does NOT register a `json` toolkit script; require("json")
-- fails with "Could not load toolkit script: json". Load the bundled pure-
-- Lua decoder via dofile instead.
local json = dofile(LrPathUtils.child(pluginPath, "json.lua"))

local ThumbnailAgent = dofile(LrPathUtils.child(pluginPath, "ThumbnailAgent.lua"))
local ApplierAgent = dofile(LrPathUtils.child(pluginPath, "ApplierAgent.lua"))
local CropCleaner = dofile(LrPathUtils.child(pluginPath, "CropCleaner.lua"))

local logger = LrLogger('NegativeCutter.ProcessAgent')
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
-- parseJSON — 解析 detect_thumb.py 的 stdout JSON (uses require("json"))
-- ------------------------------------------------------------------
function ProcessAgent.parseJSON(jsonStr)
  local emptyResult = {
    frameCount = 0, sourceWidth = 0, sourceHeight = 0,
    cropAngle = 0.0, isHorizontal = false, frames = {},
  }
  if type(jsonStr) ~= "string" or jsonStr == "" then return emptyResult end

  -- Strip leading non-JSON noise (e.g. Python [Perf] logs or warnings on stderr)
  local firstBrace = string.find(jsonStr, "{")
  if not firstBrace then return emptyResult end
  jsonStr = string.sub(jsonStr, firstBrace)

  local ok, raw = pcall(function() return json.decode(jsonStr) end)
  if not ok or type(raw) ~= "table" then return emptyResult end

  local result = {
    frameCount   = tonumber(raw.frameCount) or 0,
    sourceWidth  = tonumber(raw.sourceWidth) or 0,
    sourceHeight = tonumber(raw.sourceHeight) or 0,
    cropAngle    = tonumber(raw.cropAngle) or 0.0,
    error        = raw.error,
    _diag        = raw._diag,
    debug        = raw.debug,
    loader       = raw.loader,
    decodedWidth = tonumber(raw.decodedWidth),
    decodedHeight = tonumber(raw.decodedHeight),
    lrWidth      = tonumber(raw.lrWidth),
    lrHeight     = tonumber(raw.lrHeight),
  }

  if type(raw.debug) == "table" and type(raw.debug.isHorizontal) == "boolean" then
    result.isHorizontal = raw.debug.isHorizontal
  else
    result.isHorizontal = result.sourceWidth >= result.sourceHeight
  end

  result.frames = {}
  if type(raw.frames) == "table" then
    local sw = result.sourceWidth > 0 and result.sourceWidth or 1
    for _, f in ipairs(raw.frames) do
      if type(f) == "table" and f.index and f.top and f.bottom then
        local frame = {
          index          = tonumber(f.index),
          top            = tonumber(f.top),
          bottom         = tonumber(f.bottom),
          left           = tonumber(f.left),
          right          = tonumber(f.right),
          relativeTop    = tonumber(f.relativeTop) or 0.0,
          relativeBottom = tonumber(f.relativeBottom) or 1.0,
          relativeLeft   = tonumber(f.relativeLeft),
          relativeRight  = tonumber(f.relativeRight),
        }
        if not frame.relativeLeft then
          frame.relativeLeft = (frame.left or 0) / sw
        end
        if not frame.relativeRight then
          frame.relativeRight = (frame.right or sw) / sw
        end
        table.insert(result.frames, frame)
      end
    end
  end

  return result
end

-- ------------------------------------------------------------------
-- analyzeWithPython — 调用 detect_thumb.py 并返回解析结果
-- ------------------------------------------------------------------
function ProcessAgent.analyzeWithPython(thumbPath, expectedFrames, originalPath, formatHint, lrWidth, lrHeight)
  -- 确保工作目录存在（可能被独立调用，ThumbnailAgent 尚未初始化）
  if not LrFileUtils.exists(WORK_DIR) then
    LrFileUtils.createAllDirectories(WORK_DIR)
  end

  -- 引擎选择策略：
  -- 1. 优先使用 PyInstaller 打包的 NegativeCutter 可执行文件（分发场景，无需用户安装依赖）
  -- 2. 若不存在，则 fallback 到 detect_thumb.py + 系统 Python 3（开发/调试场景）
  local pyPath = ProcessAgent.findPythonPath()
  local scriptPath = LrPathUtils.child(pluginPath, "detect_thumb.py")
  local exePath = LrPathUtils.child(pluginPath, "NegativeCutter")
  local usePython = LrFileUtils.exists(scriptPath)
  local useExe = LrFileUtils.exists(exePath)

  if not usePython and not useExe then
    return nil, "检测引擎不存在: 未找到 NegativeCutter 可执行文件也未找到 detect_thumb.py"
  end

  -- 优先使用缩略图；若缩略图不可用，尝试原图
  local inputPath = thumbPath
  if not LrFileUtils.exists(thumbPath) then
    if originalPath and LrFileUtils.exists(originalPath) then
      logger:trace("缩略图不可用，fallback 到原图: " .. originalPath)
      inputPath = originalPath
    else
      return nil, "缩略图不存在且无原图 fallback: " .. (thumbPath or "nil")
    end
  end

    -- 安全地转义 shell 参数：将反斜杠和双引号进行转义，用于引号包裹
  local function shellEscape(s)
    if type(s) ~= "string" then
      return '""'
    end
    -- POSIX sh: 反斜杠转义反斜杠和双引号，再用双引号包裹
    return '"' .. s:gsub('\\', '\\\\'):gsub('"', '\\"') .. '"'
  end

  local cmd
  if useExe then
    -- 优先使用 PyInstaller 打包的可执行文件（分发场景，无需用户安装 Python 依赖）
    cmd = string.format('%s %s --frames %d --cleanup-scale 0.50',
      shellEscape(exePath), shellEscape(inputPath), expectedFrames)
    logger:trace("使用打包的可执行文件: " .. exePath)
  elseif usePython then
    -- fallback 到 Python 3 直接运行（开发版本，便于快速迭代）
    cmd = string.format('%s %s %s --frames %d --cleanup-scale 0.50',
      shellEscape(pyPath), shellEscape(scriptPath), shellEscape(inputPath), expectedFrames)
    logger:trace("使用 Python 3 直接运行 detect_thumb.py: " .. pyPath)
  end

  if originalPath and LrFileUtils.exists(originalPath) then
    cmd = cmd .. ' --original ' .. shellEscape(originalPath)
  end

  if formatHint and formatHint ~= "" then
    cmd = cmd .. ' --format ' .. shellEscape(formatHint)
  end

  if lrWidth and lrHeight then
    cmd = cmd .. string.format(' --lr-width %d --lr-height %d', lrWidth, lrHeight)
  end

  local tempOutputFile = LrPathUtils.child(WORK_DIR, "output_" .. tostring(math.random(10000)) .. ".txt")
  -- 同时捕获 stderr，便于诊断异常
  local shellCmd = cmd .. ' > ' .. shellEscape(tempOutputFile) .. ' 2>&1'
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
    local err = string.format("检测引擎执行失败 (路径: %s, 退出码: %d)", exePath, exitCode)
    if #output > 0 then err = err .. ": " .. string.sub(output, 1, 2000) end
    return nil, err
  end

  if #output == 0 then
    return nil, "检测引擎无输出 (路径: " .. exePath .. ")"
  end

  local result = ProcessAgent.parseJSON(output)
  if not result then return nil, "无法解析JSON输出" end
  if result.error then
    local detail = result.error
    if result.loader or result.decodedWidth then
      detail = detail .. string.format(" (loader=%s, decoded=%sx%s, lr=%sx%s)",
        tostring(result.loader or "?"),
        tostring(result.decodedWidth or "?"),
        tostring(result.decodedHeight or "?"),
        tostring(result.lrWidth or "?"),
        tostring(result.lrHeight or "?"))
    end
    return nil, detail
  end
  if not result.frames or #result.frames == 0 then return nil, "未检测到帧" end

  -- Log diagnostic info if available
  if result._diag then
    logger:trace(string.format("Python诊断: exe=%s, ver=%s, mtime=%s",
      result._diag.pythonExecutable or "?",
      result._diag.pythonVersion or "?",
      result._diag.detectorMtime or "?"))
  end
  if result.debug then
    logger:trace(string.format("DNG诊断: loader=%s, decoded=%sx%s, lr=%sx%s",
      tostring(result.debug.loader or result.loader or "?"),
      tostring(result.debug.decodedWidth or result.decodedWidth or "?"),
      tostring(result.debug.decodedHeight or result.decodedHeight or "?"),
      tostring(result.debug.lrWidth or result.lrWidth or "?"),
      tostring(result.debug.lrHeight or result.lrHeight or "?")))
  elseif result.loader or result.decodedWidth or result.lrWidth then
    logger:trace(string.format("DNG诊断: loader=%s, decoded=%sx%s, lr=%sx%s",
      tostring(result.loader or "?"),
      tostring(result.decodedWidth or "?"),
      tostring(result.decodedHeight or "?"),
      tostring(result.lrWidth or "?"),
      tostring(result.lrHeight or "?")))
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

  -- Attempt to read Lightroom's orientation string (AB/BC/CD/DA).
  -- When present, this gives an unambiguous rotation direction.
  local ok, lrOrientation = pcall(function()
    return photo:getRawMetadata("orientation")
  end)
  lrOrientation = (ok and type(lrOrientation) == "string") and lrOrientation or nil

  logger:trace(string.format("directionAlign: pyH=%s, lrH=%s, lrOrient=%s, lrW=%d, lrH=%d, srcW=%d, srcH=%d",
    tostring(isPyHorizontal), tostring(isLrHorizontal), tostring(lrOrientation),
    lrWidth, lrHeight, result.sourceWidth or 0, result.sourceHeight or 0))

  local needsRotate = false
  local rotate180 = false

  if lrOrientation == "CD" then
    -- Explicit 180° rotation. Aspect-ratio heuristic misses this because
    -- width/height stay the same, so we rely on the orientation tag.
    needsRotate = true
    rotate180 = true
    logger:trace("orientation=CD, applying 180° rotation")
  elseif isPyHorizontal ~= isLrHorizontal then
    -- 90° mismatch (BC or DA). Existing logic covers both correctly for
    -- thumbnail-based detection because the aspect-ratio flip is symmetric.
    needsRotate = true
    logger:trace("方向不一致，旋转坐标...")
  end

  if not needsRotate then
    return result
  end

  for _, frame in ipairs(result.frames) do
    local origRelTop = frame.relativeTop or 0.0
    local origRelBottom = frame.relativeBottom or 1.0
    local origRelLeft = frame.relativeLeft or 0.0
    local origRelRight = frame.relativeRight or 1.0

    if rotate180 then
      -- 180°: mirror around centre
      frame.relativeTop = 1.0 - origRelBottom
      frame.relativeBottom = 1.0 - origRelTop
      frame.relativeLeft = 1.0 - origRelRight
      frame.relativeRight = 1.0 - origRelLeft
    else
      -- 90° rotation (existing behaviour)
      frame.relativeTop = origRelLeft
      frame.relativeBottom = origRelRight
      frame.relativeLeft = origRelTop
      frame.relativeRight = origRelBottom
    end

    frame.top = math.floor(frame.relativeTop * lrHeight)
    frame.bottom = math.floor(frame.relativeBottom * lrHeight)
    frame.left = math.floor(frame.relativeLeft * lrWidth)
    frame.right = math.floor(frame.relativeRight * lrWidth)
  end

  result.sourceWidth = lrWidth
  result.sourceHeight = lrHeight

  if rotate180 then
    -- 180°: the rotation axis is flipped twice; sign stays the same.
    -- No change to cropAngle.
  else
    -- 90°: negate the angle so the correction is applied in the new orientation.
    result.cropAngle = -(result.cropAngle or 0)
  end

  for _, frame in ipairs(result.frames) do
    frame.sourceWidth = lrWidth
    frame.sourceHeight = lrHeight
  end

  return result
end

-- ------------------------------------------------------------------
-- extractThumbnail — 获取缩略图（带等待）
-- ------------------------------------------------------------------
function ProcessAgent.extractThumbnail(photo, maxWidth)
  maxWidth = maxWidth or 2048
  local thumbSuccess, thumbPath, thumbError = nil, nil, nil

  ThumbnailAgent.extract(photo, maxWidth, function(success, path, err)
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
function ProcessAgent.detectAndCrop(catalog, photo, expectedFrames, fileName, formatHint)
  local baseName = fileName:gsub("%..+$", "")

  -- 步骤1: 获取缩略图
  local thumbPath, thumbErr = ProcessAgent.extractThumbnail(photo)
  if not thumbPath then
    logger:trace("缩略图获取失败: " .. (thumbErr or "未知") .. "，尝试原图 fallback")
  end

  -- 步骤2: Python 分析（缩略图失败时 fallback 到原图）
  local originalPath = photo:getRawMetadata("path")
  local photoDimensions = photo:getRawMetadata("dimensions")
  local lrWidth = photoDimensions and photoDimensions.width or nil
  local lrHeight = photoDimensions and photoDimensions.height or nil
  local result, analyzeError = ProcessAgent.analyzeWithPython(
    thumbPath, expectedFrames, originalPath, formatHint, lrWidth, lrHeight)
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

  -- 使用 CropCleaner 按胶片类型清理边界
  local filmType = prefs.filmType or "negative"
  CropCleaner.cleanFrames(frames, result.sourceWidth, result.sourceHeight, filmType)

  for _, frame in ipairs(frames) do
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
        local copyName = string.format("%s_帧%02d", baseName, frameIdx)
        virtualCopy:setRawMetadata('copyName', copyName)
      end)

      createdCount = createdCount + 1
      LrTasks.sleep(0.2)
    end
  end

  return createdCount, nil
end

-- ------------------------------------------------------------------
-- openSponsorImage — 赞助弹窗
-- ------------------------------------------------------------------
function ProcessAgent.openSponsorImage()
  local LrDialogs = import 'LrDialogs'
  local LrView = import 'LrView'

  local f = LrView.osFactory()

  -- 查找赞赏码图片
  local sponsorPath = LrPathUtils.child(pluginPath, "sponsor.png")
  if LrFileUtils.exists(sponsorPath) ~= true then
    sponsorPath = LrPathUtils.child(pluginPath, "sponsor.jpg")
  end
  local hasSponsor = LrFileUtils.exists(sponsorPath)

  -- 赞赏码不存在：直接提示，不放无效按钮
  if not hasSponsor then
    LrDialogs.message(
      "支持 NegativeCutter",
      "请将赞赏码截图命名为 sponsor.png 或 sponsor.jpg，\n放在插件目录后即可扫码支持。\n\n作者：李冬天（小红书：李冬天 SimplyWinter）",
      "info"
    )
    return
  end

  -- 赞赏码存在：简洁双按钮弹窗（打开赞赏码 / 关闭）
  local result = LrDialogs.confirm(
    "☕ 请作者喝咖啡",
    "从 135 胶片扫描中自动识别帧边界，省去逐张手动裁剪的繁琐。\n\n如果你发现它节省了时间，一杯咖啡（¥19.9）将帮助我\n持续优化检测算法、适配更多胶片格式。",
    "打开赞赏码",
    "关闭"
  )

  if result == "ok" then
    logger:trace("打开赞赏码: " .. sponsorPath)
    if MAC_ENV then
      LrTasks.execute('open "' .. sponsorPath .. '"')
    elseif WIN_ENV then
      LrTasks.execute('start "" "' .. sponsorPath .. '"')
    end
  end
end

return ProcessAgent
