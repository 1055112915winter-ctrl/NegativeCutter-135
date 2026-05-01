--[[
  停止 FilmCrop 自动检测模式
]]--

local LrDialogs = import 'LrDialogs'
local ImportAgent = dofile(_PLUGIN.path .. "/ImportAgent.lua")

ImportAgent.stopAutoWatch()
LrDialogs.message("FilmCrop", "自动检测已停止", "info")
