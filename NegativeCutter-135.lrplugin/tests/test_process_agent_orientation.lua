local thisDir = debug.getinfo(1).source:match("@?(.*/)") or "./"
local pluginDir = thisDir .. "../"

_G._PLUGIN = {path = pluginDir}
_G.import = function(name)
    if name == "LrLogger" then
        return function()
            return {enable = function() end, trace = function() end, error = function() end}
        end
    elseif name == "LrPathUtils" then
        return {
            child = function(a, b) return a .. "/" .. b end,
            getStandardFilePath = function() return "/tmp" end,
        }
    elseif name == "LrFileUtils" then
        return {exists = function() return false end, createAllDirectories = function() end}
    elseif name == "LrTasks" then
        return {sleep = function() end, execute = function() return 0 end, pcall = pcall}
    elseif name == "LrPrefs" then
        return {prefsForPlugin = function() return {} end}
    end
    error("unexpected Lightroom import: " .. tostring(name))
end

local realDofile = dofile
_G.dofile = function(path)
    if path:match("json%.lua$") then return {decode = function() return {} end} end
    if path:match("ThumbnailAgent%.lua$") then return {} end
    if path:match("ApplierAgent%.lua$") then return {} end
    if path:match("CropCleaner%.lua$") then return {} end
    return realDofile(path)
end

local ProcessAgent = realDofile(pluginDir .. "ProcessAgent.lua")

local function assertNear(expected, actual, message)
    if math.abs(expected - actual) > 1e-9 then
        error(string.format("%s: expected %.9f, got %.9f", message, expected, actual))
    end
end

local function aligned(orientation)
    local result = {
        sourceWidth = 2000,
        sourceHeight = 1000,
        isHorizontal = true,
        cropAngle = 1.25,
        frames = {{
            relativeTop = 0.1,
            relativeBottom = 0.4,
            relativeLeft = 0.0,
            relativeRight = 0.6,
        }},
    }
    local photo = {getRawMetadata = function(_, key)
        if key == "dimensions" then return {width = 1000, height = 2000} end
        if key == "orientation" then return orientation end
        return nil
    end}
    return ProcessAgent.directionAlign(result, photo)
end

local function alignedSameAxis(orientation)
    local result = {
        sourceWidth = 1000,
        sourceHeight = 2000,
        isHorizontal = false,
        cropAngle = 1.25,
        frames = {{
            relativeTop = 0.1,
            relativeBottom = 0.4,
            relativeLeft = 0.0,
            relativeRight = 0.6,
        }},
    }
    local photo = {getRawMetadata = function(_, key)
        if key == "dimensions" then return {width = 1000, height = 2000} end
        if key == "orientation" then return orientation end
        return nil
    end}
    return ProcessAgent.directionAlign(result, photo)
end

local bc = aligned("BC")
assertNear(0.4, bc.frames[1].relativeTop, "BC top")
assertNear(1.0, bc.frames[1].relativeBottom, "BC bottom")
assertNear(0.1, bc.frames[1].relativeLeft, "BC left")
assertNear(0.4, bc.frames[1].relativeRight, "BC right")
assertNear(-1.25, bc.cropAngle, "BC angle")

local da = aligned("DA")
assertNear(0.0, da.frames[1].relativeTop, "DA top")
assertNear(0.6, da.frames[1].relativeBottom, "DA bottom")
assertNear(0.6, da.frames[1].relativeLeft, "DA left")
assertNear(0.9, da.frames[1].relativeRight, "DA right")
assertNear(-1.25, da.cropAngle, "DA angle")

-- Lightroom returns the reverse-edge labels for mirrored EXIF orientations
-- found in the real 120 fixtures: CB = EXIF 5 (transpose), AD = EXIF 7
-- (transverse).  Their displayed dimensions can already match the Python
-- decode, so the orientation tag itself must trigger the transform.
local cb = alignedSameAxis("CB")
assertNear(0.0, cb.frames[1].relativeTop, "CB top")
assertNear(0.6, cb.frames[1].relativeBottom, "CB bottom")
assertNear(0.1, cb.frames[1].relativeLeft, "CB left")
assertNear(0.4, cb.frames[1].relativeRight, "CB right")
assertNear(-1.25, cb.cropAngle, "CB angle")

local ad = alignedSameAxis("AD")
assertNear(0.4, ad.frames[1].relativeTop, "AD top")
assertNear(1.0, ad.frames[1].relativeBottom, "AD bottom")
assertNear(0.6, ad.frames[1].relativeLeft, "AD left")
assertNear(0.9, ad.frames[1].relativeRight, "AD right")
assertNear(-1.25, ad.cropAngle, "AD angle")

print("process agent orientation: PASS")
