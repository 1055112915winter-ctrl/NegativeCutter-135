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
    {
      title = "导入 FilmCrop XMP...",
      file = "ImportXMP.lua",
    },
    {
      title = "通过 FilmCrop 引擎检测...",
      file = "ImportHTTP.lua",
    },
    {
      title = "监视 FilmCrop JSON...",
      file = "ImportWatch.lua",
    },
    {
      title = "停止监视 FilmCrop JSON",
      file = "StopWatch.lua",
    },
    {
      title = "启动自动检测 (E2E)",
      file = "AutoWatch.lua",
    },
    {
      title = "停止自动检测 (E2E)",
      file = "StopAutoWatch.lua",
    },
    {
      title = LOC "$$$/FilmCrop/Menu/Settings=设置...",
      file = "Settings.lua",
    },
    {
      title = "测试 Python 环境",
      file = "TestPython.lua",
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
    {
      title = "导入 FilmCrop XMP...",
      file = "ImportXMP.lua",
    },
    {
      title = "通过 FilmCrop 引擎检测...",
      file = "ImportHTTP.lua",
    },
    {
      title = "监视 FilmCrop JSON...",
      file = "ImportWatch.lua",
    },
    {
      title = "停止监视 FilmCrop JSON",
      file = "StopWatch.lua",
    },
    {
      title = "启动自动检测 (E2E)",
      file = "AutoWatch.lua",
    },
    {
      title = "停止自动检测 (E2E)",
      file = "StopAutoWatch.lua",
    },
  },

  LrPluginInMenu = "Library",
  LrPluginInMonitor = true,
  LrInitPlugin = "Init.lua",
  LrShutdownPlugin = "Shutdown.lua",
  LrForceInitPlugin = true,

  VERSION = {
    major = 2,
    minor = 0,
    revision = 0,
  },
}
