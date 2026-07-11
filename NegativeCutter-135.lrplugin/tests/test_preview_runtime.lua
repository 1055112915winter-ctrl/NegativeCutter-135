local plugin = (debug.getinfo(1).source:match("@?(.*/)") or "./") .. "../"
local Runtime = dofile(plugin .. "PreviewRuntime.lua")

local files, directories, started, slept = {}, {}, 0, nil
local function uuidSequence(values)
  local i = 0
  return function()
    i = i + 1
    return values[i]
  end
end
local session = "11111111-1111-4111-a111-111111111111"
local prior = "22222222-2222-4222-a222-222222222222"
local active = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
local collision = "cccccccc-cccc-4ccc-accc-cccccccccccc"
local dialog = "33333333-3333-4333-a333-333333333333"
local malformed = "dddddddd-dddd-4ddd-addd-dddddddddddd"
local mismatched = "eeeeeeee-eeee-4eee-aeee-eeeeeeeeeeee"
local sdk = {
  LrTasks = {
    startAsyncTask = function(fn) started = started + 1; fn() end,
    sleep = function(seconds) slept = seconds end,
    pcall = function(fn) return pcall(fn) end,
  },
  LrDate = { currentTime = function() return 10 end },
  LrFileUtils = {
    createAllDirectories = function(path) directories[path] = true; return true end,
    writeFile = function(path, content) files[path] = content; return true end,
    readFile = function(path) return files[path] end,
    move = function(from, to) files[to] = files[from]; files[from] = nil; return true end,
    delete = function(path) files[path] = nil; directories[path] = nil; return true end,
    exists = function(path) return files[path] ~= nil or directories[path] == true end,
    filesInDirectory = function(root)
      return { root .. "/" .. prior, root .. "/" .. active, root .. "/" .. malformed, root .. "/" .. mismatched, root .. "/unowned", root .. "/../../outside" }
    end,
  },
}
local calls = {}
local processAgent = { renderPreview = function(request)
  calls[#calls + 1] = request
  if request.fail then error("render failed") end
  request.nested.value = "mutated by renderer"
  return { frames = { "frame" }, outputPath = request.outputPath }
end }

local runtime = Runtime.create(sdk, processAgent, {
  previewRoot = "/preview-root",
  sessionId = session,
  uuid = uuidSequence({collision, dialog, "44444444-4444-4444-a444-444444444444"}),
})
assert(runtime.previewRoot == "/preview-root" and runtime.sessionId == session, "runtime identity missing")
runtime.scheduler.spawn(function() end)
runtime.scheduler.sleep(120)
assert(started == 1 and slept == .12, "scheduler did not use Lightroom milliseconds conversion")
assert(runtime.clock.now() >= runtime.clock.now(), "clock regressed")

local request = { nested = { value = "original" } }
local payload, err = runtime.renderer.render(request, "/preview-root/output.jpg")
assert(payload and not err and request.nested.value == "original", "renderer did not copy request")
assert(calls[1].outputPath == "/preview-root/output.jpg", "renderer did not assign output path")
local failed, failure = runtime.renderer.render({ fail = true, nested = {} }, "/preview-root/fail.jpg")
assert(failed == nil and failure:match("render failed"), "renderer failure crossed worker boundary")
processAgent.renderPreview = function() return nil, "packaged renderer rejected request" end
local rejected, rejection = runtime.renderer.render({ nested = {} }, "/preview-root/rejected.jpg")
assert(rejected == nil and rejection == "packaged renderer rejected request", "renderer nil,error contract was lost")

local oldMarker = "/preview-root/" .. prior .. "/.negativecutter-preview-owner"
files[oldMarker] = Runtime.ownerMarker("bbbbbbbb-bbbb-4bbb-abbb-bbbbbbbbbbbb", prior)
directories["/preview-root/" .. prior] = true
directories["/preview-root/" .. active] = true
files["/preview-root/" .. active .. "/.negativecutter-preview-owner"] = Runtime.ownerMarker(session, active)
directories["/preview-root/" .. malformed] = true
files["/preview-root/" .. malformed .. "/.negativecutter-preview-owner"] = "negativecutter-preview-v1\nsession=not-a-uuid\ndialog=" .. malformed .. "\n"
directories["/preview-root/" .. mismatched] = true
files["/preview-root/" .. mismatched .. "/.negativecutter-preview-owner"] = Runtime.ownerMarker(session, active)
directories["/preview-root/unowned"] = true
directories["/preview-root/" .. collision] = true
assert(runtime.filesystem:readMarker(prior) ~= nil, "marker lookup failed")
assert(#runtime.filesystem:listOwned() == 2, "owned directory enumeration failed: " .. tostring(#runtime.filesystem:listOwned()))
runtime:initialize()
assert(not directories["/preview-root/" .. prior], "prior marker-valid session was not removed")
assert(directories["/preview-root/" .. active], "active-session directory was removed")
assert(directories["/preview-root/unowned"], "markerless directory should be preserved")
assert(directories["/preview-root/" .. malformed] and directories["/preview-root/" .. mismatched], "invalid ownership markers must be preserved")
local id, dir = runtime:createDialogDirectory()
assert(id == dialog and files[dir .. "/.negativecutter-preview-owner"] == Runtime.ownerMarker(session, dialog), "dialog owner marker missing")
local secondId, secondDir = runtime:createDialogDirectory()
assert(secondId ~= id and files[secondDir .. "/.negativecutter-preview-owner"], "multiple dialogs need separate owned directories")
assert(runtime.filesystem:removeOwned("../../outside") == false, "traversal must be rejected")
assert(runtime.filesystem:mkdir("/outside") == false, "mkdir must not escape preview root")
assert(runtime.filesystem:writeAtomic(dir .. "/../../outside", "bad") == false, "write must reject nested traversal")
assert(runtime.filesystem:publishSlot(dir .. "/../../source", dir .. "/active.json") == false, "publish source must reject nested traversal")
assert(runtime.filesystem:publishSlot(dir .. "/one", dir .. "/../../active.json") == false, "publish destination must reject nested traversal")
assert(runtime.filesystem:publishSlot(dir .. "/one", dir .. "/active.json"), "atomic publish failed")
assert(runtime.filesystem:readMarker(dir) == Runtime.ownerMarker(session, dialog), "marker read failed")

local quotedRoot = '/preview-"root\\folder'
local quotedFiles = {}
local quotedRuntime = Runtime.create({
  LrTasks = sdk.LrTasks,
  LrDate = sdk.LrDate,
  LrFileUtils = {
    createAllDirectories = function() return true end,
    writeFile = function(path, content) quotedFiles[path] = content; return true end,
    move = function(from, to) quotedFiles[to] = quotedFiles[from]; quotedFiles[from] = nil; return true end,
  },
}, processAgent, { previewRoot = quotedRoot, sessionId = session })
local quotedPath = quotedRoot .. "/" .. dialog .. '/preview-1.jpg'
local pointerPath = quotedRoot .. "/" .. dialog .. "/active.json"
assert(quotedRuntime.filesystem:publishActive({ path = quotedPath, generation = 1 }, pointerPath), "quoted pointer publish failed")
assert(quotedFiles[pointerPath] == '{"path":"/preview-\\"root\\\\folder/' .. dialog .. '/preview-1.jpg","generation":1}', "active pointer must be valid escaped JSON")

-- Lightroom exposes LrFileUtils.readFile but no writeFile API.  Exercise the
-- production io.open fallback so a real Lightroom session can create its owner
-- marker instead of leaking twenty empty candidate directories.
local originalWriteFile, originalIoOpen = sdk.LrFileUtils.writeFile, io.open
sdk.LrFileUtils.writeFile = nil
io.open = function(path, mode)
  if mode == "wb" then
    return {
      write = function(_, content) files[path] = content; return true end,
      close = function() return true end,
    }
  end
  return originalIoOpen(path, mode)
end
local sdkCompatibleDialog = "55555555-5555-4555-a555-555555555555"
local sdkCompatibleRuntime = Runtime.create(sdk, processAgent, {
  previewRoot = "/sdk-compatible-root",
  sessionId = session,
  uuid = function() return sdkCompatibleDialog end,
})
sdkCompatibleRuntime:initialize()
local sdkCompatibleId, sdkCompatibleDir = sdkCompatibleRuntime:createDialogDirectory()
io.open, sdk.LrFileUtils.writeFile = originalIoOpen, originalWriteFile
assert(sdkCompatibleId == sdkCompatibleDialog, "runtime requires nonexistent LrFileUtils.writeFile")
assert(files[sdkCompatibleDir .. "/.negativecutter-preview-owner"] == Runtime.ownerMarker(session, sdkCompatibleDialog), "io fallback did not publish owner marker")

-- Lightroom menu scripts can receive a fresh module environment even though
-- Init.lua already ran. A menu entry must be able to recover a current runtime
-- instead of depending on module-local state from plugin initialization.
Runtime.setCurrent(nil)
local recovered = Runtime.current(processAgent, {
  sdk = sdk,
  previewRoot = "/recovered-root",
  sessionId = session,
})
assert(recovered and recovered.previewRoot == "/recovered-root", "menu runtime did not recover after module state reset")
print("preview runtime tests passed")
