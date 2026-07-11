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

-- 可靠的文件存在性检查：LrFileUtils.exists 对无后缀二进制文件可能返回 false，
-- 补一个 io.open 兜底以保证引擎检测不误判。
local function fileExists(path)
  if LrFileUtils.exists(path) then return true end
  -- 二进制模式 + pcall：避免文本模式对 Mach-O 可执行文件异常，也避免 open 抛错
  local ok, f = pcall(io.open, path, "rb")
  if ok and f then f:close(); return true end
  return false
end

local function removeFile(path)
  if type(path) ~= "string" or path == "" or not LrFileUtils.delete then return false end
  local ok = pcall(function() LrFileUtils.delete(path) end)
  return ok
end

local ProcessAgent = {}

local function deepCopy(value)
  if type(value) ~= "table" then return value end
  local copy = {}
  for key, item in pairs(value) do copy[key] = deepCopy(item) end
  return copy
end

local function finiteNumber(value, default)
  local number = tonumber(value)
  if not number or number ~= number or number == math.huge or number == -math.huge then return default or 0 end
  return number
end

local function bankersRound(value)
  local lower = math.floor(value)
  local fraction = value - lower
  if fraction < 0.5 then return lower end
  if fraction > 0.5 then return lower + 1 end
  return lower % 2 == 0 and lower or lower + 1
end

local function roundedRelative(value)
  return bankersRound(value * 1000000) / 1000000
end

local function axisBounds(first, last, size)
  size = math.floor(size)
  local minimum = math.min(20, size)
  first = math.max(0, math.min(bankersRound(first), size))
  last = math.max(0, math.min(bankersRound(last), size))
  if last < first then first, last = last, first end
  if last - first < minimum then
    last = math.min(size, first + minimum)
    first = math.max(0, last - minimum)
  end
  return first, last
end

local function shellEscape(value)
  if type(value) ~= "string" then return '""' end
  return '"' .. value:gsub('\\', '\\\\'):gsub('"', '\\"'):gsub('%$', '\\$')
    :gsub('`', '\\`'):gsub('\n', '\\n') .. '"'
end

local function packagedEnginePath()
  local onedir = LrPathUtils.child(pluginPath, "NegativeCutter")
  local executable = LrPathUtils.child(onedir, "NegativeCutter")
  if fileExists(executable) then return executable end
  executable = LrPathUtils.child(pluginPath, "NegativeCutter")
  if fileExists(executable) then return executable end
  return nil
end

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

  -- 仅使用 PyInstaller onedir 打包的 NegativeCutter 可执行文件。
  -- 如果它无法执行，直接报错，不 fallback 到 Python 脚本，避免掩盖环境问题。
  local onedirSource = LrPathUtils.child(pluginPath, "NegativeCutter")
  local localExePath = LrPathUtils.child(onedirSource, "NegativeCutter")
  if not fileExists(localExePath) then
    localExePath = LrPathUtils.child(pluginPath, "NegativeCutter")
    onedirSource = nil  -- onefile 模式，无 onedir 目录可复制
  end

  if not fileExists(localExePath) then
    return nil, "检测引擎不存在: 未找到 NegativeCutter 可执行文件"
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

  -- 安全地转义 POSIX sh 参数：在双引号内处理反斜杠、双引号、美元符、反引号、换行
  local function shellEscape(s)
    if type(s) ~= "string" then
      return '""'
    end
    -- Lua 模式匹配中 $ 是特殊字符（字符串末尾锚点），匹配字面 $ 必须用 %$。
    -- 原 :gsub('$', '\\$') 会在所有字符串末尾插入 \\$，导致路径末尾多出一个 $，
    -- 在 shell 中执行时提示 "No such file or directory"（退出码 127 / 32512）。
    return '"' .. s
      :gsub('\\', '\\\\')
      :gsub('"', '\\"')
      :gsub('%$', '\\$')
      :gsub('`', '\\`')
      :gsub('\n', '\\n')
      .. '"'
  end

  -- 直接在插件目录内执行 PyInstaller onedir 可执行文件。
  -- shellEscape 已修复（Lua 模式 %$ 匹配字面 $），中文/空格路径可安全传递。
  -- 不再复制到临时目录：逐文件 LrFileUtils.copy 对 Mach-O/.dylib 等文件不可靠。
  local exePath = localExePath
  logger:trace("使用插件目录引擎: " .. exePath)

  local cmd = string.format('%s %s --frames %d --cleanup-scale 0.50',
    shellEscape(exePath), shellEscape(inputPath), expectedFrames)

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
    -- 系统级执行失败检测。以下信号表明 shell/OS/dyld 阻止了执行，而非
    -- Python 检测逻辑错误。对这类失败尝试 cp -R 到临时目录后重试。
    --
    -- 32512 = 127 << 8（shell "command not found" 或 dyld 加载失败）。
    -- exitCode <= 31 通常是进程被信号杀死（SIGKILL=9、SIGBUS=10、
    -- SIGSEGV=11 等），常见于 macOS Gatekeeper/SIP 干预。
    --
    -- 额外检查输出中是否包含已知系统错误关键词，覆盖退出码不标准但
    -- 同样是 OS 层阻止的情况。
    local isSystemFailure = (
      exitCode == 32512 or
      (exitCode >= 1 and exitCode <= 31)
    )
    if not isSystemFailure and #output > 0 then
      local lowerOutput = string.lower(output)
      isSystemFailure = (
        lowerOutput:find("dyld") ~= nil or
        lowerOutput:find("library not loaded") ~= nil or
        lowerOutput:find("operation not permitted") ~= nil or
        lowerOutput:find("killed") ~= nil or
        lowerOutput:find("command not found") ~= nil or
        lowerOutput:find("cannot execute") ~= nil or
        lowerOutput:find("bad cpu type") ~= nil or
        lowerOutput:find("no such file") ~= nil or
        lowerOutput:find("permission denied") ~= nil or
        lowerOutput:find("code signing") ~= nil or
        lowerOutput:find("terminated") ~= nil
      )
    end

    if isSystemFailure and onedirSource then
      local runtimeRoot = LrPathUtils.child(LrPathUtils.getStandardFilePath("temp"), "NegativeCutter_Runtime")
      local runtimeExeDir = LrPathUtils.child(runtimeRoot, "NegativeCutter")
      local runtimeExePath = LrPathUtils.child(runtimeExeDir, "NegativeCutter")

      logger:error(string.format("引擎执行失败 (exit=%d)，尝试 cp -R 到 %s 后重试", exitCode, runtimeExeDir))
      LrTasks.execute(string.format('rm -rf %s', shellEscape(runtimeRoot)))
      local cpCmd = string.format('cp -RL %s %s',
        shellEscape(onedirSource), shellEscape(runtimeExeDir))
      local cpExit = LrTasks.execute(cpCmd)
      if cpExit == 0 then
        LrTasks.execute(string.format('chmod +x %s', shellEscape(runtimeExePath)))
        local retryCmd = cmd .. ' > ' .. shellEscape(tempOutputFile) .. ' 2>&1'
        exitCode = LrTasks.execute(retryCmd)
        local retryFile = io.open(tempOutputFile, "r")
        if retryFile then
          output = retryFile:read("*a") or ""
          retryFile:close()
          LrFileUtils.delete(tempOutputFile)
        end
        logger:trace(string.format("analyzeWithPython cp-R retry exit=%d, len=%d", exitCode, #output))
      else
        logger:error(string.format("cp -R 复制失败 (退出码 %d)，无法重试", cpExit))
      end
    end

    if exitCode ~= 0 then
      local err = string.format("检测引擎执行失败 (路径: %s, 退出码: %d)", exePath, exitCode)
      if #output > 0 then err = err .. ": " .. string.sub(output, 1, 2000) end
      return nil, err
    end
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
  local rotationMode = nil

  if lrOrientation == "CD" then
    -- Explicit 180° rotation. Aspect-ratio heuristic misses this because
    -- width/height stay the same, so we rely on the orientation tag.
    needsRotate = true
    rotationMode = "CD"
    logger:trace("orientation=CD, applying 180° rotation")
  elseif isPyHorizontal ~= isLrHorizontal then
    -- 90° mismatch. BC and DA are different transforms; treating both as a
    -- plain transpose only appears correct for centred/symmetric rectangles.
    needsRotate = true
    if lrOrientation == "BC" or lrOrientation == "DA" then
      rotationMode = lrOrientation
    else
      rotationMode = "transpose"
    end
    logger:trace("方向不一致，按 " .. rotationMode .. " 旋转坐标...")
  end

  if not needsRotate then
    return result
  end

  for _, frame in ipairs(result.frames) do
    local origRelTop = frame.relativeTop or 0.0
    local origRelBottom = frame.relativeBottom or 1.0
    local origRelLeft = frame.relativeLeft or 0.0
    local origRelRight = frame.relativeRight or 1.0

    if rotationMode == "CD" then
      -- 180°: mirror around centre
      frame.relativeTop = 1.0 - origRelBottom
      frame.relativeBottom = 1.0 - origRelTop
      frame.relativeLeft = 1.0 - origRelRight
      frame.relativeRight = 1.0 - origRelLeft
    elseif rotationMode == "BC" then
      -- 90° clockwise: (t,b,l,r) -> (1-r,1-l,t,b)
      frame.relativeTop = 1.0 - origRelRight
      frame.relativeBottom = 1.0 - origRelLeft
      frame.relativeLeft = origRelTop
      frame.relativeRight = origRelBottom
    elseif rotationMode == "DA" then
      -- 90° counter-clockwise: (t,b,l,r) -> (l,r,1-b,1-t)
      frame.relativeTop = origRelLeft
      frame.relativeBottom = origRelRight
      frame.relativeLeft = 1.0 - origRelBottom
      frame.relativeRight = 1.0 - origRelTop
    else
      -- Metadata unavailable: retain the historical transpose fallback.
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

  if rotationMode == "CD" then
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
-- renderPreview — packaged-engine preview invocation. Temporary request and
-- result files are owned by this call; the dialog directory remains caller-owned.
-- ------------------------------------------------------------------
function ProcessAgent.renderPreview(request)
  request = request or {}
  if type(request.frames) ~= "table" or type(request.thumbnailPath) ~= "string"
    or type(request.outputPath) ~= "string" then return nil, "invalid preview render request" end
  local width, height = tonumber(request.sourceWidth), tonumber(request.sourceHeight)
  if not width or width <= 0 or not height or height <= 0 then return nil, "invalid preview source dimensions" end
  local executable = packagedEnginePath()
  if not executable then return nil, "检测引擎不存在: 未找到 NegativeCutter 可执行文件" end

  local framesPath = request.outputPath .. ".frames.json"
  local resultPath = request.outputPath .. ".result.json"
  local framesFile, writeError = io.open(framesPath, "w")
  if not framesFile then return nil, "无法写入预览帧: " .. tostring(writeError) end
  local encodedOk, encoded = pcall(json.encode, { frames = deepCopy(request.frames) })
  if not encodedOk then framesFile:close(); removeFile(framesPath); return nil, tostring(encoded) end
  framesFile:write(encoded); framesFile:close()

  local offsets = request.offsets or {}
  local command = string.format(
    '%s --render-preview --input %s --frames-json %s --source-width %d --source-height %d --top-px %.6f --bottom-px %.6f --left-px %.6f --right-px %.6f --output %s > %s 2>&1',
    shellEscape(executable), shellEscape(request.thumbnailPath), shellEscape(framesPath), width, height,
    finiteNumber(offsets.topPx), finiteNumber(offsets.bottomPx), finiteNumber(offsets.leftPx), finiteNumber(offsets.rightPx),
    shellEscape(request.outputPath), shellEscape(resultPath))
  local exitCode = LrTasks.execute(command)
  local resultFile = io.open(resultPath, "r")
  local output = resultFile and (resultFile:read("*a") or "") or ""
  if resultFile then resultFile:close() end
  removeFile(framesPath); removeFile(resultPath)
  local jsonLine = output:match("^([^\r\n]+)") or ""
  local decodedOk, payload = pcall(json.decode, jsonLine)
  if exitCode ~= 0 then
    return nil, decodedOk and payload and payload.error or (jsonLine ~= "" and jsonLine or "preview renderer failed")
  end
  if not decodedOk or type(payload) ~= "table" or payload.error then return nil, "invalid preview renderer output" end
  if payload.previewPath ~= request.outputPath or type(payload.frames) ~= "table" or not fileExists(request.outputPath) then
    return nil, "preview renderer output validation failed"
  end
  return { outputPath = request.outputPath, frames = deepCopy(payload.frames) }, nil
end

local function refreshAbsoluteFrames(frames, width, height)
  for _, frame in ipairs(frames or {}) do
    local top = math.max(0, math.min(bankersRound(finiteNumber(frame.relativeTop, 0) * height), height))
    local bottom = math.max(0, math.min(bankersRound(finiteNumber(frame.relativeBottom, 1) * height), height))
    local left = math.max(0, math.min(bankersRound(finiteNumber(frame.relativeLeft, 0) * width), width))
    local right = math.max(0, math.min(bankersRound(finiteNumber(frame.relativeRight, 1) * width), width))
    if bottom < top then top, bottom = bottom, top end
    if right < left then left, right = right, left end
    frame.top, frame.bottom, frame.left, frame.right = top, bottom, left, right
    frame.relativeTop, frame.relativeBottom = roundedRelative(top / height), roundedRelative(bottom / height)
    frame.relativeLeft, frame.relativeRight = roundedRelative(left / width), roundedRelative(right / width)
    frame.sourceWidth, frame.sourceHeight = width, height
  end
end

function ProcessAgent.detectPhoto(photo, options)
  options = options or {}
  local onStage = options.onStage or function() end
  local fileName = photo:getFormattedMetadata("fileName")
  local originalPath = photo:getRawMetadata("path")
  onStage("thumbnail")
  local thumbnailPath, thumbnailError = ProcessAgent.extractThumbnail(photo, options.thumbnailWidth or 2048)
  if not thumbnailPath then
    if type(originalPath) ~= "string" or originalPath == "" then
      return nil, "缩略图获取失败 - " .. tostring(thumbnailError or "未知")
    end
    thumbnailPath = originalPath
  end
  local dimensions = photo:getRawMetadata("dimensions") or {}
  onStage("recognition")
  local result, recognitionError = ProcessAgent.analyzeWithPython(thumbnailPath, options.expectedFrames or prefs.expectedFrames or 6,
    originalPath, options.formatHint, dimensions.width, dimensions.height)
  if not result or type(result.frames) ~= "table" or #result.frames == 0 then
    return nil, "分析失败 - " .. tostring(recognitionError or "未检测到帧")
  end
  result = ProcessAgent.directionAlign(result, photo)
  local width, height = tonumber(result.sourceWidth), tonumber(result.sourceHeight)
  if not width or width <= 0 or not height or height <= 0 then return nil, "检测结果尺寸无效" end
  onStage("cleanup")
  local frames = result.frames
  local filmType = options.filmType or prefs.filmType or "negative"
  CropCleaner.cleanFrames(frames, result.sourceWidth, result.sourceHeight, filmType)
  refreshAbsoluteFrames(frames, width, height)
  return {
    photo = photo, fileName = fileName, thumbnailPath = thumbnailPath,
    frames = deepCopy(result.frames), sourceWidth = width, sourceHeight = height,
    cropAngle = result.cropAngle or 0,
  }, nil
end

function ProcessAgent.adjustDetection(detection, offsets)
  if type(detection) ~= "table" or type(detection.frames) ~= "table" then return nil, "invalid detection" end
  if detection._previewAdjusted then return nil, "detection already adjusted" end
  local width, height = tonumber(detection.sourceWidth), tonumber(detection.sourceHeight)
  if not width or width <= 0 or not height or height <= 0 then return nil, "invalid detection dimensions" end
  offsets = offsets or {}
  local adjusted = deepCopy(detection)
  adjusted._previewAdjusted = true
  for _, frame in ipairs(adjusted.frames) do
    local top = finiteNumber(frame.relativeTop, 0) * height - finiteNumber(offsets.topPx)
    local bottom = finiteNumber(frame.relativeBottom, 1) * height + finiteNumber(offsets.bottomPx)
    local left = finiteNumber(frame.relativeLeft, 0) * width - finiteNumber(offsets.leftPx)
    local right = finiteNumber(frame.relativeRight, 1) * width + finiteNumber(offsets.rightPx)
    top, bottom = axisBounds(top, bottom, height)
    left, right = axisBounds(left, right, width)
    frame.top, frame.bottom, frame.left, frame.right = top, bottom, left, right
    frame.relativeTop, frame.relativeBottom = roundedRelative(top / height), roundedRelative(bottom / height)
    frame.relativeLeft, frame.relativeRight = roundedRelative(left / width), roundedRelative(right / width)
    frame.sourceWidth, frame.sourceHeight = width, height
  end
  return adjusted, nil
end

function ProcessAgent.createVirtualCopies(catalog, detection, options)
  options = options or {}
  local summary = { status = "success", createdCount = 0, attemptedFrames = 0, errors = {}, warnings = {} }
  local isCanceled, onStage = options.isCanceled or function() return false end, options.onStage or function() end
  local baseName = tostring(detection.fileName or "scan"):gsub("%..+$", "")
  for frameIndex, frame in ipairs(detection.frames or {}) do
    if isCanceled() then summary.status = "canceled"; return summary end
    summary.attemptedFrames = summary.attemptedFrames + 1
    onStage("frame", frameIndex, #(detection.frames or {}))
    catalog:setSelectedPhotos(detection.photo, { detection.photo }); LrTasks.sleep(0.1)
    local virtualCopy
    catalog:withWriteAccessDo("创建虚拟副本", function()
      local copies = catalog:createVirtualCopies()
      if copies and #copies > 0 then virtualCopy = copies[1] end
    end)
    if not virtualCopy then
      summary.errors[#summary.errors + 1] = string.format("%s: 第%d帧虚拟副本创建失败", detection.fileName or "scan", frameIndex)
    else
      catalog:setSelectedPhotos(virtualCopy, { virtualCopy }); LrTasks.sleep(0.2)
      catalog:withWriteAccessDo("重置裁剪", function() ApplierAgent.resetCrop(virtualCopy) end); LrTasks.sleep(0.8)
      local applyError
      catalog:withWriteAccessDo("应用裁剪", function()
        local success, err = ApplierAgent.applyCrop(virtualCopy, {
          top = frame.relativeTop, bottom = frame.relativeBottom,
          left = frame.relativeLeft or 0, right = frame.relativeRight or 1,
          sourceWidth = detection.sourceWidth, sourceHeight = detection.sourceHeight,
          cropAngle = detection.cropAngle or 0,
        })
        if not success then applyError = err or "未知错误" end
      end)
      if applyError then
        summary.errors[#summary.errors + 1] = string.format("%s: 第%d帧裁剪应用失败 - %s", detection.fileName or "scan", frameIndex, applyError)
      else
        summary.createdCount = summary.createdCount + 1
      end
      local renamed, renameError = pcall(function()
        virtualCopy:setRawMetadata("copyName", string.format("%s_帧%02d", baseName, frameIndex))
      end)
      if not renamed then
        -- Lightroom can reject copy-name metadata on catalogs with restricted
        -- metadata access. The crop itself is already committed, so preserve
        -- the successful copy and report naming as a nonfatal warning.
        summary.warnings[#summary.warnings + 1] = string.format("%s: 第%d帧重命名失败 - %s", detection.fileName or "scan", frameIndex, tostring(renameError))
      end
      LrTasks.sleep(0.2)
    end
  end
  if #summary.errors > 0 then summary.status = "partial_failure" end
  return summary
end

-- Legacy two-return wrapper retained for existing no-preview and HTTP-adjacent callers.
function ProcessAgent.detectAndCrop(catalog, photo, expectedFrames, fileName, formatHint)
  local detection, detectionError = ProcessAgent.detectPhoto(photo, {
    expectedFrames = expectedFrames, formatHint = formatHint, filmType = prefs.filmType,
  })
  if not detection then return 0, detectionError end
  detection.fileName = fileName or detection.fileName
  local summary = ProcessAgent.createVirtualCopies(catalog, detection, {})
  if summary.status ~= "success" then return summary.createdCount, table.concat(summary.errors, "; ") end
  return summary.createdCount, nil
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
