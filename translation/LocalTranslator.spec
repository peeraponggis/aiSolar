# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['make_icon']
tmp_ret = collect_all('edge_tts')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
# ถอดเสียงถามด้วยเสียง (voice_input.py): av/onnxruntime/sounddevice มี hook สำเร็จรูปจาก
# pyinstaller-hooks-contrib อยู่แล้ว (เก็บเฉพาะ binary ที่จำเป็นจริง ไม่ลาก submodule ที่ไม่ใช้
# เช่น onnxruntime.transformers ซึ่งพ่วง pandas/matplotlib มาด้วยถ้าใช้ collect_all) จึงปล่อยให้
# PyInstaller ตรวจจับอัตโนมัติ เหลือแค่ 2 ตัวที่ต้อง collect_all เอง: ctranslate2 (ไม่มี hook เลย)
# และ faster_whisper (มีไฟล์โมเดล VAD assets/silero_vad_v6.onnx เป็น package data ที่ auto-detect
# ธรรมดาของ PyInstaller มองไม่เห็น - ขาดไฟล์นี้แล้วจะ error ตอนกดปุ่มพูดถามจริง)
for pkg in ('ctranslate2', 'faster_whisper'):
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
# ctranslate2.converters (แปลงโมเดล ไม่ได้ใช้ตอนถอดเสียง) import transformers/torch - ถ้าเครื่องที่ build
# มีสองตัวนี้ติดตั้งอยู่ exe จะบวมจาก ~31 MB เป็น ~100 MB และมีไฟล์เพิ่ม ~5,000 ไฟล์
hiddenimports = [h for h in hiddenimports if not h.startswith('ctranslate2.converters')]
HEAVY_UNUSED = ['torch', 'torchvision', 'torchaudio', 'transformers', 'accelerate', 'sklearn',
                'tensorflow', 'keras', 'jax', 'datasets', 'safetensors', 'sentencepiece']


a = Analysis(
    ['translator.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['scripts'] + HEAVY_UNUSED,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LocalTranslator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['translator.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LocalTranslator',
)
