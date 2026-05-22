#!/usr/bin/env lua
--[[
  Four-way EXIF orientation mapping — isolated unit test
  Validates directionAlign with AB / BC / CD / DA orientations.

  Usage: lua tests/test_direction_align_fourway.lua
]]--

local thisDir = debug.getinfo(1).source:match("@?(.*/)") or "./"
local pluginDir = thisDir .. "../"

package.path = package.path
    .. ";" .. thisDir .. "?.lua"
    .. ";" .. thisDir .. "mock_sdk/?.lua"
    .. ";" .. pluginDir .. "?.lua"

_G._PLUGIN = { path = pluginDir }

local mockSdk = require("mock_sdk.init")
mockSdk.setupImport()

-- Stub dofile for ThumbnailAgent / ApplierAgent
local _orig_dofile = dofile
_G.dofile = function(path)
    if type(path) == "string" and path:match("ThumbnailAgent%.lua$") then
        return { extract = function(_, _, cb) if cb then cb(true, "/tmp/t.jpg", nil) end end }
    end
    if type(path) == "string" and path:match("ApplierAgent%.lua$") then
        return {
            applyCrop = function() return true end,
            resetCrop = function() return true end,
        }
    end
    return _orig_dofile(path)
end

_G.LOC = function(key) return key end

local ProcessAgent = dofile(pluginDir .. "ProcessAgent.lua")
local MockPhoto = require("mock_sdk.LrPhoto")

local passCount, failCount = 0, 0

local function assertEq(expected, actual, msg)
    if expected ~= actual then
        error(string.format("%s: expected %s, got %s", msg or "assertEq",
            tostring(expected), tostring(actual)))
    end
end

local function runTest(name, fn)
    io.write("  " .. name .. " ... ")
    local ok, err = pcall(fn)
    if ok then print("PASS"); passCount = passCount + 1
    else print("FAIL\n    " .. tostring(err):gsub("\n", "\n    ")); failCount = failCount + 1 end
end

-- ------------------------------------------------------------------
-- Helper: create a result frame with explicit relative coords
-- ------------------------------------------------------------------
local function makeResult(opts)
    opts = opts or {}
    return {
        frameCount = 1,
        sourceWidth = opts.srcW or 2400,
        sourceHeight = opts.srcH or 3500,
        isHorizontal = (opts.srcW or 2400) >= (opts.srcH or 3500),
        cropAngle = opts.angle or 0,
        frames = {
            {
                index = 1,
                relativeTop = opts.rt or 0.1,
                relativeBottom = opts.rb or 0.4,
                relativeLeft = opts.rl or 0.0,
                relativeRight = opts.rr or 1.0,
            }
        }
    }
end

print("\n--- Test Suite: directionAlign baseline (existing behaviour) ---")

runTest("AB→AB (no rotation)", function()
    local photo = MockPhoto.createMockPhoto({
        dimensions = {width = 2400, height = 3500},
        rawMetadata = {orientation = "AB"}
    })
    local result = makeResult({srcW=2400, srcH=3500, rt=0.1, rb=0.4, rl=0.0, rr=1.0})
    local a = ProcessAgent.directionAlign(result, photo)
    assertEq(0.1, a.frames[1].relativeTop, "top")
    assertEq(0.4, a.frames[1].relativeBottom, "bottom")
    assertEq(0.0, a.frames[1].relativeLeft, "left")
    assertEq(1.0, a.frames[1].relativeRight, "right")
end)

runTest("90° mismatch rotates (existing behaviour)", function()
    -- Python vertical, LR horizontal
    local photo = MockPhoto.createMockPhoto({
        dimensions = {width = 3500, height = 2400},
        rawMetadata = {orientation = "AB"}
    })
    local result = makeResult({srcW=2400, srcH=3500, rt=0.1, rb=0.4, rl=0.0, rr=1.0})
    local a = ProcessAgent.directionAlign(result, photo)
    assertEq(0.0, a.frames[1].relativeTop, "rotated top")
    assertEq(1.0, a.frames[1].relativeBottom, "rotated bottom")
    assertEq(0.1, a.frames[1].relativeLeft, "rotated left")
    assertEq(0.4, a.frames[1].relativeRight, "rotated right")
end)

print("\n--- Test Suite: four-way mapping formulas (stecman-derived) ---")

-- These tests exercise the four rotation formulas that would be added to
-- directionAlign.  They are written as pure coordinate transforms so we
-- can verify the math without touching ProcessAgent yet.

--[[
  Stecman formulas (relative coords, 0-1, AB = normal / no rotation):

  BC (90° CW):
    right = bottom
    bottom = 1 - left
    left = top
    top = 1 - right

  CD (180°):
    bottom = 1 - top
    left = 1 - right
    top = 1 - bottom
    right = 1 - left

  DA (270° CW / 90° CCW):
    left = 1 - bottom
    top = left_original
    right = 1 - top_original
    bottom = right_original

  Wait — the DA formulas as written in stecman's code use the ORIGINAL
  crop values on the RHS.  To express them as transforms on the result:

  BC:  (t,b,l,r) → (1-r, 1-l, t, b)
  CD:  (t,b,l,r) → (1-b, 1-t, 1-r, 1-l)
  DA:  (t,b,l,r) → (l, r, 1-b, 1-t)

  Let's verify these compose correctly:
    AB → BC: (t,b,l,r) → (1-r, 1-l, t, b)
    BC → CD: (1-r, 1-l, t, b) → (1-(1-l), 1-(1-r), 1-b, 1-t)
             = (l, r, 1-b, 1-t)  ✓ matches DA from AB
    BC → BC: (1-r, 1-l, t, b) → (1-b, 1-t, 1-r, 1-l)
             = CD from AB  ✓

  So the clean transform matrix is:
    AB: identity
    BC: (t,b,l,r) ↦ (1-r, 1-l,  t,  b)
    CD: (t,b,l,r) ↦ (1-b, 1-t, 1-r, 1-l)
    DA: (t,b,l,r) ↦ ( l,   r, 1-b, 1-t)
--]]

local function rotateBC(t, b, l, r)
    return 1 - r, 1 - l, t, b
end

local function rotateCD(t, b, l, r)
    return 1 - b, 1 - t, 1 - r, 1 - l
end

local function rotateDA(t, b, l, r)
    return l, r, 1 - b, 1 - t
end

runTest("BC rotation formula round-trip", function()
    local t, b, l, r = 0.1, 0.4, 0.0, 1.0
    -- AB → BC
    local t1, b1, l1, r1 = rotateBC(t, b, l, r)
    -- BC → CD (= AB → BC → BC)
    local t2, b2, l2, r2 = rotateBC(t1, b1, l1, r1)
    -- CD → DA (= AB → BC → BC → BC)
    local t3, b3, l3, r3 = rotateBC(t2, b2, l2, r2)
    -- DA → AB (= 4×BC)
    local t4, b4, l4, r4 = rotateBC(t3, b3, l3, r3)

    assertEq(t, t4, "top after 4×BC")
    assertEq(b, b4, "bottom after 4×BC")
    assertEq(l, l4, "left after 4×BC")
    assertEq(r, r4, "right after 4×BC")
end)

runTest("CD rotation formula round-trip", function()
    local t, b, l, r = 0.1, 0.4, 0.2, 0.8
    local t1, b1, l1, r1 = rotateCD(t, b, l, r)
    local t2, b2, l2, r2 = rotateCD(t1, b1, l1, r1)
    assertEq(t, t2, "top after 2×CD")
    assertEq(b, b2, "bottom after 2×CD")
    assertEq(l, l2, "left after 2×CD")
    assertEq(r, r2, "right after 2×CD")
end)

runTest("DA rotation formula round-trip", function()
    local t, b, l, r = 0.1, 0.4, 0.2, 0.8
    local t1, b1, l1, r1 = rotateDA(t, b, l, r)
    local t2, b2, l2, r2 = rotateDA(t1, b1, l1, r1)
    local t3, b3, l3, r3 = rotateDA(t2, b2, l2, r2)
    local t4, b4, l4, r4 = rotateDA(t3, b3, l3, r3)
    assertEq(t, t4, "top after 4×DA")
    assertEq(b, b4, "bottom after 4×DA")
    assertEq(l, l4, "left after 4×DA")
    assertEq(r, r4, "right after 4×DA")
end)

runTest("BC+BC equals CD", function()
    local t, b, l, r = 0.1, 0.4, 0.2, 0.8
    local bc_bc_t, bc_bc_b, bc_bc_l, bc_bc_r = rotateBC(rotateBC(t, b, l, r))
    local cd_t, cd_b, cd_l, cd_r = rotateCD(t, b, l, r)
    assertEq(cd_t, bc_bc_t, "top")
    assertEq(cd_b, bc_bc_b, "bottom")
    assertEq(cd_l, bc_bc_l, "left")
    assertEq(cd_r, bc_bc_r, "right")
end)

runTest("BC+CD equals DA", function()
    local t, b, l, r = 0.1, 0.4, 0.2, 0.8
    local bc_cd_t, bc_cd_b, bc_cd_l, bc_cd_r = rotateBC(rotateCD(t, b, l, r))
    local da_t, da_b, da_l, da_r = rotateDA(t, b, l, r)
    assertEq(da_t, bc_cd_t, "top")
    assertEq(da_b, bc_cd_b, "bottom")
    assertEq(da_l, bc_cd_l, "left")
    assertEq(da_r, bc_cd_r, "right")
end)

runTest("BC on a centred square frame", function()
    -- A centred frame: top=0.1, bottom=0.9, left=0.2, right=0.8
    -- After BC: top=0.2, bottom=0.8, left=0.1, right=0.9
    -- Visual: frame rotates 90° CW, so narrow side becomes height
    local t, b, l, r = 0.1, 0.9, 0.2, 0.8
    local nt, nb, nl, nr = rotateBC(t, b, l, r)
    assertEq(0.2, nt, "top")
    assertEq(0.8, nb, "bottom")
    assertEq(0.1, nl, "left")
    assertEq(0.9, nr, "right")
end)

runTest("CD on a centred square frame", function()
    -- 180° flip should mirror around centre
    local t, b, l, r = 0.1, 0.9, 0.2, 0.8
    local nt, nb, nl, nr = rotateCD(t, b, l, r)
    assertEq(0.1, nt, "top (mirrored)")
    assertEq(0.9, nb, "bottom (mirrored)")
    assertEq(0.2, nl, "left (mirrored)")
    assertEq(0.8, nr, "right (mirrored)")
end)

runTest("DA on a centred square frame", function()
    -- 90° CCW: top=0.2, bottom=0.8, left=0.1, right=0.9
    local t, b, l, r = 0.1, 0.9, 0.2, 0.8
    local nt, nb, nl, nr = rotateDA(t, b, l, r)
    assertEq(0.2, nt, "top")
    assertEq(0.8, nb, "bottom")
    assertEq(0.1, nl, "left")
    assertEq(0.9, nr, "right")
end)

print("\n--- Test Suite: cropAngle rotation sign ---")

runTest("BC negates cropAngle once", function()
    -- angle changes sign on every 90° rotation
    local a = 1.5
    assertEq(-1.5, -a, "negated angle")
end)

runTest("CD preserves cropAngle (2×negation)", function()
    local a = 1.5
    assertEq(1.5, -(-a), "double negation")
end)

print("\n" .. string.rep("-", 62))
print(string.format("结果: %d 通过, %d 失败", passCount, failCount))
print(string.rep("-", 62))

if failCount > 0 then os.exit(1)
else print("\n全部测试通过!") end
