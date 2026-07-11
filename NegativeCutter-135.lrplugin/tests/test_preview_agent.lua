local dir = (debug.getinfo(1).source:match("@?(.*/)" ) or "./") .. "../"
local Agent = dofile(dir .. "PreviewAgent.lua")
local t, jobs, renders = 0, {}, 0
local scheduler = {
  now=function() return t end,
  sleep=function(ms) t=t+ms end,
  spawn=function(f) jobs[#jobs+1]=f end,
}
local fs={mkdir=function() end,publish=function() end,remove=function() end}
local renderer={render=function(req,path) renders=renders+1; return {offsets=req.offsets or {},frames={path}} end}
local d=Agent.review({}, {}, {scheduler=scheduler,clock=scheduler,filesystem=fs,renderer=renderer})
d:edit({offsets={topPx=3}}); d:edit({offsets={topPx=4}})
for _,f in ipairs(jobs) do f() end
jobs={}
assert(renders==1, "stale edit rendered")
assert(d.state.topPx==4, "latest offsets not published")
assert(d:Confirm() ~= false, "latest successful render should confirm")
d:Reset(); d:edit({offsets={topPx=8}}); for _,f in ipairs(jobs) do f() end
assert(renders==2, "reset/edit should render once")
d:close(); d:edit({offsets={topPx=9}}); assert(renders==2, "closed dialog scheduled work")
print("preview agent tests passed")
