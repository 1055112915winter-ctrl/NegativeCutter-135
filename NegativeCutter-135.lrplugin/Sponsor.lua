--[[
  Sponsor.lua
  独立的赞助入口 — 通过菜单直接打开赞赏码图片
]]--

local LrTasks = import 'LrTasks'
local LrPathUtils = import 'LrPathUtils'

local pluginPath = _PLUGIN.path
local ProcessAgent = dofile(LrPathUtils.child(pluginPath, "ProcessAgent.lua"))

LrTasks.startAsyncTask(function()
  ProcessAgent.openSponsorImage()
end)
