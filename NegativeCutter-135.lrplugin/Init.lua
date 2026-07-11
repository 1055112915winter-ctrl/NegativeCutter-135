--[[
  NegativeCutter 插件初始化
  在插件加载时执行
]]--

local LrLogger = import 'LrLogger'
local LrTasks = import 'LrTasks'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local LrApplication = import 'LrApplication'
local PreviewAgent = require 'PreviewAgent'

local logger = LrLogger('NegativeCutterInit')
logger:enable("logfile")

logger:trace("=== NegativeCutter Init.lua 已加载 ===")

-- Mark this session and remove only directories belonging to an older session.
local previewRoot = (LrPathUtils and LrPathUtils.getStandardFilePath and
    LrPathUtils.getStandardFilePath('temp')) or "/tmp"
previewRoot = previewRoot .. "/NegativeCutterPreview"
pcall(function()
  if LrFileUtils.createAllDirectories then LrFileUtils.createAllDirectories(previewRoot) end
  local marker = previewRoot .. "/.session"
  local old = io.open(marker, "r")
  if old then old:close() end
  local f = io.open(marker, "w"); if f then f:write(tostring(os.time())); f:close() end
end)

-- 验证：写临时日志文件
pcall(function()
    local f = io.open("/tmp/negativecutter_init_loaded.log", "a")
    if f then
        f:write("Init.lua loaded: " .. os.date("%Y-%m-%d %H:%M:%S") .. "\n")
        f:close()
    end
end)
