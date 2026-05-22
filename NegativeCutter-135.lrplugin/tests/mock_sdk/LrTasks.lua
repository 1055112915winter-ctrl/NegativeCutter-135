--[[
  Mock LrTasks — 测试用的任务工具
  startAsyncTask 同步执行（测试中不需要真正异步）
  execute 代理到 os.execute
  sleep 跳过（测试中不需要等待）
]]--

local LrTasks = {}

-- 全局任务记录
_G.__mock_tasks = _G.__mock_tasks or {}

function LrTasks.startAsyncTask(func)
    table.insert(_G.__mock_tasks, {op = "startAsyncTask"})
    local ok, err = pcall(func)
    if not ok then
        error("Async task error: " .. tostring(err))
    end
end

function LrTasks.sleep(seconds)
    table.insert(_G.__mock_tasks, {op = "sleep", seconds = seconds})
    -- 测试中不真的 sleep
end

function LrTasks.execute(cmd)
    table.insert(_G.__mock_tasks, {op = "execute", cmd = cmd})
    local ok, exitType, exitCode = os.execute(cmd)
    -- os.execute 返回格式在不同 Lua 版本中不同
    -- Lua 5.1: 返回 exit code (number)
    -- Lua 5.2+: 返回 ok (boolean), exitType (string), exitCode (number)
    if type(ok) == "number" then
        return ok  -- Lua 5.1
    elseif ok == true then
        return exitCode or 0
    else
        return exitCode or 1
    end
end

return LrTasks
