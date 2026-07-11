local thisDir = debug.getinfo(1).source:match("@?(.*/)") or "./"
local pluginDir = thisDir .. "../"
local realDofile = dofile
local applier = { resetCrop = function() return true end, applyCrop = function() return true end }
local cleanerCalls = 0
local executeImpl = function() return 0 end
local cleanerImpl = function(frames)
  cleanerCalls = cleanerCalls + 1
  frames[1].relativeTop = frames[1].relativeTop + 0.01
end
local cleaner = { cleanFrames = function(...) return cleanerImpl(...) end }

_G._PLUGIN = { path = pluginDir }
_G.import = function(name)
  if name == "LrLogger" then
    return function() return { enable = function() end, trace = function() end, error = function() end } end
  elseif name == "LrPathUtils" then
    return { child = function(a, b) return a .. "/" .. b end, getStandardFilePath = function() return "/tmp" end }
  elseif name == "LrFileUtils" then
    return {
      exists = function(path)
        if path and path:match("NegativeCutter/NegativeCutter$") then return true end
        local file = path and io.open(path, "rb"); if file then file:close(); return true end; return false
      end,
      createAllDirectories = function() return true end,
      delete = function(path) os.remove(path); return true end,
    }
  elseif name == "LrTasks" then
    return { sleep = function() end, execute = function(command) return executeImpl(command) end }
  elseif name == "LrPrefs" then
    return { prefsForPlugin = function() return { filmType = "negative" } end }
  end
  error("unexpected import " .. tostring(name))
end

_G.dofile = function(path)
  if path:match("json%.lua$") then return realDofile(path) end
  if path:match("ThumbnailAgent%.lua$") then return {} end
  if path:match("ApplierAgent%.lua$") then return applier end
  if path:match("CropCleaner%.lua$") then return cleaner end
  return realDofile(path)
end

local ProcessAgent = realDofile(pluginDir .. "ProcessAgent.lua")

-- Packaged render owns only its request/result files and returns exact adjusted frames.
do
  local commandSeen, outputPath = nil, "/tmp/negativecutter-preview-pipeline.jpg.partial"
  executeImpl = function(command)
    commandSeen = command
    local framesPath = assert(command:match('%-%-frames%-json "([^"]+)"'))
    local renderedPath = assert(command:match('%-%-output "([^"]+)"'))
    local resultPath = assert(command:match('> "([^"]+)" 2>&1'))
    local framesFile = assert(io.open(framesPath, "r")); local framesPayload = framesFile:read("*a"); framesFile:close()
    assert(framesPayload:match('"frames"'), "frames JSON missing")
    local rendered = assert(io.open(renderedPath, "wb")); rendered:write("jpeg"); rendered:close()
    local result = assert(io.open(resultPath, "w"))
    result:write('{"previewPath":"' .. renderedPath .. '","frameCount":1,"frames":[{"index":1,"top":5,"bottom":55,"left":10,"right":90}]}')
    result:close(); return 0
  end
  local requestFrames = {{ index = 1, top = 10, bottom = 50, left = 20, right = 80 }}
  local payload, err = ProcessAgent.renderPreview({ thumbnailPath = "/thumb.jpg", frames = requestFrames,
    sourceWidth = 100, sourceHeight = 60, offsets = { topPx = 5 }, outputPath = outputPath })
  assert(payload and not err and payload.outputPath == outputPath and payload.frames[1].top == 5, "renderPreview schema failed")
  assert(payload.frames ~= requestFrames and not commandSeen:match("rm %-rf"), "renderPreview must deep-copy and preserve caller directory")
  assert(io.open(outputPath .. ".frames.json", "r") == nil and io.open(outputPath .. ".result.json", "r") == nil, "renderPreview temporary files leaked")
  os.remove(outputPath)
end

-- Pure adjustment is deep, relative-coordinate canonical, Python-parity, and single-use.
do
  local detection = { sourceWidth = 100, sourceHeight = 60, frames = {{ index = 1,
    relativeTop = 0.1, relativeBottom = 0.9, relativeLeft = 0.2, relativeRight = 0.8,
    extra = { keep = true } }} }
  local adjusted, err = ProcessAgent.adjustDetection(detection, { topPx = 10, bottomPx = 20, leftPx = -30, rightPx = 40 })
  assert(adjusted and not err, "adjustDetection failed")
  local frame = adjusted.frames[1]
  assert(frame.top == 0 and frame.bottom == 60 and frame.left == 50 and frame.right == 100, "adjustDetection pixel parity failed")
  assert(frame.relativeTop == 0 and frame.relativeBottom == 1 and frame.relativeLeft == 0.5 and frame.relativeRight == 1, "adjustDetection relative parity failed")
  assert(detection.frames[1].relativeTop == 0.1 and adjusted.frames[1].extra ~= detection.frames[1].extra, "adjustDetection mutated input")
  assert(ProcessAgent.adjustDetection(adjusted, { topPx = 1 }) == nil, "double adjustment must be rejected")
end

-- Detection stages run in order and CropCleaner is called exactly once after alignment.
do
  local stages = {}
  ProcessAgent.extractThumbnail = function() return "/thumb.jpg" end
  ProcessAgent.analyzeWithPython = function()
    return { sourceWidth = 100, sourceHeight = 60, cropAngle = 1, frames = {{ index = 1,
      relativeTop = 0.1, relativeBottom = 0.9, relativeLeft = 0.2, relativeRight = 0.8 }} }
  end
  ProcessAgent.directionAlign = function(result) stages[#stages + 1] = "aligned"; return result end
  local photo = {
    getFormattedMetadata = function() return "scan.tif" end,
    getRawMetadata = function(_, key)
      if key == "path" then return "/scan.tif" end
      if key == "dimensions" then return { width = 100, height = 60 } end
    end,
  }
  local detection, err = ProcessAgent.detectPhoto(photo, { expectedFrames = 6, filmType = "negative",
    onStage = function(stage) stages[#stages + 1] = stage end })
  assert(detection and not err and detection.photo == photo and detection.fileName == "scan.tif", "detectPhoto schema failed")
  assert(cleanerCalls == 1 and detection.frames[1].top == 7, "detectPhoto must clean once and refresh absolute coordinates")
  assert(table.concat(stages, ","):match("thumbnail.*recognition.*aligned.*cleanup"), "detectPhoto stage order failed")
end

-- Thumbnail failure preserves the legacy original-file fallback, and detection refresh does not apply preview minimums.
do
  cleanerImpl = function() cleanerCalls = cleanerCalls + 1 end
  ProcessAgent.extractThumbnail = function() return nil, "thumbnail unavailable" end
  ProcessAgent.analyzeWithPython = function(inputPath)
    assert(inputPath == "/scan.tif", "original fallback path missing")
    return { sourceWidth = 100, sourceHeight = 60, frames = {{ index = 1,
      relativeTop = 0.1, relativeBottom = 0.2, relativeLeft = 0.2, relativeRight = 0.3 }} }
  end
  ProcessAgent.directionAlign = function(result) return result end
  local photo = { getFormattedMetadata = function() return "scan.tif" end, getRawMetadata = function(_, key)
    if key == "path" then return "/scan.tif" end
    if key == "dimensions" then return { width = 100, height = 60 } end
  end }
  local detection, err = ProcessAgent.detectPhoto(photo, {})
  assert(detection and not err and detection.thumbnailPath == "/scan.tif", "legacy original fallback failed")
  assert(detection.frames[1].top == 6 and detection.frames[1].bottom == 12, "detection refresh must preserve sub-20px cleaned bounds")
end

-- Copy creation checks cancellation per frame and reports crop failure without stopping later frames.
do
  local copyIndex, copies = 0, {}
  local catalog = {
    setSelectedPhotos = function() end,
    withWriteAccessDo = function(_, _, fn) fn({}) end,
    createVirtualCopies = function()
      copyIndex = copyIndex + 1
      local copy = { setRawMetadata = function() end }; copies[#copies + 1] = copy; return { copy }
    end,
  }
  applier.applyCrop = function(_, crop) if crop.top > 0.2 then return false, "crop rejected" end; return true end
  local detection = { photo = {}, fileName = "scan.tif", sourceWidth = 100, sourceHeight = 60, cropAngle = 0,
    frames = {{ relativeTop = 0.1, relativeBottom = 0.4, relativeLeft = 0.1, relativeRight = 0.4 },
              { relativeTop = 0.3, relativeBottom = 0.7, relativeLeft = 0.2, relativeRight = 0.8 }} }
  local summary = ProcessAgent.createVirtualCopies(catalog, detection, {})
  assert(summary.status == "partial_failure" and summary.attemptedFrames == 2 and summary.createdCount == 1 and #summary.errors == 1, "copy failure accounting mismatch")
  local canceled = ProcessAgent.createVirtualCopies(catalog, detection, { isCanceled = function() return true end })
  assert(canceled.status == "canceled" and canceled.attemptedFrames == 0 and canceled.createdCount == 0, "pre-frame cancellation mismatch")

  local renameCatalog = {
    setSelectedPhotos = function() end,
    withWriteAccessDo = function(_, _, fn) fn({}) end,
    createVirtualCopies = function()
      return { { setRawMetadata = function() error("copy name locked") end } }
    end,
  }
  applier.applyCrop = function() return true end
  local renameSummary = ProcessAgent.createVirtualCopies(renameCatalog, {
    photo = {}, fileName = "scan.tif", sourceWidth = 100, sourceHeight = 60,
    cropAngle = 0, frames = { { relativeTop = 0.1, relativeBottom = 0.4, relativeLeft = 0.1, relativeRight = 0.4 } },
  }, {})
  assert(renameSummary.status == "success" and renameSummary.createdCount == 1
    and #renameSummary.errors == 0 and #renameSummary.warnings == 1,
    "rename failures must remain nonfatal warnings")
end

-- Legacy wrapper remains exactly two-return and delegates to the new stages.
do
  local oldDetect, oldCreate = ProcessAgent.detectPhoto, ProcessAgent.createVirtualCopies
  ProcessAgent.detectPhoto = function() return { frames = {} } end
  ProcessAgent.createVirtualCopies = function() return { status = "success", createdCount = 3, attemptedFrames = 3, errors = {} } end
  local count, err, third = ProcessAgent.detectAndCrop({}, {}, 6, "scan.tif", "35mm")
  assert(count == 3 and err == nil and third == nil, "legacy wrapper contract changed")
  ProcessAgent.detectPhoto, ProcessAgent.createVirtualCopies = oldDetect, oldCreate
end

print("process pipeline tests passed")
