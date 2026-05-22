--[[
  DiagOrientation.lua
  Lightroom 诊断脚本 — 探测照片 orientation raw metadata 的实际返回值。

  用法:
    1. 临时把下面这段加到 Info.lua 的 LrLibraryMenuItems 中：
       {
         title = "诊断: 查看 orientation",
         file = "tests/DiagOrientation.lua",
       },
    2. 重启 Lightroom
    3. 在图库模块选中一张照片
    4. 菜单: 文件 > 插件额外命令 > NegativeCutter 负片裁切 > 诊断: 查看 orientation

  输出会弹窗显示以下信息：
    - photo:getRawMetadata("orientation") 的原始返回值（类型 + 值）
    - photo:getRawMetadata("dimensions") 的宽高
    - 推荐的四向映射标签
]]--

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'
local LrLogger = import 'LrLogger'

local logger = LrLogger('NegativeCutter.DiagOrientation')
logger:enable("logfile")

LrTasks.startAsyncTask(function()
  local catalog = LrApplication.activeCatalog()
  local target = catalog:getTargetPhoto()

  if not target then
    LrDialogs.message("诊断错误", "请先在图库模块选中一张照片", "critical")
    return
  end

  -- 读取 orientation（这是我们最关心的值）
  local ok, orientation = pcall(function()
    return target:getRawMetadata("orientation")
  end)

  -- 读取 dimensions
  local ok2, dimensions = pcall(function()
    return target:getRawMetadata("dimensions")
  end)

  -- 读取 fileFormat
  local ok3, fileFormat = pcall(function()
    return target:getRawMetadata("fileFormat")
  end)

  -- 读取路径
  local ok4, path = pcall(function()
    return target:getRawMetadata("path")
  end)

  local infoLines = {}
  table.insert(infoLines, "文件: " .. tostring(path or "N/A"))
  table.insert(infoLines, "格式: " .. tostring(fileFormat or "N/A"))
  table.insert(infoLines, "尺寸: " .. tostring((dimensions and dimensions.width) or "?") .. " x " .. tostring((dimensions and dimensions.height) or "?"))
  table.insert(infoLines, "")
  table.insert(infoLines, "orientation 返回值:")
  if ok then
    table.insert(infoLines, "  类型: " .. type(orientation))
    table.insert(infoLines, "  值:   " .. tostring(orientation))
    if type(orientation) == "string" then
      table.insert(infoLines, "  长度: " .. tostring(#orientation))
    end
  else
    table.insert(infoLines, "  读取失败: " .. tostring(orientation))
  end

  table.insert(infoLines, "")
  table.insert(infoLines, "--- 四向映射参考 ---")
  table.insert(infoLines, "如果 orientation 为 AB → 不旋转")
  table.insert(infoLines, "如果 orientation 为 BC → 90° CW")
  table.insert(infoLines, "如果 orientation 为 CD → 180°")
  table.insert(infoLines, "如果 orientation 为 DA → 270° CW")
  table.insert(infoLines, "")
  table.insert(infoLines, "如果返回 nil 或数字，说明 SDK 未提供字符串标签，")
  table.insert(infoLines, "需改用 dimensions 的宽高比判断 + EXIF 数字方向码映射。")

  local msg = table.concat(infoLines, "\n")
  logger:trace("DiagOrientation 输出:\n" .. msg)
  LrDialogs.message("NegativeCutter — Orientation 诊断", msg, "info")
end)
