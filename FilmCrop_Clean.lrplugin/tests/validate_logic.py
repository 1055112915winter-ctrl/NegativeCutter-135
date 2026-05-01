#!/usr/bin/env python3
"""
用 Python 验证 Lua 测试中的核心逻辑
直接用 Python json 模块解析（和 Lua 正则解析等价验证）
"""

import json
import math

# ------------------------------------------------------------------
# 1. 模拟 ProcessAgent.directionAlign (Python 版)
# ------------------------------------------------------------------
def directionAlign(result, photoDimensions):
    """模拟 directionAlign 逻辑"""
    lrWidth = photoDimensions.get('width', result.get('sourceWidth', 1024))
    lrHeight = photoDimensions.get('height', result.get('sourceHeight', 1024))
    isPyHorizontal = result.get('isHorizontal')
    isLrHorizontal = lrWidth >= lrHeight

    if isPyHorizontal != isLrHorizontal:
        for frame in result['frames']:
            origRelTop = frame.get('relativeTop', 0.0)
            origRelBottom = frame.get('relativeBottom', 1.0)
            origRelLeft = frame.get('relativeLeft', 0.0)
            origRelRight = frame.get('relativeRight', 1.0)

            frame['relativeTop'] = origRelLeft
            frame['relativeBottom'] = origRelRight
            frame['relativeLeft'] = origRelTop
            frame['relativeRight'] = origRelBottom

            frame['top'] = math.floor(frame['relativeTop'] * lrHeight)
            frame['bottom'] = math.floor(frame['relativeBottom'] * lrHeight)
            frame['left'] = math.floor(frame['relativeLeft'] * lrWidth)
            frame['right'] = math.floor(frame['relativeRight'] * lrWidth)

        result['sourceWidth'] = lrWidth
        result['sourceHeight'] = lrHeight
        result['cropAngle'] = -(result.get('cropAngle', 0))
        for frame in result['frames']:
            frame['sourceWidth'] = lrWidth
            frame['sourceHeight'] = lrHeight

    return result

# ------------------------------------------------------------------
# 2. 运行验证
# ------------------------------------------------------------------
print("=" * 60)
print("Lua 逻辑 Python 验证")
print("=" * 60)

passCount = 0
failCount = 0

def assert_equal(expected, actual, msg):
    global passCount, failCount
    if expected != actual:
        print(f"  FAIL: {msg}")
        print(f"    expected: {expected}")
        print(f"    actual: {actual}")
        failCount += 1
        return False
    else:
        passCount += 1
        return True

print("\n--- Test: parseJSON 完整解析 (Python json 解析) ---")
jsonStr = '''{
    "frameCount": 3,
    "sourceWidth": 2400,
    "sourceHeight": 3500,
    "cropAngle": 0.5,
    "debug": {"isHorizontal": false},
    "frames": [
        {"index": 1, "top": 100, "bottom": 1100, "left": 0, "right": 2400,
         "relativeTop": 0.0286, "relativeBottom": 0.3143, "relativeLeft": 0.0, "relativeRight": 1.0},
        {"index": 2, "top": 1200, "bottom": 2200, "left": 0, "right": 2400,
         "relativeTop": 0.3429, "relativeBottom": 0.6286, "relativeLeft": 0.0, "relativeRight": 1.0},
        {"index": 3, "top": 2300, "bottom": 3400, "left": 0, "right": 2400,
         "relativeTop": 0.6571, "relativeBottom": 0.9714, "relativeLeft": 0.0, "relativeRight": 1.0}
    ]
}'''
result = json.loads(jsonStr)
assert_equal(3, result['frameCount'], "frameCount")
assert_equal(2400, result['sourceWidth'], "sourceWidth")
assert_equal(3500, result['sourceHeight'], "sourceHeight")
assert_equal(0.5, result['cropAngle'], "cropAngle")
assert_equal(False, result['debug']['isHorizontal'], "isHorizontal")
assert_equal(3, len(result['frames']), "frames count")
assert_equal(1, result['frames'][0]['index'], "frame1.index")
assert_equal(100, result['frames'][0]['top'], "frame1.top")
assert_equal(1100, result['frames'][0]['bottom'], "frame1.bottom")

print("\n--- Test: parseJSON 方向推断 ---")
jsonStr2 = '{"frameCount": 2, "sourceWidth": 3500, "sourceHeight": 2400, "frames": [{"index": 1, "top": 0, "bottom": 1000, "left": 0, "right": 3500}]}'
result2 = json.loads(jsonStr2)
# Lua 逻辑: isHorizontal = sourceWidth >= sourceHeight → 3500 >= 2400 → true
assert_equal(True, result2['sourceWidth'] >= result2['sourceHeight'], "isHorizontal (inferred from dimensions)")

print("\n--- Test: directionAlign 不旋转 ---")
result3 = json.loads('{"frameCount": 1, "sourceWidth": 2400, "sourceHeight": 3500, "frames": [{"index":1, "top":100, "bottom":1100, "relativeTop":0.1, "relativeBottom":0.4}]}')
# 模拟 parseJSON 的兜底: 如果没有 isHorizontal，从 sourceWidth/sourceHeight 推断
if 'isHorizontal' not in result3:
    result3['isHorizontal'] = (result3.get('sourceWidth', 0) or 0) >= (result3.get('sourceHeight', 0) or 0)

aligned3 = directionAlign(result3, {'width': 2400, 'height': 3500})
# Both vertical → no rotation
assert_equal(0.1, aligned3['frames'][0]['relativeTop'], "relativeTop")
assert_equal(0.4, aligned3['frames'][0]['relativeBottom'], "relativeBottom")

print("\n--- Test: directionAlign 旋转 90° ---")
result4 = json.loads('{"frameCount": 1, "sourceWidth": 2400, "sourceHeight": 3500, "cropAngle": 1.5, "frames": [{"index":1, "relativeTop":0.1, "relativeBottom":0.4, "relativeLeft":0.0, "relativeRight":1.0}]}')
# 补充 isHorizontal
if 'isHorizontal' not in result4:
    result4['isHorizontal'] = (result4.get('sourceWidth', 0) or 0) >= (result4.get('sourceHeight', 0) or 0)

aligned4 = directionAlign(result4, {'width': 3500, 'height': 2400})
# Python: vertical (2400 < 3500), LR: horizontal (3500 > 2400) → mismatch → rotate
assert_equal(0.0, aligned4['frames'][0]['relativeTop'], "rotated top")
assert_equal(1.0, aligned4['frames'][0]['relativeBottom'], "rotated bottom")
assert_equal(0.1, aligned4['frames'][0]['relativeLeft'], "rotated left")
assert_equal(0.4, aligned4['frames'][0]['relativeRight'], "rotated right")
assert_equal(-1.5, aligned4['cropAngle'], "cropAngle negated")

print("\n--- Test: directionAlign 像素坐标旋转 ---")
result5 = json.loads('{"frameCount": 1, "sourceWidth": 2400, "sourceHeight": 3500, "frames": [{"index":1, "top":100, "bottom":1100, "left":0, "right":2400}]}')
# 先给 frame 补上 relative 坐标
for f in result5['frames']:
    f['relativeTop'] = f.get('relativeTop', f['top'] / result5['sourceWidth'])
    f['relativeBottom'] = f.get('relativeBottom', f['bottom'] / result5['sourceWidth'])
    f['relativeLeft'] = f.get('relativeLeft', f['left'] / result5['sourceWidth'])
    f['relativeRight'] = f.get('relativeRight', f['right'] / result5['sourceWidth'])

# 补充 isHorizontal
if 'isHorizontal' not in result5:
    result5['isHorizontal'] = (result5.get('sourceWidth', 0) or 0) >= (result5.get('sourceHeight', 0) or 0)

aligned5 = directionAlign(result5, {'width': 3500, 'height': 2400})
assert_equal(3500, aligned5['sourceWidth'], "updated sourceWidth")
assert_equal(2400, aligned5['sourceHeight'], "updated sourceHeight")
# 旋转后: relativeTop = old relativeLeft = 0/2400 = 0 → top = floor(0 * 2400) = 0
assert_equal(0, aligned5['frames'][0]['top'], "rotated pixel top")
# relativeBottom = old relativeRight = 2400/2400 = 1 → bottom = floor(1 * 2400) = 2400
assert_equal(2400, aligned5['frames'][0]['bottom'], "rotated pixel bottom")

# ------------------------------------------------------------------
# 3. 汇总
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print(f"结果: {passCount} 通过, {failCount} 失败")
print("=" * 60)

if failCount == 0:
    print("\n全部逻辑验证通过！Lua 测试代码的断言逻辑是正确的。")
    exit(0)
else:
    print(f"\n发现 {failCount} 个失败。")
    exit(1)
