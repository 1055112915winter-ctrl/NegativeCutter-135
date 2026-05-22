--[[
  ApplierAgent.lua
  裁剪应用Agent - 将检测到的帧边界应用到Lightroom

  功能:
  1. 应用裁剪设置到照片（直接修改或使用虚拟副本）
  2. 获取/重置当前裁剪设置
]]--

local LrLogger = import 'LrLogger'
local LrApplication = import 'LrApplication'

local logger = LrLogger('NegativeCutter.ApplierAgent')
logger:enable("logfile")

local ApplierAgent = {}

--[[
  应用裁剪设置到照片

  重要: 此函数必须在 catalog:withWriteAccessDo() 块中调用
        否则 applyDevelopSettings 会失败

  参数:
    photo: LrPhoto 对象
    cropRegion: {top, bottom, left, right} 相对坐标 0-1

  返回:
    success: boolean
    errorMsg: string or nil
]]--
function ApplierAgent.applyCrop(photo, cropRegion)
  -- 参数检查
  if not photo then
    return false, "photo参数为空"
  end

  if not cropRegion then
    return false, "cropRegion参数为空"
  end

  -- 检查文件格式
  local fileFormat = photo:getRawMetadata("fileFormat")
  logger:trace("文件格式: " .. tostring(fileFormat))

  -- 确保值在0-1范围内
  local top = math.max(0, math.min(1, cropRegion.top))
  local bottom = math.max(0, math.min(1, cropRegion.bottom))
  local left = math.max(0, math.min(1, cropRegion.left or 0))
  local right = math.max(0, math.min(1, cropRegion.right or 1))

  -- 确保 top < bottom
  if top >= bottom then
    logger:error("无效的裁剪区域: top >= bottom")
    return false, "无效的裁剪区域"
  end

  logger:trace(string.format("应用裁剪设置: top=%.4f, bottom=%.4f, left=%.4f, right=%.4f",
    top, bottom, left, right))

  -- 应用裁剪设置
  -- 注意: 不能在 pcall 中调用 applyDevelopSettings，因为它内部会 yield
  -- 必须在 withWriteAccessDo 块中直接调用
  -- 关键: 每次修改裁剪框时必须同步禁用 Upright，否则 Lightroom 会自动重算透视校正
  -- 忽略微小旋转角（<0.5°），避免扫描噪声导致的斜边
  local rawAngle = cropRegion.cropAngle or 0
  local cropAngle = math.abs(rawAngle) > 0.5 and rawAngle or 0
  if rawAngle ~= cropAngle then
    logger:trace(string.format("忽略微小旋转角 %.3f°，重置为 0", rawAngle))
  end
  local settings = {
    CropTop = top,
    CropBottom = bottom,
    CropLeft = left,
    CropRight = right,
    CropAngle = cropAngle,
    CropConstrainToWarp = 0,
    PerspectiveVertical = 0,
    PerspectiveHorizontal = 0,
    PerspectiveRotate = 0,
    PerspectiveScale = 100,
    PerspectiveAspect = 0,
    PerspectiveUpright = 0,
    UprightMode = 0,
    UprightCenterMode = 0,
    UprightCenterNormX = 0.5,
    UprightCenterNormY = 0.5,
    LensProfileEnable = 0,
  }

  -- 关键修复：applyDevelopSettings 在图库模块中对虚拟副本可能无效
  -- 优先使用 catalog:adjustPhotoDevelopSettings（SDK 6.2+），该 API 无需 withWriteAccessDo 且在虚拟副本上可靠
  local catalog = LrApplication.activeCatalog()
  local useAdjust = type(catalog.adjustPhotoDevelopSettings) == "function"

  if useAdjust then
    logger:trace("使用 adjustPhotoDevelopSettings 应用设置")
    catalog:adjustPhotoDevelopSettings(photo, settings)
  else
    logger:trace("使用 applyDevelopSettings 应用设置")
    photo:applyDevelopSettings(settings)
  end

  -- 验证设置是否生效（仅作参考）
  local verifySettings = photo:getDevelopSettings()
  logger:trace(string.format("验证裁剪设置: CropTop=%.4f, CropBottom=%.4f, CropLeft=%.4f, CropRight=%.4f",
    verifySettings.CropTop or -1, verifySettings.CropBottom or -1, verifySettings.CropLeft or -1, verifySettings.CropRight or -1))

  logger:trace("裁剪已应用")
  return true, nil
end

--[[
  应用第一个帧的裁剪（快速预览）

  重要: 此函数必须在 catalog:withWriteAccessDo() 块中调用

  参数:
    photo: LrPhoto 对象
    frames: 帧数组

  返回:
    success: boolean
]]--

--[[
  重置裁剪及透视变换（全图显示，清除所有手动旋转/倾斜/透视校正）

  重要: 此函数必须在 catalog:withWriteAccessDo() 块中调用
]]--
function ApplierAgent.resetCrop(photo)
  if not photo then
    return false, "photo参数为空"
  end

  logger:trace("重置裁剪及透视变换")
  local settings = {
    CropTop = 0,
    CropBottom = 1,
    CropLeft = 0,
    CropRight = 1,
    CropAngle = 0,
    CropConstrainToWarp = 0,
    PerspectiveVertical = 0,
    PerspectiveHorizontal = 0,
    PerspectiveRotate = 0,
    PerspectiveScale = 100,
    PerspectiveAspect = 0,
    PerspectiveUpright = 0,
    UprightMode = 0,
    UprightCenterMode = 0,
    UprightCenterNormX = 0.5,
    UprightCenterNormY = 0.5,
    LensProfileEnable = 0,
  }

  -- 对齐 applyCrop 的 API 选择：优先使用 adjustPhotoDevelopSettings
  local catalog = LrApplication.activeCatalog()
  local useAdjust = type(catalog.adjustPhotoDevelopSettings) == "function"

  if useAdjust then
    logger:trace("使用 adjustPhotoDevelopSettings 重置裁剪")
    catalog:adjustPhotoDevelopSettings(photo, settings)
  else
    logger:trace("使用 applyDevelopSettings 重置裁剪")
    photo:applyDevelopSettings(settings)
  end

  logger:trace("裁剪及透视变换已重置")
  return true, nil
end

return ApplierAgent
