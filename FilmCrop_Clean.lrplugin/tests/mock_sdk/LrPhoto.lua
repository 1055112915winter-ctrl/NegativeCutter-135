--[[
  Mock LrPhoto — 测试用的照片对象工厂
  提供 createMockPhoto() 来构造一个符合 LrPhoto API 的 mock 对象
]]--

local LrPhoto = {}

-- Mock Photo 工厂
function LrPhoto.createMockPhoto(opts)
    opts = opts or {}

    local photo = {
        -- 内部状态（测试可读取）
        _uuid = opts.uuid or "mock-uuid-" .. tostring(math.random(100000)),
        _path = opts.path or "/tmp/test_scan.tif",
        _dimensions = opts.dimensions or {width = 2400, height = 3500},
        _fileFormat = opts.fileFormat or "TIFF",
        _copyName = opts.copyName or nil,
        _developSettings = opts.developSettings or {},
        _rawMetadata = opts.rawMetadata or {},
        _formattedMetadata = opts.formattedMetadata or {},
    }

    -- 元数据读取
    function photo:getRawMetadata(key)
        if key == "uuid" then return self._uuid end
        if key == "path" then return self._path end
        if key == "dimensions" then return self._dimensions end
        if key == "fileFormat" then return self._fileFormat end
        if key == "width" then return self._dimensions and self._dimensions.width end
        if key == "height" then return self._dimensions and self._dimensions.height end
        return self._rawMetadata[key]
    end

    function photo:getFormattedMetadata(key)
        if key == "fileName" then
            return self._path:match("([^/]+)$") or self._path
        end
        return self._formattedMetadata[key]
    end

    function photo:getDevelopSettings()
        return self._developSettings
    end

    function photo:applyDevelopSettings(settings)
        self._developSettings = settings
    end

    function photo:setRawMetadata(key, value)
        if key == "copyName" then
            self._copyName = value
        end
    end

    -- 异步缩略图请求
    function photo:requestJpegThumbnail(maxW, maxH, callback)
        -- 测试中预置缩略图路径
        local thumbPath = opts.thumbPath or "/tmp/test_scan_thumb.jpg"
        if callback then
            callback(true, thumbPath, nil)
        end
    end

    return photo
end

return LrPhoto
