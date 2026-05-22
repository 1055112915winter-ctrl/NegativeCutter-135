--[[
  Mock LrPrefs — 测试用的偏好设置
  使用内存存储，每次测试前重置
]]--

-- 使用全局存储，但提供 reset 方法
_G.__mock_prefs = _G.__mock_prefs or {}

local LrPrefs = {}

function LrPrefs.prefsForPlugin()
    return _G.__mock_prefs
end

-- 测试辅助：重置偏好
function LrPrefs._reset()
    _G.__mock_prefs = {}
end

return LrPrefs
