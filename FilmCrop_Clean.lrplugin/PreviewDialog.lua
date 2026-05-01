--[[
  PreviewDialog.lua
  预览和调整对话框 - 显示检测到的帧边界并允许手动微调

  功能:
  1. 显示带边界标记的预览图
  2. 提供每个帧的top/bottom数值调整
  3. 确认后应用调整后的边界
]]--

local LrDialogs = import 'LrDialogs'
local LrView = import 'LrView'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrLogger = import 'LrLogger'
local LrTasks = import 'LrTasks'

local logger = LrLogger('FilmCrop.PreviewDialog')
logger:enable("logfile")

local PreviewDialog = {}

-- 辅助函数：四舍五入到指定小数位
local function round(num, decimals)
  local mult = 10 ^ (decimals or 0)
  return math.floor(num * mult + 0.5) / mult
end

--[[
  生成带边界标记的预览图
]]--
local function generatePreview(thumbPath, frames, outputPath)
  local pluginPath = _PLUGIN.path
  local scriptPath = LrPathUtils.child(pluginPath, "generate_preview.py")

  -- 构建帧数据JSON（包含完整信息）
  local jsonParts = {"["}
  for i, frame in ipairs(frames) do
    if i > 1 then table.insert(jsonParts, ",") end
    -- 使用实际检测到的边界，不再硬编码 3:2
    local left = frame.left or 0
    local right = frame.right or (frame.sourceWidth or 1024)

    local sourceWidth = frame.sourceWidth or (frame.right or 1024)
    local sourceHeight = frame.sourceHeight or (frame.bottom or 1024)
    table.insert(jsonParts, string.format(
      '{"top":%d,"bottom":%d,"left":%d,"right":%d,"sourceWidth":%d,"sourceHeight":%d}',
      frame.top, frame.bottom, left, right, sourceWidth, sourceHeight))
  end
  table.insert(jsonParts, "]")
  local framesJson = table.concat(jsonParts)

  -- 将JSON写入临时文件，避免shell转义问题
  local tempJsonPath = outputPath .. ".json"
  local jsonFile = io.open(tempJsonPath, "w")
  if not jsonFile then
    logger:error("无法创建临时JSON文件")
    return false
  end
  jsonFile:write(framesJson)
  jsonFile:close()

  -- 检查 Python 脚本是否存在
  if not LrFileUtils.exists(scriptPath) then
    logger:error("Python脚本不存在: " .. scriptPath)
    return false
  end

  -- 检查缩略图是否存在
  if not LrFileUtils.exists(thumbPath) then
    logger:error("缩略图不存在: " .. thumbPath)
    return false
  end

  logger:trace("开始生成预览图: 缩略图=" .. thumbPath .. ", 帧数=" .. #frames)

  -- 使用共享的 Python 路径解析
  local ProcessAgent = dofile(LrPathUtils.child(pluginPath, "ProcessAgent.lua"))
  local pythonCmd = ProcessAgent.findPythonPath()
  logger:trace("使用Python: " .. pythonCmd)

  -- 使用正确的重定向顺序：先重定向stdout，再将stderr重定向到stdout
  local cmd = string.format('"%s" "%s" "%s" "%s" "%s"',
    pythonCmd, scriptPath, thumbPath, tempJsonPath, outputPath)

  logger:trace("生成预览命令: " .. cmd)

  -- 执行并捕获输出（正确顺序：> file 2>&1）
  local outputFile = outputPath .. ".log"
  local shellCmd = cmd .. ' > "' .. outputFile .. '" 2>&1'
  logger:trace("执行shell命令: " .. shellCmd)
  local exitCode = LrTasks.execute(shellCmd)

  -- 读取输出
  local output = ""
  local logFile = io.open(outputFile, "r")
  if logFile then
    output = logFile:read("*a") or ""
    logFile:close()
    LrFileUtils.delete(outputFile)
  end

  logger:trace("预览生成退出码: " .. tostring(exitCode))
  if #output > 0 then
    logger:trace("预览生成输出: " .. string.sub(output, 1, 500))
  end

  -- 检查输出文件是否实际生成
  if LrFileUtils.exists(outputPath) then
    logger:trace("预览图文件已生成: " .. outputPath)
    -- 等待文件完全写入磁盘
    LrTasks.sleep(0.1)
  else
    logger:error("预览图文件未生成: " .. outputPath)
  end

  -- 清理临时JSON文件
  pcall(function()
    if LrFileUtils.exists(tempJsonPath) then
      LrFileUtils.delete(tempJsonPath)
    end
  end)

  return exitCode == 0
end

--[[
  显示预览和调整对话框

  参数:
    thumbPath: 缩略图路径
    frames: 检测到的帧数组
    photoName: 照片名称

  返回:
    confirmed: boolean 是否确认
    adjustedFrames: 调整后的帧数组
]]--
function PreviewDialog.show(thumbPath, frames, photoName)
  local f = LrView.osFactory()
  local bind = LrView.bind

  -- 复制帧数据用于绑定
  local data = {
    frameCount = #frames,
    confirmed = false,
    hasPreview = false,
    previewFailed = false
  }

  -- 获取源图像尺寸（用于相对位置计算）
  local sourceHeight = frames[1] and frames[1].sourceHeight or 1024
  local sourceWidth = frames[1] and frames[1].sourceWidth or 1024
  local isHorizontalFrame = (sourceWidth or 0) >= (sourceHeight or 0)

  -- 为每个帧创建可调整的字段（四边全部可编辑）
  for i, frame in ipairs(frames) do
    data["top_" .. i] = frame.top
    data["bottom_" .. i] = frame.bottom
    data["left_" .. i] = frame.left
    data["right_" .. i] = frame.right
  end

  -- 生成预览图（保存到插件目录，避免临时目录权限问题）
  local pluginPath = _PLUGIN.path
  local previewPath = LrPathUtils.child(pluginPath, "preview_marked.jpg")
  -- 清理可能存在的旧预览图
  if LrFileUtils.exists(previewPath) then
    LrFileUtils.delete(previewPath)
  end
  logger:trace("预览图路径: " .. previewPath)
  logger:trace("缩略图路径: " .. thumbPath)
  logger:trace("缩略图存在: " .. tostring(LrFileUtils.exists(thumbPath)))

  local hasPreview = generatePreview(thumbPath, frames, previewPath)
  data.hasPreview = hasPreview
  data.previewFailed = not hasPreview
  if not hasPreview then
    logger:error("预览图生成失败")
  else
    logger:trace("预览图生成成功，检查文件是否存在...")
    -- 在对话框显示前再次检查文件
    if LrFileUtils.exists(previewPath) then
      logger:trace("预览图文件确认存在: " .. previewPath)
    else
      logger:error("预览图文件不存在（虽然命令成功）: " .. previewPath)
      data.hasPreview = false
      data.previewFailed = true
    end
  end

  -- 构建帧编辑行
  local frameRows = {}

  -- 标题行
  table.insert(frameRows, f:row {
    spacing = f:label_spacing(),
    f:static_text { title = "帧", width = 24, font = "<system/bold>" },
    f:static_text { title = "顶部", width = 64, font = "<system/bold>" },
    f:static_text { title = "底部", width = 64, font = "<system/bold>" },
    f:static_text { title = "左侧", width = 64, font = "<system/bold>" },
    f:static_text { title = "右侧", width = 64, font = "<system/bold>" },
  })

  -- 辅助函数：创建编辑框 + +/-10 按钮组合
  local function makeEditRow(fieldKey)
    return f:row {
      spacing = 1,
      f:edit_field {
        value = bind(fieldKey),
        width_in_chars = 4,
        precision = 0,
      },
      f:column {
        spacing = 0,
        f:push_button {
          title = "+",
          width = 22,
          height = 14,
          action = function()
            data[fieldKey] = (tonumber(data[fieldKey]) or 0) + 10
          end,
        },
        f:push_button {
          title = "-",
          width = 22,
          height = 14,
          action = function()
            data[fieldKey] = (tonumber(data[fieldKey]) or 0) - 10
          end,
        },
      },
    }
  end

  -- 每帧一行
  for i = 1, #frames do
    local frameIndex = i
    table.insert(frameRows, f:row {
      spacing = f:label_spacing(),
      f:static_text { title = tostring(frameIndex), width = 24 },
      makeEditRow("top_" .. frameIndex),
      makeEditRow("bottom_" .. frameIndex),
      makeEditRow("left_" .. frameIndex),
      makeEditRow("right_" .. frameIndex),
    })
  end

  -- 创建对话框内容
  local contents = f:column {
    spacing = f:control_spacing(),
    bind_to_object = data,

    -- 标题
    f:static_text {
      title = "FilmCrop - 预览与调整: " .. photoName,
      font = "<system/bold>",
    },

    f:separator {},

    -- 预览图
    f:static_text {
      title = "检测到 " .. #frames .. " 帧（按实际边界预览）",
      font = "<system/bold>",
    },

    -- 预览图（成功时显示）
    f:static_text {
      title = previewPath,
      visible = bind "hasPreview",
      font = "<system/bold>",
    },
    f:picture {
      path = previewPath,
      width = 400,
      visible = bind "hasPreview",
    },

    -- 错误信息（失败时显示）
    f:static_text {
      title = "预览图生成失败，但裁剪仍会继续",
      visible = bind "previewFailed",
      font = "<system/bold>",
    },

    f:separator {},

    -- 帧边界调整
    f:static_text {
      title = "调整帧边界（像素坐标）:",
      font = "<system/bold>",
    },

    f:column {
      spacing = f:control_spacing(),
      unpack(frameRows)
    },

    f:separator {},

    -- 说明
    f:static_text {
      title = "使用说明：",
      font = "<system/bold>",
    },
    f:static_text {
      title = isHorizontalFrame and "• 横向排列胶片帧：四边均可裁切" or "• 竖向排列胶片帧：四边均可裁切",
      height_in_lines = 2,
    },
    f:static_text {
      title = "• 预览图仅供参考，调整数值后不会实时更新",
      height_in_lines = 2,
    },
    f:static_text {
      title = "• 如需精确调整，请在创建后到'修改照片'模块手动调整",
      height_in_lines = 2,
    },
    f:static_text {
      title = "• 当前检测基于缩略图，最终裁剪会应用到原始高分辨率图像",
      height_in_lines = 2,
    },
  }

  -- 显示对话框
  local result = LrDialogs.presentModalDialog {
    title = "FilmCrop - 预览帧边界",
    contents = contents,
    actionVerb = "创建虚拟副本",
    cancelVerb = "取消",
  }

  -- 构建调整后的帧数据
  local adjustedFrames = {}
  if result == "ok" then
    for i, originalFrame in ipairs(frames) do
      local sourceHeight = originalFrame.sourceHeight or 1024
      local sourceWidth = originalFrame.sourceWidth or 1024
      local isHorizontalFrame = (sourceWidth or 0) >= (sourceHeight or 0)
      logger:trace(string.format("构建adjustedFrames[%d]: isHorizontal=%s, orig.relLeft=%.4f, orig.relRight=%.4f, orig.relTop=%.4f, orig.relBottom=%.4f",
        i, tostring(isHorizontalFrame), originalFrame.relativeLeft or -1, originalFrame.relativeRight or -1, originalFrame.relativeTop or -1, originalFrame.relativeBottom or -1))

      local top = tonumber(data["top_" .. i]) or originalFrame.top
      local bottom = tonumber(data["bottom_" .. i]) or originalFrame.bottom
      local left = tonumber(data["left_" .. i]) or originalFrame.left
      local right = tonumber(data["right_" .. i]) or originalFrame.right

      table.insert(adjustedFrames, {
        index = i,
        top = top,
        bottom = bottom,
        left = left,
        right = right,
        sourceHeight = sourceHeight,
        sourceWidth = sourceWidth,
        relativeTop = round(top / sourceHeight, 6),
        relativeBottom = round(bottom / sourceHeight, 6),
        relativeLeft = round(left / sourceWidth, 6),
        relativeRight = round(right / sourceWidth, 6),
      })
    end
  end

  -- 清理预览图
  if LrFileUtils.exists(previewPath) then
    LrFileUtils.delete(previewPath)
  end

  return result == "ok", adjustedFrames
end

return PreviewDialog
