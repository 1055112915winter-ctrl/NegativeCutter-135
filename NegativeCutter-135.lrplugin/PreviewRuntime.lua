-- Lightroom-specific preview adapters.  PreviewAgent stays SDK-agnostic.
local PreviewRuntime = {}
local OWNER_FILE = ".negativecutter-preview-owner"
local OWNER_TAG = "negativecutter-preview-v1"
local currentRuntime

local function clone(value)
  if type(value) ~= "table" then return value end
  local copy = {}
  for key, item in pairs(value) do copy[key] = clone(item) end
  return copy
end

local function jsonString(value)
  return '"' .. tostring(value):gsub('\\', '\\\\'):gsub('"', '\\"')
    :gsub('\b', '\\b'):gsub('\f', '\\f'):gsub('\n', '\\n'):gsub('\r', '\\r'):gsub('\t', '\\t') .. '"'
end

local function isUuid(value)
  return type(value) == "string" and value:match("^[%x][%x%-]+$") ~= nil
    and value:match("^%x%x%x%x%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$") ~= nil
end

local function child(root, name)
  if not isUuid(name) then return nil end
  return root .. "/" .. name
end

function PreviewRuntime.ownerMarker(sessionId, dialogId)
  return OWNER_TAG .. "\nsession=" .. sessionId .. "\ndialog=" .. dialogId .. "\n"
end

local function validOwnerMarker(marker, directoryId)
  if type(marker) ~= "string" or marker:sub(1, #OWNER_TAG + 1) ~= OWNER_TAG .. "\n" then return false end
  local sessionId, dialogId = marker:sub(#OWNER_TAG + 2):match("^session=([^\n]+)\ndialog=([^\n]+)\n$")
  return isUuid(sessionId) and isUuid(dialogId) and dialogId == directoryId
end

local function defaultUuid()
  local chunks = {}
  for index = 1, 32 do chunks[index] = string.format("%x", math.random(0, 15)) end
  return table.concat(chunks):sub(1, 8) .. "-" .. table.concat(chunks):sub(9, 12)
    .. "-4" .. table.concat(chunks):sub(14, 16) .. "-a" .. table.concat(chunks):sub(18, 20)
    .. "-" .. table.concat(chunks):sub(21, 32)
end

function PreviewRuntime.create(sdk, processAgent, options)
  sdk, options = sdk or {}, options or {}
  local tasks, dates, fileUtils = sdk.LrTasks or {}, sdk.LrDate or {}, sdk.LrFileUtils or {}
  local binding, view, dialogs = sdk.LrBinding or {}, sdk.LrView or {}, sdk.LrDialogs or {}
  local functionContext = sdk.LrFunctionContext or {}
  local runtime = {
    previewRoot = options.previewRoot or "/tmp/NegativeCutterPreview",
    sessionId = options.sessionId or (options.uuid or defaultUuid)(),
  }
  local lastClock = 0
  runtime.scheduler = {
    spawn = function(fn) return tasks.startAsyncTask(fn) end,
    sleep = function(milliseconds) return tasks.sleep(milliseconds / 1000) end,
  }
  runtime.clock = {
    now = function()
      local value = math.floor((dates.currentTime and dates.currentTime() or os.time()) * 1000)
      if value < lastClock then value = lastClock end
      lastClock = value
      return value
    end,
  }
  runtime.renderer = {
    render = function(request, outputPath)
      local copied = clone(request)
      copied.outputPath = outputPath
      local ok, payload, renderError = (tasks.pcall or pcall)(function()
        return processAgent.renderPreview(copied)
      end)
      if not ok then return nil, tostring(payload) end
      if payload == nil then return nil, renderError or "preview renderer returned no payload" end
      return payload
    end,
  }
  function runtime:withContext(name, fn)
    if not functionContext.callWithContext then error("LrFunctionContext.callWithContext unavailable") end
    return functionContext.callWithContext(name, fn)
  end
  function runtime:makePropertyTable(context)
    if not binding.makePropertyTable then error("LrBinding.makePropertyTable unavailable") end
    return binding.makePropertyTable(context)
  end
  function runtime:addObserver(properties, key, callback)
    if not properties or not properties.addObserver then error("property table observer unavailable") end
    return properties:addObserver(key, callback)
  end
  function runtime:viewFactory()
    if not view.osFactory then error("LrView.osFactory unavailable") end
    return view.osFactory()
  end
  function runtime:bind(key)
    if not view.bind then error("LrView.bind unavailable") end
    return view.bind(key)
  end
  function runtime:presentModalDialog(spec)
    if not dialogs.presentModalDialog then error("LrDialogs.presentModalDialog unavailable") end
    return dialogs.presentModalDialog(spec)
  end

  local function pathFor(value)
    if isUuid(value) then return child(runtime.previewRoot, value) end
    if type(value) == "string" and value:sub(1, #runtime.previewRoot + 1) == runtime.previewRoot .. "/" then
      local id = value:sub(#runtime.previewRoot + 2):match("^([^/]+)$")
      return child(runtime.previewRoot, id)
    end
    return nil
  end
  local function isPreviewPath(path)
    if type(path) ~= "string" or path:sub(1, #runtime.previewRoot + 1) ~= runtime.previewRoot .. "/" then return false end
    local relative = path:sub(#runtime.previewRoot + 2)
    local first, rest = relative:match("^([^/]+)/(.*)$")
    if not first or not isUuid(first) or rest == "" then return false end
    for component in rest:gmatch("[^/]+") do
      if component == "." or component == ".." then return false end
    end
    return not rest:find("//", 1, true) and relative:sub(-1) ~= "/"
  end
  local function writeFile(path, content)
    -- Kept as a test/legacy adapter only. Lightroom's documented API does not
    -- provide LrFileUtils.writeFile, so production falls through to io.open.
    if fileUtils.writeFile then return fileUtils.writeFile(path, content) end
    local handle, openError = io.open(path, "wb")
    if not handle then return false, tostring(openError or "open failed") end
    local ok, writeError = pcall(function() handle:write(content) end)
    local closeOk, closeError = pcall(function() return handle:close() end)
    if not ok then return false, tostring(writeError or "write failed") end
    if not closeOk or closeError == false then return false, "close failed" end
    return true
  end
  local function readFile(path)
    if fileUtils.readFile then return fileUtils.readFile(path) end
    local handle = io.open(path, "rb")
    if not handle then return nil end
    local content = handle:read("*a")
    handle:close()
    return content
  end
  local function directoryEntries(path)
    if fileUtils.filesInDirectory then return fileUtils.filesInDirectory(path) or {} end
    if not fileUtils.directoryEntries then return {} end
    local entries = {}
    for entry in fileUtils.directoryEntries(path) do entries[#entries + 1] = entry end
    return entries
  end
  local filesystem = {}
  function filesystem:mkdir(path)
    if path ~= runtime.previewRoot and not pathFor(path) then return false, "outside preview root" end
    return fileUtils.createAllDirectories(path)
  end
  function filesystem:exists(path) return fileUtils.exists and fileUtils.exists(path) or false end
  function filesystem:writeAtomic(path, content)
    if not isPreviewPath(path) then return false, "outside preview root" end
    local partial = path .. ".partial"
    local ok, writeError = writeFile(partial, content)
    if not ok then return false, writeError or "write failed" end
    local moved = fileUtils.move and fileUtils.move(partial, path)
    if moved == false or moved == nil then return false, "rename failed" end
    return true
  end
  function filesystem:publishSlot(source, destination)
    if not isPreviewPath(source) or not isPreviewPath(destination) then return false, "outside preview root" end
    local moved = fileUtils.move and fileUtils.move(source, destination)
    if moved == false or moved == nil then return false, "rename failed" end
    return true
  end
  -- A rendered JPEG is never overwritten.  The renderer receives the sibling
  -- partial name; this rename makes the generation path visible atomically.
  function filesystem:finalizePreview(partial, final)
    if not isPreviewPath(partial) or not isPreviewPath(final) or partial ~= final .. ".partial" then
      return false, "outside preview root"
    end
    local moved = fileUtils.move and fileUtils.move(partial, final)
    if moved == false or moved == nil then return false, "image rename failed" end
    return true
  end
  function filesystem:publishActive(pointer, destination)
    if type(pointer) ~= "table" or type(pointer.generation) ~= "number" or not isPreviewPath(pointer.path) then
      return false, "invalid preview pointer"
    end
    if destination ~= nil and not isPreviewPath(destination) then return false, "outside preview root" end
    local target = destination or (pointer.path:match("^(.*)/[^/]+$") .. "/active.json")
    return self:writeAtomic(target, string.format('{"path":%s,"generation":%d}', jsonString(pointer.path), pointer.generation))
  end
  function filesystem:removeFile(path)
    if not isPreviewPath(path) then return false, "outside preview root" end
    if fileUtils.delete then fileUtils.delete(path) end
    return true
  end
  function filesystem:readMarker(value)
    local directory = pathFor(value)
    return directory and readFile(directory .. "/" .. OWNER_FILE) or nil
  end
  function filesystem:listOwned()
    local owned = {}
    for _, path in ipairs(directoryEntries(runtime.previewRoot)) do
      local id = type(path) == "string" and path:match("([^/]+)$") or nil
      local directory = pathFor(id)
      if directory then
        local marker = readFile(directory .. "/" .. OWNER_FILE)
        if validOwnerMarker(marker, id) then owned[#owned + 1] = { id = id, path = directory, marker = marker } end
      end
    end
    return owned
  end
  function filesystem:removeOwned(value)
    local directory = pathFor(value)
    if not directory then return false, "invalid owned directory" end
    local marker = self:readMarker(directory)
    if not validOwnerMarker(marker, value:match("([^/]+)$") or value) then return false, "owner marker missing" end
    if fileUtils.delete then fileUtils.delete(directory) end
    return true
  end
  runtime.filesystem = filesystem
  function runtime:createDialogDirectory()
    local createUuid = options.uuid or defaultUuid
    for _ = 1, 20 do
      local id = createUuid()
      local directory = child(self.previewRoot, id)
      if directory and not filesystem:exists(directory) then
        filesystem:mkdir(directory)
        local markerOk = filesystem:writeAtomic(directory .. "/" .. OWNER_FILE, PreviewRuntime.ownerMarker(self.sessionId, id))
        if markerOk then return id, directory end
        -- This directory was allocated by this call and has no valid owner
        -- marker, so remove it directly instead of leaking failed candidates.
        if fileUtils.delete then fileUtils.delete(directory) end
      end
    end
    return nil, "could not allocate preview directory"
  end
  function runtime:initialize()
    filesystem:mkdir(self.previewRoot)
    for _, entry in ipairs(filesystem:listOwned()) do
      local oldSession = entry.marker:match("\nsession=([^\n]+)")
      if oldSession and oldSession ~= self.sessionId then filesystem:removeOwned(entry.path) end
    end
    return self
  end
  return runtime
end

function PreviewRuntime.setCurrent(runtime) currentRuntime = runtime end
function PreviewRuntime.current(processAgent, options)
  if currentRuntime or not processAgent then return currentRuntime end
  options = options or {}
  local sdk = options.sdk
  local runtimeOptions = clone(options)
  runtimeOptions.sdk = nil
  if not sdk then
    local pathUtils = import 'LrPathUtils'
    sdk = {
      LrTasks = import 'LrTasks', LrDate = import 'LrDate', LrFileUtils = import 'LrFileUtils',
      LrBinding = import 'LrBinding', LrView = import 'LrView', LrDialogs = import 'LrDialogs',
      LrFunctionContext = import 'LrFunctionContext',
    }
    if not runtimeOptions.previewRoot then
      local temp = pathUtils and pathUtils.getStandardFilePath and pathUtils.getStandardFilePath('temp') or "/tmp"
      runtimeOptions.previewRoot = temp .. "/NegativeCutterPreview"
    end
  end
  currentRuntime = PreviewRuntime.create(sdk, processAgent, runtimeOptions)
  currentRuntime:initialize()
  return currentRuntime
end
return PreviewRuntime
