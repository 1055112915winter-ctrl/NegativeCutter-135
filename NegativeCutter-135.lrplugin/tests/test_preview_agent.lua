local plugin = (debug.getinfo(1).source:match("@?(.*/)") or "./") .. "../"
local Agent = dofile(plugin .. "PreviewAgent.lua")

local function clone(value)
  if type(value) ~= "table" then return value end
  local copy = {}; for key, item in pairs(value) do copy[key] = clone(item) end; return copy
end

local function fixture(options)
  options = options or {}
  local clock, jobs, rendering, renders, bound, removed, finals, pointers = 0, {}, 0, {}, {}, {}, {}, {}
  local fs = {
    finalizePreview = function(_, partial, final)
      if options.imageFailure then return false, "image rename failed" end
      finals[#finals + 1] = { partial = partial, final = final }; return true
    end,
    publishActive = function(_, pointer)
      if options.pointerFailure then return false, "pointer rename failed" end
      pointers[#pointers + 1] = clone(pointer); return true
    end,
    removeFile = function(_, path) removed[#removed + 1] = path; return true end,
    removeOwned = function(_, path) removed[#removed + 1] = "owned:" .. path; return true end,
  }
  local runtime = {
    uuid = function() return "12345678-1234-4123-a123-123456789abc" end,
    previewRoot = "/preview",
    scheduler = { spawn = function(fn) jobs[#jobs + 1] = fn end, sleep = function(ms)
      if options.sleepAt and clock < options.sleepAt and options.sleepAt < clock + ms then
        clock = options.sleepAt; local callback = options.onSleep; options.sleepAt = nil; if callback then callback() end
      else clock = clock + ms end
    end },
    clock = { now = function() return clock end }, filesystem = fs,
    renderer = { render = function(request, partial)
      rendering = rendering + 1; assert(rendering == 1, "renders must be serialized")
      renders[#renders + 1] = { request = clone(request), partial = partial }
      if options.duringRender then options.duringRender() end
      rendering = rendering - 1
      if options.rendererFailure then return nil, "renderer failed" end
      return { frames = clone(request.frames), offsets = clone(request.offsets) }
    end },
  }
  local dialog = Agent.review({ bindPreview = function(path) bound[#bound + 1] = path end }, options.request or { frames = { { left = 1 } }, sourceWidth = 100, sourceHeight = 200 }, runtime)
  local function drain()
    while #jobs > 0 do local job = table.remove(jobs, 1); job() end
  end
  return { dialog = dialog, drain = drain, now = function() return clock end, renders = renders, bound = bound, removed = removed, finals = finals, pointers = pointers, jobs = jobs }
end

-- Trailing-edge: an edit at 119ms postpones the one worker for another full 120ms.
do
  local f; f = fixture({ sleepAt = 119, onSleep = function() f.dialog:edit({ frames = { { left = 4 } }, offsets = { topPx = 4 } }) end })
  f.dialog:edit({ frames = { { left = 3 } }, offsets = { topPx = 3 } })
  f.drain()
  assert(#f.renders == 1 and f.now() == 239, "edit at 119ms must wait another full 120ms")
  assert(f.renders[1].request.offsets.topPx == 4, "latest edit must win")
end

-- Reset writes a single immutable zero snapshot even though four fields change.
do
  local f = fixture(); f.dialog:edit({ offsets = { topPx = 9 }, frames = { { left = 9 } } }); f.drain()
  assert(f.dialog.state.topPx == 9, "successful edit must update observable state")
  f.dialog:Reset(); f.drain()
  assert(#f.renders == 2, "Reset must create exactly one generation")
  local offsets = f.renders[2].request.offsets
  assert(offsets.topPx == 0 and offsets.bottomPx == 0 and offsets.leftPx == 0 and offsets.rightPx == 0, "Reset snapshot must contain four zeroes")
end

-- Reset is a single observer-suspended edit boundary: all four values change at once.
do
  local calls, f = 0, fixture()
  f.dialog:edit({ offsets = { topPx = 7, bottomPx = 6, leftPx = 5, rightPx = 4 } }); f.drain()
  f.dialog._context = { suspendObservers = function(fn) calls = calls + 1; fn() end }
  f.dialog:Reset()
  assert(calls == 1 and f.dialog.state.topPx == 0 and f.dialog.state.bottomPx == 0 and f.dialog.state.leftPx == 0 and f.dialog.state.rightPx == 0, "Reset must immediately atomically expose four zeroes")
  f.drain(); assert(#f.renders == 2, "one Reset burst must enqueue exactly one generation")
end

-- Callers may mutate their request after scheduling; worker sees only the snapshot.
do
  local f = fixture(); local request = { frames = { { left = 8 } }, dimensions = { width = 20 }, offsets = { leftPx = 2 } }
  f.dialog:edit(request); request.frames[1].left = 99; request.dimensions.width = 99; request.offsets.leftPx = 99; f.drain()
  local actual = f.renders[1].request
  assert(actual.frames[1].left == 8 and actual.dimensions.width == 20 and actual.offsets.leftPx == 2, "scheduled request must be deep immutable")
end

-- A new generation during rendering must not publish stale pixels.
do
  local f; local once = true
  f = fixture({ duringRender = function() if once then once = false; f.dialog:edit({ frames = { { left = 2 } }, offsets = { topPx = 2 } }) end end })
  f.dialog:edit({ frames = { { left = 1 } }, offsets = { topPx = 1 } }); f.drain()
  assert(#f.renders == 2 and #f.bound == 1 and f.bound[1]:match("preview%-2%-"), "stale in-flight generation must not bind")
end

-- Each successful publication is immutable, pointer-backed, and retains only current + previous.
do
  local f = fixture()
  for n = 1, 2 do f.dialog:edit({ frames = { { left = n } }, offsets = { topPx = n } }); f.drain() end
  assert(#f.removed == 0, "current and immediately previous preview must both be retained")
  f.dialog:edit({ frames = { { left = 3 } }, offsets = { topPx = 3 } }); f.drain()
  assert(#f.bound == 3 and #f.pointers == 3 and #f.finals == 3, "three generations must all publish")
  assert(f.bound[1] ~= f.bound[2] and f.bound[2] ~= f.bound[3], "every bound path must be immutable and unique")
  assert(f.bound[3]:match("preview%-3%-") and f.finals[3].partial == f.bound[3] .. ".partial", "partial must atomically become immutable final")
  assert(f.pointers[3].path == f.bound[3] and f.pointers[3].generation == 3, "active pointer must follow final rename")
  assert(#f.removed >= 1 and f.removed[1] == f.bound[1], "worker must asynchronously remove generations older than previous")
end

-- Any candidate failure preserves the last good UI/pointer and disables Confirm.
for _, failure in ipairs({ "rendererFailure", "imageFailure", "pointerFailure" }) do
  local f = fixture(); f.dialog:edit({ frames = { { left = 1 } } }); f.drain(); local good = f.bound[1]
  local mode = {}; mode[failure] = true
  -- Change the injected operation on the existing fixture without changing the last good pointer.
  if failure == "rendererFailure" then f.dialog._runtime.renderer.render = function() return nil, "renderer failed" end
  elseif failure == "imageFailure" then f.dialog._runtime.filesystem.finalizePreview = function() return false, "image rename failed" end
  else f.dialog._runtime.filesystem.publishActive = function() return false, "pointer rename failed" end end
  f.dialog:edit({ frames = { { left = 2 } } }); f.drain()
  assert(#f.bound == 1 and f.bound[1] == good and f.dialog.state.status == "failure" and f.dialog:Confirm() == false, failure .. " must fail closed without stale pointer replacement")
end

-- Close/Shutdown forbid late binding and defer owned-directory cleanup until synchronous rendering returns.
do
  local f; f = fixture({ duringRender = function() f.dialog:close(); assert(#f.bound == 0, "close during render must not bind") end })
  f.dialog:edit({ frames = { { left = 1 } } }); f.drain()
  assert(#f.bound == 0 and f.removed[#f.removed] == "owned:" .. f.dialog.dir, "close during render must clean in worker finally")
  local other = fixture(); other.dialog:edit({ frames = { { left = 2 } } }); Agent.closeAll(); other.drain()
  assert(#other.bound == 0 and other.dialog.state.closed, "Shutdown must close dialogs and forbid publication")
end

print("preview agent tests passed")
