--[[
  NegativeCutter 插件初始化
  在插件加载时执行
]]--

local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local PreviewRuntime = require 'PreviewRuntime'
local ProcessAgent = require 'ProcessAgent'

local logger = LrLogger('NegativeCutterInit')
logger:enable("logfile")

logger:trace("=== NegativeCutter Init.lua 已加载 ===")

-- Mark this session and remove only directories belonging to an older session.
local previewRoot = (LrPathUtils and LrPathUtils.getStandardFilePath and
    LrPathUtils.getStandardFilePath('temp')) or "/tmp"
previewRoot = previewRoot .. "/NegativeCutterPreview"
local previewOk, previewError = pcall(function()
  PreviewRuntime.current(ProcessAgent, { previewRoot = previewRoot })
end)
if not previewOk then logger:error("Preview runtime initialization failed: " .. tostring(previewError)) end

-- 验证：写临时日志文件
pcall(function()
    local f = io.open("/tmp/negativecutter_init_loaded.log", "a")
    if f then
        f:write("Init.lua loaded: " .. os.date("%Y-%m-%d %H:%M:%S") .. "\n")
        f:close()
    end
end)
