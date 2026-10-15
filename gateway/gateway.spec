# -*- mode: python ; coding: utf-8 -*-
# Build: python -m PyInstaller gateway.spec --noconfirm --distpath <tmp>\dist --workpath <tmp>\work
# Deploy to C:\Users\Lenovo\LungPeeAI by copying gateway.exe, _internal\base_library.zip and any
# _internal library files that changed. ui\, knowledge\ and model.md live only in the install's
# _internal folder (edited in place), so they are intentionally not bundled here.

a = Analysis(
    ['gateway.py'],
    pathex=['..'],               # clipgen.py lives in F:\LocalAI and is imported lazily by /api/clip
    hiddenimports=['clipgen'],
    excludes=['tkinter'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='gateway',
    console=True,
    icon=r'C:\Users\Lenovo\LungPeeAI\lungpee.ico',
)
coll = COLLECT(exe, a.binaries, a.datas, name='gateway')
