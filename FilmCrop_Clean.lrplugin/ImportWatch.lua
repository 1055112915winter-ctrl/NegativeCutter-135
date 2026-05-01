-- FilmCrop JSON 监视入口
local ImportAgent = dofile(_PLUGIN.path .. "/ImportAgent.lua")
ImportAgent.watchJsonFile()
