--[[
  Settings.lua
  FilmCrop插件设置对话框
]]--

local LrDialogs = import 'LrDialogs'
local LrView = import 'LrView'
local LrPrefs = import 'LrPrefs'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'

local prefs = LrPrefs.prefsForPlugin()

-- 默认值
if not prefs.pythonPath then
  prefs.pythonPath = '/usr/bin/python3'
end
if not prefs.detectorScript then
  prefs.detectorScript = LrPathUtils.child(_PLUGIN.path, 'detect_thumb.py')
end
if not prefs.expectedFrames then
  prefs.expectedFrames = 6
end
if not prefs.maxHeight then
  prefs.maxHeight = 4000
end

-- 创建设置对话框
local function showSettingsDialog()
  local f = LrView.osFactory()

  -- 创建绑定
  local bind = LrView.bind
  local share = LrView.share

  local contents = f:column {
    spacing = f:control_spacing(),

    f:static_text {
      title = "FilmCrop 设置",
      font = "<system/bold>",
    },

    f:separator {},

    -- Python路径设置
    f:row {
      spacing = f:label_spacing(),
      f:static_text {
        title = "Python路径:",
        width = share "label_width",
      },
      f:edit_field {
        value = bind "pythonPath",
        width_in_chars = 40,
      },
    },

    -- 检测脚本路径
    f:row {
      spacing = f:label_spacing(),
      f:static_text {
        title = "检测脚本:",
        width = share "label_width",
      },
      f:edit_field {
        value = bind "detectorScript",
        width_in_chars = 40,
      },
    },

    f:separator {},

    -- 检测参数
    f:static_text {
      title = "检测参数",
      font = "<system/bold>",
    },

    f:row {
      spacing = f:label_spacing(),
      f:static_text {
        title = "预期帧数:",
        width = share "label_width",
      },
      f:edit_field {
        value = bind "expectedFrames",
        width_in_chars = 5,
        precision = 0,
      },
      f:static_text {
        title = "(每卷胶片的帧数，通常为 6)",
      },
    },

    f:row {
      spacing = f:label_spacing(),
      f:static_text {
        title = "最大高度:",
        width = share "label_width",
      },
      f:edit_field {
        value = bind "maxHeight",
        width_in_chars = 6,
        precision = 0,
      },
      f:static_text {
        title = "px (内存优化，默认4000)",
      },
    },

    f:separator {},

    -- 当前设置信息
    f:static_text {
      title = "当前设置",
      font = "<system/bold>",
    },

    f:static_text {
      title = function()
        local scriptExists = LrFileUtils.exists(prefs.detectorScript) and "✓ 已找到" or "✗ 未找到"
        return string.format(
          "Python: %s\n脚本: %s\n预期帧数: %d\n最大高度: %d px",
          prefs.pythonPath,
          scriptExists,
          prefs.expectedFrames,
          prefs.maxHeight
        )
      end,
      height_in_lines = 4,
    },
  }

  local result = LrDialogs.presentModalDialog {
    title = "FilmCrop 设置",
    contents = contents,
    actionVerb = "保存",
    cancelVerb = "取消",
  }

  if result == "ok" then
    LrDialogs.message("FilmCrop", "设置已保存", "info")
  end
end

--[[
  由 Lightroom 菜单项触发执行；请勿在插件初始化时 dofile/require 加载此文件。
--]]
showSettingsDialog()
