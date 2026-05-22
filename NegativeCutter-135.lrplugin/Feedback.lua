--[[
  Feedback.lua
  一键问题反馈 — 自动收集诊断信息并打包到桌面

  流程:
    1. 收集环境信息 + 最近处理参数 + 照片完整元数据
    2. 查找并复制 Lightroom 插件日志（自动匹配 LrClassicLogs 目录）
    3. 打包成 zip（diagnostic.txt + 所有日志）保存到桌面
    4. 提示用户将 zip 文件发送给作者
]]--

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'
local LrPrefs = import 'LrPrefs'
local LrView = import 'LrView'

local pluginPath = _PLUGIN.path
local logger = LrLogger('NegativeCutter.Feedback')
logger:enable("logfile")

local prefs = LrPrefs.prefsForPlugin()

-- ------------------------------------------------------------------
-- 获取 Lightroom 版本（最佳 effort）
-- ------------------------------------------------------------------
local function getLightroomVersion()
  local version = "未知"

  -- 尝试从 macOS Info.plist 读取
  if MAC_ENV then
    local appPaths = {
      "/Applications/Adobe Lightroom Classic.app",
      "/Applications/Adobe Lightroom.app",
    }
    for _, appPath in ipairs(appPaths) do
      local infoPlist = LrPathUtils.child(appPath, "Contents/Info.plist")
      if LrFileUtils.exists(infoPlist) then
        local cmd = 'defaults read "' .. appPath .. '/Contents/Info" CFBundleShortVersionString 2>/dev/null'
        local handle = io.popen(cmd)
        if handle then
          local result = handle:read("*l")
          handle:close()
          if result and #result > 0 then
            version = result
            break
          end
        end
      end
    end
  end

  -- 尝试从 Lightroom 安装目录的版本文件读取（Windows / macOS 通用 fallback）
  if version == "未知" then
    local lrRoot = LrPathUtils.getStandardFilePath("home")
    if MAC_ENV then
      lrRoot = LrPathUtils.child(lrRoot, "Library/Application Support/Adobe/Lightroom")
    else
      lrRoot = LrPathUtils.child(lrRoot, "AppData/Roaming/Adobe/Lightroom")
    end
    if LrFileUtils.exists(lrRoot) then
      version = "请手动补充（目录: " .. lrRoot .. "）"
    end
  end

  return version
end

-- ------------------------------------------------------------------
-- 收集诊断信息
-- ------------------------------------------------------------------
local function collectDiagnostics()
  local catalog = LrApplication.activeCatalog()
  local selectedPhotos = catalog:getTargetPhotos()

  local lrVersion = getLightroomVersion()
  local osName = MAC_ENV and "macOS" or (WIN_ENV and "Windows" or "未知")

  local info = dofile(LrPathUtils.child(pluginPath, "Info.lua"))
  local pluginVersion = string.format("%d.%d.%d",
    info.VERSION.major, info.VERSION.minor, info.VERSION.revision)

  local photoLines = {}
  if selectedPhotos and #selectedPhotos > 0 then
    for i, photo in ipairs(selectedPhotos) do
      if i > 3 then
        table.insert(photoLines, "... 等 " .. #selectedPhotos .. " 张")
        break
      end
      local name = photo:getFormattedMetadata("fileName") or "未知"
      local fullPath = photo:getRawMetadata("path") or "未知"
      local fmt = photo:getRawMetadata("fileFormat") or "未知"
      local dims = photo:getRawMetadata("dimensions")
      local dimStr = dims and (dims.width .. "x" .. dims.height) or "未知"
      local orientation = "未知"
      pcall(function()
        orientation = photo:getRawMetadata("orientation") or "无"
      end)
      table.insert(photoLines, "• " .. name)
      table.insert(photoLines, "  路径: " .. fullPath)
      table.insert(photoLines, "  格式: " .. fmt .. " | 尺寸: " .. dimStr .. " | 方向: " .. orientation)
    end
  else
    table.insert(photoLines, "未选择照片")
  end

  return {
    lrVersion = lrVersion,
    osName = osName,
    pluginVersion = pluginVersion,
    photos = table.concat(photoLines, "\n"),
    lastFrames = tostring(prefs.expectedFrames or "未设置"),
    lastFormat = tostring(prefs.filmFormat or "自动"),
    date = os.date("%Y-%m-%d %H:%M:%S"),
  }
end

-- ------------------------------------------------------------------
-- 生成诊断文本
-- ------------------------------------------------------------------
local function buildBody(diag)
  local lines = {}
  table.insert(lines, "【问题描述】")
  table.insert(lines, "（请在此补充你遇到的问题，可附上截图）")
  table.insert(lines, "")
  table.insert(lines, "---------- 以下信息由插件自动收集 ----------")
  table.insert(lines, "")
  table.insert(lines, "插件版本: " .. diag.pluginVersion)
  table.insert(lines, "Lightroom: " .. diag.lrVersion)
  table.insert(lines, "操作系统: " .. diag.osName)
  table.insert(lines, "反馈时间: " .. diag.date)
  table.insert(lines, "")
  table.insert(lines, "【检测参数】")
  table.insert(lines, "预期帧数: " .. diag.lastFrames)
  table.insert(lines, "胶片格式: " .. diag.lastFormat)
  table.insert(lines, "")
  table.insert(lines, "【照片信息】")
  table.insert(lines, diag.photos)
  table.insert(lines, "")
  table.insert(lines, "【附件说明】")
  table.insert(lines, "本反馈包附带插件日志文件（logs/ 目录），")
  table.insert(lines, "包含每次检测的详细 JSON 输出和坐标转换记录，")
  table.insert(lines, "是排查问题的核心依据。")
  table.insert(lines, "")
  table.insert(lines, "【联系方式】")
  table.insert(lines, "小红书：李冬天 SimplyWinter")
  table.insert(lines, "")
  return table.concat(lines, "\n")
end

-- ------------------------------------------------------------------
-- 查找 Lightroom 插件日志目录
-- 返回: logsDir（包含所有 NegativeCutter*.log 的目录）
-- ------------------------------------------------------------------
local function findLogDir()
  local home = LrPathUtils.getStandardFilePath("home")
  local candidates = {}

  if MAC_ENV then
    table.insert(candidates, LrPathUtils.child(home, "Library/Logs/Adobe/Lightroom/LrClassicLogs"))
    table.insert(candidates, LrPathUtils.child(home, "Library/Logs/Adobe/Lightroom"))
  elseif WIN_ENV then
    table.insert(candidates, LrPathUtils.child(home, "AppData/Roaming/Adobe/Lightroom/Logs"))
    table.insert(candidates, LrPathUtils.child(home, "AppData/Local/Adobe/Lightroom/Logs"))
  end

  for _, dir in ipairs(candidates) do
    if LrFileUtils.exists(dir) then
      return dir
    end
  end
  return nil
end

-- ------------------------------------------------------------------
-- 打包反馈文件
-- ------------------------------------------------------------------
local function packFeedback(diag, logDir)
  local timestamp = os.date("%Y%m%d_%H%M%S")
  local tempDir = LrPathUtils.child(LrPathUtils.getStandardFilePath("temp"), "NC_Feedback_" .. timestamp)

  -- 创建临时目录
  LrFileUtils.createDirectory(tempDir)

  -- 写入诊断文本
  local infoPath = LrPathUtils.child(tempDir, "diagnostic.txt")
  local f = io.open(infoPath, "w")
  if f then
    f:write(buildBody(diag))
    f:close()
  end

  -- 复制所有日志到 logs/ 子目录
  if logDir then
    local logsDest = LrPathUtils.child(tempDir, "logs")
    LrFileUtils.createDirectory(logsDest)

    local copyCmd
    if MAC_ENV then
      copyCmd = string.format(
        'sh -c \'for f in "%s"/NegativeCutter*.log; do [ -f "$f" ] && cp "$f" "%s/"; done\'',
        logDir, logsDest
      )
    else
      copyCmd = string.format(
        'powershell -Command "Get-ChildItem -Path \'%s\' -Filter \'NegativeCutter*.log\' | Copy-Item -Destination \'%s\'"',
        logDir, logsDest
      )
    end
    logger:trace("反馈打包日志命令: " .. copyCmd)
    local exitCode = LrTasks.execute(copyCmd)
    logger:trace("反馈打包日志命令 exitCode=" .. tostring(exitCode))
  end

  -- 打包成 zip
  local desktop = LrPathUtils.getStandardFilePath("desktop")
  local zipPath = LrPathUtils.child(desktop, "NegativeCutter_反馈_" .. timestamp .. ".zip")

  local packCmd
  if MAC_ENV then
    packCmd = string.format('cd "%s" && zip -q -r "%s" .', tempDir, zipPath)
  else
    packCmd = string.format('powershell -Command "Compress-Archive -Path \'%s\\*\' -DestinationPath \'%s\' -Force"', tempDir, zipPath)
  end
  LrTasks.execute(packCmd)

  return zipPath
end

-- ------------------------------------------------------------------
-- 主流程
-- ------------------------------------------------------------------
LrTasks.startAsyncTask(function()
  local diag = collectDiagnostics()
  local logDir = findLogDir()

  -- 打包
  local zipPath = packFeedback(diag, logDir)

  local f = LrView.osFactory()

  -- 直接提示用户手动发送
  local contents = f:column {
    spacing = f:control_spacing(),
    f:static_text {
      title = "✅  反馈包已准备好",
      font = "<system/bold>",
      height_in_lines = 1,
    },
    f:separator {},
    f:static_text {
      title = "反馈包已保存到桌面，包含诊断信息和插件日志。\n请将 zip 文件发给作者。",
      height_in_lines = 2,
    },
    f:separator {},
    f:static_text {
      title = zipPath,
      font = "<system/small>",
      selectable = true,
      height_in_lines = 2,
    },
    f:static_text {
      title = "\n小红书：李冬天 SimplyWinter",
      font = "<system/small>",
      height_in_lines = 1,
    },
  }

  LrDialogs.presentModalDialog {
    title = "NegativeCutter - 反馈已就绪",
    contents = contents,
    actionVerb = "关闭",
  }
end)
