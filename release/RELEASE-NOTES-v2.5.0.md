## NegativeCutter-135 v2.5.0

本版本发布 Lightroom Classic 插件。Standalone APP 不在本次附件范围内。

### 主要更新

- 新增 Lightroom 内实时裁切预览，四个像素偏移会在停止输入后刷新
- 新增逐张预览、整批统一和不预览三种识别流程
- 新增原生批次进度与取消；取消不会回滚已成功创建的虚拟副本
- 批量处理中单张检测失败不会阻止后续照片继续成功处理
- 零成功批次现在显示“失败”，混合成功/失败批次显示“部分完成”
- 加固预览渲染生命周期：请求串行化、原子指针更新、last-good 保留和拥有目录清理
- 两个识别对话框每次以自动检测/6 帧打开，画幅与帧数不跨对话框残留

### 系统要求

- macOS 11 或更高版本
- Apple Silicon（arm64）
- Adobe Lightroom Classic 10.0+
- 用户端不需要安装 Python 或额外依赖

### 安装

1. 下载并解压 `NegativeCutter-135-v2.5.0.zip`
2. 在解压目录运行顶层 `install.sh`
3. 重启 Lightroom Classic
4. 在“文件 → 增效工具管理器”确认 NegativeCutter 正在运行

### 发布附件

- `NegativeCutter-135-v2.5.0.zip`（Lightroom 插件）

本次发布不包含 Standalone ZIP，也不应上传 `marketing/`、`.claude/` 或仓库内的历史构建目录。
