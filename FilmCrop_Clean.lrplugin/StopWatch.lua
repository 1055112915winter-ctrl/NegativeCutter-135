--[[
  FilmCrop JSON 监视停止入口
]]--

local LrDialogs = import 'LrDialogs'
local LrPrefs = import 'LrPrefs'

local prefs = LrPrefs.prefsForPlugin()

if prefs.watchActive then
  prefs.watchActive = false
  prefs.watchJsonPath = nil
  LrDialogs.message("FilmCrop", "JSON 监视已停止", "info")
else
  LrDialogs.message("FilmCrop", "当前没有正在进行的 JSON 监视", "info")
end
