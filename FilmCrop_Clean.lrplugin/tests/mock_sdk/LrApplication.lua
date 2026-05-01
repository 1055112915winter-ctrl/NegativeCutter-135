--[[
  Mock LrApplication — 测试用的应用接口
  返回一个 mock catalog
]]--

local LrApplication = {}

-- 全局 catalog 状态，测试可以设置和断言
_G.__mock_catalog = _G.__mock_catalog or {
    photos = {},
    selectedPhotos = {},
    virtualCopies = {},
    writeAccessLog = {},
}

function LrApplication.activeCatalog()
    local catalog = _G.__mock_catalog

    -- 确保方法存在
    catalog.getTargetPhotos = catalog.getTargetPhotos or function(self)
        return self.selectedPhotos or {}
    end

    catalog.setSelectedPhotos = catalog.setSelectedPhotos or function(self, photo, others)
        self.selectedPhotos = {photo}
        if others then
            for _, p in ipairs(others) do
                table.insert(self.selectedPhotos, p)
            end
        end
    end

    catalog.withWriteAccessDo = catalog.withWriteAccessDo or function(self, name, func)
        table.insert(self.writeAccessLog or {}, {name = name})
        local ok, err = pcall(func, {})
        if not ok then error(err) end
    end

    catalog.createVirtualCopies = catalog.createVirtualCopies or function(self)
        -- 返回虚拟副本列表（mock）
        return _G.__mock_catalog.virtualCopies or {}
    end

    catalog.adjustPhotoDevelopSettings = catalog.adjustPhotoDevelopSettings or function(self, photo, settings)
        -- 记录应用设置
        if photo then
            photo._developSettings = settings
        end
    end

    return catalog
end

-- 测试辅助：重置 catalog
function LrApplication._resetCatalog()
    _G.__mock_catalog = {
        photos = {},
        selectedPhotos = {},
        virtualCopies = {},
        writeAccessLog = {},
    }
end

return LrApplication
