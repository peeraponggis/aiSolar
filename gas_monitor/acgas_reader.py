# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

"""Read live values from the AcGasSynchro window.

AcGasSynchro draws its numbers as pixels (no text controls), so this module
captures the window with PrintWindow and reads the navy digits in the right
value panel by template matching. Read-only: it never talks to the ECU.
"""
import ctypes
import ctypes.wintypes as wt
import json
from pathlib import Path

from PIL import Image

EXE_NAME = 'acgassynchro.exe'
TEMPLATE_FILE = Path(__file__).with_name('acgas_digits.json')
GLYPH_ROWS = 14            # 12 digit rows + 2 rows for the comma tail
GRID_W, GRID_H = 8, 12

# name: (digit top y from window top, x0, x1 relative to the panel's right edge)
FIELDS = {
    'GAS_bar':  (65,  -48, 0),
    'MAP_bar':  (80,  -48, 0),
    **{f'P{i}': (127 + 16 * (i - 1), -118, -81) for i in range(1, 9)},
    **{f'L{i}': (127 + 16 * (i - 1), -40, 0) for i in range(1, 9)},
    'GAS_TEMP': (273, -40, 0),
    'RED_TEMP': (289, -40, 0),
    'LAMBDA1':  (320, -48, 0),
    'LAMBDA2':  (336, -48, 0),
    'BATT_V':   (352, -56, 0),
    'RPM':      (384, -56, 0),
}
STATUS_GAS = (0, 128, 0)
STATUS_PETROL = (0, 0, 255)


class NotFound(Exception):
    pass


class Minimized(Exception):
    pass


# ── window capture ───────────────────────────────────────────────────────────

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32
_kernel32 = ctypes.windll.kernel32


def _process_name(pid):
    h = _kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ''
    try:
        buf = ctypes.create_unicode_buffer(520)
        size = wt.DWORD(len(buf))
        if _kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return Path(buf.value).name.lower()
        return ''
    finally:
        _kernel32.CloseHandle(h)


def find_window():
    """Largest visible top-level window of AcGasSynchro, or None."""
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if _user32.IsWindowVisible(hwnd):
            pid = wt.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if _process_name(pid.value) == EXE_NAME:
                r = wt.RECT()
                _user32.GetWindowRect(hwnd, ctypes.byref(r))
                found.append(((r.right - r.left) * (r.bottom - r.top), hwnd))
        return True

    _user32.EnumWindows(cb, 0)
    found.sort(reverse=True)
    return found[0][1] if found and found[0][0] > 0 else None


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG),
                ('biPlanes', wt.WORD), ('biBitCount', wt.WORD), ('biCompression', wt.DWORD),
                ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', wt.LONG),
                ('biYPelsPerMeter', wt.LONG), ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD)]


def capture(hwnd=None):
    """PrintWindow capture of AcGasSynchro (works while covered, not while minimized)."""
    hwnd = hwnd or find_window()
    if not hwnd:
        raise NotFound('AcGasSynchro is not running')
    if _user32.IsIconic(hwnd):
        raise Minimized('AcGasSynchro is minimized')
    r = wt.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = _user32.GetWindowDC(hwnd)
    mdc = _gdi32.CreateCompatibleDC(hdc)
    bmp = _gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = _gdi32.SelectObject(mdc, bmp)
    try:
        _user32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT
        bih = _BITMAPINFOHEADER(ctypes.sizeof(_BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        _gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
        return Image.frombuffer('RGB', (w, h), buf, 'raw', 'BGRX', 0, 1)
    finally:
        _gdi32.SelectObject(mdc, old)
        _gdi32.DeleteObject(bmp)
        _gdi32.DeleteDC(mdc)
        _user32.ReleaseDC(hwnd, hdc)


# ── panel reading ────────────────────────────────────────────────────────────

def _core(c):
    r, g, b = c
    return 80 <= b <= 200 and r < 80 and g < 80 and b - r > 50


def _soft(c):
    if _core(c):
        return 255
    r, g, b = c
    return 128 if (b - r > 40 and b < 230) else 0


def find_panel(img):
    """Return (right_edge_x, fuel) from the status block, or None if not found."""
    px = img.load()
    w, h = img.size
    for y in range(h - 1, max(h - 200, 0), -1):
        for x in range(w - 1, max(w - 200, 0), -1):
            c = px[x, y]
            if c in (STATUS_GAS, STATUS_PETROL):
                # walk right to the block's edge on this row
                xr = x
                while xr + 1 < w and px[xr + 1, y] == c:
                    xr += 1
                return xr + 1, ('gas' if c == STATUS_GAS else 'petrol')
    return None


def _glyph_runs(img, y, x0, x1):
    px = img.load()
    cols = [sum(_core(px[x, y + dy]) for dy in range(GLYPH_ROWS)) for x in range(x0, x1)]
    runs, start = [], None
    for i, n in enumerate(cols + [0]):
        if n and start is None:
            start = i
        if not n and start is not None:
            runs.append((start, i)); start = None
    out = []
    for a, b in runs:
        out.extend(_split(cols, a, b))
    return [(x0 + a, x0 + b) for a, b in out]


def _split(cols, a, b, max_w=11):
    if b - a <= max_w:
        return [(a, b)]
    lo, hi = a + 5, b - 5
    cut = min(range(lo, hi), key=lambda i: cols[i])
    return _split(cols, a, cut, max_w) + _split(cols, cut + 1, b, max_w)


def _glyph_grid(img, y, a, b):
    px = img.load()
    g = Image.new('L', (b - a + 1, GRID_H))
    gp = g.load()
    for dx in range(b - a + 1):
        for dy in range(GRID_H):
            gp[dx, dy] = _soft(px[a + dx, y + dy])
    return list(g.resize((GRID_W, GRID_H), Image.BILINEAR).getdata())


def _is_comma(img, y, a, b):
    px = img.load()
    return b - a <= 4 and any(_core(px[x, y + dy]) for x in range(a, b) for dy in (12, 13))


def _load_templates():
    data = json.loads(TEMPLATE_FILE.read_text(encoding='utf-8'))
    return {ch: (v['grid'], v['width']) for ch, v in data.items()}


_TEMPLATES = None


def _classify(grid, width):
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = _load_templates()
    best, best_d = None, None
    for ch, (tg, tw) in _TEMPLATES.items():
        d = sum(abs(p - q) for p, q in zip(grid, tg)) + 60 * abs(width - tw)
        if best_d is None or d < best_d:
            best, best_d = ch, d
    return best


def read_text(img, y, x0, x1):
    chars = []
    for a, b in _glyph_runs(img, y, x0, x1):
        if _is_comma(img, y, a, b):
            chars.append(',')
        else:
            chars.append(_classify(_glyph_grid(img, y, a, b), b - a))
    return ''.join(chars)


def read_panel(img):
    """Read every field. Returns dict with floats (None if unreadable) plus 'fuel'."""
    anchor = find_panel(img)
    if not anchor:
        raise NotFound('value panel not visible')
    right, fuel = anchor
    right -= 1
    out = {'fuel': fuel}
    for name, (y, o0, o1) in FIELDS.items():
        text = read_text(img, y, right + o0, right + o1 + 1)
        try:
            out[name] = float(text.replace(',', '.')) if text else None
        except ValueError:
            out[name] = None
    return out


def to_params(raw):
    """Map raw panel values to GAS Monitor parameter keys and units."""
    def avg(prefix):
        vals = [raw.get(f'{prefix}{i}') for i in range(1, 7)]
        vals = [v for v in vals if v is not None and v > 0]
        return round(sum(vals) / len(vals), 2) if vals else 0.0
    out = {
        'GAS_kPa':  None if raw.get('GAS_bar') is None else round(raw['GAS_bar'] * 100, 1),
        'MAP_kPa':  None if raw.get('MAP_bar') is None else round(raw['MAP_bar'] * 100, 1),
        'RED_TEMP': raw.get('RED_TEMP'),
        'GAS_TEMP': raw.get('GAS_TEMP'),
        'RPM':      raw.get('RPM'),
        'INJ_ms':   avg('L'),
        'PET_ms':   avg('P'),
        'LAMBDA1':  raw.get('LAMBDA1'),
        'LAMBDA2':  raw.get('LAMBDA2'),
        'BATT_V':   raw.get('BATT_V'),
        'ON_GAS':   1.0 if raw.get('fuel') == 'gas' else 0.0,
    }
    return {k: v for k, v in out.items() if v is not None}


def read_live():
    """Capture AcGasSynchro and return (params, raw)."""
    raw = read_panel(capture())
    return to_params(raw), raw
