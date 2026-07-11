-- SDK-agnostic live-preview state machine.  The runtime supplies the worker,
-- renderer and owned filesystem; every scheduled generation is immutable.
local PreviewAgent = {}
local registry = {}

local function clone(value)
  if type(value) ~= "table" then return value end
  local copy = {}
  for key, item in pairs(value) do copy[key] = clone(item) end
  return copy
end

local function now(clock) return (clock and clock.now and clock.now()) or (os.time() * 1000) end
local function spawn(scheduler, fn) if scheduler and scheduler.spawn then return scheduler.spawn(fn) end; return fn() end
local function sleep(scheduler, milliseconds) if scheduler and scheduler.sleep then scheduler.sleep(milliseconds) end end

function PreviewAgent.newSession(context, request, runtime)
  runtime, context, request = runtime or {}, context or {}, request or {}
  local scheduler, clock = runtime.scheduler or {}, runtime.clock
  local filesystem, renderer = runtime.filesystem or {}, runtime.renderer or {}
  local id, dir
  if runtime.createDialogDirectory then
    id, dir = runtime:createDialogDirectory()
    if not id then return nil, dir or "preview directory allocation failed" end
  else
    id = runtime.uuid and runtime.uuid() or tostring(math.random(1000000, 9999999))
    dir = (runtime.previewRoot or "/tmp/NegativeCutterPreview") .. "/" .. id
    if filesystem.mkdir then filesystem:mkdir(dir) end
  end

  local state = { topPx = 0, bottomPx = 0, leftPx = 0, rightPx = 0, generation = 0,
    deadline = 0, pending = false, closed = false, status = "idle", frames = {}, previewPath = nil }
  local dialog = { id = id, dir = dir, state = state, _runtime = runtime, _context = context }
  local snapshots, workerActive, rendering, cleaned = {}, false, false, false
  local current, previous
  registry[id] = dialog

  local function removeFile(path)
    if path and filesystem.removeFile then filesystem:removeFile(path) end
  end
  local function cleanCandidate(path)
    removeFile(path .. ".partial"); removeFile(path)
  end
  local function removeOwned()
    if cleaned then return end
    cleaned = true
    if filesystem.removeOwned then filesystem:removeOwned(dir)
    elseif filesystem.remove then filesystem:remove(dir) end
  end
  local function finishClosed()
    if state.closed and not rendering then removeOwned() end
  end
  local function fail(generation, message, candidate)
    cleanCandidate(candidate)
    if not state.closed and generation == state.generation then
      state.pending, state.status, state.error = false, "failure", tostring(message or "preview publication failed")
      if context.bindFailure then context.bindFailure(state.error) end
    end
  end
  local function bind(generation, payload, path)
    if state.closed or generation ~= state.generation then return false end
    state.status, state.pending, state.error = "ready", false, nil
    state.frames, state.previewPath = clone(payload.frames or {}), path
    if payload.offsets then
      for key, value in pairs(payload.offsets) do if type(value) == "number" then state[key] = value end end
    end
    if context.bindPreview then context.bindPreview(path) end
    local expired = previous
    previous, current = current, { path = path, generation = generation, payload = clone(payload) }
    if expired then removeFile(expired.path) end
    return true
  end
  local function renderGeneration(generation, snapshot)
    local suffix = runtime.uuid and runtime.uuid() or id
    local candidate = dir .. "/preview-" .. tostring(generation) .. "-" .. suffix .. ".jpg"
    local partial = candidate .. ".partial"
    rendering = true
    local ok, payload, renderError = pcall(function()
      if not renderer.render then error("renderer.render missing") end
      return renderer.render(snapshot, partial, context)
    end)
    rendering = false
    if state.closed then cleanCandidate(candidate); finishClosed(); return end
    if generation ~= state.generation then cleanCandidate(candidate); return end
    if not ok or payload == nil or payload == false then return fail(generation, renderError or payload, candidate) end
    local finalOk, finalError = true, nil
    if filesystem.finalizePreview then finalOk, finalError = filesystem:finalizePreview(partial, candidate) end
    if finalOk == false then return fail(generation, finalError, candidate) end
    -- The active pointer is written only after the immutable image is final.
    if state.closed or generation ~= state.generation then return cleanCandidate(candidate) end
    local pointerOk, pointerError = true, nil
    if filesystem.publishActive then pointerOk, pointerError = filesystem:publishActive({ path = candidate, generation = generation }, dir .. "/active.json") end
    if pointerOk == false then return fail(generation, pointerError, candidate) end
    if not bind(generation, type(payload) == "table" and payload or { frames = payload }, candidate) then cleanCandidate(candidate) end
  end
  local function runWorker()
    while not state.closed do
      local generation, deadline = state.generation, state.deadline
      while not state.closed and generation == state.generation do
        local remaining = deadline - now(clock)
        if remaining <= 0 then break end
        sleep(scheduler, remaining)
        if generation ~= state.generation then break end
      end
      if state.closed then break end
      if generation == state.generation and now(clock) >= state.deadline then
        renderGeneration(generation, snapshots[generation])
        if generation == state.generation then break end
      end
    end
    workerActive = false
    finishClosed()
  end
  local function ensureWorker()
    if workerActive then return end
    workerActive = true; spawn(scheduler, runWorker)
  end
  local function schedule(snapshot)
    if state.closed then return false end
    state.generation = state.generation + 1
    state.deadline, state.pending, state.status, state.error = now(clock) + 120, true, "pending", nil
    snapshots[state.generation] = clone(snapshot)
    if context.bindPending then context.bindPending() end
    ensureWorker()
    return state.generation
  end
  function dialog:edit(editRequest)
    return schedule(editRequest)
  end
  function dialog:Reset()
    local resetState = function()
      state.topPx, state.bottomPx, state.leftPx, state.rightPx = 0, 0, 0, 0
    end
    if self._context.suspendObservers then self._context.suspendObservers(resetState) else resetState() end
    return schedule({ frames = clone(request.frames), thumbnailPath = request.thumbnailPath,
      sourceWidth = request.sourceWidth, sourceHeight = request.sourceHeight,
      offsets = { topPx = 0, bottomPx = 0, leftPx = 0, rightPx = 0 } })
  end
  function dialog:Confirm()
    if state.closed or state.pending or state.status ~= "ready" then return false end
    return context.confirm and context.confirm(current and current.payload) or current
  end
  function dialog:Cancel() if state.closed then return false end; self:close(); return true end
  function dialog:close()
    if state.closed then return end
    state.closed, state.pending = true, false; registry[id] = nil
    if not rendering then removeOwned() end
  end
  return dialog
end

local function validateRequest(request)
  if type(request) ~= "table" then return "preview request is required" end
  if type(request.frames) ~= "table" or #request.frames == 0 then return "preview frames are required" end
  if type(request.thumbnailPath) ~= "string" or request.thumbnailPath == "" then return "preview thumbnail path is required" end
  if type(request.sourceWidth) ~= "number" or request.sourceWidth <= 0
    or type(request.sourceHeight) ~= "number" or request.sourceHeight <= 0 then
    return "positive preview source dimensions are required"
  end
  if type(request.title) ~= "string" or request.title == "" then return "preview title is required" end
end

local function errorResult(message) return { status = "error", error = tostring(message) } end

local function reviewWithContext(functionContext, request, runtime)
  if not runtime.makePropertyTable or not runtime.addObserver or not runtime.viewFactory
    or not runtime.bind or not runtime.presentModalDialog then
    return errorResult("Lightroom preview UI runtime is unavailable")
  end
  local props = runtime:makePropertyTable(functionContext)
  local suspended = false
  props.topPx, props.bottomPx, props.leftPx, props.rightPx = 0, 0, 0, 0
  props.previewPath, props.failureText, props.confirmEnabled = request.thumbnailPath, "", false

  local session
  local uiContext = {
    bindPending = function()
      props.confirmEnabled, props.failureText = false, ""
    end,
    bindFailure = function(message)
      props.confirmEnabled, props.failureText = false, tostring(message or "预览渲染失败")
    end,
    bindPreview = function(path)
      props.previewPath, props.failureText, props.confirmEnabled = path, "", true
    end,
    suspendObservers = function(fn)
      suspended = true
      fn()
      props.topPx, props.bottomPx, props.leftPx, props.rightPx = 0, 0, 0, 0
      suspended = false
    end,
  }
  session = PreviewAgent.newSession(uiContext, request, runtime)
  if not session then return errorResult("preview session could not be created") end

  local function snapshotFromProperties()
    return {
      frames = clone(request.frames), thumbnailPath = request.thumbnailPath,
      sourceWidth = request.sourceWidth, sourceHeight = request.sourceHeight,
      offsets = {
        topPx = tonumber(props.topPx) or 0, bottomPx = tonumber(props.bottomPx) or 0,
        leftPx = tonumber(props.leftPx) or 0, rightPx = tonumber(props.rightPx) or 0,
      },
    }
  end
  local function observe()
    if not suspended then session:edit(snapshotFromProperties()) end
  end
  for _, key in ipairs({ "topPx", "bottomPx", "leftPx", "rightPx" }) do
    runtime:addObserver(props, key, observe)
  end
  session:edit(snapshotFromProperties())

  local f, bind = runtime:viewFactory(), function(key) return runtime:bind(key) end
  local contents = f:column {
    bind_to_object = props,
    spacing = f:control_spacing(),
    f:picture { value = bind "previewPath", width = 720, height = 480 },
    f:static_text { title = "正数会把对应边界向胶片画面外扩展（像素）", font = "<system/small>" },
    f:row { spacing = f:label_spacing(), f:static_text { title = "上边界", width = 90 },
      f:edit_field { value = bind "topPx", width_in_chars = 7, precision = 0, immediate = true },
      f:static_text { title = "向外增加", font = "<system/small>" } },
    f:row { spacing = f:label_spacing(), f:static_text { title = "下边界", width = 90 },
      f:edit_field { value = bind "bottomPx", width_in_chars = 7, precision = 0, immediate = true },
      f:static_text { title = "向外增加", font = "<system/small>" } },
    f:row { spacing = f:label_spacing(), f:static_text { title = "左边界", width = 90 },
      f:edit_field { value = bind "leftPx", width_in_chars = 7, precision = 0, immediate = true },
      f:static_text { title = "向外增加", font = "<system/small>" } },
    f:row { spacing = f:label_spacing(), f:static_text { title = "右边界", width = 90 },
      f:edit_field { value = bind "rightPx", width_in_chars = 7, precision = 0, immediate = true },
      f:static_text { title = "向外增加", font = "<system/small>" } },
    f:row {
      f:push_button { title = "重置", action = function() session:Reset() end },
      f:static_text { title = bind "failureText", fill_horizontal = 1 },
    },
  }
  local ok, modalResult = pcall(function()
    return runtime:presentModalDialog {
      title = request.title, contents = contents, actionVerb = "确认", cancelVerb = "取消",
      actionBinding = {
        enabled = { bind_to_object = props, key = "confirmEnabled" },
      },
    }
  end)
  if not ok then session:close(); return errorResult(modalResult) end
  if modalResult ~= "ok" then session:close(); return { status = "canceled" } end
  local payload = session:Confirm()
  if not payload then session:close(); return errorResult(session.state.error or "preview is not ready") end
  local result = {
    status = "confirmed", frames = clone(payload.frames or session.state.frames),
    offsets = {
      topPx = tonumber(props.topPx) or 0, bottomPx = tonumber(props.bottomPx) or 0,
      leftPx = tonumber(props.leftPx) or 0, rightPx = tonumber(props.rightPx) or 0,
    },
  }
  session:close()
  return result
end

function PreviewAgent.review(context, request, runtime)
  local validationError = validateRequest(request)
  if validationError then return errorResult(validationError) end
  runtime = runtime or {}
  if context ~= nil then return reviewWithContext(context, request, runtime) end
  if not runtime.withContext then return errorResult("Lightroom function context is unavailable") end
  local result
  local ok, failure = pcall(function()
    runtime:withContext("NegativeCutterPreview", function(createdContext)
      result = reviewWithContext(createdContext, request, runtime)
    end)
  end)
  if not ok then return errorResult(failure) end
  return result or errorResult("preview dialog returned no result")
end

function PreviewAgent.closeAll()
  local dialogs = {}; for _, dialog in pairs(registry) do dialogs[#dialogs + 1] = dialog end
  for _, dialog in ipairs(dialogs) do dialog:close() end
  registry = {}
end
function PreviewAgent.registry() return registry end
return PreviewAgent
