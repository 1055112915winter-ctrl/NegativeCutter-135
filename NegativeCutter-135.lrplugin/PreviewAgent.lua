-- Live crop preview orchestration.  Deliberately dependency injected so it can
-- be exercised without Lightroom (and so rendering remains a replaceable seam).
local PreviewAgent = {}
local registry = {}
local nextId = 0

local function now(clock) return (clock and clock.now and clock.now()) or os.clock() end
local function spawn(s, f) if s and s.spawn then return s.spawn(f) end; return f() end
local function sleep(s, ms) if s and s.sleep then return s.sleep(ms) end end

function PreviewAgent.review(context, request, adapters)
  adapters = adapters or {}; local scheduler = adapters.scheduler or {}
  local clock, fs, renderer = adapters.clock, adapters.filesystem or {}, adapters.renderer or {}
  nextId = nextId + 1
  local id = tostring(nextId); local root = adapters.previewRoot or fs.previewRoot or "/tmp/NegativeCutterPreview"
  local dir = root .. "/" .. id
  if fs.mkdir then fs.mkdir(dir) end
  local state = {topPx=0,bottomPx=0,leftPx=0,rightPx=0,generation=0,deadline=0,pending=false,closed=false,status="idle",frames={}}
  local current, activeGeneration = nil, 0
  local dialog = { state=state, id=id, dir=dir }
  registry[id] = dialog

  local function publish(gen, payload)
    if state.closed or gen ~= state.generation then return false end
    state.status = "ready"; state.pending = false; state.frames = payload.frames or payload
    if payload.offsets then
      for k,v in pairs(payload.offsets) do if type(v)=="number" then state[k]=v end end
    end
    current = payload; activeGeneration = gen; return true
  end
  local function worker(gen, req, deadline)
    sleep(scheduler, math.max(0, deadline - now(clock)))
    if state.closed or state.generation ~= gen or now(clock) < deadline then return end
    local out = dir .. "/preview-" .. tostring(gen) .. ".png"
    local ok, result = pcall(function()
      if not renderer.render then error("renderer.render missing") end
      return renderer.render(req, out, context)
    end)
    if state.closed or state.generation ~= gen then return end
    if not ok or result == false then state.pending=false; state.status="failure"; return end
    if fs.publish then fs.publish(out, dir .. "/active.png", gen) end
    if type(result) ~= "table" then result = {frames=result} end
    publish(gen, result)
  end
  function dialog:edit(req)
    if state.closed then return false end
    state.generation = state.generation + 1; local gen = state.generation; local deadline = now(clock) + 120
    state.deadline = deadline; state.pending=true; state.status="pending"
    spawn(scheduler, function() worker(gen, req, deadline) end); return gen
  end
  function dialog:Reset()
    if state.closed then return false end
    state.topPx,state.bottomPx,state.leftPx,state.rightPx=0,0,0,0
    state.generation=state.generation+1; local gen=state.generation; local deadline=now(clock)+120
    state.deadline=deadline; state.pending=true; state.status="pending"
    spawn(scheduler, function() worker(gen, request, deadline) end); return true
  end
  function dialog:Confirm()
    if state.closed or state.pending or state.status ~= "ready" then return false end
    if context and context.confirm then return context.confirm(current) end; return current
  end
  function dialog:Cancel() if state.closed then return false end; self:close(); return true end
  function dialog:close()
    if state.closed then return end; state.closed=true; state.pending=false; registry[id]=nil
    if fs.remove then fs.remove(dir) end
  end
  return dialog
end

function PreviewAgent.closeAll() for _,d in pairs(registry) do d:close() end; registry={} end
function PreviewAgent.registry() return registry end
return PreviewAgent
