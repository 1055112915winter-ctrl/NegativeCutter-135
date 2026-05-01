--[[
  FilmCrop 自动检测模式（E2E 测试入口）
  启动后监视固定路径的 JSON 文件，变化时自动应用
]]--

local LrDialogs = import 'LrDialogs'
local LrFileUtils = import 'LrFileUtils'
local LrApplicationView = import 'LrApplicationView'

local LrPathUtils = import 'LrPathUtils'
local ImportAgent = dofile(_PLUGIN.path .. "/ImportAgent.lua")
local AUTO_JSON = LrPathUtils.child(_PLUGIN.path, "filmcrop_e2e.json")

-- 确保 JSON 文件存在（空文件即可）
if not LrFileUtils.exists(AUTO_JSON) then
  local f = io.open(AUTO_JSON, "w")
  if f then
    f:write('{"frames":[]}')
    f:close()
  end
end

local currentModule = LrApplicationView.getCurrentModuleName()
if currentModule ~= "develop" then
  LrDialogs.message(
    "FilmCrop - 自动检测",
    "请在「修改照片」模块中运行自动检测模式。",
    "warning"
  )
  return
end

local ok, msg = ImportAgent.startAutoWatch(AUTO_JSON)
if ok then
  LrDialogs.message(
    "FilmCrop - 自动检测已启动",
    "正在监视: " .. AUTO_JSON .. "\n\n测试脚本更新此文件后将自动触发检测。\n（通过「停止自动检测」菜单项可终止）",
    "info"
  )
else
  LrDialogs.message("FilmCrop - 自动检测启动失败", msg, "critical")
end
