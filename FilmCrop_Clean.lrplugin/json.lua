--[[
  Bundled minimal JSON decoder for FilmCrop plugin.

  Lightroom Classic ships JSON.lua (uppercase, method-call API) but does
  NOT register a `json` toolkit script — `require("json")` fails with
  "Could not load toolkit script: json". This file shims that gap so
  ImportAgent.lua and ProcessAgent.lua can use require("json").decode().

  Scope: covers the JSON shapes produced by detect_thumb.py and the
  filmcrop_e2e.json watch sidecar — objects, arrays, numbers (int/float/
  negative), booleans, double-quoted strings.
  Does NOT support: \uXXXX decoding (escapes left as raw bytes — fine for
  current callers since affected fields like _diag.detectorPath are pass-
  through only), embedded \" inside strings, null in nested positions
  (returned as nil → key removed).

  A copy lives at tests/mock_sdk/json.lua for vanilla-lua test runs.
]]--

local M = {}

local function skip_ws(s, i)
  while i <= #s do
    local c = s:byte(i)
    if c ~= 32 and c ~= 9 and c ~= 10 and c ~= 13 then return i end
    i = i + 1
  end
  return i
end

local parse_value

local function parse_string(s, i)
  -- assumes s:sub(i,i) == '"'
  local j = i + 1
  while j <= #s do
    local c = s:sub(j, j)
    if c == '\\' then
      j = j + 2  -- skip escape (best-effort, no decode)
    elseif c == '"' then
      return s:sub(i + 1, j - 1), j + 1
    else
      j = j + 1
    end
  end
  error("unterminated string at " .. i)
end

local function parse_number(s, i)
  local _, ne = s:find("^[%-%+]?[%d%.]+[eE]?[%-%+]?%d*", i)
  if not ne then error("bad number at " .. i) end
  return tonumber(s:sub(i, ne)), ne + 1
end

local function parse_object(s, i)
  -- assumes s:sub(i,i) == '{'
  local t = {}
  i = skip_ws(s, i + 1)
  if s:sub(i, i) == '}' then return t, i + 1 end
  while i <= #s do
    i = skip_ws(s, i)
    if s:sub(i, i) ~= '"' then error("expected string key at " .. i) end
    local key, ni = parse_string(s, i)
    i = skip_ws(s, ni)
    if s:sub(i, i) ~= ':' then error("expected ':' at " .. i) end
    i = skip_ws(s, i + 1)
    local val, vi = parse_value(s, i)
    if val ~= nil then t[key] = val end
    i = skip_ws(s, vi)
    local c = s:sub(i, i)
    if c == ',' then i = skip_ws(s, i + 1)
    elseif c == '}' then return t, i + 1
    else error("expected ',' or '}' at " .. i) end
  end
  error("unterminated object")
end

local function parse_array(s, i)
  -- assumes s:sub(i,i) == '['
  local t = {}
  i = skip_ws(s, i + 1)
  if s:sub(i, i) == ']' then return t, i + 1 end
  while i <= #s do
    i = skip_ws(s, i)
    local val, ni = parse_value(s, i)
    t[#t + 1] = val
    i = skip_ws(s, ni)
    local c = s:sub(i, i)
    if c == ',' then i = skip_ws(s, i + 1)
    elseif c == ']' then return t, i + 1
    else error("expected ',' or ']' at " .. i) end
  end
  error("unterminated array")
end

parse_value = function(s, i)
  i = skip_ws(s, i)
  local c = s:sub(i, i)
  if c == '{' then return parse_object(s, i)
  elseif c == '[' then return parse_array(s, i)
  elseif c == '"' then return parse_string(s, i)
  elseif c == 't' and s:sub(i, i + 3) == 'true' then return true, i + 4
  elseif c == 'f' and s:sub(i, i + 4) == 'false' then return false, i + 5
  elseif c == 'n' and s:sub(i, i + 3) == 'null' then return nil, i + 4
  elseif c == '-' or c:match("%d") then return parse_number(s, i)
  else error("unexpected char '" .. c .. "' at " .. i) end
end

function M.decode(s)
  if type(s) ~= "string" then error("json.decode: string expected") end
  local val = parse_value(s, 1)
  return val
end

return M
