--[[
  Mock LrPathUtils — 测试用的路径工具
]]--

local LrPathUtils = {}

function LrPathUtils.child(parent, child)
    if not parent then return child end
    if parent:sub(-1) == "/" then return parent .. child end
    return parent .. "/" .. child
end

function LrPathUtils.getStandardFilePath(type)
    if type == "temp" then
        return "/tmp/filmcrop_test"
    end
    return "/tmp"
end

function LrPathUtils.extension(path)
    if not path then return "" end
    return path:match("%.([^%.]+)$") or ""
end

function LrPathUtils.removeExtension(path)
    if not path then return "" end
    return path:gsub("%.[^%.]+$", "")
end

return LrPathUtils
