# FilmCrop Lightroom 插件（精简版）指令

## 工具索引

| 系统 | 触发条件 | 调用入口 |
|------|----------|----------|
| **FilmCrop 插件（精简版）** | Lightroom 胶片裁切插件 | 本插件目录 |

## 注意事项

- 这是清理/精简版插件包，功能与完整版一致，体积更小。
- 部署至 Lightroom 插件目录使用。

## Codebase Patterns

- **Menu items are defined in `Info.lua`**, not in the individual script files. `DetectFrames.lua`, `ImportXMP.lua`, etc. contain only the execution logic.
- **No native directory listing in Lightroom SDK.** `LrFileUtils` does not have `filesInDirectory` or `directoryFiles` in standard SDK versions. Use a Python temp script + `LrTasks.execute()` as a cross-platform fallback.
- **Virtual copy duplicate detection:** scan `catalog:getAllPhotos()`, filter by `photo:getRawMetadata("path")`, and index by `photo:getFormattedMetadata("copyName")`. This allows checking if a copy like `baseName_帧01` already exists before creating a new one.
- **Backward-compatible function signature changes:** when adding optional return values to existing functions (e.g., `createVirtualCopiesFromFrames`), keep the original return order `(created, errors, ...)` so callers capturing only two variables continue to work.
- **XMP sidecar format:** `.filmcrop.xmp` files use a custom `filmcrop:` namespace inside `<rdf:li><rdf:Description .../></rdf:li>` elements. The Lua parser uses `gmatch("<rdf:li>(.-)</rdf:li>")` and `gmatch("filmcrop:(%w+)=%"([^%"]+)%")` to extract frame coordinates.
- **Develop module check before detection:** `applyDevelopSettings` only works in the Develop module (`currentModule == "develop"`). Always check `LrApplicationView.getCurrentModuleName()` before creating virtual copies or applying crops, and show a warning dialog if the user is in Library or another module.
- **Direction alignment for HTTP API results:** The standalone detector returns coordinates based on actual pixel dimensions, but Lightroom may interpret EXIF orientation differently. Always call `ProcessAgent.directionAlign(result, photo)` on API results before creating virtual copies, just like `DetectFrames.lua` does for local detection.
- **Progress bar for long operations:** Use `LrProgressScope` inside async tasks to show progress during multi-photo operations. Create with `LrProgressScope({ title = "...", caption = "..." })`, update via `setPortionComplete(done, total)` and `setCaption("...")`, and check `isCanceled()` to allow the user to abort. Always call `done()` when finished.
- **HTTP API requests use LuaSocket:** `socket.http` + `ltn12` is the most reliable way to POST JSON with a body in Lightroom Lua. Guard the entire request in `pcall` and capture the second return value (`httpErr`) to report meaningful error messages instead of silent failures.
- **JSON file watch mode uses plugin prefs for stop signaling:** Store `prefs.watchActive` and `prefs.watchJsonPath` to track polling state. The background task checks `prefs.watchActive` in its `while` loop condition. A separate "Stop Watching" menu item sets `prefs.watchActive = false` to terminate polling gracefully. Always clear these prefs in `Shutdown.lua` to avoid stale state on plugin reload.
- **`LrDialogs.confirm` for three-button dialogs:** Use `LrDialogs.confirm(title, message, actionButton, cancelButton, otherButton)` where returns are `"ok"`, `"cancel"`, or `"other"`. This is simpler than `presentModalDialog` for yes/no/skip or stop/restart/cancel workflows.
- **Direction alignment for JSON watch results:** Just like HTTP API results, JSON sidecar coordinates are based on raw pixel dimensions. Always call `ProcessAgent.directionAlign(data, photo)` before creating virtual copies from external JSON files.
- **Use `json.decode` instead of regex for JSON parsing:** The Lightroom SDK provides `require("json")` with a `decode()` function. Prefer it over fragile Lua regex patterns for parsing `.filmcrop.json` sidecars.
