#!/usr/bin/env python3
"""
Four-way EXIF orientation mapping — isolated unit test (Python port)
Validates directionAlign rotation formulas for AB/BC/CD/DA orientations.

Since lua is not installed in this environment, this Python port verifies
the exact same math that the Lua four-way mapper would use.

Usage: python3 tests/test_direction_align_fourway.py
"""

import sys

pass_count = 0
fail_count = 0


def assert_eq(expected, actual, msg="", eps=1e-9):
    if isinstance(expected, tuple):
        if len(expected) != len(actual):
            raise AssertionError(
                f"{msg}: tuple length mismatch {len(expected)} vs {len(actual)}"
            )
        for i, (e, a) in enumerate(zip(expected, actual)):
            assert_eq(e, a, f"{msg}[{i}]", eps)
        return
    if abs(expected - actual) > eps:
        raise AssertionError(
            f"{msg}: expected {expected!r}, got {actual!r}"
        )


def run_test(name, fn):
    global pass_count, fail_count
    print(f"  {name} ... ", end="")
    try:
        fn()
        print("PASS")
        pass_count += 1
    except Exception as e:
        print(f"FAIL\n    {e}")
        fail_count += 1


# ------------------------------------------------------------------
# Stecman-derived formulas (relative coords 0-1, AB = normal)
# ------------------------------------------------------------------
def rotate_bc(t, b, l, r):
    """90 deg CW: (t,b,l,r) -> (1-r, 1-l, t, b)"""
    return 1.0 - r, 1.0 - l, t, b


def rotate_cd(t, b, l, r):
    """180 deg: (t,b,l,r) -> (1-b, 1-t, 1-r, 1-l)"""
    return 1.0 - b, 1.0 - t, 1.0 - r, 1.0 - l


def rotate_da(t, b, l, r):
    """270 deg CW / 90 deg CCW: (t,b,l,r) -> (l, r, 1-b, 1-t)"""
    return l, r, 1.0 - b, 1.0 - t


print("\n--- Test Suite: rotation formula group axioms ---")


def test_bc_roundtrip():
    t, b, l, r = 0.1, 0.4, 0.2, 0.8
    t1, b1, l1, r1 = rotate_bc(t, b, l, r)
    t2, b2, l2, r2 = rotate_bc(t1, b1, l1, r1)
    t3, b3, l3, r3 = rotate_bc(t2, b2, l2, r2)
    t4, b4, l4, r4 = rotate_bc(t3, b3, l3, r3)
    assert_eq(t, t4, "top")
    assert_eq(b, b4, "bottom")
    assert_eq(l, l4, "left")
    assert_eq(r, r4, "right")


def test_cd_roundtrip():
    t, b, l, r = 0.1, 0.4, 0.2, 0.8
    t1, b1, l1, r1 = rotate_cd(t, b, l, r)
    t2, b2, l2, r2 = rotate_cd(t1, b1, l1, r1)
    assert_eq(t, t2, "top")
    assert_eq(b, b2, "bottom")
    assert_eq(l, l2, "left")
    assert_eq(r, r2, "right")


def test_da_roundtrip():
    t, b, l, r = 0.1, 0.4, 0.2, 0.8
    t1, b1, l1, r1 = rotate_da(t, b, l, r)
    t2, b2, l2, r2 = rotate_da(t1, b1, l1, r1)
    t3, b3, l3, r3 = rotate_da(t2, b2, l2, r2)
    t4, b4, l4, r4 = rotate_da(t3, b3, l3, r3)
    assert_eq(t, t4, "top")
    assert_eq(b, b4, "bottom")
    assert_eq(l, l4, "left")
    assert_eq(r, r4, "right")


def test_bc_bc_equals_cd():
    t, b, l, r = 0.1, 0.4, 0.2, 0.8
    bc_bc = rotate_bc(*rotate_bc(t, b, l, r))
    cd = rotate_cd(t, b, l, r)
    assert_eq(cd, bc_bc, "combined")


def test_bc_cd_equals_da():
    t, b, l, r = 0.1, 0.4, 0.2, 0.8
    bc_cd = rotate_bc(*rotate_cd(t, b, l, r))
    da = rotate_da(t, b, l, r)
    assert_eq(da, bc_cd, "combined")


def test_cd_bc_equals_da():
    t, b, l, r = 0.1, 0.4, 0.2, 0.8
    cd_bc = rotate_cd(*rotate_bc(t, b, l, r))
    da = rotate_da(t, b, l, r)
    assert_eq(da, cd_bc, "combined")


print("\n--- Test Suite: geometric sanity checks ---")


def test_bc_centred_square():
    t, b, l, r = 0.1, 0.9, 0.2, 0.8
    nt, nb, nl, nr = rotate_bc(t, b, l, r)
    assert_eq(0.2, nt, "top")
    assert_eq(0.8, nb, "bottom")
    assert_eq(0.1, nl, "left")
    assert_eq(0.9, nr, "right")


def test_cd_centred_square():
    t, b, l, r = 0.1, 0.9, 0.2, 0.8
    nt, nb, nl, nr = rotate_cd(t, b, l, r)
    assert_eq(0.1, nt, "top")
    assert_eq(0.9, nb, "bottom")
    assert_eq(0.2, nl, "left")
    assert_eq(0.8, nr, "right")


def test_da_centred_square():
    t, b, l, r = 0.1, 0.9, 0.2, 0.8
    nt, nb, nl, nr = rotate_da(t, b, l, r)
    assert_eq(0.2, nt, "top")
    assert_eq(0.8, nb, "bottom")
    assert_eq(0.1, nl, "left")
    assert_eq(0.9, nr, "right")


def test_bc_preserves_aspect_ratio():
    t, b, l, r = 0.1, 0.5, 0.0, 1.0
    nt, nb, nl, nr = rotate_bc(t, b, l, r)
    orig_w = r - l
    orig_h = b - t
    new_w = nr - nl
    new_h = nb - nt
    assert_eq(orig_w, new_h, "width -> height")
    assert_eq(orig_h, new_w, "height -> width")


def test_da_preserves_aspect_ratio():
    t, b, l, r = 0.1, 0.5, 0.0, 1.0
    nt, nb, nl, nr = rotate_da(t, b, l, r)
    orig_w = r - l
    orig_h = b - t
    new_w = nr - nl
    new_h = nb - nt
    assert_eq(orig_w, new_h, "width -> height")
    assert_eq(orig_h, new_w, "height -> width")


print("\n--- Test Suite: edge cases ---")


def test_full_frame_bc():
    t, b, l, r = 0.0, 1.0, 0.0, 1.0
    nt, nb, nl, nr = rotate_bc(t, b, l, r)
    assert_eq(0.0, nt, "top")
    assert_eq(1.0, nb, "bottom")
    assert_eq(0.0, nl, "left")
    assert_eq(1.0, nr, "right")


def test_degenerate_width_bc():
    t, b, l, r = 0.1, 0.3, 0.3, 0.3
    nt, nb, nl, nr = rotate_bc(t, b, l, r)
    assert_eq(0.7, nt, "top")
    assert_eq(0.7, nb, "bottom")
    assert_eq(0.1, nl, "left")
    assert_eq(0.3, nr, "right")


# Run all tests
run_test("BC round-trip (4x = identity)", test_bc_roundtrip)
run_test("CD round-trip (2x = identity)", test_cd_roundtrip)
run_test("DA round-trip (4x = identity)", test_da_roundtrip)
run_test("BC + BC == CD", test_bc_bc_equals_cd)
run_test("BC + CD == DA", test_bc_cd_equals_da)
run_test("CD + BC == DA", test_cd_bc_equals_da)
run_test("BC on centred square frame", test_bc_centred_square)
run_test("CD on centred square frame", test_cd_centred_square)
run_test("DA on centred square frame", test_da_centred_square)
run_test("Full-strip frame BC preserves aspect ratio", test_bc_preserves_aspect_ratio)
run_test("Full-strip frame DA preserves aspect ratio", test_da_preserves_aspect_ratio)
run_test("Zero-margin frame BC", test_full_frame_bc)
run_test("Degenerate-width frame BC", test_degenerate_width_bc)

print("\n" + "-" * 62)
print(f"结果: {pass_count} 通过, {fail_count} 失败")
print("-" * 62)

if fail_count > 0:
    sys.exit(1)
else:
    print("\n全部测试通过!")
