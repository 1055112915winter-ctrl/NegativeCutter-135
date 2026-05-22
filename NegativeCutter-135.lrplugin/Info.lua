--[[
  NegativeCutter-135.lrplugin
  Lightroom 135 胶片扫描自动裁剪插件

  功能: 自动识别长条扫描胶片中的单帧，并创建虚拟副本
  版本: 2.4.1
]]--

return {
  LrSdkVersion = 6.0,
  LrSdkMinimumVersion = 5.0,
  LrToolkitIdentifier = 'com.negativecutter.lightroom',
  LrPluginName = LOC "$$$/NegativeCutter/PluginName=NegativeCutter 负片裁切",
  LrPluginDescription = "自动识别135胶片帧并创建虚拟副本。作者：李冬天（小红书号：李冬天 SimplyWinter）",
  LrPluginInfoUrl = "https://github.com/1055112915winter-ctrl/NegativeCutter-135",
  LrPluginInfoProvider = 'PluginInfoProvider.lua',

  LrExportMenuItems = {
    {
      title = LOC "$$$/NegativeCutter/Menu/DetectFrames=检测胶片帧",
      file = "DetectFrames.lua",
    },
    {
      title = LOC "$$$/NegativeCutter/Menu/BatchProcess=批量处理",
      file = "BatchProcess.lua",
    },
    {
      title = LOC "$$$/NegativeCutter/Menu/Sponsor=☕ 赞助插件",
      file = "Sponsor.lua",
    },
    {
      title = LOC "$$$/NegativeCutter/Menu/Feedback=🐛 问题反馈",
      file = "Feedback.lua",
    },
  },

  LrLibraryMenuItems = {
    {
      title = LOC "$$$/NegativeCutter/Menu/DetectFrames=检测胶片帧",
      file = "DetectFrames.lua",
    },
    {
      title = LOC "$$$/NegativeCutter/Menu/BatchProcess=批量处理",
      file = "BatchProcess.lua",
    },
    {
      title = LOC "$$$/NegativeCutter/Menu/DiagOrientation=[诊断] 查看 orientation",
      file = "tests/DiagOrientation.lua",
    },
    {
      title = LOC "$$$/NegativeCutter/Menu/Sponsor=☕ 赞助插件",
      file = "Sponsor.lua",
    },
    {
      title = LOC "$$$/NegativeCutter/Menu/Feedback=🐛 问题反馈",
      file = "Feedback.lua",
    },
  },

  LrPluginInMenu = "Library",
  LrPluginInMonitor = true,
  LrInitPlugin = "Init.lua",
  LrShutdownPlugin = "Shutdown.lua",
  LrForceInitPlugin = true,

  VERSION = {
    major = 2,
    minor = 4,
    revision = 1,
  },
}
