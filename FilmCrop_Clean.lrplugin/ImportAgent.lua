--[[
  FilmCrop 导入代理 - 三种 Lightroom 集成模式
  1. XMP 边车导入
  2. HTTP API 调用
  3. JSON 文件监视
]]--

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local LrTasks = import 'LrTasks'
local LrFileUtils = import 'LrFileUtils'
local LrView = import 'LrView'

local logger = LrLogger('FilmCropImport')
logger:enable("logfile")

local pluginPath = _PLUGIN.path
local WORK_DIR = LrPathUtils.child(LrPathUtils.getStandardFilePath("temp"), "filmcrop")

-- Lr Lua sandbox does NOT register a `json` toolkit script; require("json")
-- fails with "Could not load toolkit script: json". Load the bundled pure-
-- Lua decoder via dofile instead — this is the same mechanism we already
-- use for ProcessAgent.lua / ApplierAgent.lua.
local json = dofile(LrPathUtils.child(pluginPath, "json.lua"))

-- =====================================================================
-- 公共: 创建虚拟副本并应用裁剪
-- =====================================================================
local function createVirtualCopiesFromFrames(catalog, photo, frames, sourceW, sourceH, cropAngle, existingCopies, duplicateAction)
  existingCopies = existingCopies or {}
  duplicateAction = duplicateAction or "create"
  local fileName = photo:getFormattedMetadata('fileName')
  local baseName = fileName:gsub("%..+$", "")
  local created = 0
  local updated = 0
  local skipped = 0
  local errors = {}
  local photoPath = photo:getRawMetadata("path")

  for frameIdx, frame in ipairs(frames) do
    local copyName = string.format("%s_帧%02d", baseName, frameIdx)
    local existingPhoto = existingCopies[photoPath] and existingCopies[photoPath][copyName]

    if existingPhoto and duplicateAction == "skip" then
      skipped = skipped + 1
    elseif existingPhoto and duplicateAction == "overwrite" then
      -- 更新现有虚拟副本的裁剪设置
      catalog:setSelectedPhotos(existingPhoto, {existingPhoto})
      LrTasks.sleep(0.2)

      local ApplierAgent = dofile(LrPathUtils.child(pluginPath, "ApplierAgent.lua"))
      local applyErr = nil
      catalog:withWriteAccessDo(string.format("更新第%d帧裁剪", frameIdx), function(context)
        local success, err = ApplierAgent.applyCrop(existingPhoto, {
          top = frame.relativeTop or 0,
          bottom = frame.relativeBottom or 1,
          left = frame.relativeLeft or 0,
          right = frame.relativeRight or 1,
          sourceWidth = sourceW,
          sourceHeight = sourceH,
          cropAngle = cropAngle or 0
        })
        if not success then applyErr = err or "未知错误" end
      end)

      if applyErr then
        table.insert(errors, string.format("%s: 第%d帧裁剪更新失败 - %s", fileName, frameIdx, applyErr))
      else
        updated = updated + 1
      end

      LrTasks.sleep(0.2)
    else
      -- 创建新虚拟副本（原有逻辑）
      catalog:setSelectedPhotos(photo, {photo})
      LrTasks.sleep(0.1)

      local virtualCopy = nil
      catalog:withWriteAccessDo(string.format("创建第%d帧虚拟副本", frameIdx), function(context)
        local copies = catalog:createVirtualCopies()
        if copies and #copies > 0 then
          virtualCopy = copies[1]
        end
      end)

      if not virtualCopy then
        table.insert(errors, string.format("%s: 第%d帧虚拟副本创建失败", fileName, frameIdx))
      else
        catalog:setSelectedPhotos(virtualCopy, {virtualCopy})
        LrTasks.sleep(0.2)

        local ApplierAgent = dofile(LrPathUtils.child(pluginPath, "ApplierAgent.lua"))
        catalog:withWriteAccessDo(string.format("重置第%d帧裁剪", frameIdx), function(context)
          ApplierAgent.resetCrop(virtualCopy)
        end)
        LrTasks.sleep(0.8)

        if sourceW and sourceW > 0 and sourceH and sourceH > 0 then
          local applyErr = nil
          catalog:withWriteAccessDo(string.format("应用第%d帧裁剪", frameIdx), function(context)
            local success, err = ApplierAgent.applyCrop(virtualCopy, {
              top = frame.relativeTop or 0,
              bottom = frame.relativeBottom or 1,
              left = frame.relativeLeft or 0,
              right = frame.relativeRight or 1,
              sourceWidth = sourceW,
              sourceHeight = sourceH,
              cropAngle = cropAngle or 0
            })
            if not success then applyErr = err or "未知错误" end
          end)

          if applyErr then
            table.insert(errors, string.format("%s: 第%d帧裁剪应用失败 - %s", fileName, frameIdx, applyErr))
          else
            created = created + 1
          end
        end

        pcall(function()
          virtualCopy:setRawMetadata('copyName', copyName)
        end)

        LrTasks.sleep(0.2)
      end
    end
  end

  return created, errors, updated, skipped
end

-- =====================================================================
-- 目录扫描辅助函数
-- =====================================================================
local function getDirectoryFiles(directory)
  -- 尝试 Lightroom SDK 原生方法（新版本可能支持）
  local ok, files = pcall(function()
    return LrFileUtils.filesInDirectory(directory)
  end)
  if ok and type(files) == "table" then return files end

  ok, files = pcall(function()
    return LrFileUtils.directoryFiles(directory)
  end)
  if ok and type(files) == "table" then return files end

  -- 回退：使用 Python 临时脚本列出目录
  if not LrFileUtils.exists(WORK_DIR) then
    LrFileUtils.createAllDirectories(WORK_DIR)
  end

  local pyCode = string.format([[
import json, os
d = %q
try:
    files = [os.path.join(d, f) for f in sorted(os.listdir(d))]
    print(json.dumps(files))
except Exception:
    print(json.dumps([]))
]], directory)

  local tempPy = LrPathUtils.child(WORK_DIR, "listdir_" .. tostring(math.random(100000)) .. ".py")
  local tempOut = LrPathUtils.child(WORK_DIR, "listdir_out_" .. tostring(math.random(100000)) .. ".txt")

  local file = io.open(tempPy, "w")
  if not file then return nil end
  file:write(pyCode)
  file:close()

  local pythonPaths = {"/usr/bin/python3", "/usr/local/bin/python3", "/opt/homebrew/bin/python3"}
  local pythonPath = "python3"
  for _, p in ipairs(pythonPaths) do
    if LrFileUtils.exists(p) then
      pythonPath = p
      break
    end
  end

  local cmd = string.format('"%s" "%s" > "%s" 2>&1', pythonPath, tempPy, tempOut)
  LrTasks.execute(cmd)

  local output = ""
  pcall(function()
    output = LrFileUtils.readFile(tempOut) or ""
  end)

  pcall(function()
    LrFileUtils.delete(tempPy)
    LrFileUtils.delete(tempOut)
  end)

  local decodeOk, result = pcall(function() return json.decode(output) end)
  if decodeOk and type(result) == "table" then
    return result
  end
  return nil
end

local function scanFilmcropXmp(directory)
  local allFiles = getDirectoryFiles(directory)
  if not allFiles then return {} end
  local xmpFiles = {}
  for _, fpath in ipairs(allFiles) do
    local fname = LrPathUtils.leafName(fpath)
    if fname:lower():match("%.filmcrop%.xmp$") then
      table.insert(xmpFiles, fpath)
    end
  end
  table.sort(xmpFiles)
  return xmpFiles
end

-- =====================================================================
-- XMP 解析辅助函数
-- =====================================================================
local function parseXmpContent(xmpContent)
  local frames = {}
  for frameXml in xmpContent:gmatch("<rdf:li>(.-)</rdf:li>") do
    local frame = {}
    for key, val in frameXml:gmatch("filmcrop:(%w+)=\"([^\"]+)\"") do
      frame[key] = tonumber(val) or val
    end
    if frame.index then
      table.insert(frames, frame)
    end
  end
  table.sort(frames, function(a, b) return (a.index or 0) < (b.index or 0) end)
  return frames
end

-- =====================================================================
-- 重复虚拟副本检测
-- =====================================================================
local function buildExistingCopiesMap(catalog, selectedPhotos)
  local targetPaths = {}
  for _, photo in ipairs(selectedPhotos) do
    targetPaths[photo:getRawMetadata("path")] = true
  end

  local map = {}
  for _, photo in ipairs(catalog:getAllPhotos()) do
    local path = photo:getRawMetadata("path")
    if targetPaths[path] then
      if not map[path] then map[path] = {} end
      local copyName = photo:getFormattedMetadata("copyName") or ""
      if copyName ~= "" then
        map[path][copyName] = photo
      end
    end
  end
  return map
end

local function showDuplicateDialog(duplicateCount)
  local f = LrView.osFactory()
  local bind = LrView.bind
  local dialogData = { action = "overwrite" }

  local contents = f:column {
    spacing = f:control_spacing(),
    bind_to_object = dialogData,
    f:static_text {
      title = string.format("发现 %d 个虚拟副本已存在。", duplicateCount),
      height_in_lines = 2,
    },
    f:static_text {
      title = "请选择处理方式：",
    },
    f:row {
      spacing = f:label_spacing(),
      f:radio_button {
        title = "覆盖裁剪设置 (应用到现有虚拟副本)",
        value = bind("action"),
        checked_value = "overwrite",
      },
    },
    f:row {
      spacing = f:label_spacing(),
      f:radio_button {
        title = "跳过现有副本 (不修改)",
        value = bind("action"),
        checked_value = "skip",
      },
    },
  }

  local result = LrDialogs.presentModalDialog {
    title = "FilmCrop - 虚拟副本已存在",
    contents = contents,
    actionVerb = "确定",
    cancelVerb = "取消",
  }

  if result ~= "ok" then return nil end
  return dialogData.action
end

-- =====================================================================
-- US-009: XMP 边车导入模式
-- =====================================================================
local function importFromXMP()
  logger:trace("=== XMP 导入模式 ===")

  local catalog = LrApplication.activeCatalog()
  local selectedPhotos = catalog:getTargetPhotos()

  if not selectedPhotos or #selectedPhotos == 0 then
    LrDialogs.message("FilmCrop - XMP 导入", "请先选择要导入的原始图像", "info")
    return
  end

  -- 目录选择器
  local dirResult = LrDialogs.runOpenPanel {
    title = "选择包含 FilmCrop XMP 边车文件的文件夹",
    canChooseFiles = false,
    canChooseDirectories = true,
    allowsMultipleSelection = false,
  }

  if not dirResult or #dirResult == 0 then return end
  local directory = dirResult[1]

  -- 扫描 .filmcrop.xmp 文件
  local xmpFiles = scanFilmcropXmp(directory)
  if #xmpFiles == 0 then
    LrDialogs.message("FilmCrop - 未找到文件", "该文件夹中没有找到 .filmcrop.xmp 文件", "warning")
    return
  end

  -- 解析所有 XMP 文件并匹配到照片
  local xmpData = {}
  local unmatchedXmps = {}

  for _, xmpPath in ipairs(xmpFiles) do
    local xmpContent = LrFileUtils.readFile(xmpPath)
    if xmpContent and xmpContent ~= "" then
      local frames = parseXmpContent(xmpContent)
      if #frames > 0 then
        local xmpBase = LrPathUtils.leafName(xmpPath):gsub("%.filmcrop%.xmp$", ""):gsub("%.filmcrop%.XMP$", "")
        local matches = {}
        for _, photo in ipairs(selectedPhotos) do
          local fileName = photo:getFormattedMetadata('fileName')
          local photoBase = fileName:gsub("%..+$", "")
          if photoBase == xmpBase then
            table.insert(matches, photo)
          end
        end
        if #matches > 0 then
          table.insert(xmpData, {
            path = xmpPath,
            frames = frames,
            photos = matches,
            baseName = xmpBase,
          })
        else
          table.insert(unmatchedXmps, LrPathUtils.leafName(xmpPath))
        end
      end
    end
  end

  if #xmpData == 0 then
    local msg = "未找到与选中照片匹配的 XMP 文件。"
    if #unmatchedXmps > 0 then
      msg = msg .. "\n\n未匹配的文件:\n" .. table.concat(unmatchedXmps, "\n")
    end
    LrDialogs.message("FilmCrop - 无匹配", msg, "warning")
    return
  end

  -- 检测重复虚拟副本
  local existingCopies = buildExistingCopiesMap(catalog, selectedPhotos)
  local duplicateCount = 0

  for _, entry in ipairs(xmpData) do
    for _, photo in ipairs(entry.photos) do
      local path = photo:getRawMetadata("path")
      local fileName = photo:getFormattedMetadata('fileName')
      local photoBase = fileName:gsub("%..+$", "")
      for frameIdx, _ in ipairs(entry.frames) do
        local copyName = string.format("%s_帧%02d", photoBase, frameIdx)
        if existingCopies[path] and existingCopies[path][copyName] then
          duplicateCount = duplicateCount + 1
        end
      end
    end
  end

  local duplicateAction = "create"
  if duplicateCount > 0 then
    local choice = showDuplicateDialog(duplicateCount)
    if not choice then return end
    duplicateAction = choice
  end

  -- 批量导入
  local totalCreated = 0
  local totalUpdated = 0
  local totalSkipped = 0
  local allErrors = {}

  for _, entry in ipairs(xmpData) do
    for _, photo in ipairs(entry.photos) do
      local w = photo:getRawMetadata("width") or 1024
      local h = photo:getRawMetadata("height") or 1024
      local created, errors, updated, skipped = createVirtualCopiesFromFrames(
        catalog, photo, entry.frames, w, h, 0, existingCopies, duplicateAction
      )
      totalCreated = totalCreated + created
      totalUpdated = totalUpdated + updated
      totalSkipped = totalSkipped + skipped
      for _, err in ipairs(errors) do table.insert(allErrors, err) end
    end
  end

  -- 显示结果
  local msg = string.format("创建: %d\n更新: %d\n跳过: %d", totalCreated, totalUpdated, totalSkipped)
  if #unmatchedXmps > 0 then
    msg = msg .. "\n\n未匹配的 XMP 文件:\n" .. table.concat(unmatchedXmps, "\n")
  end
  if #allErrors > 0 then
    local errMsg = table.concat(allErrors, "\n")
    if #errMsg > 500 then errMsg = string.sub(errMsg, 1, 500) .. "\n..." end
    msg = msg .. "\n\n错误:\n" .. errMsg
    LrDialogs.message("FilmCrop - XMP 导入完成 (部分失败)", msg, "warning")
  else
    LrDialogs.message("FilmCrop - XMP 导入完成", msg, "info")
  end
end

-- =====================================================================
-- US-010: HTTP API 模式
-- =====================================================================
local function detectViaHttp()
  logger:trace("=== HTTP API 模式 ===")

  local catalog = LrApplication.activeCatalog()
  local selectedPhotos = catalog:getTargetPhotos()

  if not selectedPhotos or #selectedPhotos == 0 then
    LrDialogs.message("FilmCrop - HTTP 检测", "请先选择要处理的胶片扫描文件", "info")
    return
  end

  -- SDK 限制：applyDevelopSettings 仅在修改照片模块生效
  local LrApplicationView = import 'LrApplicationView'
  local currentModule = LrApplicationView.getCurrentModuleName()
  if currentModule ~= "develop" then
    LrDialogs.message(
      "FilmCrop - 请在修改照片模块中运行",
      "由于 Lightroom SDK 限制，applyDevelopSettings 在图库模块中对虚拟副本无法生效。\n\n请切换到「修改照片」模块后重试。",
      "warning"
    )
    return
  end

  local f = LrView.osFactory()
  local bind = LrView.bind
  local dialogData = {
    apiUrl = "http://localhost:8765",
    expectedFrames = prefs.expectedFrames or 6,
  }
  local contents = f:column {
    spacing = f:control_spacing(),
    bind_to_object = dialogData,
    f:static_text { title = "FilmCrop 独立引擎 API 地址:" },
    f:edit_field { value = bind "apiUrl", width_in_chars = 40 },
    f:row {
      spacing = f:label_spacing(),
      f:static_text { title = "预期帧数:", width = 80 },
      f:edit_field {
        value = bind "expectedFrames",
        width_in_chars = 5,
        precision = 0,
      },
      f:static_text { title = "(填 0 自动检测，或手动指定实际帧数)" },
    },
    f:static_text { title = "请确保独立引擎已启动 (python -m filmcrop.gui)" },
  }

  local result = LrDialogs.presentModalDialog {
    title = "FilmCrop - HTTP 检测",
    contents = contents,
    actionVerb = "开始检测",
    cancelVerb = "取消",
  }
  if result ~= "ok" then return end

  local apiUrl = dialogData.apiUrl or "http://localhost:8765"
  local expectedFrames = tonumber(dialogData.expectedFrames) or (prefs.expectedFrames or 6)

  local hasHttp = false
  pcall(function()
    local http = require("socket.http")
    local ltn12 = require("ltn12")
    local response = {}
    local _, status = http.request {
      url = apiUrl .. "/health",
      sink = ltn12.sink.table(response),
    }
    if status == 200 then hasHttp = true end
  end)

  if not hasHttp then
    LrDialogs.message(
      "FilmCrop - 引擎未连接",
      "无法连接到 FilmCrop 独立引擎。\n\n请按以下步骤操作:\n1. 在终端运行: python -m filmcrop.gui\n2. 在 GUI 中点击「工具 → 启动 API 服务器」\n3. 重新运行此菜单项",
      "warning"
    )
    return
  end

  local LrProgressScope = import 'LrProgressScope'
  local progress = LrProgressScope {
    title = "FilmCrop HTTP 检测",
    caption = "正在连接引擎...",
  }
  progress:setPortionComplete(0, #selectedPhotos)

  local totalCreated = 0
  local allErrors = {}

  for i, photo in ipairs(selectedPhotos) do
    if progress:isCanceled() then
      table.insert(allErrors, "用户取消")
      break
    end

    local fileName = photo:getFormattedMetadata('fileName')
    progress:setCaption(string.format("正在检测: %s (%d/%d)", fileName, i, #selectedPhotos))

    local originalPath = photo:getRawMetadata("path")

    local analyzeResult = nil
    local httpOk, httpErr = pcall(function()
      local http = require("socket.http")
      local ltn12 = require("ltn12")
      local reqBody = json.encode({
        image_path = originalPath,
        expected_frames = expectedFrames,
        cleanup_scale = 0.5,
      })
      local response = {}
      local _, status = http.request {
        url = apiUrl .. "/analyze",
        method = "POST",
        headers = {
          ["Content-Type"] = "application/json",
          ["Content-Length"] = tostring(#reqBody),
        },
        source = ltn12.source.string(reqBody),
        sink = ltn12.sink.table(response),
      }
      if status == 200 then
        analyzeResult = json.decode(table.concat(response))
      else
        error("HTTP " .. tostring(status))
      end
    end)

    if not httpOk then
      table.insert(allErrors, fileName .. ": 请求失败 - " .. tostring(httpErr))
    elseif not analyzeResult or not analyzeResult.frames then
      table.insert(allErrors, fileName .. ": API 分析失败")
    else
      -- 方向对齐：处理 EXIF 方向与像素维度不一致的情况
      local ProcessAgent = dofile(LrPathUtils.child(pluginPath, "ProcessAgent.lua"))
      analyzeResult = ProcessAgent.directionAlign(analyzeResult, photo)

      local w = analyzeResult.sourceWidth or photo:getRawMetadata("width") or 1024
      local h = analyzeResult.sourceHeight or photo:getRawMetadata("height") or 1024

      progress:setCaption(string.format("正在创建虚拟副本: %s (%d/%d)", fileName, i, #selectedPhotos))

      local created, errors = createVirtualCopiesFromFrames(
        catalog, photo, analyzeResult.frames, w, h, analyzeResult.cropAngle or 0
      )
      totalCreated = totalCreated + created
      for _, err in ipairs(errors) do table.insert(allErrors, err) end
    end

    progress:setPortionComplete(i, #selectedPhotos)
  end

  progress:done()

  if #allErrors > 0 then
    local msg = table.concat(allErrors, "\n")
    if #msg > 500 then msg = string.sub(msg, 1, 500) .. "\n..." end
    LrDialogs.message("FilmCrop - HTTP 检测完成 (部分失败)",
      string.format("创建虚拟副本: %d\n失败: %d\n\n%s", totalCreated, #allErrors, msg), "warning")
  else
    LrDialogs.message("FilmCrop - HTTP 检测完成",
      string.format("成功创建 %d 个虚拟副本", totalCreated), "info")
  end
end

-- =====================================================================
-- US-011: JSON 监视模式
-- =====================================================================
local function watchJsonFile()
  logger:trace("=== JSON 监视模式 ===")

  -- 如果已在监视中，询问用户操作
  if prefs.watchActive and prefs.watchJsonPath then
    local result = LrDialogs.confirm(
      "FilmCrop - JSON 监视中",
      "当前正在监视:\n" .. tostring(prefs.watchJsonPath) .. "\n\n请选择操作:",
      "停止监视",
      "取消",
      "选择新文件"
    )
    if result == "cancel" then
      return
    elseif result == "ok" then
      prefs.watchActive = false
      prefs.watchJsonPath = nil
      LrDialogs.message("FilmCrop", "JSON 监视已停止", "info")
      return
    end
    -- result == "other" → 选择新文件，继续执行
  end

  local catalog = LrApplication.activeCatalog()
  local selectedPhotos = catalog:getTargetPhotos()

  if not selectedPhotos or #selectedPhotos == 0 then
    LrDialogs.message("FilmCrop - JSON 监视", "请先选择要关联的原始图像", "info")
    return
  end

  -- SDK 限制：applyDevelopSettings 仅在修改照片模块生效
  local LrApplicationView = import 'LrApplicationView'
  local currentModule = LrApplicationView.getCurrentModuleName()
  if currentModule ~= "develop" then
    LrDialogs.message(
      "FilmCrop - 请在修改照片模块中运行",
      "由于 Lightroom SDK 限制，applyDevelopSettings 在图库模块中对虚拟副本无法生效。\n\n请切换到「修改照片」模块后重试。",
      "warning"
    )
    return
  end

  local jsonPath = LrDialogs.runOpenPanel {
    title = "选择 FilmCrop JSON 边车文件",
    canChooseFiles = true,
    canChooseDirectories = false,
    allowsMultipleSelection = false,
    fileTypes = {"json"},
  }

  if not jsonPath or #jsonPath == 0 then return end
  jsonPath = jsonPath[1]

  local function parseJson(content)
    local decodeOk, data = pcall(function() return json.decode(content) end)
    if not decodeOk or type(data) ~= "table" then
      return nil, "JSON 解析失败"
    end
    if not data.frames or #data.frames == 0 then
      return nil, "未找到帧数据"
    end
    -- 补全缺省坐标
    for _, frame in ipairs(data.frames) do
      frame.top = frame.top or 0
      frame.bottom = frame.bottom or (data.sourceHeight or 1024)
      frame.left = frame.left or 0
      frame.right = frame.right or (data.sourceWidth or 1024)
      frame.relativeTop = frame.relativeTop or 0.0
      frame.relativeBottom = frame.relativeBottom or 1.0
      frame.relativeLeft = frame.relativeLeft or 0.0
      frame.relativeRight = frame.relativeRight or 1.0
    end
    table.sort(data.frames, function(a, b) return (a.index or 0) < (b.index or 0) end)
    return data
  end

  local function loadAndApply(isInitial)
    local content = LrFileUtils.readFile(jsonPath)
    if not content or content == "" then
      return false, "无法读取 JSON 文件"
    end

    local data, err = parseJson(content)
    if not data then
      return false, err
    end

    -- 方向对齐：处理 EXIF 方向与像素维度不一致的情况
    local ProcessAgent = dofile(LrPathUtils.child(pluginPath, "ProcessAgent.lua"))
    for _, photo in ipairs(selectedPhotos) do
      data = ProcessAgent.directionAlign(data, photo)
    end

    -- 重复虚拟副本检测
    local existingCopies = buildExistingCopiesMap(catalog, selectedPhotos)
    local duplicateCount = 0
    for _, photo in ipairs(selectedPhotos) do
      local path = photo:getRawMetadata("path")
      local fileName = photo:getFormattedMetadata('fileName')
      local photoBase = fileName:gsub("%..+$", "")
      for frameIdx, _ in ipairs(data.frames) do
        local copyName = string.format("%s_帧%02d", photoBase, frameIdx)
        if existingCopies[path] and existingCopies[path][copyName] then
          duplicateCount = duplicateCount + 1
        end
      end
    end

    local duplicateAction = "create"
    if duplicateCount > 0 then
      if isInitial then
        local choice = showDuplicateDialog(duplicateCount)
        if not choice then return false, "用户取消" end
        duplicateAction = choice
      else
        local result = LrDialogs.confirm(
          "FilmCrop - JSON 文件已更新",
          string.format("检测到 %d 个虚拟副本已存在。\n\n是否应用更新的帧边界?", duplicateCount),
          "覆盖",
          "取消",
          "跳过"
        )
        if result == "cancel" then
          return false, "用户取消"
        elseif result == "other" then
          duplicateAction = "skip"
        else
          duplicateAction = "overwrite"
        end
      end
    end

    local totalCreated = 0
    local totalUpdated = 0
    local totalSkipped = 0
    local allErrors = {}

    for _, photo in ipairs(selectedPhotos) do
      local w = data.sourceWidth or photo:getRawMetadata("width") or 1024
      local h = data.sourceHeight or photo:getRawMetadata("height") or 1024
      local created, errors, updated, skipped = createVirtualCopiesFromFrames(
        catalog, photo, data.frames, w, h, data.cropAngle or 0, existingCopies, duplicateAction
      )
      totalCreated = totalCreated + created
      totalUpdated = totalUpdated + updated
      totalSkipped = totalSkipped + skipped
      for _, e in ipairs(errors) do table.insert(allErrors, e) end
    end

    local msg = string.format("创建: %d, 更新: %d, 跳过: %d", totalCreated, totalUpdated, totalSkipped)
    if #allErrors > 0 then
      local errMsg = table.concat(allErrors, "\n")
      if #errMsg > 300 then errMsg = string.sub(errMsg, 1, 300) .. "\n..." end
      msg = msg .. "\n错误:\n" .. errMsg
    end

    return true, msg
  end

  -- 初始加载（带进度条）
  local LrProgressScope = import 'LrProgressScope'
  local progress = LrProgressScope {
    title = "FilmCrop JSON 导入",
    caption = "正在解析 JSON...",
  }

  local ok, msg = loadAndApply(true)
  progress:done()

  if not ok then
    LrDialogs.message("FilmCrop - JSON 导入失败", msg, "critical")
    return
  end

  LrDialogs.message("FilmCrop - JSON 监视已启动",
    msg .. "\n\nFilmCrop 将每 2 秒检查一次文件更新。\n（可通过「停止监视 FilmCrop JSON」菜单项随时终止）",
    "info")

  -- 保存监视状态
  prefs.watchActive = true
  prefs.watchJsonPath = jsonPath

  -- 后台轮询
  LrTasks.startAsyncTask(function()
    local lastModified = LrFileUtils.fileAttributes(jsonPath).fileModificationDate or 0
    while prefs.watchActive do
      LrTasks.sleep(2)
      if not prefs.watchActive then break end

      local attrs = LrFileUtils.fileAttributes(jsonPath)
      if attrs and attrs.fileModificationDate and attrs.fileModificationDate > lastModified then
        lastModified = attrs.fileModificationDate
        logger:trace("JSON 文件已更新，重新应用...")
        local success, message = loadAndApply(false)
        if success then
          logger:trace(message)
        else
          logger:trace("更新失败: " .. tostring(message))
        end
      end
    end

    prefs.watchActive = false
    prefs.watchJsonPath = nil
    logger:trace("JSON 监视已终止")
  end)
end

-- =====================================================================
-- 自动检测模式（无对话框）
-- =====================================================================
local function parseJson(content)
  local decodeOk, data = pcall(function() return json.decode(content) end)
  if not decodeOk or type(data) ~= "table" then
    return nil, "JSON 解析失败"
  end
  if not data.frames or #data.frames == 0 then
    return nil, "未找到帧数据"
  end
  for _, frame in ipairs(data.frames) do
    frame.top = frame.top or 0
    frame.bottom = frame.bottom or (data.sourceHeight or 1024)
    frame.left = frame.left or 0
    frame.right = frame.right or (data.sourceWidth or 1024)
    frame.relativeTop = frame.relativeTop or 0.0
    frame.relativeBottom = frame.relativeBottom or 1.0
    frame.relativeLeft = frame.relativeLeft or 0.0
    frame.relativeRight = frame.relativeRight or 1.0
  end
  table.sort(data.frames, function(a, b) return (a.index or 0) < (b.index or 0) end)
  return data
end

local function silentApplyJson(catalog, selectedPhotos, jsonPath)
  logger:trace("silentApplyJson: 入口, jsonPath=" .. tostring(jsonPath) .. ", selected=" .. tostring(#selectedPhotos))
  local content = LrFileUtils.readFile(jsonPath)
  if not content or content == "" then
    return false, "无法读取 JSON 文件"
  end
  logger:trace("silentApplyJson: readFile 完成, len=" .. #content)

  local data, err = parseJson(content)
  if not data then
    return false, err
  end
  logger:trace("silentApplyJson: parseJson 完成, frames=" .. tostring(data.frames and #data.frames or 0) .. ", target=" .. tostring(data.targetBasename))

  -- 如果 JSON 指定了目标照片，过滤选中的照片
  local targetBasename = data.targetBasename
  local photosToProcess = selectedPhotos
  if targetBasename and targetBasename ~= "" then
    local filtered = {}
    for _, photo in ipairs(selectedPhotos) do
      -- NOTE: photo:getFormattedMetadata is a yielding LR call. Wrapping it
      -- in pcall raises "Yielding is not allowed within a C or metamethod
      -- call". The async task is already inside startAsyncTask which is
      -- yield-safe; let exceptions surface to the outer pcall in startAutoWatch.
      local fileName = photo:getFormattedMetadata('fileName') or ""
      local baseName = fileName:gsub("%..+$", "")
      if baseName == targetBasename then
        table.insert(filtered, photo)
      end
    end
    if #filtered > 0 then
      photosToProcess = filtered
      logger:trace("自动检测: 过滤后处理 " .. #filtered .. " 张照片 (目标: " .. targetBasename .. ")")
    else
      logger:trace("自动检测: 未找到匹配目标照片 " .. targetBasename)
      return false, "未找到匹配的目标照片: " .. targetBasename
    end
  end

  logger:trace("silentApplyJson: 加载 ProcessAgent")
  local ProcessAgent = dofile(LrPathUtils.child(pluginPath, "ProcessAgent.lua"))
  logger:trace("silentApplyJson: ProcessAgent 加载完成, 进入 directionAlign")
  for _, photo in ipairs(photosToProcess) do
    data = ProcessAgent.directionAlign(data, photo)
  end
  logger:trace("silentApplyJson: directionAlign 完成")

  local existingCopies = buildExistingCopiesMap(catalog, photosToProcess)
  local duplicateAction = "create"

  local totalCreated = 0
  local totalUpdated = 0
  local totalSkipped = 0
  local allErrors = {}

  for _, photo in ipairs(photosToProcess) do
    local w = data.sourceWidth or photo:getRawMetadata("width") or 1024
    local h = data.sourceHeight or photo:getRawMetadata("height") or 1024
    local created, errors, updated, skipped = createVirtualCopiesFromFrames(
      catalog, photo, data.frames, w, h, data.cropAngle or 0, existingCopies, duplicateAction
    )
    totalCreated = totalCreated + created
    totalUpdated = totalUpdated + updated
    totalSkipped = totalSkipped + skipped
    for _, e in ipairs(errors) do table.insert(allErrors, e) end
  end

  local msg = string.format("创建: %d, 更新: %d, 跳过: %d", totalCreated, totalUpdated, totalSkipped)
  if #allErrors > 0 then
    local errMsg = table.concat(allErrors, "\n")
    if #errMsg > 300 then errMsg = string.sub(errMsg, 1, 300) .. "\n..." end
    msg = msg .. "\n错误:\n" .. errMsg
  end

  return true, msg
end

local function startAutoWatch(jsonPath)
  logger:trace("=== 自动检测模式 ===")

  local LrApplicationView = import 'LrApplicationView'
  if LrApplicationView.getCurrentModuleName() ~= "develop" then
    logger:trace("自动检测: 不在 develop 模块，取消")
    return false, "请在修改照片模块中运行"
  end

  local catalog = LrApplication.activeCatalog()
  local selectedPhotos = catalog:getTargetPhotos()
  if not selectedPhotos or #selectedPhotos == 0 then
    logger:trace("自动检测: 未选择照片，取消")
    return false, "未选择照片"
  end

  local LrPrefs = import 'LrPrefs'
  local prefs = LrPrefs.prefsForPlugin()
  prefs.autoWatchActive = true
  prefs.autoWatchJsonPath = jsonPath

  logger:trace("自动检测已启动，监视: " .. jsonPath)

  LrTasks.startAsyncTask(function()
    local lastModified = LrFileUtils.fileAttributes(jsonPath).fileModificationDate or 0
    while prefs.autoWatchActive do
      LrTasks.sleep(2)
      if not prefs.autoWatchActive then break end

      local attrs = LrFileUtils.fileAttributes(jsonPath)
      if attrs and attrs.fileModificationDate and attrs.fileModificationDate > lastModified then
        lastModified = attrs.fileModificationDate
        logger:trace("自动检测: JSON 文件已更新，开始应用...")

        -- 每次处理时重新获取当前选中的照片
        -- NOTE: Lua's built-in `pcall` is a C boundary that disallows
        -- coroutine yields. activeCatalog/getTargetPhotos/silentApplyJson
        -- all may yield (selection inspection, catalog access, metadata
        -- fetch). Use LrTasks.pcall — Lr's yield-safe error capture.
        local okCat, currentCatalog = LrTasks.pcall(LrApplication.activeCatalog)
        if not okCat then
          logger:trace("自动检测: activeCatalog 抛错: " .. tostring(currentCatalog))
        else
          logger:trace("自动检测: activeCatalog ok")
          local okSel, currentPhotos = LrTasks.pcall(function() return currentCatalog:getTargetPhotos() end)
          if not okSel then
            logger:trace("自动检测: getTargetPhotos 抛错: " .. tostring(currentPhotos))
          elseif currentPhotos and #currentPhotos > 0 then
            logger:trace("自动检测: 进入 silentApplyJson 前, photo 数=" .. #currentPhotos)
            local ok, success, message = LrTasks.pcall(silentApplyJson, currentCatalog, currentPhotos, jsonPath)
            if not ok then
              logger:trace("自动检测异常 (LrTasks.pcall): " .. tostring(success))
            elseif success then
              logger:trace("自动检测成功: " .. tostring(message))
            else
              logger:trace("自动检测失败: " .. tostring(message))
            end
          else
            logger:trace("自动检测: 没有选中的照片，跳过")
          end
        end
      end
    end

    prefs.autoWatchActive = false
    prefs.autoWatchJsonPath = nil
    logger:trace("自动检测已终止")
  end)

  return true, "自动检测已启动"
end

local function stopAutoWatch()
  local LrPrefs = import 'LrPrefs'
  local prefs = LrPrefs.prefsForPlugin()
  prefs.autoWatchActive = false
  prefs.autoWatchJsonPath = nil
  logger:trace("自动检测已停止")
end

-- =====================================================================
-- 导出接口
-- =====================================================================
return {
  importFromXMP = importFromXMP,
  detectViaHttp = detectViaHttp,
  watchJsonFile = watchJsonFile,
  silentApplyJson = silentApplyJson,
  startAutoWatch = startAutoWatch,
  stopAutoWatch = stopAutoWatch,
  createVirtualCopiesFromFrames = createVirtualCopiesFromFrames,
}
