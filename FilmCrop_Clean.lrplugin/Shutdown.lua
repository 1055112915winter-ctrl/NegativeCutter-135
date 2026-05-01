--[[
  Shutdown.lua
  插件关闭时的清理
]]--

local LrLogger = import 'LrLogger'
local LrPrefs = import 'LrPrefs'

local logger = LrLogger('FilmCrop')
logger:enable("logfile")

local prefs = LrPrefs.prefsForPlugin()
if prefs.watchActive then
  prefs.watchActive = false
  prefs.watchJsonPath = nil
  logger:trace("FilmCrop 插件已关闭，JSON 监视状态已清除")
else
  logger:trace("FilmCrop 插件已关闭")
end
