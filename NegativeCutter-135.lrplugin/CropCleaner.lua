--[[
  CropCleaner.lua — 胶片裁切边界清理模块

  将原本散落在 DetectFrames.lua 和 ProcessAgent.lua 中的 INSET 逻辑
  抽离出来，并支持不同胶片类型（负片/反转片/正片）使用不同的清理策略。

  暴露接口：
    CropCleaner.cleanFrames(frames, sourceWidth, sourceHeight, filmType)
      - filmType: "negative" | "reversal" | "positive"，默认 "negative"
]]--

local LrLogger = import 'LrLogger'
local logger = LrLogger('NegativeCutter.CropCleaner')
logger:enable("logfile")

local CropCleaner = {}

-- 各胶片类型的内收比例（相对坐标）
local INSET_CONFIG = {
  negative = 0.003,   -- 负片：默认 0.3% 内收，清理边界脏边/bleed
  reversal = 0.003,   -- 反转片：与负片相同，可独立调优
  positive = 0.005,   -- 正片：通常对比度更低，稍微多收一点
}

function CropCleaner.getInset(filmType)
  return INSET_CONFIG[filmType] or INSET_CONFIG.negative
end

function CropCleaner.availableTypes()
  return {
    { value = "negative", display = "负片（Negative）" },
    { value = "reversal", display = "反转片（Reversal / 正像胶片）" },
    { value = "positive", display = "正片（Positive / 黑白正片）" },
  }
end

--[[
  为每帧补充缺省绝对坐标，并按胶片类型进行微小内收清理边界脏边/bleed。
  直接修改 frames 数组中的 frame 对象，并返回该数组。
]]--
function CropCleaner.cleanFrames(frames, sourceWidth, sourceHeight, filmType)
  if type(frames) ~= "table" or #frames == 0 then
    return frames
  end

  local inset = CropCleaner.getInset(filmType)
  logger:trace(string.format("CropCleaner 使用胶片类型: %s, inset=%.4f", tostring(filmType), inset))

  local sw = sourceWidth or 1024
  local sh = sourceHeight or 1024

  for _, frame in ipairs(frames) do
    frame.top = frame.top or 0
    frame.bottom = frame.bottom or sh
    frame.left = frame.left or 0
    frame.right = frame.right or sw

    frame.relativeTop = math.min(1.0, (frame.relativeTop or 0.0) + inset)
    frame.relativeBottom = math.max(0.0, (frame.relativeBottom or 1.0) - inset)
    frame.relativeLeft = math.min(1.0, (frame.relativeLeft or 0.0) + inset)
    frame.relativeRight = math.max(0.0, (frame.relativeRight or 1.0) - inset)

    -- 防止内收过度导致坐标反转，保持至少 1% 的有效区域
    if frame.relativeTop >= frame.relativeBottom then
      local mid = (frame.relativeTop + frame.relativeBottom) / 2
      frame.relativeTop = math.max(0.0, mid - 0.005)
      frame.relativeBottom = math.min(1.0, mid + 0.005)
    end
    if frame.relativeLeft >= frame.relativeRight then
      local mid = (frame.relativeLeft + frame.relativeRight) / 2
      frame.relativeLeft = math.max(0.0, mid - 0.005)
      frame.relativeRight = math.min(1.0, mid + 0.005)
    end
  end

  return frames
end

return CropCleaner
