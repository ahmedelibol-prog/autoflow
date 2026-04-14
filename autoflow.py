#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoFlow v5.0 - EBYS Otomasyon
Tamamen Windows API - Klavye kopya/yapistir tam destek
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

# ══════════════════════════════════════
#  WINDOWS API TANIMLARI
# ══════════════════════════════════════
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Hook tipleri
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14

# Klavye mesajlari
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Fare mesajlari
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A

# VK kodlari
VK_ESCAPE = 0x1B

# SendInput sabitleri
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
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


# Hook struct tanimlari
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_ulong),
        ("scanCode", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wt.POINT),
        ("mouseData", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", INPUT_UNION)]

HOOKPROC_KB = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(KBDLLHOOKSTRUCT))
HOOKPROC_MS = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(MSLLHOOKSTRUCT))


# ══════════════════════════════════════
#  MAKRO MOTORU - SIFIRDAN WINDOWS API
# ══════════════════════════════════════
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

        self.on_esc = None  # ESC callback

        # Hook referanslari
        self._kb_hook = None
        self._ms_hook = None
        self._kb_proc = HOOKPROC_KB(self._kb_callback)
        self._ms_proc = HOOKPROC_MS(self._ms_callback)
        self._hook_thread = None

        # Ekran boyutu (fare konumu hesabi icin)
        self._sx = user32.GetSystemMetrics(0)
        self._sy = user32.GetSystemMetrics(1)

    def _ts(self):
        return time.time() - self.start_time

    # ── HOOK CALLBACKS ──
    def _kb_callback(self, nCode, wParam, lParam):
        if nCode >= 0:
            vk = lParam.contents.vkCode
            scan = lParam.contents.scanCode

            # ESC = durdur (her zaman)
            if vk == VK_ESCAPE and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if self.on_esc:
                    self.on_esc()

            # Kayit modundaysa kaydet
            if self.recording:
                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    self.events.append({'t': 'kd', 'vk': vk, 'sc': scan, 's': self._ts()})
                elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                    self.events.append({'t': 'ku', 'vk': vk, 'sc': scan, 's': self._ts()})

        return user32.CallNextHookEx(self._kb_hook, nCode, wParam, lParam)

    def _ms_callback(self, nCode, wParam, lParam):
        if nCode >= 0 and self.recording:
            pt = lParam.contents.pt
            x, y = pt.x, pt.y
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
                delta = ctypes.c_short(lParam.contents.mouseData >> 16).value
                self.events.append({'t': 'mw', 'x': x, 'y': y, 'd': delta, 's': self._ts()})

        return user32.CallNextHookEx(self._ms_hook, nCode, wParam, lParam)

    # ── KAYIT ──
    def rec_start(self):
        self.events = []
        self.recording = True
        self.start_time = time.time()
        self.last_move = 0
        self._start_hooks()

    def rec_stop(self):
        self.recording = False
        self._stop_hooks()

    def _start_hooks(self):
        def run():
            hmod = kernel32.GetModuleHandleW(None)
            self._kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, hmod, 0)
            self._ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._ms_proc, hmod, 0)
            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        self._hook_thread = threading.Thread(target=run, daemon=True)
        self._hook_thread.start()

    def _stop_hooks(self):
        if self._kb_hook:
            user32.UnhookWindowsHookEx(self._kb_hook)
            self._kb_hook = None
        if self._ms_hook:
            user32.UnhookWindowsHookEx(self._ms_hook)
            self._ms_hook = None

    # ── OYNATMA ──
    def play(self, on_prog=None, on_done=None):
        if not self.events:
            return
        self.playing = True
        self.stop_flag = False

        # ESC yakalamak icin sadece klavye hook ac
        def esc_hook():
            hmod = kernel32.GetModuleHandleW(None)
            self._kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, hmod, 0)
            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        esc_thread = threading.Thread(target=esc_hook, daemon=True)
        esc_thread.start()

        def worker():
            for lp in range(self.loops):
                if self.stop_flag:
                    break
                prev = 0
                total = len(self.events)
                for i, ev in enumerate(self.events):
                    if self.stop_flag:
                        break
                    delay = (ev['s'] - prev) / self.speed
                    if delay > 0:
                        w = 0.0
                        while w < delay and not self.stop_flag:
                            time.sleep(min(0.01, delay - w))
                            w += 0.01
                    if self.stop_flag:
                        break
                    prev = ev['s']
                    try:
                        self._exec(ev)
                    except Exception:
                        pass
                    if on_prog:
                        on_prog(i + 1, total, lp + 1)

            self.playing = False
            # ESC hook temizle
            if self._kb_hook:
                user32.UnhookWindowsHookEx(self._kb_hook)
                self._kb_hook = None
            if on_done:
                on_done()

        threading.Thread(target=worker, daemon=True).start()

    def stop(self):
        self.stop_flag = True
        self.playing = False

    def _exec(self, ev):
        t = ev['t']

        if t == 'mm':
            # Fare hareket
            ax = int(ev['x'] * 65535 / self._sx)
            ay = int(ev['y'] * 65535 / self._sy)
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.union.mi.dx = ax
            inp.union.mi.dy = ay
            inp.union.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
            inp.union.mi.mouseData = 0
            inp.union.mi.time = 0
            inp.union.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

        elif t == 'md':
            # Fare tikla (bas)
            ax = int(ev['x'] * 65535 / self._sx)
            ay = int(ev['y'] * 65535 / self._sy)
            flag = {'l': MOUSEEVENTF_LEFTDOWN, 'r': MOUSEEVENTF_RIGHTDOWN, 'm': MOUSEEVENTF_MIDDLEDOWN}.get(ev['b'], MOUSEEVENTF_LEFTDOWN)
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.union.mi.dx = ax
            inp.union.mi.dy = ay
            inp.union.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | flag
            inp.union.mi.mouseData = 0
            inp.union.mi.time = 0
            inp.union.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

        elif t == 'mu':
            # Fare tikla (birak)
            ax = int(ev['x'] * 65535 / self._sx)
            ay = int(ev['y'] * 65535 / self._sy)
            flag = {'l': MOUSEEVENTF_LEFTUP, 'r': MOUSEEVENTF_RIGHTUP, 'm': MOUSEEVENTF_MIDDLEUP}.get(ev['b'], MOUSEEVENTF_LEFTUP)
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.union.mi.dx = ax
            inp.union.mi.dy = ay
            inp.union.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | flag
            inp.union.mi.mouseData = 0
            inp.union.mi.time = 0
            inp.union.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

        elif t == 'mw':
            # Fare scroll
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.union.mi.dx = 0
            inp.union.mi.dy = 0
            inp.union.mi.dwFlags = MOUSEEVENTF_WHEEL
            inp.union.mi.mouseData = ev['d']
            inp.union.mi.time = 0
            inp.union.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

        elif t == 'kd':
            # Klavye bas
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.union.ki.wVk = ev['vk']
            inp.union.ki.wScan = ev.get('sc', 0)
            inp.union.ki.dwFlags = 0
            inp.union.ki.time = 0
            inp.union.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

        elif t == 'ku':
            # Klavye birak
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.union.ki.wVk = ev['vk']
            inp.union.ki.wScan = ev.get('sc', 0)
            inp.union.ki.dwFlags = KEYEVENTF_KEYUP
            inp.union.ki.time = 0
            inp.union.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'v': '5', 'n': len(self.events), 'e': self.events}, f)

    def load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.events = d['e']
        return d.get('n', len(self.events))


# ══════════════════════════════════════
#  ARAYUZ - BASIT TEK BOLUM
# ══════════════════════════════════════
class AutoFlowApp:
    BG = "#f0f4f8"
    CARD = "#ffffff"
    BLUE = "#2563eb"
    RED = "#dc2626"
    GREEN = "#16a34a"
    ORANGE = "#ea580c"
    PURPLE = "#7c3aed"
    TEXT = "#1e293b"
    TEXT2 = "#64748b"
    TEXT3 = "#94a3b8"
    BORDER = "#e2e8f0"

    def __init__(self, root):
        self.root = root
        self.engine = MacroEngine()
        self.engine.on_esc = lambda: self.root.after(0, self._stop)
        self._build()

    def _build(self):
        self.root.configure(bg=self.BG)
        main = tk.Frame(self.root, bg=self.BG, padx=20, pady=12)
        main.pack(fill='both', expand=True)

        # Baslik
        tk.Label(main, text="AutoFlow", font=("Segoe UI", 20, "bold"),
                 fg=self.BLUE, bg=self.BG).pack(anchor='w')
        tk.Label(main, text="EBYS Otomasyon - Kaydet, Donguye Al, Calistir",
                 font=("Segoe UI", 9), fg=self.TEXT3, bg=self.BG).pack(anchor='w', pady=(0, 12))

        # ══════════════════════════════════
        #  TEK BOLUM - DONGU KAYDET/OYNAT
        # ══════════════════════════════════
        card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                        highlightthickness=1, padx=20, pady=16)
        card.pack(fill='x', pady=(0, 10))

        # Ust satir: Kaydet + Yukle + Dongu sayisi
        row1 = tk.Frame(card, bg=self.CARD)
        row1.pack(fill='x', pady=(0, 12))

        self.btn_rec = tk.Button(row1, text="KAYDET",
            font=("Segoe UI", 12, "bold"), bg=self.RED, fg="white",
            activebackground="#ef4444", activeforeground="white",
            relief='flat', cursor='hand2', padx=20, pady=10,
            command=self._toggle_rec)
        self.btn_rec.pack(side='left', padx=(0, 6))

        tk.Button(row1, text="Dosyaya Kaydet",
            font=("Segoe UI", 10), bg="#f1f5f9", fg=self.TEXT,
            relief='flat', cursor='hand2', padx=12, pady=10,
            command=self._save).pack(side='left', padx=(0, 6))

        tk.Button(row1, text="Dosyadan Ac",
            font=("Segoe UI", 10), bg="#f1f5f9", fg=self.TEXT,
            relief='flat', cursor='hand2', padx=12, pady=10,
            command=self._load).pack(side='left')

        # Dongu sayisi
        row2 = tk.Frame(card, bg=self.CARD)
        row2.pack(fill='x', pady=(0, 12))

        tk.Label(row2, text="Kac kez tekrar etsin?",
                 font=("Segoe UI", 11, "bold"), fg=self.TEXT, bg=self.CARD).pack(side='left')

        self.loop_var = tk.StringVar(value="100")

        for v in ["1", "10", "50", "100", "500"]:
            tk.Button(row2, text=v, font=("Segoe UI", 10, "bold"),
                      bg="#f1f5f9", fg=self.TEXT, relief='flat', cursor='hand2',
                      width=4, pady=4,
                      command=lambda x=v: self.loop_var.set(x)
                      ).pack(side='left', padx=2)

        tk.Entry(row2, textvariable=self.loop_var, font=("Segoe UI", 12, "bold"),
                 width=5, bg="#f8fafc", fg=self.TEXT, relief='solid', bd=1,
                 justify='center').pack(side='left', padx=(8, 0), ipady=3)

        # Hiz
        row3 = tk.Frame(card, bg=self.CARD)
        row3.pack(fill='x', pady=(0, 12))

        tk.Label(row3, text="Hiz:",
                 font=("Segoe UI", 10, "bold"), fg=self.TEXT, bg=self.CARD).pack(side='left', padx=(0, 8))

        self.speed_var = tk.StringVar(value="1.0")
        for label, val in [("Yavas (0.5x)", "0.5"), ("Normal (1x)", "1.0"),
                            ("Hizli (2x)", "2.0"), ("Cok Hizli (5x)", "5.0")]:
            tk.Button(row3, text=label, font=("Segoe UI", 9),
                      bg="#f1f5f9", fg=self.TEXT, relief='flat', cursor='hand2',
                      padx=8, pady=4,
                      command=lambda v=val: self.speed_var.set(v)
                      ).pack(side='left', padx=2)

        # BUYUK OYNAT BUTONU
        self.btn_play = tk.Button(card,
            text="DONGUYU BASLAT",
            font=("Segoe UI", 14, "bold"),
            bg=self.GREEN, fg="white",
            activebackground="#22c55e", activeforeground="white",
            relief='flat', cursor='hand2', pady=14,
            command=self._play)
        self.btn_play.pack(fill='x', pady=(0, 8))

        # DURDUR
        self.btn_stop = tk.Button(card,
            text="DURDUR  (ESC tusa basin)",
            font=("Segoe UI", 12, "bold"),
            bg="#fef2f2", fg=self.RED,
            activebackground="#fee2e2", activeforeground=self.RED,
            relief='flat', cursor='hand2', pady=10,
            command=self._stop, state='disabled')
        self.btn_stop.pack(fill='x')

        # ══════════════════════════════════
        #  DURUM
        # ══════════════════════════════════
        stat = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                        highlightthickness=1, padx=20, pady=10)
        stat.pack(fill='x', pady=(0, 8))

        self.lbl_status = tk.Label(stat, text="Hazir",
                                    font=("Segoe UI", 12), fg=self.BLUE, bg=self.CARD)
        self.lbl_status.pack(anchor='w')

        self.lbl_detail = tk.Label(stat, text="KAYDET butonuna basip islemi bir kez yapin",
                                    font=("Segoe UI", 9), fg=self.TEXT3, bg=self.CARD)
        self.lbl_detail.pack(anchor='w')

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("G.Horizontal.TProgressbar",
                         troughcolor="#e2e8f0", background=self.GREEN, thickness=8)
        self.progress = ttk.Progressbar(stat, mode='determinate',
                                         style="G.Horizontal.TProgressbar")

        # Temizle
        tk.Button(main, text="Temizle", font=("Segoe UI", 9),
                  bg="#e2e8f0", fg=self.RED, relief='flat', cursor='hand2',
                  padx=10, pady=3, command=self._clear).pack(anchor='w', pady=(0, 4))

        # Bilgi
        info = tk.Frame(main, bg=self.BG)
        info.pack(fill='x')
        tk.Label(info, text="ESC = Durdur  |  Ctrl+C/V/A tam destek  |  Yonetici olarak calistirin",
                 font=("Segoe UI", 8), fg=self.TEXT3, bg=self.BG).pack(anchor='w')

    # ── Kayit ──
    def _toggle_rec(self):
        if self.engine.playing:
            return
        if not self.engine.recording:
            self.engine.rec_start()
            self.btn_rec.configure(text="KAYDI DURDUR", bg=self.ORANGE)
            self.btn_play.configure(state='disabled')
            self.btn_stop.configure(state='normal')
            self.lbl_status.configure(text="KAYDEDILIYOR...", fg=self.RED)
            self.lbl_detail.configure(text="Islemlerinizi yapin, bitince ESC basin veya butona tiklayin")
            self._tick()
        else:
            self._stop_rec()

    def _stop_rec(self):
        if not self.engine.recording:
            return
        self.engine.rec_stop()
        # ESC olaylarini kayittan cikar
        self.engine.events = [e for e in self.engine.events
                               if not (e['t'] in ('kd', 'ku') and e.get('vk') == VK_ESCAPE)]
        n = len(self.engine.events)
        d = self.engine.events[-1]['s'] if self.engine.events else 0
        self.btn_rec.configure(text="KAYDET", bg=self.RED)
        self.btn_play.configure(state='normal')
        self.btn_stop.configure(state='disabled')
        self.lbl_status.configure(text=f"Kayit tamam! {n} hareket, {d:.1f} saniye", fg=self.GREEN)
        self.lbl_detail.configure(text="Simdi tekrar sayisini secip DONGUYU BASLAT basin")

    # ── Oynat ──
    def _play(self):
        if self.engine.recording or self.engine.playing:
            return
        if not self.engine.events:
            messagebox.showinfo("Bilgi",
                "Once bir kayit yapin!\n\n"
                "1. KAYDET butonuna basin\n"
                "2. EBYS'de islemi bir kez yapin\n"
                "3. ESC tusuna basin (kayit durur)\n"
                "4. Tekrar sayisini girip DONGUYU BASLAT basin")
            return
        try:
            self.engine.loops = max(1, int(self.loop_var.get()))
        except ValueError:
            self.engine.loops = 1
        try:
            self.engine.speed = float(self.speed_var.get())
        except ValueError:
            self.engine.speed = 1.0

        self.btn_rec.configure(state='disabled')
        self.btn_play.configure(state='disabled')
        self.btn_stop.configure(state='normal')
        self.progress.pack(fill='x', pady=(8, 0))
        self.progress['maximum'] = len(self.engine.events)
        self.progress['value'] = 0
        lt = f" ({self.engine.loops}x)" if self.engine.loops > 1 else ""
        self.lbl_status.configure(text=f"Calisiyor{lt}...", fg=self.BLUE)
        self.lbl_detail.configure(text="Durdurmak icin ESC tusuna basin")
        self.engine.play(on_prog=self._prog, on_done=self._done)

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
            self.lbl_detail.configure(text=f"{self.engine.loops} islem basariyla tamamlandi")
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

    def _enable_all(self):
        self.btn_rec.configure(state='normal', text="KAYDET", bg=self.RED)
        self.btn_play.configure(state='normal')
        self.btn_stop.configure(state='disabled')

    def _save(self):
        if not self.engine.events:
            messagebox.showinfo("Bilgi", "Kaydedilecek makro yok!")
            return
        fp = filedialog.asksaveasfilename(title="Kaydet", defaultextension=".autoflow",
            filetypes=[("AutoFlow", "*.autoflow"), ("Hepsi", "*.*")])
        if fp:
            self.engine.save(fp)
            self.lbl_status.configure(text="Kaydedildi!", fg=self.GREEN)

    def _load(self):
        fp = filedialog.askopenfilename(title="Ac",
            filetypes=[("AutoFlow", "*.autoflow"), ("Hepsi", "*.*")])
        if fp:
            n = self.engine.load(fp)
            self.lbl_status.configure(text=f"Yuklendi: {n} hareket", fg=self.GREEN)
            self.lbl_detail.configure(text="Tekrar sayisini secip DONGUYU BASLAT basin")

    def _clear(self):
        if self.engine.events and messagebox.askyesno("Onay", "Silinsin mi?"):
            self.engine.events = []
            self.lbl_status.configure(text="Temizlendi", fg=self.TEXT2)
            self.lbl_detail.configure(text="")

    def _tick(self):
        if self.engine.recording:
            el = time.time() - self.engine.start_time
            n = len(self.engine.events)
            self.lbl_detail.configure(text=f"{el:.1f}s | {n} hareket | ESC = durdur")
            self.root.after(100, self._tick)


def main():
    root = tk.Tk()
    root.title("AutoFlow - EBYS Otomasyon")
    root.geometry("560x580")
    root.minsize(480, 520)
    root.configure(bg="#f0f4f8")
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    AutoFlowApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
