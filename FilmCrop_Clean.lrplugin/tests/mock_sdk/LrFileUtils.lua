--[[
  Mock LrFileUtils — 测试用的文件工具
  代理到真实文件系统，但记录所有操作
]]--

local LrFileUtils = {}

-- 全局操作记录，测试可以断言
_G.__mock_file_ops = _G.__mock_file_ops or {}

function LrFileUtils.exists(path)
    table.insert(_G.__mock_file_ops, {op = "exists", path = path})
    if not path then return false end
    local f = io.open(path, "r")
    if f then f:close() return true end
    return false
end

function LrFileUtils.createAllDirectories(path)
    table.insert(_G.__mock_file_ops, {op = "createAllDirectories", path = path})
    if not path then return false end
    os.execute("mkdir -p '" .. path .. "' 2>/dev/null")
    return true
end

function LrFileUtils.delete(path)
    table.insert(_G.__mock_file_ops, {op = "delete", path = path})
    if not path then return false end
    os.remove(path)
    return true
end

function LrFileUtils.copy(sourcePath, destPath)
    table.insert(_G.__mock_file_ops, {op = "copy", source = sourcePath, dest = destPath})
    local infile = io.open(sourcePath, "rb")
    if not infile then return false end
    local outfile = io.open(destPath, "wb")
    if not outfile then infile:close() return false end
    outfile:write(infile:read("*a"))
    infile:close()
    outfile:close()
    return true
end

return LrFileUtils
