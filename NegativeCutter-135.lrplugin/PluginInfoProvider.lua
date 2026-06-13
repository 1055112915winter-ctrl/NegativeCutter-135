--[[
  PluginInfoProvider.lua
  提供插件信息到Lightroom
]]--

local LrView = import 'LrView'
local LrPrefs = import 'LrPrefs'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'

local prefs = LrPrefs.prefsForPlugin()

return {
  sectionsForTopOfDialog = function(f, propertyTable)
    -- 确保默认值
    if not prefs.pythonPath then
      prefs.pythonPath = '/usr/bin/python3'
    end
    if not prefs.detectorScript then
      prefs.detectorScript = LrPathUtils.child(_PLUGIN.path, 'detect_thumb.py')
    end
    if not prefs.expectedFrames then
      prefs.expectedFrames = 6
    end

    local detectorScript = LrPathUtils.child(_PLUGIN.path, 'detect_thumb.py')
    local bundledExe = LrPathUtils.child(_PLUGIN.path, 'NegativeCutter')
    -- LrFileUtils.exists returns true/false; avoid strict equality against boolean
    -- in case the SDK returns a different truthy/falsy type.
    local hasScript = LrFileUtils.exists(detectorScript)
    local hasExe = LrFileUtils.exists(bundledExe)
    local scriptStatus
    if hasExe then
      scriptStatus = "✓ 已找到打包引擎 (NegativeCutter)"
    elseif hasScript then
      scriptStatus = "✓ 已找到检测脚本 (detect_thumb.py)"
    else
      scriptStatus = "✗ 未找到检测引擎"
    end

    return {
      {
        title = "NegativeCutter 负片裁切插件",
        synopsis = "自动识别135胶片帧并创建虚拟副本",

        f:row {
          f:static_text {
            title = "版本: 2.4.4",
          },
        },

        f:row {
          f:static_text {
            title = "检测脚本状态: " .. scriptStatus,
          },
        },

        f:row {
          f:static_text {
            title = "使用方法:",
            font = "<system/bold>",
          },
        },

        f:static_text {
          title = "1. 在图库中选择DNG/TIFF格式的胶片扫描文件\n" ..
                  "2. 使用菜单: 文件 > 增效工具额外命令 > NegativeCutter > 检测胶片帧\n" ..
                  "3. 插件将自动检测帧边界并创建虚拟副本\n" ..
                  "4. 每个虚拟副本将应用对应的裁剪",
          height_in_lines = 4,
        },
      },
    }
  end,
}
