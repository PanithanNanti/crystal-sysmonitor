#!/usr/bin/env python3
"""
CRYSTAL System Monitor — Ultra-transparent glassmorphism
No title bar. Content floats directly on real Windows acrylic blur.

  Drag   : click-and-drag anywhere on widget
  Resize : drag bottom-right corner
  Close  : click ✕ top-right
"""

import tkinter as tk
import psutil, time, threading, queue, math, datetime, ctypes
from ctypes import windll, Structure, POINTER, c_uint, pointer

try:
    import pythoncom, wmi as _wmi
    WMI_OK = True
except ImportError:
    WMI_OK = False


# ─── DWM Acrylic Blur ─────────────────────────────────────────────────────────
class ACCENTPOLICY(Structure):
    _fields_ = [('AccentState',   c_uint),
                ('AccentFlags',   c_uint),
                ('GradientColor', c_uint),   # AABBGGRR
                ('AnimationId',   c_uint)]

class WINCOMPATTRDATA(Structure):
    _fields_ = [('Attribute',   c_uint),
                ('Data',        POINTER(ACCENTPOLICY)),
                ('SizeOfData',  c_uint)]

def _apply_acrylic(hwnd: int, tint: int = 0x10FFFFFF) -> bool:
    try:
        ap = ACCENTPOLICY()
        ap.AccentState   = 4        # ACCENT_ENABLE_ACRYLICBLURBEHIND
        ap.AccentFlags   = 2
        ap.GradientColor = tint     # very low alpha = very transparent
        wd = WINCOMPATTRDATA()
        wd.Attribute  = 19          # WCA_ACCENT_POLICY
        wd.Data       = pointer(ap)
        wd.SizeOfData = ctypes.sizeof(ap)
        windll.user32.SetWindowCompositionAttribute(hwnd, pointer(wd))
        return True
    except Exception:
        return False


# ─── Palette ──────────────────────────────────────────────────────────────────
TRANSPARENT = '#010101'   # pixels this colour become truly transparent

FG   = '#0d1e3a'          # dark navy — readable on any blurred bg
FG2  = '#4a6888'          # medium
FG3  = '#8aa8cc'          # dim

COLORS = {
    'cpu':  '#1a7fff',
    'gpu':  '#f97316',
    'ram':  '#10b981',
    'disk': '#8b5cf6',
    'netu': '#ef4444',
    'netd': '#06b6d4',
}

FONT      = 'Segoe UI'
FONT_MONO = 'Consolas'
MIN_W, MIN_H = 220, 280
W0, H0   = 270, 360
TICK_MS  = 80
RZ       = 20     # resize zone px
CLOSE_R  = 12     # close-button radius


# ─── Helpers ──────────────────────────────────────────────────────────────────
def fmt_bytes(b: float) -> str:
    if b >= 1024**3: return f'{b/1024**3:.1f}G'
    if b >= 1024**2: return f'{b/1024**2:.1f}M'
    if b >= 1024:    return f'{b/1024:.0f}K'
    return f'{b:.0f}B'

def net_pct(bps: float) -> float:
    if bps <= 0: return 0.0
    return max(0.0, min(1.0, math.log10(bps+1) / math.log10(100*1024**2)))

def blend(c1: str, c2: str, t: float) -> str:
    r = lambda s,i: int(s[1+2*i:3+2*i], 16)
    return '#{:02x}{:02x}{:02x}'.format(
        int(r(c1,0)+(r(c2,0)-r(c1,0))*t),
        int(r(c1,1)+(r(c2,1)-r(c1,1))*t),
        int(r(c1,2)+(r(c2,2)-r(c1,2))*t),
    )

def lighten(c: str, f: float = 0.70) -> str:
    return blend(c, '#ffffff', f)


# ─── Rounded rectangle primitives ────────────────────────────────────────────
def _rrect_fill(cv, x1, y1, x2, y2, r, fill):
    r = max(1, min(r, (x2-x1)//2, (y2-y1)//2))
    kw = dict(style='pieslice', fill=fill, outline='')
    cv.create_arc(x1,     y1,     x1+2*r, y1+2*r, start=90,  extent=90, **kw)
    cv.create_arc(x2-2*r, y1,     x2,     y1+2*r, start=0,   extent=90, **kw)
    cv.create_arc(x1,     y2-2*r, x1+2*r, y2,     start=180, extent=90, **kw)
    cv.create_arc(x2-2*r, y2-2*r, x2,     y2,     start=270, extent=90, **kw)
    cv.create_rectangle(x1+r, y1,   x2-r, y2,   fill=fill, outline='')
    cv.create_rectangle(x1,   y1+r, x2,   y2-r, fill=fill, outline='')


# ─── Data Collector ───────────────────────────────────────────────────────────
class DataCollector:
    def __init__(self, q: queue.Queue):
        self.q        = q
        self.running  = True
        self._net0    = psutil.net_io_counters()
        self._t0      = time.time()
        self._wmi_obj = None

    def _init_wmi(self):
        if not WMI_OK: return
        try:
            pythoncom.CoInitialize()
            self._wmi_obj = _wmi.WMI(namespace=r'root\cimv2')
        except Exception:
            self._wmi_obj = None

    def _gpu(self):
        if not self._wmi_obj: return None
        try:
            engines = self._wmi_obj.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine()
            total = sum(float(e.UtilizationPercentage)
                        for e in engines if 'engtype_3D' in (e.Name or ''))
            return min(total, 100.0)
        except Exception:
            return None

    def _collect(self) -> dict:
        d = {}
        d['cpu'] = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        d['ram_pct']   = ram.percent
        d['ram_used']  = ram.used  / 1024**3
        d['ram_total'] = ram.total / 1024**3
        disk = psutil.disk_usage('C:\\')
        d['disk_pct']  = disk.percent
        d['disk_used']  = disk.used  / 1024**3
        d['disk_total'] = disk.total / 1024**3
        now = time.time(); net = psutil.net_io_counters(); dt = now - self._t0
        d['net_up'] = (net.bytes_sent - self._net0.bytes_sent) / dt if dt > 0 else 0
        d['net_dn'] = (net.bytes_recv - self._net0.bytes_recv) / dt if dt > 0 else 0
        self._net0, self._t0 = net, now
        d['gpu'] = self._gpu()
        return d

    def run(self):
        self._init_wmi()
        psutil.cpu_percent(interval=None)
        time.sleep(0.5)
        while self.running:
            try:
                data = self._collect()
                if self.q.full():
                    try: self.q.get_nowait()
                    except: pass
                self.q.put_nowait(data)
            except Exception:
                pass
            time.sleep(1.0)

    def stop(self): self.running = False


# ─── Widget ───────────────────────────────────────────────────────────────────
class SysWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('CRYSTAL')
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg=TRANSPARENT)
        self.root.wm_attributes('-transparentcolor', TRANSPARENT)
        self.root.geometry(f'{W0}x{H0}+80+80')

        self._data      = None
        self._frame     = 0
        self._dragging  = False
        self._drag_x    = self._drag_y = 0
        self._resizing  = False
        self._rsx = self._rsy = self._rsw = self._rsh = 0
        self._close_hot = False   # mouse over close btn

        # Single canvas — no title bar
        self.canvas = tk.Canvas(self.root, bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self._bind_events()

        # Enable real DWM acrylic blur (0x10 ≈ 6% white tint → very transparent)
        self.root.update()
        hwnd = self.root.winfo_id()
        # 0x55FFFFFF = 33% white tint + window alpha 0.78 → frosted แต่โปร่งกว่า
        self.root.attributes('-alpha', 0.78)
        if not _apply_acrylic(hwnd, 0x55FFFFFF):
            self.root.wm_attributes('-transparentcolor', '')
            self.root.configure(bg='#eef3ff')
            self.root.attributes('-alpha', 0.78)

        self.q = queue.Queue(maxsize=2)
        self.collector = DataCollector(self.q)
        threading.Thread(target=self.collector.run, daemon=True).start()
        self.root.after(500, self._tick)

    # ── Event binding ─────────────────────────────────────────────────────────
    def _bind_events(self):
        self.canvas.bind('<ButtonPress-1>',   self._press)
        self.canvas.bind('<B1-Motion>',       self._motion)
        self.canvas.bind('<ButtonRelease-1>', self._release)
        self.canvas.bind('<Motion>',          self._hover)

    def _close_zone(self, x, y) -> bool:
        W = self.canvas.winfo_width()
        return math.hypot(x - (W - CLOSE_R - 8), y - (CLOSE_R + 8)) < CLOSE_R + 4

    def _in_rz(self, x, y) -> bool:
        W = self.canvas.winfo_width()
        H = self.canvas.winfo_height()
        return x > W - RZ and y > H - RZ

    def _press(self, e):
        if self._in_rz(e.x, e.y):
            self._resizing = True
            self._rsx, self._rsy = e.x_root, e.y_root
            self._rsw = self.root.winfo_width()
            self._rsh = self.root.winfo_height()
        elif self._close_zone(e.x, e.y):
            self._quit()
        else:
            self._dragging = True
            self._drag_x = e.x_root - self.root.winfo_x()
            self._drag_y = e.y_root - self.root.winfo_y()

    def _motion(self, e):
        if self._resizing:
            nw = max(MIN_W, self._rsw + e.x_root - self._rsx)
            nh = max(MIN_H, self._rsh + e.y_root - self._rsy)
            self.root.geometry(f'{nw}x{nh}+{self.root.winfo_x()}+{self.root.winfo_y()}')
        elif self._dragging:
            self.root.geometry(f'+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}')

    def _release(self, e):
        self._resizing = self._dragging = False
        self.root.config(cursor='')

    def _hover(self, e):
        hot = self._close_zone(e.x, e.y)
        if hot != self._close_hot:
            self._close_hot = hot
        if self._in_rz(e.x, e.y):
            self.root.config(cursor='size_nw_se')
        elif hot:
            self.root.config(cursor='hand2')
        else:
            self.root.config(cursor='fleur')

    # ── Main loop ─────────────────────────────────────────────────────────────
    def _tick(self):
        self._frame += 1
        try:    self._data = self.q.get_nowait()
        except: pass
        if self._data: self._redraw(self._data)
        else:          self._draw_loading()
        self.root.after(TICK_MS, self._tick)

    # ── Redraw ────────────────────────────────────────────────────────────────
    def _redraw(self, d: dict):
        cv = self.canvas
        cv.delete('all')
        W = cv.winfo_width()
        H = cv.winfo_height()
        if W < 10 or H < 10: return

        # ── Scale factor (1.0 = default size, <1 = smaller, >1 = larger) ─────
        sc  = min(W / W0, H / H0)
        sc  = max(0.5, sc)          # ไม่เล็กกว่า 50%

        PAD    = max(8,  int(14 * sc))
        R_PAN  = max(8,  int(16 * sc))
        fs_bar = max(6,  int(8  * sc))   # font ขนาด bar label/value
        fs_ft  = max(6,  int(7  * sc))   # font ขนาด footer
        bar_h  = max(4,  int(7  * sc))   # ความสูง bar
        lw     = max(28, int(44 * sc))   # label column width
        vw     = max(42, int(64 * sc))   # value column width
        cr     = max(8,  int(12 * sc))   # close button radius
        cp     = max(6,  int(8  * sc))   # close button padding

        # ── Frosted glass background ──────────────────────────────────────────
        self._glass_panel(cv, 2, 2, W-2, H-2, r=R_PAN)

        # ── Close button (top-right, scales with sc) ──────────────────────────
        cxb = W - cr - cp
        cyb = cr + cp
        btn_col  = '#ff5f57' if self._close_hot else blend('#ffffff', '#ff5f57', 0.35)
        cv.create_oval(cxb-cr, cyb-cr, cxb+cr, cyb+cr,
                       fill=btn_col, outline=blend('#000000', btn_col, 0.6), width=1)
        cv.create_text(cxb, cyb, text='✕', fill='white',
                       font=(FONT, max(6, int(7*sc)), 'bold'), anchor='center')

        # ── Gauge section (top 44%) ───────────────────────────────────────────
        gh    = int(H * 0.44)
        mid   = W // 2
        half  = mid - PAD - max(4, int(6*sc))
        lcx   = PAD + half // 2
        rcx   = W - PAD - half // 2
        gcy   = (PAD + gh) // 2
        arc_r = max(22, min(
            half // 2 - max(8, int(12*sc)),
            (gh - PAD*2)  // 2 - max(6, int(10*sc))
        ))

        self._gauge(cv, lcx, gcy, arc_r,
                    d['ram_pct'] / 100, COLORS['ram'], 'RAM',
                    f"{d['ram_used']:.1f}/{d['ram_total']:.0f}G")

        gpu_val = d.get('gpu')
        self._gauge(cv, rcx, gcy, arc_r,
                    (gpu_val / 100) if gpu_val is not None else 0,
                    COLORS['gpu'], 'GPU',
                    f"{gpu_val:.0f}%" if gpu_val is not None else 'N/A')

        # ── Divider ───────────────────────────────────────────────────────────
        sep_y = gh + max(4, int(8*sc))
        cv.create_line(PAD+10, sep_y, W-PAD-10, sep_y, fill='#c0d0e8', width=1)

        # ── Bars section ──────────────────────────────────────────────────────
        rows = [
            ('CPU',   d['cpu'] / 100,       f"{d['cpu']:.0f}%",                             COLORS['cpu']),
            ('DISK',  d['disk_pct'] / 100,  f"{d['disk_used']:.0f}/{d['disk_total']:.0f}G", COLORS['disk']),
            ('↑NET',  net_pct(d['net_up']), fmt_bytes(d['net_up']) + '/s',                   COLORS['netu']),
            ('↓NET',  net_pct(d['net_dn']), fmt_bytes(d['net_dn']) + '/s',                   COLORS['netd']),
        ]

        bar_top = sep_y + max(6, int(10*sc))
        bar_bot = H - max(18, int(26*sc))
        slot    = (bar_bot - bar_top) / len(rows)

        for i, (lbl, pct, txt, col) in enumerate(rows):
            cy2 = bar_top + i * slot + slot / 2
            self._bar(cv, PAD, W-PAD, cy2 - bar_h/2, cy2 + bar_h/2,
                      lbl, pct, txt, col, lw, vw, fs_bar)

        # ── Footer ────────────────────────────────────────────────────────────
        now    = datetime.datetime.now()
        boot   = datetime.datetime.fromtimestamp(psutil.boot_time())
        up_s   = int((now - boot).total_seconds())
        h_up, rem = divmod(up_s, 3600);  m_up = rem // 60
        fty = H - max(8, int(12*sc))

        cv.create_text(PAD, fty, anchor='w',
                       text=now.strftime('%H:%M:%S'),
                       fill=COLORS['cpu'], font=(FONT_MONO, fs_ft))
        cv.create_text(W/2, fty, anchor='center',
                       text=f'up {h_up}h {m_up:02d}m',
                       fill=FG2, font=(FONT_MONO, fs_ft))

        # ── Resize grip ───────────────────────────────────────────────────────
        step = max(4, int(5*sc))
        for k in range(3):
            off = step + k * step
            cv.create_line(W-off-2, H-2, W-2, H-off-2, fill=FG3, width=1)

    # ── Loading state ─────────────────────────────────────────────────────────
    def _draw_loading(self):
        cv = self.canvas; cv.delete('all')
        W, H = cv.winfo_width(), cv.winfo_height()
        if W < 10: return
        self._glass_panel(cv, 2, 2, W-2, H-2, r=16)
        dots = '.' * (1 + self._frame % 4)
        cv.create_text(W/2, H/2, anchor='center',
                       text=f'Loading{dots}', fill=FG2, font=(FONT, 9))
        # Close button still accessible
        cx = W - CLOSE_R - 8; cy = CLOSE_R + 8
        cv.create_oval(cx-CLOSE_R, cy-CLOSE_R, cx+CLOSE_R, cy+CLOSE_R,
                       fill='#ff5f57', outline='', )
        cv.create_text(cx, cy, text='✕', fill='white',
                       font=(FONT, 7, 'bold'), anchor='center')

    # ── Frosted glass panel ───────────────────────────────────────────────────
    def _glass_panel(self, cv, x1, y1, x2, y2, r=16):
        """Draw a frosted glass panel: border → fill → top-reflection → inner highlight."""
        # Outer border (defines glass edge)
        _rrect_fill(cv, x1-1, y1-1, x2+1, y2+1, r+1, '#b8cce8')
        # Main frosted fill (อมฟ้า-ขาว เหมือนกระจกขุ่น)
        _rrect_fill(cv, x1, y1, x2, y2, r, '#eef4ff')
        # Upper highlight: ด้านบน 28% สว่างกว่า (แสงสะท้อนกระจก)
        hi_y2 = y1 + int((y2 - y1) * 0.28)
        _rrect_fill(cv, x1+1, y1+1, x2-1, hi_y2, max(2, r-1), '#f8fbff')
        # 1-px white line ขอบในบน (glass edge glint)
        cv.create_line(x1+r, y1+1, x2-r, y1+1, fill='#ffffff', width=1)

    # ── Arc Gauge — all sizes derived from arc radius r ───────────────────────
    def _gauge(self, cv, cx, cy, r, pct: float, color: str, label: str, val: str):
        glow1   = lighten(color, 0.82)
        glow2   = lighten(color, 0.40)
        track_c = blend(color, '#ffffff', 0.88)

        # All widths/sizes scale with r
        track_w = max(2, int(r * 0.10))
        gw1     = max(6, int(r * 0.32))    # outer glow
        gw2     = max(3, int(r * 0.16))    # mid glow
        gw_main = max(2, int(r * 0.07))    # main arc line
        dot_r   = max(3, int(r * 0.12))    # tip dot radius
        ring_d  = max(4, int(r * 0.14))    # outer ring gap
        tick_mj = max(3, int(r * 0.12))    # major tick length
        tick_mn = max(2, int(r * 0.08))    # minor tick length
        ir      = r - max(8, int(r * 0.25))  # inner circle radius

        # Outer ring
        cv.create_oval(cx-r-ring_d, cy-r-ring_d, cx+r+ring_d, cy+r+ring_d,
                       outline=lighten(color, 0.65), width=1)

        # Tick marks (13 ticks over 240°)
        for i in range(13):
            rad   = math.radians(225 - i * 20)
            major = (i % 3 == 0)
            ri    = r + max(2, int(r*0.06))
            ro    = ri + (tick_mj if major else tick_mn)
            ca, sa = math.cos(rad), math.sin(rad)
            cv.create_line(cx+ri*ca, cy-ri*sa, cx+ro*ca, cy-ro*sa,
                           fill=FG3 if major else lighten(FG3, 0.5), width=1)

        # Background track arc
        cv.create_arc(cx-r, cy-r, cx+r, cy+r,
                      start=225, extent=-240,
                      style='arc', outline=track_c, width=track_w)

        # Value arc + glow
        if pct > 0:
            ext = -pct * 240
            cv.create_arc(cx-r, cy-r, cx+r, cy+r,
                          start=225, extent=ext, style='arc', outline=glow1, width=gw1)
            cv.create_arc(cx-r, cy-r, cx+r, cy+r,
                          start=225, extent=ext, style='arc', outline=glow2, width=gw2)
            cv.create_arc(cx-r, cy-r, cx+r, cy+r,
                          start=225, extent=ext, style='arc', outline=color,  width=gw_main)
            # Tip dot
            tip = math.radians(225 - pct * 240)
            tx  = cx + r * math.cos(tip)
            ty  = cy - r * math.sin(tip)
            cv.create_oval(tx-dot_r, ty-dot_r, tx+dot_r, ty+dot_r,
                           fill=color, outline='white', width=1)

        # Inner white circle (readability)
        cv.create_oval(cx-ir, cy-ir, cx+ir, cy+ir,
                       fill='#ffffff', outline=lighten(color, 0.55), width=1)

        # Value text (large, scales with r)
        fsize = max(8, int(r * 0.30))
        cv.create_text(cx, cy - max(2, int(r*0.06)), anchor='center',
                       text=val, fill=color, font=(FONT_MONO, fsize, 'bold'))
        # Label text (small, below centre)
        lsize = max(6, int(r * 0.20))
        cv.create_text(cx, cy + int(r * 0.38), anchor='center',
                       text=label, fill=FG2, font=(FONT, lsize))

    # ── Bar row — lw/vw/fs passed from _redraw (already scaled) ──────────────
    def _bar(self, cv, x1, x2, by, by2,
             label: str, pct: float, val: str, color: str,
             lw: int = 40, vw: int = 60, fs: int = 7):
        bx   = x1 + lw
        bx2  = x2 - vw
        glow = lighten(color, 0.72)

        # Label
        cv.create_text(x1 + lw - 4, (by+by2)/2, anchor='e',
                       text=label, fill=FG2, font=(FONT, fs, 'bold'))

        # Track
        cv.create_rectangle(bx, by, bx2, by2, fill='#d8e4f4', outline='')

        # Fill
        fw = int((bx2-bx) * max(0.0, min(1.0, pct)))
        if fw > 0:
            cv.create_rectangle(bx, by-1, bx+fw, by2+1, fill=glow,  outline='')
            cv.create_rectangle(bx, by,   bx+fw, by2,   fill=color, outline='')
            tw = min(max(2, int(fw*0.06)), fw)
            cv.create_rectangle(bx+fw-tw, by-1, bx+fw, by2+1, fill='white', outline='')

        # Value
        cv.create_text(x2, (by+by2)/2, anchor='e',
                       text=val, fill=FG, font=(FONT_MONO, fs))

    def _quit(self):
        self.collector.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    SysWidget().run()
