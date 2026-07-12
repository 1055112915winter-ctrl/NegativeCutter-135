local thisDir = debug.getinfo(1).source:match("@?(.*/)") or "./"
local pluginDir = thisDir .. "../"
local realDofile, asyncBody = dofile, nil
local ProcessAgent, PreviewAgent = {}, {}

_G._PLUGIN = { path = pluginDir }
_G.import = function(name)
  if name == "LrLogger" then return function() return { enable = function() end, trace = function() end, error = function() end } end end
  if name == "LrPathUtils" then return { child = function(a, b) return a .. "/" .. b end } end
  if name == "LrPrefs" then return { prefsForPlugin = function() return {} end } end
  if name == "LrTasks" then return { startAsyncTask = function(fn) asyncBody = fn end, pcall = pcall } end
  if name == "LrApplication" or name == "LrDialogs" or name == "LrView" or name == "LrProgressScope" then return {} end
  if name == "LrBinding" or name == "LrFunctionContext" then return {} end
  error("unexpected import " .. tostring(name))
end
_G.dofile = function(path)
  if path:match("ProcessAgent%.lua$") then return ProcessAgent end
  if path:match("CropCleaner%.lua$") then return { availableTypes = function() return {{ value = "negative", display = "负片" }} end } end
  return realDofile(path)
end
_G.require = function(name)
  if name == "PreviewAgent" then return PreviewAgent end
  if name == "PreviewRuntime" then return { current = function() return {} end } end
  error("unexpected require " .. tostring(name))
end

local Entry = realDofile(pluginDir .. "DetectFrames.lua")
assert(type(Entry) == "table" and type(Entry.runRecognition) == "function", "recognition runner must be injectable")
local BatchEntry = realDofile(pluginDir .. "BatchProcess.lua")
assert(type(BatchEntry) == "table" and type(BatchEntry.runRecognition) == "function", "batch runner must be injectable")
assert(type(BatchEntry.outcomePresentation) == "function", "batch outcome presentation must be testable")

local function progress()
  local value = { doneCalls = 0, portions = {}, captions = {}, canceled = false }
  function value:isCanceled() return self.canceled end
  function value:setCaption(caption) self.captions[#self.captions + 1] = caption end
  function value:setPortionComplete(done, total) self.portions[#self.portions + 1] = { done, total } end
  function value:done() self.doneCalls = self.doneCalls + 1 end
  return value
end

local photos = {{ name = "a" }, { name = "b" }}
local catalog = {}

-- Terminal photos alone advance the fixed denominator, and done is exactly once.
do
  local p = progress()
  ProcessAgent.detectPhoto = function(photo, options)
    options.onStage("thumbnail"); options.onStage("recognition")
    return { photo = photo, fileName = photo.name, thumbnailPath = "/thumb.jpg", sourceWidth = 100, sourceHeight = 60, frames = {{}} }
  end
  ProcessAgent.createVirtualCopies = function(_, _, options)
    options.onStage("frame", 1, 1); return { status = "success", createdCount = 1, attemptedFrames = 1, errors = {} }
  end
  ProcessAgent.adjustDetection = function(detection) return detection end
  PreviewAgent.review = function() error("no-preview mode must not open dialog") end
  local stats = Entry.runRecognition(catalog, photos, { previewMode = "none" }, {}, { progress = p })
  assert(stats.processedPhotos == 2 and stats.unprocessedPhotos == 0 and stats.created == 2, "terminal accounting failed")
  assert(#p.portions == 2 and p.portions[1][1] == 1 and p.portions[2][1] == 2 and p.portions[2][2] == 2, "progress denominator changed")
  assert(p.doneCalls == 1 and not stats.canceled and not stats.unexpectedError, "success finalization failed")
end

-- A click during synchronous recognition takes effect immediately after recognition returns.
do
  local p = progress(); local copies = 0
  ProcessAgent.detectPhoto = function(photo, options)
    options.onStage("recognition"); p.canceled = true
    return { photo = photo, fileName = photo.name, frames = {{}}, sourceWidth = 1, sourceHeight = 1 }
  end
  ProcessAgent.createVirtualCopies = function() copies = copies + 1 end
  local stats = Entry.runRecognition(catalog, photos, { previewMode = "none" }, {}, { progress = p })
  assert(stats.canceled and stats.processedPhotos == 0 and stats.unprocessedPhotos == 2 and copies == 0, "post-recognition cancel boundary failed")
  assert(p.doneCalls == 1, "cancel must finalize progress once")
end

-- Mid-photo cancellation preserves successful partial copies without making the photo terminal.
do
  local p = progress()
  ProcessAgent.detectPhoto = function(photo) return { photo = photo, fileName = photo.name, frames = {{}, {}}, sourceWidth = 1, sourceHeight = 1 } end
  ProcessAgent.createVirtualCopies = function(_, _, options)
    options.onStage("frame", 1, 2); p.canceled = true
    return { status = "canceled", createdCount = 1, attemptedFrames = 1, errors = {} }
  end
  local stats = Entry.runRecognition(catalog, photos, { previewMode = "none" }, {}, { progress = p })
  assert(stats.canceled and stats.partialCurrent and stats.created == 1, "partial cancel copies were lost")
  assert(stats.processedPhotos == 0 and stats.unprocessedPhotos == 2 and #p.portions == 0, "partial photo became terminal")
end

-- Unexpected errors still finalize progress and are distinct from cancellation.
do
  local p = progress()
  ProcessAgent.detectPhoto = function() error("unexpected boom") end
  local stats = Entry.runRecognition(catalog, photos, { previewMode = "none" }, {}, { progress = p })
  assert(type(stats.unexpectedError) == "string" and not stats.canceled and p.doneCalls == 1, "unexpected error finalization failed")
end

-- A batch with errors and zero successful copies is a failure, not partial completion.
do
  local title, body, severity = BatchEntry.outcomePresentation {
    processedPhotos = 1, unprocessedPhotos = 0, created = 0,
    errors = { "bad detection" }, canceled = false, partialCurrent = false,
  }
  assert(title == "NegativeCutter - 失败" and severity == "critical", "zero-success batch must be classified as failure")
  assert(body:match("创建 0 个虚拟副本") and body:match("错误 1 个"), "failure summary counts changed")
end

print("recognition progress tests passed")
