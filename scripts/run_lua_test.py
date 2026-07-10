#!/usr/bin/env python3
"""Run a standalone Lua test with a bundled system LuaJIT library."""

import ctypes
from pathlib import Path
import sys


LIBRARIES = (
    Path("/Applications/IINA.app/Contents/Frameworks/libluajit-5.1.2.dylib"),
    Path("/Applications/OBS.app/Contents/Frameworks/libluajit-5.1.2.dylib"),
    Path("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/libluajit-5.1.2.dylib"),
)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run_lua_test.py TEST.lua", file=sys.stderr)
        return 2
    script = Path(sys.argv[1]).resolve()
    library_path = next((path for path in LIBRARIES if path.is_file()), None)
    if library_path is None:
        print("no supported LuaJIT library found", file=sys.stderr)
        return 1

    lib = ctypes.CDLL(str(library_path))
    lib.luaL_newstate.restype = ctypes.c_void_p
    lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
    lib.luaL_loadfile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.luaL_loadfile.restype = ctypes.c_int
    lib.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.lua_pcall.restype = ctypes.c_int
    lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    lib.lua_tolstring.restype = ctypes.c_char_p
    lib.lua_close.argtypes = [ctypes.c_void_p]

    state = lib.luaL_newstate()
    if not state:
        print("luaL_newstate failed", file=sys.stderr)
        return 1
    try:
        lib.luaL_openlibs(state)
        status = lib.luaL_loadfile(state, str(script).encode())
        if status == 0:
            status = lib.lua_pcall(state, 0, -1, 0)
        if status != 0:
            raw = lib.lua_tolstring(state, -1, None)
            print(raw.decode(errors="replace") if raw else f"Lua error {status}", file=sys.stderr)
            return 1
    finally:
        lib.lua_close(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
