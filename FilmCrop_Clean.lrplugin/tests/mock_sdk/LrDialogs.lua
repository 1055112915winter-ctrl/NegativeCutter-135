--[[
  Mock LrDialogs — 测试用的对话框
  记录所有调用，不弹窗
]]--

local LrDialogs = {}

-- 全局对话框记录
_G.__mock_dialogs = _G.__mock_dialogs or {}

function LrDialogs.message(title, msg, type)
    table.insert(_G.__mock_dialogs, {method = "message", title = title, msg = msg, type = type})
end

function LrDialogs.confirm(title, msg, action, cancel, other)
    table.insert(_G.__mock_dialogs, {method = "confirm", title = title, msg = msg, action = action})
    return "ok"  -- 测试中默认确认
end

function LrDialogs.presentModalDialog(args)
    table.insert(_G.__mock_dialogs, {method = "presentModalDialog", args = args})
    return "ok"
end

return LrDialogs
