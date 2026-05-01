-- FilmCrop HTTP API 检测入口
local ImportAgent = dofile(_PLUGIN.path .. "/ImportAgent.lua")
ImportAgent.detectViaHttp()
