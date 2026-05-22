--[[
  ThumbnailAgent.lua
  缩略图获取Agent - 使用 requestJpegThumbnail 获取预览图
]]--

local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'
local LrLogger = import 'LrLogger'

local logger = LrLogger('NegativeCutter.ThumbnailAgent')
logger:enable("logfile")

local ThumbnailAgent = {}

-- 临时工作目录（跨平台）
local WORK_DIR = LrPathUtils.child(LrPathUtils.getStandardFilePath("temp"), "negativecutter")

-- 确保工作目录存在
local function ensureWorkDir()
  if not LrFileUtils.exists(WORK_DIR) then
    LrFileUtils.createAllDirectories(WORK_DIR)
    logger:trace("创建工作目录: " .. WORK_DIR)
  end
end

-- 清理旧文件
local function cleanupOldFiles(photoUuid)
  -- 移除 UUID 中的特殊字符
  local safeUuid = string.gsub(photoUuid, "[^%w]", "_")
  -- 注意：Lua没有直接的文件通配删除，这里简化处理
  local thumbPath = LrPathUtils.child(WORK_DIR, "thumb_" .. safeUuid .. ".jpg")
  local pnmPath = LrPathUtils.child(WORK_DIR, "thumb_" .. safeUuid .. ".pnm")
  local resultPath = LrPathUtils.child(WORK_DIR, "result_" .. safeUuid .. ".json")

  if LrFileUtils.exists(thumbPath) then
    LrFileUtils.delete(thumbPath)
  end
  if LrFileUtils.exists(pnmPath) then
    LrFileUtils.delete(pnmPath)
  end
  if LrFileUtils.exists(resultPath) then
    LrFileUtils.delete(resultPath)
  end
end

--[[
  获取照片的缩略图

  参数:
    photo: LrPhoto 对象
    maxWidth: 最大宽度（默认1024）
    callback: 回调函数 function(success, thumbPath, errorMsg)

  返回:
    通过回调返回结果
]]--
function ThumbnailAgent.extract(photo, maxWidth, callback)
  -- 参数检查
  if not photo then
    callback(false, nil, "photo参数为空")
    return
  end

  maxWidth = maxWidth or 1024
  ensureWorkDir()

  local uuid = photo:getRawMetadata("uuid")
  if not uuid then
    callback(false, nil, "无法获取照片UUID")
    return
  end

  -- 清理旧文件
  cleanupOldFiles(uuid)

  -- 移除 UUID 中的特殊字符，防止路径问题
  local safeUuid = string.gsub(uuid, "[^%w]", "_")
  local thumbPath = LrPathUtils.child(WORK_DIR, "thumb_" .. safeUuid .. ".jpg")
  logger:trace("请求缩略图: " .. uuid .. ", 最大宽度: " .. maxWidth)

  -- requestJpegThumbnail 是异步的，需要使用 LrFunctionContext 和观察器模式
  local jpegData = nil
  local errorMsg = nil
  local isComplete = false

  -- 创建回调函数
  local function thumbnailCallback(data, error)
    jpegData = data
    errorMsg = error
    isComplete = true
    logger:trace("缩略图回调触发, 数据大小: " .. (data and #data or "nil"))
  end

  -- 请求缩略图
  local holdRef = photo:requestJpegThumbnail(maxWidth, nil, thumbnailCallback)

  -- 等待完成（轮询方式）
  local waitCount = 0
  local maxWait = 100  -- 10秒超时

  while not isComplete and waitCount < maxWait do
    LrTasks.sleep(0.1)
    waitCount = waitCount + 1
  end

  -- 释放引用
  if holdRef then
    holdRef = nil
  end

  -- 检查是否超时
  if not isComplete then
    logger:error("缩略图获取超时")
    callback(false, nil, "缩略图获取超时")
    return
  end

  -- 检查是否有错误
  if errorMsg then
    logger:error("缩略图获取失败: " .. errorMsg)
    callback(false, nil, errorMsg)
    return
  end

  -- 检查数据
  if not jpegData or #jpegData == 0 then
    logger:error("缩略图数据为空")
    callback(false, nil, "缩略图数据为空")
    return
  end

  -- 保存到文件
  local success, err = pcall(function()
    local file = io.open(thumbPath, "wb")
    if not file then
      error("无法创建文件: " .. thumbPath)
    end
    file:write(jpegData)
    file:close()
  end)

  if not success then
    logger:error("保存缩略图失败: " .. tostring(err))
    callback(false, nil, "保存缩略图失败: " .. tostring(err))
    return
  end

  logger:trace("缩略图已保存: " .. thumbPath .. " (" .. #jpegData .. " 字节)")
  callback(true, thumbPath, nil)
end

--[[
  获取照片信息

  参数:
    photo: LrPhoto 对象

  返回:
    table 包含照片信息
]]--
function ThumbnailAgent.getPhotoInfo(photo)
  local info = {}

  -- 基本元数据
  info.uuid = photo:getRawMetadata("uuid")
  info.fileName = photo:getFormattedMetadata("fileName")
  info.filePath = photo:getRawMetadata("path")

  -- 尺寸信息
  local dimensions = photo:getRawMetadata("dimensions")
  if dimensions then
    info.width = dimensions.width
    info.height = dimensions.height
  end

  -- 文件格式
  info.fileFormat = photo:getRawMetadata("fileFormat")

  logger:trace("照片信息: " .. info.fileName .. " (" .. (info.width or "?") .. "x" .. (info.height or "?") .. ")")

  return info
end

--[[
  获取临时工作目录
]]--
function ThumbnailAgent.getWorkDir()
  return WORK_DIR
end

--[[
  清理所有临时文件
]]--
function ThumbnailAgent.cleanupAll()
  -- 简化：只清理当前会话的文件
  logger:trace("清理临时文件")
end

return ThumbnailAgent
