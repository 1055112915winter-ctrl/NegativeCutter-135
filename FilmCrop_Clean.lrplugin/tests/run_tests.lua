#!/usr/bin/env lua
--[[
  FilmCrop Mock SDK 测试入口
  用法: lua tests/run_tests.lua
  或:   luajit tests/run_tests.lua
]]--

-- ------------------------------------------------------------------
-- 1. 设置模块搜索路径
-- ------------------------------------------------------------------
local thisDir = debug.getinfo(1).source:match("@?(.*/)") or "./"
local pluginDir = thisDir .. "../"

-- 添加 mock_sdk 和插件目录到搜索路径
package.path = package.path
    .. ";" .. thisDir .. "?.lua"
    .. ";" .. thisDir .. "mock_sdk/?.lua"
    .. ";" .. pluginDir .. "?.lua"

-- ------------------------------------------------------------------
-- 2. Mock 全局环境
-- ------------------------------------------------------------------

-- Mock _PLUGIN（Lightroom 插件目录）
_G._PLUGIN = {
    path = pluginDir
}

-- Mock import() — 劫持 Lightroom SDK 加载
local mockSdk = require("mock_sdk.init")
mockSdk.setupImport()

-- Mock dofile — 当 ProcessAgent 加载 ThumbnailAgent/ApplierAgent 时返回 stub
local _original_dofile = dofile
_G.dofile = function(path)
    if type(path) == "string" and path:match("ThumbnailAgent%.lua$") then
        -- 返回 ThumbnailAgent stub
        return {
            extract = function(photo, maxSize, callback)
                -- 测试中预置缩略图
                local thumbPath = "/tmp/test_scan_thumb.jpg"
                if callback then callback(true, thumbPath, nil) end
                return true, thumbPath, nil
            end
        }
    end

    if type(path) == "string" and path:match("ApplierAgent%.lua$") then
        -- 返回 ApplierAgent stub
        return {
            applyCrop = function(photo, cropRegion)
                -- 记录应用到 mock photo
                if photo then
                    photo._developSettings = photo._developSettings or {}
                    photo._developSettings.CropTop = cropRegion.top or 0
                    photo._developSettings.CropBottom = cropRegion.bottom or 1
                    photo._developSettings.CropLeft = cropRegion.left or 0
                    photo._developSettings.CropRight = cropRegion.right or 1
                    photo._developSettings.CropAngle = cropRegion.cropAngle or 0
                end
                return true, nil
            end,
            resetCrop = function(photo)
                if photo then
                    photo._developSettings = {
                        CropTop = 0, CropBottom = 1,
                        CropLeft = 0, CropRight = 1, CropAngle = 0,
                    }
                end
                return true, nil
            end,
            getCurrentCrop = function(photo)
                local s = photo and photo._developSettings or {}
                return {
                    top = s.CropTop or 0,
                    bottom = s.CropBottom or 1,
                    left = s.CropLeft or 0,
                    right = s.CropRight or 1,
                    angle = s.CropAngle or 0,
                }
            end
        }
    end

    return _original_dofile(path)
end

-- Mock LOC() 本地化函数
_G.LOC = function(key) return key end

-- ------------------------------------------------------------------
-- 3. 加载被测模块
-- ------------------------------------------------------------------
print("=" .. string.rep("=", 60))
print("FilmCrop Mock SDK 架构测试")
print("=" .. string.rep("=", 60))

print("\n加载 ProcessAgent...")
local ProcessAgent = dofile(pluginDir .. "ProcessAgent.lua")
print("  OK")

print("加载 Mock 工具...")
local MockInit = require("mock_sdk.init")
local MockPhoto = require("mock_sdk.LrPhoto")
print("  OK")

-- ------------------------------------------------------------------
-- 4. 测试套件
-- ------------------------------------------------------------------
local passCount = 0
local failCount = 0

local function runTest(name, fn)
    io.write("  " .. name .. " ... ")
    MockInit.resetMocks()
    local ok, err = pcall(fn)
    if ok then
        print("PASS")
        passCount = passCount + 1
        return true
    else
        print("FAIL")
        print("    " .. tostring(err):gsub("\n", "\n    "))
        failCount = failCount + 1
        return false
    end
end

print("\n--- Test Suite: ProcessAgent.parseJSON ---")

runTest("解析完整 JSON 结果", function()
    local jsonStr = [[{
        "frameCount": 3,
        "sourceWidth": 2400,
        "sourceHeight": 3500,
        "cropAngle": 0.5,
        "debug": {"isHorizontal": false},
        "frames": [
            {"index": 1, "top": 100, "bottom": 1100, "left": 0, "right": 2400,
             "relativeTop": 0.0286, "relativeBottom": 0.3143, "relativeLeft": 0.0, "relativeRight": 1.0},
            {"index": 2, "top": 1200, "bottom": 2200, "left": 0, "right": 2400,
             "relativeTop": 0.3429, "relativeBottom": 0.6286, "relativeLeft": 0.0, "relativeRight": 1.0},
            {"index": 3, "top": 2300, "bottom": 3400, "left": 0, "right": 2400,
             "relativeTop": 0.6571, "relativeBottom": 0.9714, "relativeLeft": 0.0, "relativeRight": 1.0}
        ]
    }]]

    local result = ProcessAgent.parseJSON(jsonStr)

    MockInit.assertEqual(3, result.frameCount, "frameCount")
    MockInit.assertEqual(2400, result.sourceWidth, "sourceWidth")
    MockInit.assertEqual(3500, result.sourceHeight, "sourceHeight")
    MockInit.assertEqual(0.5, result.cropAngle, "cropAngle")
    MockInit.assertEqual(false, result.isHorizontal, "isHorizontal")
    MockInit.assertEqual(3, #result.frames, "frames count")

    local f1 = result.frames[1]
    MockInit.assertEqual(1, f1.index, "frame1.index")
    MockInit.assertEqual(100, f1.top, "frame1.top")
    MockInit.assertEqual(1100, f1.bottom, "frame1.bottom")
    MockInit.assertEqual(0, f1.left, "frame1.left")
    MockInit.assertEqual(2400, f1.right, "frame1.right")
end)

runTest("解析无 debug 字段的 JSON（方向推断）", function()
    local jsonStr = [[{
        "frameCount": 2,
        "sourceWidth": 3500,
        "sourceHeight": 2400,
        "frames": [
            {"index": 1, "top": 0, "bottom": 1000, "left": 0, "right": 3500}
        ]
    }]]

    local result = ProcessAgent.parseJSON(jsonStr)
    -- sourceWidth 3500 > sourceHeight 2400, 所以 isHorizontal = true
    MockInit.assertEqual(true, result.isHorizontal, "isHorizontal (inferred)")
    MockInit.assertEqual(1, #result.frames, "frames count")
end)

runTest("解析空 frames", function()
    local jsonStr = [[{"frameCount": 0, "sourceWidth": 1000, "sourceHeight": 1000, "frames": []}]]
    local result = ProcessAgent.parseJSON(jsonStr)
    MockInit.assertEqual(0, #result.frames, "empty frames")
end)

print("\n--- Test Suite: ProcessAgent.directionAlign ---")

runTest("方向一致时不旋转", function()
    local jsonStr = [[{
        "frameCount": 1, "sourceWidth": 2400, "sourceHeight": 3500,
        "frames": [{"index":1, "top":100, "bottom":1100, "relativeTop":0.1, "relativeBottom":0.4}]
    }]]
    local result = ProcessAgent.parseJSON(jsonStr)

    -- photo 和 Python 结果都是 vertical (2400<3500)
    local photo = MockPhoto.createMockPhoto({
        dimensions = {width = 2400, height = 3500}
    })

    local aligned = ProcessAgent.directionAlign(result, photo)

    MockInit.assertEqual(false, aligned.isHorizontal, "isHorizontal")
    MockInit.assertEqual(0.1, aligned.frames[1].relativeTop, "relativeTop unchanged")
    MockInit.assertEqual(0.4, aligned.frames[1].relativeBottom, "relativeBottom unchanged")
end)

runTest("方向不一致时旋转 90°", function()
    local jsonStr = [[{
        "frameCount": 1, "sourceWidth": 2400, "sourceHeight": 3500,
        "cropAngle": 1.5,
        "frames": [{"index":1, "relativeTop":0.1, "relativeBottom":0.4,
                    "relativeLeft":0.0, "relativeRight":1.0}]
    }]]
    local result = ProcessAgent.parseJSON(jsonStr)

    -- Python 结果是 vertical (2400<3500)，但 LR 照片是 horizontal (3500>2400)
    local photo = MockPhoto.createMockPhoto({
        dimensions = {width = 3500, height = 2400}
    })

    local aligned = ProcessAgent.directionAlign(result, photo)

    -- 坐标应该被旋转
    -- 原来: top=0.1, bottom=0.4, left=0.0, right=1.0
    -- 旋转后: top=left=0.0, bottom=right=1.0, left=top=0.1, right=bottom=0.4
    MockInit.assertEqual(0.0, aligned.frames[1].relativeTop, "rotated top")
    MockInit.assertEqual(1.0, aligned.frames[1].relativeBottom, "rotated bottom")
    MockInit.assertEqual(0.1, aligned.frames[1].relativeLeft, "rotated left")
    MockInit.assertEqual(0.4, aligned.frames[1].relativeRight, "rotated right")

    -- cropAngle 应该取反
    MockInit.assertEqual(-1.5, aligned.cropAngle, "cropAngle negated")
end)

runTest("方向不一致时像素坐标也旋转", function()
    local jsonStr = [[{
        "frameCount": 1, "sourceWidth": 2400, "sourceHeight": 3500,
        "frames": [{"index":1, "top":100, "bottom":1100, "left":0, "right":2400}]
    }]]
    local result = ProcessAgent.parseJSON(jsonStr)

    -- LR 照片是 horizontal 3500x2400
    local photo = MockPhoto.createMockPhoto({
        dimensions = {width = 3500, height = 2400}
    })

    local aligned = ProcessAgent.directionAlign(result, photo)

    -- sourceWidth/sourceHeight 应该更新
    MockInit.assertEqual(3500, aligned.sourceWidth, "updated sourceWidth")
    MockInit.assertEqual(2400, aligned.sourceHeight, "updated sourceHeight")

    -- 像素坐标基于 LR 尺寸重新计算
    -- relativeTop=0, relativeBottom=1, relativeLeft=100/3500≈0.0286, relativeRight=1100/3500≈0.3143
    -- top = floor(0 * 2400) = 0, bottom = floor(1 * 2400) = 2400
    -- left = floor(0.0286 * 3500) = 100, right = floor(0.3143 * 3500) = 1100
    MockInit.assertEqual(0, aligned.frames[1].top, "rotated pixel top")
    MockInit.assertEqual(2400, aligned.frames[1].bottom, "rotated pixel bottom")
end)

print("\n--- Test Suite: ProcessAgent.findPythonPath ---")

runTest("找到可用的 Python 解释器", function()
    -- 创建一个假的 python3 路径
    local fakePython = "/tmp/fake_python3"
    local f = io.open(fakePython, "w")
    f:write("#!/bin/sh\necho 'Python 3.14.0'\n")
    f:close()
    os.execute("chmod +x '" .. fakePython .. "'")

    -- 临时修改 findPythonPath 的搜索列表
    -- 由于 findPythonPath 使用硬编码路径，我们用 os.execute 创建一个真实文件
    local pythonPath = ProcessAgent.findPythonPath()
    MockInit.assertTrue(pythonPath and #pythonPath > 0, "found python path")

    os.remove(fakePython)
end)

print("\n--- Test Suite: ProcessAgent.analyzeWithPython (需要 Python 环境) ---")

runTest("Python 脚本不存在时返回错误", function()
    -- 临时修改 pluginPath 指向不存在的目录
    local origPath = _PLUGIN.path
    _PLUGIN.path = "/nonexistent/"

    local result, err = ProcessAgent.analyzeWithPython("/tmp/test.jpg", 6, "/tmp/test.jpg")

    _PLUGIN.path = origPath

    MockInit.assertEqual(nil, result, "result should be nil")
    MockInit.assertTrue(err and err:match("不存在"), "error mentions missing script")
end)

-- ------------------------------------------------------------------
-- 5. 测试汇总
-- ------------------------------------------------------------------
print("\n" .. string.rep("-", 62))
print(string.format("结果: %d 通过, %d 失败", passCount, failCount))
print(string.rep("-", 62))

if failCount > 0 then
    os.exit(1)
else
    print("\n全部测试通过!")
    os.exit(0)
end
