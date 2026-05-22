#!/usr/bin/env python3
"""
Mock SDK 架构验证脚本
用 Python 模拟 Lua 加载流程，检查语法和引用问题
"""

import os
import re
import sys

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(PLUGIN_DIR, "tests")
MOCK_SDK_DIR = os.path.join(TESTS_DIR, "mock_sdk")

errors = []
warnings = []

# ------------------------------------------------------------------
# 1. 检查文件存在性
# ------------------------------------------------------------------
print("=" * 60)
print("1. 检查文件存在性")
print("=" * 60)

required_files = [
    "run_tests.lua",
    "mock_sdk/init.lua",
    "mock_sdk/LrApplication.lua",
    "mock_sdk/LrApplicationView.lua",
    "mock_sdk/LrDialogs.lua",
    "mock_sdk/LrFileUtils.lua",
    "mock_sdk/LrLogger.lua",
    "mock_sdk/LrPathUtils.lua",
    "mock_sdk/LrPhoto.lua",
    "mock_sdk/LrPrefs.lua",
    "mock_sdk/LrTasks.lua",
]

for f in required_files:
    path = os.path.join(TESTS_DIR, f)
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"  [OK] {f} ({size} bytes)")
    else:
        errors.append(f"缺少文件: {f}")
        print(f"  [FAIL] {f} 不存在")

# ------------------------------------------------------------------
# 2. 基本 Lua 语法检查（括号匹配、引号匹配）
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("2. 基本 Lua 语法检查")
print("=" * 60)

def check_lua_syntax(filepath):
    """检查 Lua 文件的括号/引号匹配"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    issues = []

    # 跟踪括号
    stack = []
    line_no = 0
    in_string = None  # nil, '"', "'", '[', '='
    string_start_line = 0

    for line in lines:
        line_no += 1
        i = 0
        while i < len(line):
            ch = line[i]

            # 跳过注释
            if not in_string:
                if ch == '-' and i + 1 < len(line) and line[i+1] == '-':
                    break  # 单行注释，跳过剩余部分

            # 字符串处理
            if not in_string:
                if ch == '"' or ch == "'":
                    in_string = ch
                    string_start_line = line_no
                elif ch == '[':
                    # 检查长字符串/注释 [[ ... ]]
                    j = i + 1
                    eq_count = 0
                    while j < len(line) and line[j] == '=':
                        eq_count += 1
                        j += 1
                    if j < len(line) and line[j] == '[':
                        in_string = ('[', eq_count)
                        string_start_line = line_no
                        i = j
                elif ch in '({[':
                    stack.append((ch, line_no))
                elif ch == ')':
                    if not stack or stack[-1][0] != '(':
                        issues.append(f"  第 {line_no} 行: 多余的 ')'")
                    else:
                        stack.pop()
                elif ch == '}':
                    if not stack or stack[-1][0] != '{':
                        issues.append(f"  第 {line_no} 行: 多余的 '}}'")
                    else:
                        stack.pop()
                elif ch == ']':
                    if not stack or stack[-1][0] != '[':
                        # 可能是长字符串结束，先不报错
                        pass
                    else:
                        stack.pop()
            else:
                # 在字符串内
                if in_string == '"' or in_string == "'":
                    if ch == in_string:
                        # 检查是否转义
                        backslash_count = 0
                        j = i - 1
                        while j >= 0 and line[j] == '\\':
                            backslash_count += 1
                            j -= 1
                        if backslash_count % 2 == 0:
                            in_string = None
                elif isinstance(in_string, tuple) and in_string[0] == '[':
                    # 长字符串
                    if ch == ']':
                        j = i + 1
                        eq_count = 0
                        while j < len(line) and line[j] == '=':
                            eq_count += 1
                            j += 1
                        if j < len(line) and line[j] == ']' and eq_count == in_string[1]:
                            in_string = None
                            i = j

            i += 1

    if in_string:
        issues.append(f"  第 {string_start_line} 行: 字符串未闭合")

    if stack:
        for ch, ln in stack:
            issues.append(f"  第 {ln} 行: '{ch}' 未闭合")

    return issues

lua_files = []
for root, dirs, files in os.walk(TESTS_DIR):
    for f in files:
        if f.endswith('.lua'):
            lua_files.append(os.path.join(root, f))

for filepath in sorted(lua_files):
    rel = os.path.relpath(filepath, TESTS_DIR)
    issues = check_lua_syntax(filepath)
    if issues:
        print(f"\n  [FAIL] {rel}")
        for issue in issues:
            print(issue)
        errors.append(f"语法问题: {rel}")
    else:
        print(f"  [OK] {rel}")

# ------------------------------------------------------------------
# 3. 检查 import 引用完整性
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("3. 检查 import 引用完整性")
print("=" * 60)

# 收集所有 mock SDK 模块
mock_modules = set()
for f in os.listdir(MOCK_SDK_DIR):
    if f.endswith('.lua'):
        mod = f[:-4]  # 去掉 .lua
        mock_modules.add(mod)

print(f"  已实现的 mock 模块: {', '.join(sorted(mock_modules))}")

# 扫描插件代码中 import 了哪些模块
plugin_imports = set()
for root, dirs, files in os.walk(PLUGIN_DIR):
    # 跳过 tests 目录
    if 'tests' in root:
        continue
    for f in files:
        if f.endswith('.lua'):
            filepath = os.path.join(root, f)
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()
            # 匹配 import 'LrModuleName'
            imports = re.findall(r"import\s+'(Lr\w+)'", content)
            for imp in imports:
                plugin_imports.add(imp)

print(f"\n  插件代码 import 的模块:")
for imp in sorted(plugin_imports):
    status = "[OK]" if imp in mock_modules else "[MISSING - 测试中可能需要补充]"
    print(f"    {status} {imp}")
    if imp not in mock_modules:
        warnings.append(f"mock SDK 未实现: {imp}")

# ------------------------------------------------------------------
# 4. 模拟加载流程
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("4. 模拟加载流程")
print("=" * 60)

# 检查 run_tests.lua 中加载的模块路径
run_tests_path = os.path.join(TESTS_DIR, "run_tests.lua")
with open(run_tests_path, 'r') as f:
    run_tests_content = f.read()

# 检查 ProcessAgent.lua 路径
pa_path = os.path.join(PLUGIN_DIR, "ProcessAgent.lua")
if os.path.exists(pa_path):
    print(f"  [OK] ProcessAgent.lua 存在 ({os.path.getsize(pa_path)} bytes)")
else:
    errors.append("ProcessAgent.lua 不存在")
    print(f"  [FAIL] ProcessAgent.lua 不存在")

# 检查 run_tests.lua 是否能正确引用
# package.path 设置
if "mock_sdk/?.lua" in run_tests_content:
    print("  [OK] package.path 包含 mock_sdk")
else:
    errors.append("package.path 未包含 mock_sdk")
    print("  [FAIL] package.path 未包含 mock_sdk")

# 检查 _PLUGIN.path 设置
if "_PLUGIN.path" in run_tests_content:
    print("  [OK] _PLUGIN.path 已 mock")
else:
    errors.append("_PLUGIN.path 未 mock")
    print("  [FAIL] _PLUGIN.path 未 mock")

# 检查 import 函数
if "function import" in run_tests_content or "_G.import" in run_tests_content or "setupImport" in run_tests_content:
    print("  [OK] import() 函数已定义")
else:
    errors.append("import() 函数未定义")
    print("  [FAIL] import() 函数未定义")

# ------------------------------------------------------------------
# 5. 检查 ProcessAgent.lua 中的依赖
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("5. 分析 ProcessAgent.lua 依赖")
print("=" * 60)

with open(pa_path, 'r') as f:
    pa_content = f.read()

# 检查 dofile 引用
dofile_refs = re.findall(r'dofile\(([^)]+)\)', pa_content)
print(f"  dofile 引用:")
for ref in dofile_refs:
    ref_clean = ref.strip().strip('"').strip("'")
    if "ThumbnailAgent" in ref_clean:
        print(f"    [STUBBED] ThumbnailAgent (测试中 stub)")
    elif "ApplierAgent" in ref_clean:
        print(f"    [STUBBED] ApplierAgent (测试中 stub)")
    else:
        print(f"    [WARN] {ref_clean}")
        warnings.append(f"未处理的 dofile: {ref_clean}")

# 检查 _PLUGIN.path 使用
if "_PLUGIN.path" in pa_content:
    print(f"  [OK] ProcessAgent 使用 _PLUGIN.path")

# 检查 io.open 使用（用于读取 Python 输出）
if "io.open" in pa_content:
    print(f"  [OK] ProcessAgent 使用 io.open (标准 Lua API，无需 mock)")

# 检查 math.random
if "math.random" in pa_content:
    print(f"  [OK] ProcessAgent 使用 math.random (标准 Lua API)")

# ------------------------------------------------------------------
# 6. 汇总
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("6. 验证汇总")
print("=" * 60)

if errors:
    print(f"\n  错误 ({len(errors)}):")
    for e in errors:
        print(f"    - {e}")

if warnings:
    print(f"\n  警告 ({len(warnings)}):")
    for w in warnings:
        print(f"    - {w}")

if not errors and not warnings:
    print("\n  全部检查通过！Mock SDK 架构看起来正确。")
    print("\n  运行测试:")
    print(f"    cd {TESTS_DIR}")
    print("    lua run_tests.lua")
    sys.exit(0)
elif not errors:
    print(f"\n  有 {len(warnings)} 个警告，但没有致命错误。")
    print("  Mock SDK 可以运行，但某些测试可能需要补充 mock。")
    sys.exit(0)
else:
    print(f"\n  发现 {len(errors)} 个错误，需要修复。")
    sys.exit(1)
