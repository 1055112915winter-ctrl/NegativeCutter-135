--[[
  Shutdown.lua
  插件关闭时的清理
]]--

local LrLogger = import 'LrLogger'
local LrPrefs = import 'LrPrefs'
local PreviewAgent = require 'PreviewAgent'

local logger = LrLogger('NegativeCutter')
logger:enable("logfile")
local prefs = LrPrefs.prefsForPlugin()

pcall(function() PreviewAgent.closeAll() end)
if prefs.watchActive then
  prefs.watchActive = false
  prefs.watchJsonPath = nil
  logger:trace("NegativeCutter 插件已关闭，JSON 监视状态已清除")
end
if prefs.autoWatchActive then
  prefs.autoWatchActive = false
  prefs.autoWatchJsonPath = nil
  logger:trace("NegativeCutter 插件已关闭，自动检测状态已清除")
end
logger:trace("NegativeCutter 插件已关闭")
