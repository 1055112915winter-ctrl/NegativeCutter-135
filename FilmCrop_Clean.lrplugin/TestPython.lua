--[[
  TestPython.lua
  测试 Lightroom 是否能正确执行 Python 脚本
]]--

local LrDialogs = import 'LrDialogs'
local LrView = import 'LrView'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'
local LrLogger = import 'LrLogger'

local logger = LrLogger('FilmCrop.TestPython')
logger:enable("logfile")

LrTasks.startAsyncTask(function()
  local pluginPath = _PLUGIN.path
  local testOutput = LrPathUtils.child(LrPathUtils.getStandardFilePath("temp"), "test_output.txt")

  local ProcessAgent = dofile(LrPathUtils.child(pluginPath, "ProcessAgent.lua"))

  -- 测试1: 检查 Python 路径
  logger:trace("=== 测试 Python 环境 ===")

  local pythonCmd = ProcessAgent.findPythonPath()
  local pythonFound = pythonCmd
  logger:trace("Python路径: " .. pythonCmd)

  -- 测试2: 尝试执行 Python 命令
  logger:trace("=== 测试 Python 执行 ===")
  local cmd = string.format('"%s" -c "print(\'Hello from Python\\\")" > "%s" 2>&1',
    pythonCmd, testOutput)

  logger:trace("执行命令: " .. cmd)
  local exitCode = LrTasks.execute(cmd)
  logger:trace("退出码: " .. tostring(exitCode))

  -- 读取输出
  local output = ""
  local file = io.open(testOutput, "r")
  if file then
    output = file:read("*a") or ""
    file:close()
    logger:trace("输出: " .. output)
  else
    logger:trace("无法读取输出文件")
  end

  -- 清理
  if LrFileUtils.exists(testOutput) then
    LrFileUtils.delete(testOutput)
  end

  -- 显示结果对话框
  local f = LrView.osFactory()
  local message = "Python 测试结果:\n"
  message = message .. "Python 路径: " .. (pythonFound or "未找到，使用默认 'python3'") .. "\n"
  message = message .. "退出码: " .. tostring(exitCode) .. "\n"
  message = message .. "输出: " .. (output ~= "" and output or "(无输出)")

  LrDialogs.message("FilmCrop - Python 测试", message, "info")
end)
