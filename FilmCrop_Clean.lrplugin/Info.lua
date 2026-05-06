--[[
  FilmCrop.lrplugin
  Lightroom胶片扫描自动裁剪插件

  功能: 自动识别长条扫描胶片中的单帧，并创建虚拟副本
  版本: 2.0.0
]]--

return {
  LrSdkVersion = 6.0,
  LrSdkMinimumVersion = 5.0,
  LrToolkitIdentifier = 'com.filmcrop.lightroom',
  LrPluginName = LOC "$$$/FilmCrop/PluginName=FilmCrop 胶片裁剪",
  LrPluginDescription = "自动识别胶片帧并创建虚拟副本",
  LrPluginInfoUrl = "https://github.com/filmcrop/lightroom",
  LrPluginInfoProvider = 'PluginInfoProvider.lua',

  LrExportMenuItems = {
    {
      title = LOC "$$$/FilmCrop/Menu/DetectFrames=检测胶片帧",
      file = "DetectFrames.lua",
    },
    {
      title = LOC "$$$/FilmCrop/Menu/BatchProcess=批量处理",
      file = "BatchProcess.lua",
    },
  },

  LrLibraryMenuItems = {
    {
      title = LOC "$$$/FilmCrop/Menu/DetectFrames=检测胶片帧",
      file = "DetectFrames.lua",
    },
    {
      title = LOC "$$$/FilmCrop/Menu/BatchProcess=批量处理",
      file = "BatchProcess.lua",
    },
  },

  LrPluginInMenu = "Library",
  LrPluginInMonitor = true,
  LrInitPlugin = "Init.lua",
  LrShutdownPlugin = "Shutdown.lua",
  LrForceInitPlugin = true,

  VERSION = {
    major = 2,
    minor = 2,
    revision = 0,
  },
}
