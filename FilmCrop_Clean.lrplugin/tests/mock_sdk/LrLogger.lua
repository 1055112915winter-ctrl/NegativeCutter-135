--[[
  Mock LrLogger — 测试用的日志模块
  记录所有 trace/error 调用，测试可以断言日志内容
]]--

local LrLogger = {}

-- 全局日志记录器，测试可以读取
_G.__mock_logs = _G.__mock_logs or {}

function LrLogger:new(name)
    local obj = {
        name = name or "unknown",
        _enabled = false,
    }
    setmetatable(obj, self)
    self.__index = self
    return obj
end

function LrLogger:enable(mode)
    self._enabled = true
end

function LrLogger:trace(msg)
    table.insert(_G.__mock_logs, {level = "trace", name = self.name, msg = tostring(msg)})
end

function LrLogger:error(msg)
    table.insert(_G.__mock_logs, {level = "error", name = self.name, msg = tostring(msg)})
end

-- LrLogger 在 Lightroom 中可直接调用: LrLogger('name')
setmetatable(LrLogger, {
    __call = function(self, name)
        return self:new(name)
    end
})

return LrLogger
