--[[
  Mock SDK 初始化模块
  设置全局环境，劫持 import()，提供测试辅助函数
]]--

local M = {}

-- 设置 import 劫持
function M.setupImport()
    -- 记录原始的 require（如果需要）
    _G._original_require = _G._original_require or require

    -- Mock import 函数
    _G.import = function(moduleName)
        -- 映射到 mock_sdk 目录下的模块
        local mockPath = "mock_sdk." .. moduleName
        local ok, mod = pcall(require, mockPath)
        if ok then
            return mod
        end

        -- 尝试从当前目录加载
        ok, mod = pcall(require, moduleName)
        if ok then
            return mod
        end

        error("Mock SDK 未实现: " .. moduleName)
    end
end

-- 重置所有 mock 状态（每个测试前调用）
function M.resetMocks()
    _G.__mock_logs = {}
    _G.__mock_file_ops = {}
    _G.__mock_tasks = {}
    _G.__mock_dialogs = {}
    _G.__mock_prefs = {}
    _G.__mock_current_module = "develop"
    _G.__mock_catalog = {
        photos = {},
        selectedPhotos = {},
        virtualCopies = {},
        writeAccessLog = {},
    }
end

-- 断言辅助函数
function M.assertEqual(expected, actual, msg)
    if expected ~= actual then
        local err = string.format("ASSERT FAIL: %s\n  expected: %s\n  actual: %s",
            msg or "", tostring(expected), tostring(actual))
        error(err)
    end
end

function M.assertTrue(value, msg)
    if not value then
        error("ASSERT FAIL: " .. (msg or "expected true") .. ", got " .. tostring(value))
    end
end

function M.assertTableEqual(expected, actual, msg)
    msg = msg or ""
    if type(expected) ~= "table" or type(actual) ~= "table" then
        error("ASSERT FAIL: " .. msg .. " - expected table, got " .. type(actual))
    end

    for k, v in pairs(expected) do
        if type(v) == "table" then
            M.assertTableEqual(v, actual[k], msg .. "." .. tostring(k))
        else
            if v ~= actual[k] then
                error(string.format("ASSERT FAIL: %s.%s\n  expected: %s\n  actual: %s",
                    msg, tostring(k), tostring(v), tostring(actual[k])))
            end
        end
    end

    for k, v in pairs(actual) do
        if expected[k] == nil then
            error("ASSERT FAIL: " .. msg .. " - unexpected key: " .. tostring(k))
        end
    end
end

-- 简单测试运行器
function M.runTest(name, testFunc)
    io.write("  " .. name .. " ... ")
    local ok, err = pcall(testFunc)
    if ok then
        print("PASS")
        return true
    else
        print("FAIL")
        print("    " .. tostring(err))
        return false
    end
end

return M
