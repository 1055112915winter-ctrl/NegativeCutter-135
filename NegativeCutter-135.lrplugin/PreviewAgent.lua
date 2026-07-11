-- Live crop preview orchestration.  Deliberately dependency injected so it can
-- be exercised without Lightroom (and so rendering remains a replaceable seam).
local PreviewAgent = {}
local registry = {}
local nextId = 0
local function clone(v) if type(v) ~= 'table' then return v end; local n={}; for k,x in pairs(v) do n[k]=clone(x) end; return n end

local function now(clock) return (clock and clock.now and clock.now()) or (os.time() * 1000) end
local function spawn(s, f) if s and s.spawn then return s.spawn(f) end; return f() end
local function sleep(s, ms) if s and s.sleep then return s.sleep(ms) end end
function PreviewAgent.makeAdapters(LrTasks, LrFileUtils)
  return {scheduler={startAsyncTask=function(f) return LrTasks.startAsyncTask(f) end,spawn=function(f) return LrTasks.startAsyncTask(f) end,sleep=function(ms) return LrTasks.sleep(ms/1000) end},clock={now=function() return os.time()*1000 + math.floor((os.clock()%1)*1000) end},filesystem={mkdir=function(p) return LrFileUtils.createAllDirectories(p) end}}
end

function PreviewAgent.review(context, request, adapters)
  adapters = adapters or {}; local scheduler = adapters.scheduler or {}
  local clock, fs, renderer = adapters.clock, adapters.filesystem or {}, adapters.renderer or {}
  nextId = nextId + 1
  local id = adapters.uuid and adapters.uuid() or (function() local h=""; for i=1,32 do h=h..string.format("%x", math.random(0,15)) end; return h:sub(1,8).."-"..h:sub(9,12).."-4"..h:sub(14,16).."-a"..h:sub(18,20).."-"..h:sub(21) end)()
  local root = adapters.previewRoot or fs.previewRoot or "/tmp/NegativeCutterPreview"
  local dir = root .. "/" .. id
  if fs.mkdir then fs.mkdir(dir) end
  local state = {topPx=0,bottomPx=0,leftPx=0,rightPx=0,generation=0,deadline=0,pending=false,closed=false,status="idle",frames={}}
  local current, activeGeneration, workerActive = nil, 0, false
  local slot = 0
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
    local out = dir .. "/slot-" .. tostring((slot + 1) % 2) .. ".png"
    local ok, result = pcall(function()
      if not renderer.render then error("renderer.render missing") end
      return renderer.render(req, out, context)
    end)
    if state.closed or state.generation ~= gen then return end
    if not ok or result == false then state.pending=false; state.status="failure"; return end
    if fs.publish then local ok,err=fs.publish(out, dir .. "/active.png", gen); if ok==false then state.pending=false; state.status="failure"; return end; slot=(slot+1)%2 end
    if type(result) ~= "table" then result = {frames=result} end
    publish(gen, result)
  end
  local function ensureWorker()
    if workerActive then return end
    workerActive=true
    spawn(scheduler, function()
      while not state.closed do
        local gen, deadline, req = state.generation, state.deadline, dialog._request
        worker(gen, req, deadline)
        if state.closed or gen == state.generation then break end
      end
      workerActive=false
    end)
  end
  function dialog:edit(req)
    if state.closed then return false end
    state.generation = state.generation + 1; local gen = state.generation; local deadline = now(clock) + 120
    state.deadline = deadline; state.pending=true; state.status="pending"
    dialog._request=clone(req); ensureWorker(); return gen
  end
  function dialog:Reset()
    if state.closed then return false end
    state.topPx,state.bottomPx,state.leftPx,state.rightPx=0,0,0,0
    state.generation=state.generation+1; local gen=state.generation; local deadline=now(clock)+120
    state.deadline=deadline; state.pending=true; state.status="pending"
    dialog._request={offsets={topPx=0,bottomPx=0,leftPx=0,rightPx=0}, source=clone(request)}; ensureWorker(); return true
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

function PreviewAgent.closeAll() local all={}; for _,d in pairs(registry) do all[#all+1]=d end; for _,d in ipairs(all) do d:close() end; registry={} end
function PreviewAgent.registry() return registry end
function PreviewAgent.scavenge(root, fs, currentSession)
  if not fs or not fs.list then return 0 end
  local n=0
  for _,name in ipairs(fs.list(root) or {}) do
    if name ~= currentSession and name:match("^[%x]+-[%x]+$") then if fs.remove then fs.remove(root.."/"..name); n=n+1 end end
  end
  return n
end
return PreviewAgent
