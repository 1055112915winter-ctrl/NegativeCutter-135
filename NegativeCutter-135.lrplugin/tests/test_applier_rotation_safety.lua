local thisDir = debug.getinfo(1).source:match("@?(.*/)") or "./"
local pluginDir = thisDir .. "../"

local appliedSettings = nil
local catalog = {
    adjustPhotoDevelopSettings = function(_, _, settings)
        appliedSettings = settings
    end,
}

_G.import = function(name)
    if name == "LrLogger" then
        return function()
            return {
                enable = function() end,
                trace = function() end,
                error = function() end,
            }
        end
    end
    if name == "LrApplication" then
        return {activeCatalog = function() return catalog end}
    end
    error("unexpected Lightroom import: " .. tostring(name))
end

local photo = {
    getRawMetadata = function() return "TIFF" end,
    getDevelopSettings = function() return appliedSettings or {} end,
}

local ApplierAgent = dofile(pluginDir .. "ApplierAgent.lua")

local function assertEqual(expected, actual, message)
    if expected ~= actual then
        error(string.format("%s: expected %s, got %s", message, tostring(expected), tostring(actual)))
    end
end

local function applyAngle(angle)
    appliedSettings = nil
    local ok, err = ApplierAgent.applyCrop(photo, {
        top = 0.1,
        bottom = 0.9,
        left = 0.1,
        right = 0.9,
        cropAngle = angle,
    })
    if not ok then error(err or "applyCrop failed") end
    return appliedSettings.CropAngle
end

assertEqual(0, applyAngle(0.3), "sub-threshold angle")
assertEqual(1.25, applyAngle(1.25), "safe angle")
assertEqual(0, applyAngle(8.13), "large positive angle")
assertEqual(0, applyAngle(-33.69), "large negative angle")
assertEqual(0, applyAngle(0 / 0), "NaN angle")
assertEqual(0, applyAngle(1 / 0), "infinite angle")

print("rotation safety: PASS")
