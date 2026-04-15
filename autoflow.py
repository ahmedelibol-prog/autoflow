#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoFlow v6.0 - 4 Kayit Slotu, Basit Arayuz
Windows API ile tam klavye destegi (Ctrl+C/V vb)
ESC = Durdur
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import json
import os
import sys
import ctypes
import ctypes.wintypes as wt

# Windows API
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
VK_ESCAPE = 0x1B
INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", ctypes.c_ulong), ("scanCode", ctypes.c_ulong),
                ("flags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", ctypes.c_ulong),
                ("flags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", INPUT_UNION)]

HOOKPROC_KB = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(KBDLLHOOKSTRUCT))
HOOKPROC_MS = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(MSLLHOOKSTRUCT))


def extra_ptr():
    return ctypes.pointer(ctypes.c_ulong(0))


class MacroEngine:
    def __init__(self):
        self.events = []
        self.recording = False
        self.playing = False
        self.start_time = 0
        self.speed = 1.0
        self.loops = 1
        self.stop_flag = False
        self.last_move = 0
        self.on_esc = None
        self._kb_hook = None
        self._ms_hook = None
        self._kb_proc = HOOKPROC_KB(self._kb_cb)
        self._ms_proc = HOOKPROC_MS(self._ms_cb)
        self._sx = user32.GetSystemMetrics(0)
        self._sy = user32.GetSystemMetrics(1)

    def _ts(self):
        return time.time() - self.start_time

    def _kb_cb(self, nCode, wParam, lParam):
        if nCode >= 0:
            vk = lParam.contents.vkCode
            sc = lParam.contents.scanCode
            if vk == VK_ESCAPE and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if self.on_esc:
                    self.on_esc()
            if self.recording:
                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    self.events.append({'t': 'kd', 'vk': vk, 'sc': sc, 's': self._ts()})
                elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                    self.events.append({'t': 'ku', 'vk': vk, 'sc': sc, 's': self._ts()})
        return user32.CallNextHookEx(self._kb_hook, nCode, wParam, lParam)

    def _ms_cb(self, nCode, wParam, lParam):
        if nCode >= 0 and self.recording:
            x, y = lParam.contents.pt.x, lParam.contents.pt.y
            now = time.time()
            if wParam == WM_MOUSEMOVE:
                if now - self.last_move < 0.025:
                    return user32.CallNextHookEx(self._ms_hook, nCode, wParam, lParam)
                self.last_move = now
                self.events.append({'t': 'mm', 'x': x, 'y': y, 's': self._ts()})
            elif wParam == WM_LBUTTONDOWN:
                self.events.append({'t': 'md', 'x': x, 'y': y, 'b': 'l', 's': self._ts()})
            elif wParam == WM_LBUTTONUP:
                self.events.append({'t': 'mu', 'x': x, 'y': y, 'b': 'l', 's': self._ts()})
            elif wParam == WM_RBUTTONDOWN:
                self.events.append({'t': 'md', 'x': x, 'y': y, 'b': 'r', 's': self._ts()})
            elif wParam == WM_RBUTTONUP:
                self.events.append({'t': 'mu', 'x': x, 'y': y, 'b': 'r', 's': self._ts()})
            elif wParam == WM_MBUTTONDOWN:
                self.events.append({'t': 'md', 'x': x, 'y': y, 'b': 'm', 's': self._ts()})
            elif wParam == WM_MBUTTONUP:
                self.events.append({'t': 'mu', 'x': x, 'y': y, 'b': 'm', 's': self._ts()})
            elif wParam == WM_MOUSEWHEEL:
                d = ctypes.c_short(lParam.contents.mouseData >> 16).value
                self.events.append({'t': 'mw', 'x': x, 'y': y, 'd': d, 's': self._ts()})
        return user32.CallNextHookEx(self._ms_hook, nCode, wParam, lParam)

    def rec_start(self):
        self.events = []
        self.recording = True
        self.start_time = time.time()
        self.last_move = 0
        def run():
            h = kernel32.GetModuleHandleW(None)
            self._kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, h, 0)
            self._ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._ms_proc, h, 0)
            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        threading.Thread(target=run, daemon=True).start()

    def rec_stop(self):
        self.recording = False
        if self._kb_hook: user32.UnhookWindowsHookEx(self._kb_hook); self._kb_hook = None
        if self._ms_hook: user32.UnhookWindowsHookEx(self._ms_hook); self._ms_hook = None
        self.events = [e for e in self.events if not (e['t'] in ('kd','ku') and e.get('vk') == VK_ESCAPE)]

    def play(self, on_prog=None, on_done=None):
        if not self.events: return
        self.playing = True
        self.stop_flag = False
        # ESC hook
        def esc_run():
            h = kernel32.GetModuleHandleW(None)
            self._kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, h, 0)
            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        threading.Thread(target=esc_run, daemon=True).start()

        def worker():
            for lp in range(self.loops):
                if self.stop_flag: break
                prev = 0
                tot = len(self.events)
                for i, ev in enumerate(self.events):
                    if self.stop_flag: break
                    dly = (ev['s'] - prev) / self.speed
                    if dly > 0:
                        w = 0.0
                        while w < dly and not self.stop_flag:
                            time.sleep(min(0.01, dly - w)); w += 0.01
                    if self.stop_flag: break
                    prev = ev['s']
                    try: self._exec(ev)
                    except: pass
                    if on_prog: on_prog(i+1, tot, lp+1)
            self.playing = False
            if self._kb_hook: user32.UnhookWindowsHookEx(self._kb_hook); self._kb_hook = None
            if on_done: on_done()
        threading.Thread(target=worker, daemon=True).start()

    def stop(self):
        self.stop_flag = True
        self.playing = False

    def _exec(self, ev):
        t = ev['t']
        if t == 'mm':
            self._mouse_move(ev['x'], ev['y'])
        elif t == 'md':
            self._mouse_move(ev['x'], ev['y'])
            f = {'l': MOUSEEVENTF_LEFTDOWN, 'r': MOUSEEVENTF_RIGHTDOWN, 'm': MOUSEEVENTF_MIDDLEDOWN}[ev['b']]
            self._mouse_btn(f)
        elif t == 'mu':
            self._mouse_move(ev['x'], ev['y'])
            f = {'l': MOUSEEVENTF_LEFTUP, 'r': MOUSEEVENTF_RIGHTUP, 'm': MOUSEEVENTF_MIDDLEUP}[ev['b']]
            self._mouse_btn(f)
        elif t == 'mw':
            inp = INPUT(); inp.type = INPUT_MOUSE
            inp.union.mi.dwFlags = MOUSEEVENTF_WHEEL; inp.union.mi.mouseData = ev['d']
            inp.union.mi.dwExtraInfo = extra_ptr()
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        elif t == 'kd':
            self._key(ev['vk'], ev.get('sc', 0), False)
        elif t == 'ku':
            self._key(ev['vk'], ev.get('sc', 0), True)

    def _mouse_move(self, x, y):
        inp = INPUT(); inp.type = INPUT_MOUSE
        inp.union.mi.dx = int(x * 65535 / self._sx)
        inp.union.mi.dy = int(y * 65535 / self._sy)
        inp.union.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        inp.union.mi.dwExtraInfo = extra_ptr()
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _mouse_btn(self, flag):
        inp = INPUT(); inp.type = INPUT_MOUSE
        inp.union.mi.dwFlags = flag
        inp.union.mi.dwExtraInfo = extra_ptr()
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _key(self, vk, sc, up):
        inp = INPUT(); inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = vk; inp.union.ki.wScan = sc
        inp.union.ki.dwFlags = KEYEVENTF_KEYUP if up else 0
        inp.union.ki.dwExtraInfo = extra_ptr()
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'v': '6', 'n': len(self.events), 'e': self.events}, f)

    def load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.events = d['e']
        return d.get('n', len(self.events))


# ══════════════════════════════════════
#  ARAYUZ - 4 SLOT, BASIT
# ══════════════════════════════════════
class AutoFlowApp:
    BG = "#f0f4f8"
    CARD = "#ffffff"
    BLUE = "#2563eb"
    RED = "#dc2626"
    GREEN = "#16a34a"
    ORANGE = "#ea580c"
    TEXT = "#1e293b"
    TEXT2 = "#64748b"
    TEXT3 = "#94a3b8"
    BORDER = "#e2e8f0"

    COLORS = ["#7c3aed", "#2563eb", "#0d9488", "#ea580c"]
    SLOT_NAMES = ["Kayit 1", "Kayit 2", "Kayit 3", "Kayit 4"]
    MACROS_DIR = os.path.join(os.path.expanduser("~"), ".autoflow")

    def __init__(self, root):
        self.root = root
        self.engine = MacroEngine()
        self.engine.on_esc = lambda: self.root.after(0, self._stop)
        self.recording_slot = None
        os.makedirs(self.MACROS_DIR, exist_ok=True)
        self._build()

    def _slot_path(self, i):
        return os.path.join(self.MACROS_DIR, f"slot{i}.autoflow")

    def _slot_info(self, i):
        p = self._slot_path(i)
        if os.path.exists(p):
            try:
                with open(p) as f:
                    d = json.load(f)
                return f"{d.get('n', '?')} hareket"
            except: pass
        return "bos"

    def _build(self):
        self.root.configure(bg=self.BG)
        main = tk.Frame(self.root, bg=self.BG, padx=20, pady=12)
        main.pack(fill='both', expand=True)

        # Baslik
        tk.Label(main, text="AutoFlow", font=("Segoe UI", 20, "bold"),
                 fg=self.BLUE, bg=self.BG).pack(anchor='w')
        tk.Label(main, text="Kaydet - Donguye Al - Calistir",
                 font=("Segoe UI", 9), fg=self.TEXT3, bg=self.BG).pack(anchor='w', pady=(0, 12))

        # ═══════════════════════════
        #  4 SLOT
        # ═══════════════════════════
        self.slot_frames = []
        self.slot_labels = []
        self.slot_play_btns = []
        self.slot_rec_btns = []

        for i in range(4):
            color = self.COLORS[i]
            card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                            highlightthickness=1, padx=14, pady=10)
            card.pack(fill='x', pady=(0, 6))

            row = tk.Frame(card, bg=self.CARD)
            row.pack(fill='x')

            # Sol: renk cizgi + isim
            tag = tk.Frame(row, bg=color, width=4, height=36)
            tag.pack(side='left', padx=(0, 10), fill='y')
            tag.pack_propagate(False)

            info = tk.Frame(row, bg=self.CARD)
            info.pack(side='left', fill='x', expand=True)

            lbl_name = tk.Label(info, text=self.SLOT_NAMES[i],
                                 font=("Segoe UI", 11, "bold"), fg=self.TEXT, bg=self.CARD)
            lbl_name.pack(anchor='w')

            lbl_info = tk.Label(info, text=self._slot_info(i),
                                 font=("Segoe UI", 8), fg=self.TEXT3, bg=self.CARD)
            lbl_info.pack(anchor='w')
            self.slot_labels.append(lbl_info)

            # Sag: butonlar
            btn_play = tk.Button(row, text="OYNAT",
                font=("Segoe UI", 10, "bold"), bg=color, fg="white",
                relief='flat', cursor='hand2', padx=14, pady=6,
                command=lambda idx=i: self._play_slot(idx))
            btn_play.pack(side='right', padx=(4, 0))
            self.slot_play_btns.append(btn_play)

            btn_rec = tk.Button(row, text="Kaydet",
                font=("Segoe UI", 9), bg="#f1f5f9", fg=self.TEXT,
                relief='flat', cursor='hand2', padx=10, pady=6,
                command=lambda idx=i: self._rec_slot(idx))
            btn_rec.pack(side='right', padx=(4, 0))
            self.slot_rec_btns.append(btn_rec)

            btn_file = tk.Button(row, text="Ac",
                font=("Segoe UI", 9), bg="#f1f5f9", fg=self.TEXT2,
                relief='flat', cursor='hand2', padx=8, pady=6,
                command=lambda idx=i: self._load_slot(idx))
            btn_file.pack(side='right')

            self.slot_frames.append(card)

        # ═══════════════════════════
        #  TEKRAR + HIZ
        # ═══════════════════════════
        set_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                            highlightthickness=1, padx=14, pady=10)
        set_card.pack(fill='x', pady=(4, 6))

        r1 = tk.Frame(set_card, bg=self.CARD)
        r1.pack(fill='x', pady=(0, 6))

        tk.Label(r1, text="Tekrar:", font=("Segoe UI", 10, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(side='left')

        self.loop_var = tk.StringVar(value="100")
        for v in ["1", "10", "50", "100", "500"]:
            tk.Button(r1, text=v, font=("Segoe UI", 9, "bold"),
                      bg="#f1f5f9", fg=self.TEXT, relief='flat', cursor='hand2',
                      width=4, pady=3,
                      command=lambda x=v: self.loop_var.set(x)
                      ).pack(side='left', padx=2)
        tk.Entry(r1, textvariable=self.loop_var, font=("Segoe UI", 11, "bold"),
                 width=5, bg="#f8fafc", fg=self.TEXT, relief='solid', bd=1,
                 justify='center').pack(side='left', padx=(8, 0), ipady=2)

        r2 = tk.Frame(set_card, bg=self.CARD)
        r2.pack(fill='x')

        tk.Label(r2, text="Hiz:", font=("Segoe UI", 10, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(side='left', padx=(0, 8))
        self.speed_var = tk.StringVar(value="1.0")
        for l, v in [("Yavas", "0.5"), ("Normal", "1.0"), ("Hizli", "2.0"), ("Max", "5.0")]:
            tk.Button(r2, text=l, font=("Segoe UI", 9),
                      bg="#f1f5f9", fg=self.TEXT, relief='flat', cursor='hand2',
                      padx=8, pady=3,
                      command=lambda x=v: self.speed_var.set(x)
                      ).pack(side='left', padx=2)

        # ═══════════════════════════
        #  DURDUR
        # ═══════════════════════════
        self.btn_stop = tk.Button(main,
            text="DURDUR  (ESC)",
            font=("Segoe UI", 12, "bold"),
            bg="#fef2f2", fg=self.RED,
            activebackground="#fee2e2", activeforeground=self.RED,
            relief='flat', cursor='hand2', pady=8,
            command=self._stop, state='disabled')
        self.btn_stop.pack(fill='x', pady=(0, 6))

        # ═══════════════════════════
        #  DURUM
        # ═══════════════════════════
        stat = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                        highlightthickness=1, padx=14, pady=8)
        stat.pack(fill='x')

        self.lbl_status = tk.Label(stat, text="Hazir",
                                    font=("Segoe UI", 11), fg=self.BLUE, bg=self.CARD)
        self.lbl_status.pack(anchor='w')

        self.lbl_detail = tk.Label(stat, text="Bir slotun Kaydet butonuna basin",
                                    font=("Segoe UI", 8), fg=self.TEXT3, bg=self.CARD)
        self.lbl_detail.pack(anchor='w')

        style = ttk.Style(); style.theme_use('clam')
        style.configure("G.Horizontal.TProgressbar",
                         troughcolor="#e2e8f0", background=self.GREEN, thickness=6)
        self.progress = ttk.Progressbar(stat, mode='determinate',
                                         style="G.Horizontal.TProgressbar")

        tk.Label(main, text="ESC = Durdur  |  Ctrl+C/V tam destek  |  Yonetici olarak calistirin",
                 font=("Segoe UI", 7), fg=self.TEXT3, bg=self.BG).pack(pady=(4, 0))

    # ── Slot Kayit ──
    def _rec_slot(self, idx):
        if self.engine.recording or self.engine.playing:
            return
        self.recording_slot = idx
        name = self.SLOT_NAMES[idx]

        self.lbl_status.configure(text="3 saniye sonra kayit basliyor...", fg=self.ORANGE)
        self.lbl_detail.configure(text=f"{name} icin hazirlanin")
        self._disable_all()

        self.root.after(3000, lambda: self._rec_start(idx))

    def _rec_start(self, idx):
        self.engine.rec_start()
        self.btn_stop.configure(state='normal')
        name = self.SLOT_NAMES[idx]
        self.lbl_status.configure(text=f"KAYDEDILIYOR - {name}", fg=self.RED)
        self.lbl_detail.configure(text="Islemleri yapin, bitince ESC basin")
        self._tick()

    def _stop_rec(self):
        if not self.engine.recording:
            return
        self.engine.rec_stop()
        idx = self.recording_slot
        if idx is not None and self.engine.events:
            self.engine.save(self._slot_path(idx))
            self.slot_labels[idx].configure(text=self._slot_info(idx))
            name = self.SLOT_NAMES[idx]
            n = len(self.engine.events)
            self.lbl_status.configure(text=f"{name} kaydedildi! ({n} hareket)", fg=self.GREEN)
            self.lbl_detail.configure(text="OYNAT butonuna basarak calistirabilirsiniz")
        else:
            self.lbl_status.configure(text="Kayit iptal edildi", fg=self.ORANGE)
            self.lbl_detail.configure(text="")
        self.recording_slot = None
        self._enable_all()

    # ── Slot Oynat ──
    def _play_slot(self, idx):
        if self.engine.recording or self.engine.playing:
            return
        path = self._slot_path(idx)
        if not os.path.exists(path):
            messagebox.showinfo("Bilgi", f"{self.SLOT_NAMES[idx]} bos!\nOnce Kaydet butonuna basin.")
            return
        try:
            self.engine.load(path)
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            return

        try: self.engine.loops = max(1, int(self.loop_var.get()))
        except: self.engine.loops = 1
        try: self.engine.speed = float(self.speed_var.get())
        except: self.engine.speed = 1.0

        self._disable_all()
        self.btn_stop.configure(state='normal')
        self.progress.pack(fill='x', pady=(6, 0))
        self.progress['maximum'] = len(self.engine.events)
        self.progress['value'] = 0

        name = self.SLOT_NAMES[idx]
        lt = f" ({self.engine.loops}x)" if self.engine.loops > 1 else ""
        self.lbl_status.configure(text=f"{name} calisiyor{lt}...", fg=self.BLUE)
        self.lbl_detail.configure(text="ESC = durdur")

        self.engine.play(on_prog=self._prog, on_done=self._done)

    # ── Slot Dosyadan Ac ──
    def _load_slot(self, idx):
        if self.engine.recording or self.engine.playing:
            return
        fp = filedialog.askopenfilename(title=f"{self.SLOT_NAMES[idx]} icin dosya sec",
            filetypes=[("AutoFlow", "*.autoflow"), ("Hepsi", "*.*")])
        if fp:
            try:
                with open(fp, 'r') as f:
                    data = json.load(f)
                with open(self._slot_path(idx), 'w') as f:
                    json.dump(data, f)
                self.slot_labels[idx].configure(text=self._slot_info(idx))
                self.lbl_status.configure(text=f"{self.SLOT_NAMES[idx]} yuklendi!", fg=self.GREEN)
            except Exception as e:
                messagebox.showerror("Hata", str(e))

    # ── Genel ──
    def _prog(self, cur, tot, lp):
        def u():
            self.progress['value'] = cur
            pct = int(cur / tot * 100)
            lt = f" [{lp}/{self.engine.loops}]" if self.engine.loops > 1 else ""
            self.lbl_status.configure(text=f"Calisiyor %{pct}{lt}", fg=self.BLUE)
        self.root.after(0, u)

    def _done(self):
        def u():
            self._enable_all()
            self.progress.pack_forget()
            self.lbl_status.configure(text="Tamamlandi!", fg=self.GREEN)
            self.lbl_detail.configure(text=f"{self.engine.loops} islem tamamlandi")
        self.root.after(0, u)

    def _stop(self):
        if self.engine.recording:
            self._stop_rec()
            return
        if self.engine.playing:
            self.engine.stop()
            if self.engine._kb_hook:
                user32.UnhookWindowsHookEx(self.engine._kb_hook)
                self.engine._kb_hook = None
            self._enable_all()
            self.progress.pack_forget()
            self.lbl_status.configure(text="Durduruldu.", fg=self.ORANGE)
            self.lbl_detail.configure(text="")

    def _disable_all(self):
        for b in self.slot_play_btns + self.slot_rec_btns:
            b.configure(state='disabled')

    def _enable_all(self):
        for b in self.slot_play_btns + self.slot_rec_btns:
            b.configure(state='normal')
        self.btn_stop.configure(state='disabled')

    def _tick(self):
        if self.engine.recording:
            el = time.time() - self.engine.start_time
            n = len(self.engine.events)
            self.lbl_detail.configure(text=f"{el:.1f}s | {n} hareket | ESC = durdur")
            self.root.after(100, self._tick)


def main():
    root = tk.Tk()
    root.title("AutoFlow")
    root.geometry("520x620")
    root.minsize(460, 560)
    root.configure(bg="#f0f4f8")
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    AutoFlowApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
