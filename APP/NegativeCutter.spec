# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for NegativeCutter standalone GUI
# Build: pyinstaller NegativeCutter.spec --clean

import os
import sys
from pathlib import Path

# The spec file is executed via exec(), so __file__ is unreliable.
# Use sys.argv[0] which PyInstaller sets to the spec path.
spec_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
app_dir = spec_dir
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Use only the canonical icon generated beside this spec. Never fall back to
# another worktree, where a stale brand asset could be selected silently.
_icon_path = os.path.join(app_dir, 'NegativeCutter.icns')
if not os.path.isfile(_icon_path):
    raise FileNotFoundError(
        f'Missing application icon: {_icon_path}. Run generate_icns.py first.'
    )

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[app_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        # filmcrop package (copied into this app)
        'filmcrop',
        'filmcrop.detector',
        'filmcrop.export',
        'filmcrop.api',
        # GUI modules
        'filmcrop.gui',
        'filmcrop.gui.main_window',
        'filmcrop.gui.image_view',
        'filmcrop.gui.frame_item',
        'filmcrop.gui.export_dialog',
        'filmcrop.gui.theme',
        'filmcrop.gui.style_sheet',
        'filmcrop.gui.logo',
        # PyQt6
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        'PyQt6.QtDBus',
        # rawpy + LibRaw for DNG decoding
        'rawpy',
        # PIL image plugins (lazy-loaded, must be explicit for PyInstaller)
        'PIL.TiffImagePlugin',
        'PIL.JpegImagePlugin',
        'PIL.PngImagePlugin',
        'PIL.BmpImagePlugin',
        'PIL.GifImagePlugin',
        'PIL.WebPImagePlugin',
        'PIL.PpmImagePlugin',
        'PIL.PcxImagePlugin',
        'PIL.MpoImagePlugin',
        'PIL.IcnsImagePlugin',
        'PIL.IcoImagePlugin',
        'PIL.FliImagePlugin',
        'PIL.FpxImagePlugin',
        'PIL.FtexImagePlugin',
        'PIL.GbrImagePlugin',
        'PIL.ImImagePlugin',
        'PIL.ImtImagePlugin',
        'PIL.IptcImagePlugin',
        'PIL.McIdasImagePlugin',
        'PIL.MicImagePlugin',
        'PIL.MpegImagePlugin',
        'PIL.PalmImagePlugin',
        'PIL.PdfImagePlugin',
        'PIL.PixarImagePlugin',
        'PIL.PsdImagePlugin',
        'PIL.SgiImagePlugin',
        'PIL.SpiderImagePlugin',
        'PIL.SunImagePlugin',
        'PIL.TgaImagePlugin',
        'PIL.WalImageFile',
        'PIL.XbmImagePlugin',
        'PIL.XpmImagePlugin',
        'PIL.XVThumbImagePlugin',
        'PIL.DdsImagePlugin',
        'PIL.EpsImagePlugin',
        'PIL.FitsImagePlugin',
        'PIL.Hdf5StubImagePlugin',
        'PIL.BufrStubImagePlugin',
        'PIL.GribStubImagePlugin',
        'PIL.WmfImagePlugin',
        'PIL.TiffTags',
        # numpy submodules commonly needed at runtime
        'numpy.core._dtype_ctypes',
        'numpy.core._multiarray_umath',
        'numpy.core.arrayprint',
        'numpy.core.defchararray',
        'numpy.core.einsumfunc',
        'numpy.core.fromnumeric',
        'numpy.core.function_base',
        'numpy.core.getlimits',
        'numpy.core.multiarray',
        'numpy.core.numeric',
        'numpy.core.numerictypes',
        'numpy.core.overrides',
        'numpy.core.records',
        'numpy.core.shape_base',
        'numpy.core.umath',
        'numpy.lib.format',
        'numpy.lib.mixins',
        'numpy.lib.npyio',
        'numpy.lib.scimath',
        'numpy.lib.stride_tricks',
        'numpy.lib.user_array',
        'numpy.linalg.lapack_lite',
        'numpy.linalg._umath_linalg',
        'numpy.random._common',
        'numpy.random._bounded_integers',
        'numpy.random._generator',
        'numpy.random._mt19937',
        'numpy.random._pcg64',
        'numpy.random._philox',
        'numpy.random._sfc64',
        'numpy.random.bit_generator',
        'numpy.random.mtrand',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy optional packages to keep binary smaller
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'PyQt5',
        'PySide2',
        'PySide6',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'unittest',
        'pydoc',
        'doctest',
        'optparse',
        'calendar',
        'ftplib',
        'smtplib',
        'xmlrpc',
        'idlelib',
        'setuptools',
        'pydantic',
        'pydantic_core',
        'packaging',
        'yaml',
        'charset_normalizer',
        'defusedxml',
        'typing_extensions',
        'typing_inspection',
        'annotated_types',
        'mypy',
        'mypy_extensions',
        'altgraph',
        'macholib',
        'playwright',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Target architecture: default to current machine, or override via PYI_TARGET_ARCH env var.
_target_arch = os.environ.get('PYI_TARGET_ARCH', None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NegativeCutter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=_target_arch,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='_internal',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NegativeCutter',
)

app = BUNDLE(
    coll,
    name='NegativeCutter.app',
    icon=_icon_path,
    bundle_identifier='io.negativecutter.app',
    info_plist={
        'CFBundleName': 'NegativeCutter',
        'CFBundleDisplayName': 'NegativeCutter',
        'CFBundleShortVersionString': '2.4.5',
        'CFBundleVersion': '2.4.5',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
    },
)
