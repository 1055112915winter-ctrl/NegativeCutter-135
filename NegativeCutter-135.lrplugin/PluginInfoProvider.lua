--[[
  PluginInfoProvider.lua
  提供插件信息到Lightroom
]]--

local LrView = import 'LrView'
local LrPrefs = import 'LrPrefs'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'

local prefs = LrPrefs.prefsForPlugin()
local json = dofile(LrPathUtils.child(_PLUGIN.path, 'json.lua'))

local function shellEscape(value)
  return '"' .. tostring(value):gsub('\\', '\\\\'):gsub('"', '\\"'):gsub('%$', '\\$')
    :gsub('`', '\\`'):gsub('\n', '\\n') .. '"'
end

local function engineSelfTest(path)
  local outputPath = LrPathUtils.child(
    LrPathUtils.getStandardFilePath('temp'),
    'negativecutter-plugin-self-test.json'
  )
  local command = shellEscape(path) .. ' --self-test > ' .. shellEscape(outputPath) .. ' 2>&1'
  local exitCode = LrTasks.execute(command)
  local file = io.open(outputPath, 'r')
  local output = file and (file:read('*a') or '') or ''
  if file then file:close() end
  LrFileUtils.delete(outputPath)
  local firstBrace = output:find('{')
  local payload
  if firstBrace then
    local ok, decoded = pcall(function() return json.decode(output:sub(firstBrace)) end)
    if ok and type(decoded) == 'table' then payload = decoded end
  end
  if exitCode == 0 and payload and payload.ok == true then
    return string.format('✓ 引擎自检通过 (%s, macOS %s)',
      tostring(payload.architecture or '?'), tostring(payload.macOSVersion or '?'))
  end
  local code = payload and payload.errorCode or 'ENGINE_NOT_STARTABLE'
  local detail = payload and payload.error or output:gsub('%s+', ' ')
  local lowerOutput = output:lower()
  if not payload then
    if lowerOutput:find('bad cpu type') or lowerOutput:find('exec format') then
      code = 'UNSUPPORTED_ARCHITECTURE'
    elseif lowerOutput:find('dyld') or lowerOutput:find('library not loaded') then
      code = 'DEPENDENCY_LOAD_FAILED'
    elseif lowerOutput:find('operation not permitted') or lowerOutput:find('code signing')
      or lowerOutput:find('killed') then
      code = 'SIGNATURE_OR_GATEKEEPER_BLOCKED'
    end
  end
  if detail == '' then detail = '进程未返回诊断 JSON' end
  return string.format('✗ 引擎自检失败 [%s]: %s', code, detail:sub(1, 260))
end

return {
  sectionsForTopOfDialog = function(f, propertyTable)
    -- 确保默认值
    if not prefs.pythonPath then
      prefs.pythonPath = '/usr/bin/python3'
    end
    if not prefs.detectorScript then
      prefs.detectorScript = LrPathUtils.child(_PLUGIN.path, 'detect_thumb.py')
    end
    if not prefs.expectedFrames then
      prefs.expectedFrames = 6
    end

    -- 可靠的存在性检查：LrFileUtils.exists 对无后缀二进制文件可能返回 false
    local function fileExists(path)
      if LrFileUtils.exists(path) then return true end
      -- 二进制模式 + pcall：避免文本模式对 Mach-O 可执行文件异常，也避免 open 抛错
      local ok, f = pcall(io.open, path, "rb")
      if ok and f then f:close(); return true end
      return false
    end

    local detectorScript = LrPathUtils.child(_PLUGIN.path, 'detect_thumb.py')
    local bundledExeDir = LrPathUtils.child(_PLUGIN.path, 'NegativeCutter')
    local bundledExe = LrPathUtils.child(bundledExeDir, 'NegativeCutter')
    if not fileExists(bundledExe) then
      bundledExe = LrPathUtils.child(_PLUGIN.path, 'NegativeCutter')
    end
    local hasScript = fileExists(detectorScript)
    local hasExe = fileExists(bundledExe)
    local scriptStatus
    if hasExe then
      scriptStatus = engineSelfTest(bundledExe)
    elseif hasScript then
      scriptStatus = "✗ 只有开发脚本，未找到可运行的打包引擎（不会回退系统 Python）"
    else
      scriptStatus = "✗ 未找到检测引擎"
    end

    return {
      {
        title = "NegativeCutter 负片裁切插件",
        synopsis = "自动识别135胶片帧并创建虚拟副本",

        f:row {
          f:static_text {
            title = "版本: 2.4.7",
          },
        },

        f:row {
          f:static_text {
            title = "检测脚本状态: " .. scriptStatus,
          },
        },

        f:row {
          f:static_text {
            title = "使用方法:",
            font = "<system/bold>",
          },
        },

        f:static_text {
          title = "1. 在图库中选择DNG/TIFF格式的胶片扫描文件\n" ..
                  "2. 使用菜单: 文件 > 增效工具额外命令 > NegativeCutter > 检测胶片帧\n" ..
                  "3. 插件将自动检测帧边界并创建虚拟副本\n" ..
                  "4. 每个虚拟副本将应用对应的裁剪",
          height_in_lines = 4,
        },
      },
    }
  end,
}
