-- Source-only manual harness.  This is intentionally not registered in Info.lua.
local Harness = {}

function Harness.run(request, runtime)
  local plugin = (debug.getinfo(1).source:match("@?(.*/)") or "./") .. "../"
  local PreviewAgent = dofile(plugin .. "PreviewAgent.lua")
  return PreviewAgent.review(nil, request, runtime)
end

return Harness
