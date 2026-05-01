--[[
  Mock LrApplicationView — 测试用的视图接口
  假装在 develop 模块（因为裁剪操作需要）
]]--

local LrApplicationView = {}

-- 可配置，测试可以改
_G.__mock_current_module = _G.__mock_current_module or "develop"

function LrApplicationView.getCurrentModuleName()
    return _G.__mock_current_module
end

-- 测试辅助
function LrApplicationView._setModule(name)
    _G.__mock_current_module = name
end

return LrApplicationView
