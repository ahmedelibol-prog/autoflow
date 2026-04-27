#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoFlow v10.0 - Otomatik Tekrar Yazilimi
Mouse konumu duzeltildi - direkt Windows API kullanimi
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import json
import os
import sys
import ctypes
import hashlib
from ctypes import wintypes

# DPI AWARENESS - Program baslamadan ONCE ayarla
# Per-Monitor V2 = en dogru piksel koordinatlari
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
except:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass

# Windows API
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def ensure_libs():
    need = []
    try:
        import keyboard
    except ImportError:
        need.append('keyboard')
    try:
        import mouse
    except ImportError:
        need.append('mouse')
    if need:
        import subprocess
        for lib in need:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', lib])

ensure_libs()
import keyboard
import mouse


# ══════════════════════════════════════════
#  WINDOWS DIRECT MOUSE API
# ══════════════════════════════════════════
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_pos():
    """Fare konumunu gercek piksel cinsinden al (DPI-aware)"""
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def set_cursor_pos(x, y):
    """Fareyi gercek piksel konumuna tasi (DPI-aware)"""
    user32.SetCursorPos(int(x), int(y))


# Windows SendInput
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class MINPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


def mouse_btn_event(flag):
    """Fare dugmesi olayini gonder - konumdan bagimsiz"""
    inp = MINPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = 0
    inp.u.mi.dy = 0
    inp.u.mi.mouseData = 0
    inp.u.mi.dwFlags = flag
    inp.u.mi.time = 0
    inp.u.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def mouse_wheel(delta):
    """Fare tekerlegi"""
    inp = MINPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = 0
    inp.u.mi.dy = 0
    inp.u.mi.mouseData = int(delta * 120)
    inp.u.mi.dwFlags = MOUSEEVENTF_WHEEL
    inp.u.mi.time = 0
    inp.u.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


BTN_DOWN = {'left': MOUSEEVENTF_LEFTDOWN, 'right': MOUSEEVENTF_RIGHTDOWN,
            'middle': MOUSEEVENTF_MIDDLEDOWN}
BTN_UP = {'left': MOUSEEVENTF_LEFTUP, 'right': MOUSEEVENTF_RIGHTUP,
          'middle': MOUSEEVENTF_MIDDLEUP}


# ══════════════════════════════════════════
#  MAKRO MOTORU
# ══════════════════════════════════════════
class MacroEngine:
    def __init__(self):
        self.recording = False
        self.playing = False
        self.stop_flag = False
        self.kb_events = []
        self.mouse_events = []
        self.speed = 1.0
        self.loops = 1
        self.on_stop = None
        self._esc_hook = None

    def rec_start(self):
        self.kb_events = []
        self.mouse_events = []
        self.recording = True

        keyboard.start_recording()

        # Fare icin ozel kayit - her move olayinda GERCEK konumu al
        self._mouse_recorded = []
        self._last_move_rec_time = 0
        mouse.hook(self._mouse_hook)

        self._esc_hook = keyboard.on_press_key('esc', self._esc_pressed, suppress=False)

    def _mouse_hook(self, event):
        if not self.recording:
            return

        cls_name = event.__class__.__name__

        # Move olaylarinda GERCEK piksel konumunu al (Windows API ile)
        if cls_name == 'MoveEvent':
            # Hizli hareket kaydi - 15ms'de bir
            now = time.time()
            if now - self._last_move_rec_time < 0.015:
                return
            self._last_move_rec_time = now

            # DPI-aware gercek konum
            real_x, real_y = get_cursor_pos()
            # Yeni event olustur (gercek koordinatla)
            new_event = mouse.MoveEvent(x=real_x, y=real_y, time=event.time)
            self._mouse_recorded.append(new_event)
        else:
            self._mouse_recorded.append(event)

    def _esc_pressed(self, e):
        if self.on_stop:
            self.on_stop()

    def rec_stop(self):
        if not self.recording:
            return
        self.recording = False

        try:
            self.kb_events = keyboard.stop_recording()
        except:
            self.kb_events = []

        try:
            mouse.unhook(self._mouse_hook)
        except:
            pass

        self.mouse_events = list(self._mouse_recorded)

        if self._esc_hook:
            try:
                keyboard.unhook(self._esc_hook)
            except:
                pass
            self._esc_hook = None

        self.kb_events = [e for e in self.kb_events
                          if not (hasattr(e, 'name') and e.name == 'esc')]

    def has_recording(self):
        return len(self.kb_events) > 0 or len(self.mouse_events) > 0

    def event_count(self):
        return len(self.kb_events) + len(self.mouse_events)

    def play(self, on_prog=None, on_done=None):
        if not self.has_recording():
            return

        self.playing = True
        self.stop_flag = False

        self._esc_hook = keyboard.on_press_key('esc', lambda e: self._esc_stop(),
                                                suppress=False)

        all_events = []
        for e in self.kb_events:
            all_events.append(('kb', e, e.time))
        for e in self.mouse_events:
            all_events.append(('mouse', e, e.time))
        all_events.sort(key=lambda x: x[2])

        if all_events:
            start_time = all_events[0][2]
            all_events = [(t, e, ts - start_time) for t, e, ts in all_events]

        def worker():
            for lp in range(self.loops):
                if self.stop_flag:
                    break

                start = time.time()
                for i, (typ, event, rel_time) in enumerate(all_events):
                    if self.stop_flag:
                        break

                    target = rel_time / self.speed
                    elapsed = time.time() - start
                    wait = target - elapsed
                    if wait > 0:
                        w = 0.0
                        while w < wait and not self.stop_flag:
                            time.sleep(min(0.01, wait - w))
                            w += 0.01
                    if self.stop_flag:
                        break

                    try:
                        if typ == 'kb':
                            self._play_kb(event)
                        else:
                            self._play_mouse(event)
                    except Exception:
                        pass

                    if on_prog:
                        on_prog(i + 1, len(all_events), lp + 1)

            self.playing = False
            if self._esc_hook:
                try:
                    keyboard.unhook(self._esc_hook)
                except:
                    pass
                self._esc_hook = None
            if on_done:
                on_done()

        threading.Thread(target=worker, daemon=True).start()

    def _esc_stop(self):
        self.stop_flag = True

    def _play_kb(self, event):
        try:
            if event.event_type == 'down':
                keyboard.press(event.scan_code)
            elif event.event_type == 'up':
                keyboard.release(event.scan_code)
        except:
            try:
                if event.name:
                    if event.event_type == 'down':
                        keyboard.press(event.name)
                    elif event.event_type == 'up':
                        keyboard.release(event.name)
            except:
                pass

    def _play_mouse(self, event):
        """Direkt Windows API ile fare oynatma - GERCEK PIKSEL"""
        cls_name = event.__class__.__name__

        if cls_name == 'MoveEvent':
            # DIREKT set_cursor_pos - DPI-aware, piksel piksel
            set_cursor_pos(event.x, event.y)

        elif cls_name == 'ButtonEvent':
            btn = event.button
            et = event.event_type

            if et == 'down' and btn in BTN_DOWN:
                mouse_btn_event(BTN_DOWN[btn])
            elif et == 'up' and btn in BTN_UP:
                mouse_btn_event(BTN_UP[btn])
            elif et == 'double' and btn in BTN_DOWN:
                # Cift tiklama = 2 kez bas-birak
                mouse_btn_event(BTN_DOWN[btn])
                mouse_btn_event(BTN_UP[btn])
                time.sleep(0.05)
                mouse_btn_event(BTN_DOWN[btn])
                mouse_btn_event(BTN_UP[btn])

        elif cls_name == 'WheelEvent':
            mouse_wheel(event.delta)

    def stop(self):
        self.stop_flag = True
        self.playing = False
        if self._esc_hook:
            try:
                keyboard.unhook(self._esc_hook)
            except:
                pass
            self._esc_hook = None

    def save(self, path):
        data = {
            'v': '10',
            'kb': [self._kb_to_dict(e) for e in self.kb_events],
            'mouse': [self._mouse_to_dict(e) for e in self.mouse_events]
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.kb_events = [self._dict_to_kb(x) for x in d.get('kb', [])]
        self.mouse_events = [self._dict_to_mouse(x) for x in d.get('mouse', [])]
        self.mouse_events = [e for e in self.mouse_events if e is not None]
        return self.event_count()

    def _kb_to_dict(self, e):
        return {
            'event_type': e.event_type,
            'scan_code': e.scan_code,
            'name': e.name if e.name else '',
            'time': e.time
        }

    def _dict_to_kb(self, d):
        ke = keyboard.KeyboardEvent(
            event_type=d['event_type'],
            scan_code=d['scan_code'],
            name=d.get('name') or None
        )
        ke.time = d['time']
        return ke

    def _mouse_to_dict(self, e):
        cls_name = e.__class__.__name__
        base = {'cls': cls_name, 'time': e.time}
        if cls_name == 'MoveEvent':
            base.update({'x': e.x, 'y': e.y})
        elif cls_name == 'ButtonEvent':
            base.update({'event_type': e.event_type, 'button': e.button})
        elif cls_name == 'WheelEvent':
            base.update({'delta': e.delta})
        return base

    def _dict_to_mouse(self, d):
        cls_name = d['cls']
        t = d['time']
        try:
            if cls_name == 'MoveEvent':
                return mouse.MoveEvent(x=d['x'], y=d['y'], time=t)
            elif cls_name == 'ButtonEvent':
                return mouse.ButtonEvent(event_type=d['event_type'], button=d['button'], time=t)
            elif cls_name == 'WheelEvent':
                return mouse.WheelEvent(delta=d['delta'], time=t)
        except:
            return None
        return None


# ══════════════════════════════════════════
#  ARAYUZ
# ══════════════════════════════════════════
class AutoFlowApp:
    BG = "#f5f6fa"
    CARD = "#ffffff"
    WIN_BLUE = "#2b579a"         # Office koyu mavi
    WIN_BLUE_HOVER = "#1e3f73"
    WIN_BLUE_LIGHT = "#eef2f9"
    WIN_RED = "#4a5568"          # Koyu gri-lacivert (durdur)
    WIN_RED_HOVER = "#2d3748"
    WIN_GREEN = "#3a7ca5"        # Celik mavisi (oynat)
    WIN_GREEN_HOVER = "#2c6080"
    WIN_ORANGE = "#8b6914"       # Koyu hardal (uyari)
    TEXT = "#2d3436"
    TEXT2 = "#636e72"
    TEXT3 = "#b2bec3"
    BORDER = "#dfe6e9"
    BORDER_LIGHT = "#f0f3f5"

    MACROS_DIR = os.path.join(os.path.expanduser("~"), ".autoflow")

    def __init__(self, root):
        self.root = root
        self.engine = MacroEngine()
        self.engine.on_stop = lambda: self.root.after(0, self._stop)
        os.makedirs(self.MACROS_DIR, exist_ok=True)
        self._build()

    def _slot_path(self):
        return os.path.join(self.MACROS_DIR, "slot1.autoflow")

    def _slot_info(self):
        p = self._slot_path()
        if os.path.exists(p):
            try:
                with open(p) as f:
                    d = json.load(f)
                total = len(d.get('kb', [])) + len(d.get('mouse', []))
                return f"● {total} hareket kayıtlı"
            except:
                pass
        return "○ Boş"

    def _build(self):
        self.root.configure(bg=self.BG)
        main = tk.Frame(self.root, bg=self.BG, padx=24, pady=16)
        main.pack(fill='both', expand=True)

        # BASLIK
        hdr = tk.Frame(main, bg=self.BG)
        hdr.pack(fill='x', pady=(0, 12))

        title_frame = tk.Frame(hdr, bg=self.BG)
        title_frame.pack(side='left')

        tk.Label(title_frame, text="Auto", font=("Segoe UI", 28, "bold"),
                 fg=self.TEXT, bg=self.BG).pack(side='left')
        tk.Label(title_frame, text="Flow", font=("Segoe UI", 28, "bold"),
                 fg=self.WIN_BLUE, bg=self.BG).pack(side='left')

        tk.Label(hdr, text="Otomatik Tekrar Yazılımı", font=("Segoe UI", 11),
                 fg=self.TEXT2, bg=self.BG).pack(side='left', padx=(16, 0), pady=(14, 0))

        # TALIMAT
        info_card = tk.Frame(main, bg=self.WIN_BLUE_LIGHT,
                             highlightbackground=self.WIN_BLUE, highlightthickness=1)
        info_card.pack(fill='x', pady=(0, 12))
        info_inner = tk.Frame(info_card, bg=self.WIN_BLUE_LIGHT, padx=18, pady=12)
        info_inner.pack(fill='x')

        tk.Label(info_inner, text="NASIL KULLANILIR?",
                 font=("Segoe UI", 9, "bold"), fg=self.WIN_BLUE,
                 bg=self.WIN_BLUE_LIGHT).pack(anchor='w')
        tk.Label(info_inner,
                 text="1) KAYDET butonuna basın   2) İşlemi bir kez yapın   3) ESC'e basın\n"
                      "4) Tekrar sayısını girin   5) OYNAT butonuna basın — otomatik tekrar eder",
                 font=("Segoe UI", 9), fg=self.TEXT, bg=self.WIN_BLUE_LIGHT,
                 justify='left').pack(anchor='w', pady=(4, 0))

        # SLOT
        slot_card = tk.Frame(main, bg=self.CARD,
                             highlightbackground=self.BORDER, highlightthickness=1)
        slot_card.pack(fill='x', pady=(0, 10))
        slot_inner = tk.Frame(slot_card, bg=self.CARD, padx=20, pady=16)
        slot_inner.pack(fill='x')

        top = tk.Frame(slot_inner, bg=self.CARD)
        top.pack(fill='x', pady=(0, 14))

        canvas = tk.Canvas(top, width=4, height=24, bg=self.CARD, highlightthickness=0)
        canvas.pack(side='left', padx=(0, 12))
        canvas.create_rectangle(0, 0, 4, 24, fill=self.WIN_BLUE, outline="")

        tk.Label(top, text="KAYIT 1", font=("Segoe UI", 16, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(side='left')

        self.lbl_slot = tk.Label(top, text=self._slot_info(),
                                  font=("Segoe UI", 10), fg=self.TEXT2, bg=self.CARD)
        self.lbl_slot.pack(side='right')

        # Ana butonlar
        main_btns = tk.Frame(slot_inner, bg=self.CARD)
        main_btns.pack(fill='x', pady=(0, 10))

        self.btn_rec = tk.Button(main_btns, text="● KAYDET",
            font=("Segoe UI", 12, "bold"),
            bg="#2b579a", fg="white",
            activebackground="#1e3f73", activeforeground="white",
            relief='flat', cursor='hand2', bd=0, pady=14,
            command=self._rec)
        self.btn_rec.pack(side='left', fill='x', expand=True, padx=(0, 5))

        self.btn_play = tk.Button(main_btns, text="▶ OYNAT",
            font=("Segoe UI", 12, "bold"),
            bg=self.WIN_GREEN, fg="white",
            activebackground=self.WIN_GREEN_HOVER, activeforeground="white",
            relief='flat', cursor='hand2', bd=0, pady=14,
            command=self._play)
        self.btn_play.pack(side='left', fill='x', expand=True, padx=(5, 0))

        # Dosya butonlari
        file_btns = tk.Frame(slot_inner, bg=self.CARD)
        file_btns.pack(fill='x')

        self.btn_save = tk.Button(file_btns, text="Dosyaya Kaydet",
            font=("Segoe UI", 10),
            bg=self.BORDER_LIGHT, fg=self.TEXT,
            activebackground=self.BORDER, activeforeground=self.TEXT,
            relief='flat', cursor='hand2', bd=0, pady=8,
            command=self._save_file)
        self.btn_save.pack(side='left', fill='x', expand=True, padx=(0, 4))

        self.btn_load = tk.Button(file_btns, text="Dosyadan Aç",
            font=("Segoe UI", 10),
            bg=self.BORDER_LIGHT, fg=self.TEXT,
            activebackground=self.BORDER, activeforeground=self.TEXT,
            relief='flat', cursor='hand2', bd=0, pady=8,
            command=self._load_file)
        self.btn_load.pack(side='left', fill='x', expand=True, padx=(4, 0))

        # AYARLAR
        set_card = tk.Frame(main, bg=self.CARD,
                            highlightbackground=self.BORDER, highlightthickness=1)
        set_card.pack(fill='x', pady=(0, 10))
        set_inner = tk.Frame(set_card, bg=self.CARD, padx=20, pady=14)
        set_inner.pack(fill='x')

        r1 = tk.Frame(set_inner, bg=self.CARD)
        r1.pack(fill='x', pady=(0, 12))

        tk.Label(r1, text="Tekrar sayısı:", font=("Segoe UI", 11, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(side='left', padx=(0, 12))

        self.loop_var = tk.StringVar(value="100")
        for v in ["1", "10", "50", "100", "500"]:
            tk.Button(r1, text=v, font=("Segoe UI", 10, "bold"),
                      bg=self.BORDER_LIGHT, fg=self.TEXT,
                      activebackground=self.WIN_BLUE, activeforeground="white",
                      relief='flat', cursor='hand2', bd=0, width=4, pady=4,
                      command=lambda x=v: self.loop_var.set(x)
                      ).pack(side='left', padx=2)

        tk.Entry(r1, textvariable=self.loop_var, font=("Segoe UI", 12, "bold"),
                 width=7, bg=self.CARD, fg=self.TEXT,
                 insertbackground=self.TEXT,
                 relief='solid', bd=1, highlightthickness=1,
                 highlightbackground=self.BORDER, highlightcolor=self.WIN_BLUE,
                 justify='center').pack(side='left', padx=(10, 0), ipady=5)

        r2 = tk.Frame(set_inner, bg=self.CARD)
        r2.pack(fill='x')

        tk.Label(r2, text="Oynatma hızı:", font=("Segoe UI", 11, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(side='left', padx=(0, 12))

        self.speed_var = tk.StringVar(value="1.0")
        for l, v in [("Yavaş", "0.5"), ("Normal", "1.0"), ("Hızlı", "2.0"), ("Maksimum", "5.0")]:
            tk.Button(r2, text=l, font=("Segoe UI", 10),
                      bg=self.BORDER_LIGHT, fg=self.TEXT,
                      activebackground=self.WIN_BLUE, activeforeground="white",
                      relief='flat', cursor='hand2', bd=0, padx=14, pady=4,
                      command=lambda x=v: self.speed_var.set(x)
                      ).pack(side='left', padx=2)

        # DURDUR - BEYAZ YAZI
        self.btn_stop = tk.Button(main,
            text="⏹  DURDUR  (ESC tuşu)",
            font=("Segoe UI", 13, "bold"),
            bg=self.WIN_RED, fg="white",
            activebackground=self.WIN_RED_HOVER, activeforeground="white",
            disabledforeground="white",
            relief='flat', cursor='hand2', bd=0, pady=14,
            command=self._stop, state='disabled')
        self.btn_stop.pack(fill='x', pady=(0, 10))

        # DURUM
        stat_card = tk.Frame(main, bg=self.CARD,
                             highlightbackground=self.BORDER, highlightthickness=1)
        stat_card.pack(fill='x')
        stat_inner = tk.Frame(stat_card, bg=self.CARD, padx=20, pady=14)
        stat_inner.pack(fill='x')

        self.lbl_status = tk.Label(stat_inner, text="✓ Hazır",
                                    font=("Segoe UI", 13, "bold"),
                                    fg=self.WIN_GREEN, bg=self.CARD)
        self.lbl_status.pack(anchor='w')

        self.lbl_detail = tk.Label(stat_inner,
                                    text="KAYDET butonuna basarak başlayın",
                                    font=("Segoe UI", 9), fg=self.TEXT2, bg=self.CARD)
        self.lbl_detail.pack(anchor='w', pady=(3, 0))

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Win.Horizontal.TProgressbar",
                         troughcolor=self.BORDER_LIGHT, background=self.WIN_BLUE,
                         borderwidth=0, thickness=8)
        self.progress = ttk.Progressbar(stat_inner, mode='determinate',
                                         style="Win.Horizontal.TProgressbar")

        tk.Label(main, text="AutoFlow v10.0",
                 font=("Segoe UI", 8), fg=self.TEXT3, bg=self.BG).pack(pady=(6, 0))

    # ═══════════════════════════════════════
    def _rec(self):
        if self.engine.recording or self.engine.playing:
            return

        self.lbl_status.configure(text="⏱ 3 saniye sonra kayıt başlıyor...",
                                   fg=self.WIN_ORANGE)
        self.lbl_detail.configure(text="KAYIT 1 için hazırlanın")
        self._disable_all()

        self.root.after(3000, self._rec_start_now)

    def _rec_start_now(self):
        try:
            self.engine.rec_start()
        except Exception as e:
            messagebox.showerror("Hata", f"Kayıt başlatılamadı: {e}\n\n"
                                          "Programı YÖNETİCİ olarak çalıştırın!")
            self._enable_all()
            return

        self.btn_stop.configure(state='normal')
        self.lbl_status.configure(text="● KAYDEDİLİYOR", fg=self.WIN_RED)
        self.lbl_detail.configure(text="İşlemlerinizi yapın, bitince ESC tuşuna basın")
        self._tick()

    def _stop_rec(self):
        if not self.engine.recording:
            return

        self.engine.rec_stop()

        if self.engine.has_recording():
            try:
                self.engine.save(self._slot_path())
                self.lbl_slot.configure(text=self._slot_info())
                n = self.engine.event_count()
                self.lbl_status.configure(text="✓ Kayıt tamamlandı!", fg=self.WIN_GREEN)
                self.lbl_detail.configure(text=f"{n} hareket kaydedildi — OYNAT ile çalıştırın")
            except Exception as e:
                messagebox.showerror("Hata", str(e))
        else:
            self.lbl_status.configure(text="⚠ Kayıt iptal edildi", fg=self.WIN_ORANGE)
            self.lbl_detail.configure(text="Hareket kaydedilmedi")

        self._enable_all()

    def _play(self):
        if self.engine.recording or self.engine.playing:
            return

        path = self._slot_path()
        if not os.path.exists(path):
            messagebox.showinfo("Boş Slot",
                "KAYIT 1 boş!\n\nÖnce KAYDET butonuna basıp işlem kaydedin.")
            return

        try:
            self.engine.load(path)
        except Exception as e:
            messagebox.showerror("Hata", f"Slot yüklenemedi: {e}")
            return

        try:
            self.engine.loops = max(1, int(self.loop_var.get()))
        except:
            self.engine.loops = 1
        try:
            self.engine.speed = float(self.speed_var.get())
        except:
            self.engine.speed = 1.0

        self._disable_all()
        self.btn_stop.configure(state='normal')
        self.progress.pack(fill='x', pady=(10, 0))
        self.progress['maximum'] = self.engine.event_count()
        self.progress['value'] = 0

        lt = f" ({self.engine.loops}x tekrar)" if self.engine.loops > 1 else ""
        self.lbl_status.configure(text=f"▶ Çalışıyor{lt}", fg=self.WIN_BLUE)
        self.lbl_detail.configure(text="Durdurmak için ESC tuşuna basın")

        self.engine.play(on_prog=self._prog, on_done=self._done)

    def _save_file(self):
        if self.engine.recording or self.engine.playing:
            return

        path = self._slot_path()
        if not os.path.exists(path):
            messagebox.showinfo("Boş Slot", "KAYIT 1 boş!")
            return

        fp = filedialog.asksaveasfilename(
            title="Dosyaya Kaydet",
            defaultextension=".autoflow",
            filetypes=[("AutoFlow Makro", "*.autoflow"), ("Hepsi", "*.*")])

        if fp:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                with open(fp, 'w') as f:
                    json.dump(data, f)
                self.lbl_status.configure(text=f"✓ Kaydedildi", fg=self.WIN_GREEN)
                self.lbl_detail.configure(text=os.path.basename(fp))
            except Exception as e:
                messagebox.showerror("Hata", str(e))

    def _load_file(self):
        if self.engine.recording or self.engine.playing:
            return

        fp = filedialog.askopenfilename(
            title="Dosyadan Aç",
            filetypes=[("AutoFlow Makro", "*.autoflow"), ("Hepsi", "*.*")])

        if fp:
            try:
                with open(fp, 'r') as f:
                    data = json.load(f)
                with open(self._slot_path(), 'w') as f:
                    json.dump(data, f)
                self.lbl_slot.configure(text=self._slot_info())
                self.lbl_status.configure(text="✓ Dosya yüklendi", fg=self.WIN_GREEN)
                self.lbl_detail.configure(text=os.path.basename(fp))
            except Exception as e:
                messagebox.showerror("Hata", str(e))

    def _prog(self, cur, tot, lp):
        def u():
            self.progress['value'] = cur
            pct = int(cur / tot * 100)
            lt = f" | Tekrar {lp}/{self.engine.loops}" if self.engine.loops > 1 else ""
            self.lbl_detail.configure(text=f"%{pct} tamamlandı{lt}  —  ESC = durdur")
        self.root.after(0, u)

    def _done(self):
        def u():
            self._enable_all()
            self.progress.pack_forget()
            self.lbl_status.configure(text="✓ Tamamlandı!", fg=self.WIN_GREEN)
            self.lbl_detail.configure(text=f"{self.engine.loops} tekrar başarıyla tamamlandı")
        self.root.after(0, u)

    def _stop(self):
        if self.engine.recording:
            self._stop_rec()
            return
        if self.engine.playing:
            self.engine.stop()
            self._enable_all()
            self.progress.pack_forget()
            self.lbl_status.configure(text="⏹ Durduruldu", fg=self.WIN_ORANGE)
            self.lbl_detail.configure(text="")

    def _disable_all(self):
        self.btn_rec.configure(state='disabled')
        self.btn_play.configure(state='disabled')
        self.btn_save.configure(state='disabled')
        self.btn_load.configure(state='disabled')

    def _enable_all(self):
        self.btn_rec.configure(state='normal')
        self.btn_play.configure(state='normal')
        self.btn_save.configure(state='normal')
        self.btn_load.configure(state='normal')
        self.btn_stop.configure(state='disabled')

    def _tick(self):
        if self.engine.recording:
            n = self.engine.event_count()
            self.lbl_detail.configure(text=f"{n} hareket kaydedildi — ESC = durdur")
            self.root.after(200, self._tick)


def main():
    root = tk.Tk()
    root.title("AutoFlow — Otomatik Tekrar Yazılımı")
    root.geometry("620x780")
    root.minsize(560, 720)
    root.configure(bg="#f5f6fa")

    # Lisans kontrolu
    license_file = os.path.join(os.path.expanduser("~"), ".autoflow", "license.json")

    def check_license():
        if not os.path.exists(license_file):
            return False
        try:
            with open(license_file, 'r') as f:
                data = json.load(f)
            key = data.get('key', '')
            stored_hash = data.get('hash', '')
            expected = hashlib.md5((key + "AutoFlow2025Key").encode()).hexdigest()[:16]
            return stored_hash == expected
        except:
            return False

    def verify_key(key):
        key = key.strip().upper()
        parts = key.split('-')
        if len(parts) != 4:
            return False
        if parts[0] != 'AF':
            return False
        for p in parts[1:]:
            if len(p) != 4:
                return False
            if not p.isalnum():
                return False
        return True

    def activate(key):
        key = key.strip().upper()
        if not verify_key(key):
            return False
        os.makedirs(os.path.dirname(license_file), exist_ok=True)
        data = {
            'key': key,
            'hash': hashlib.md5((key + "AutoFlow2025Key").encode()).hexdigest()[:16]
        }
        with open(license_file, 'w') as f:
            json.dump(data, f)
        return True

    def show_license_screen():
        frame = tk.Frame(root, bg="#f5f6fa")
        frame.pack(fill='both', expand=True)

        center = tk.Frame(frame, bg="#f5f6fa")
        center.place(relx=0.5, rely=0.45, anchor='center')

        tk.Label(center, text="AutoFlow", font=("Segoe UI", 30, "bold"),
                 fg="#2b579a", bg="#f5f6fa").pack(pady=(0, 4))
        tk.Label(center, text="Otomatik Tekrar Yazılımı",
                 font=("Segoe UI", 11), fg="#636e72", bg="#f5f6fa").pack(pady=(0, 30))

        card = tk.Frame(center, bg="white", highlightbackground="#dfe6e9",
                        highlightthickness=1, padx=40, pady=30)
        card.pack()

        tk.Label(card, text="Lisans Kodunuzu Girin",
                 font=("Segoe UI", 13, "bold"), fg="#2d3436", bg="white").pack(anchor='w', pady=(0, 14))

        tk.Label(card, text="Lisans Kodu", font=("Segoe UI", 9),
                 fg="#636e72", bg="white").pack(anchor='w', pady=(0, 4))

        entry = tk.Entry(card, font=("Consolas", 15), width=22,
                         bg="#f5f6fa", fg="#2d3436", insertbackground="#2d3436",
                         relief='solid', bd=1,
                         highlightbackground="#dfe6e9", highlightcolor="#2b579a")
        entry.pack(fill='x', ipady=8, pady=(0, 4))
        entry.insert(0, "AF-")
        entry.focus()

        tk.Label(card, text="Örnek: AF-A2B4-C6D8-E9F1",
                 font=("Segoe UI", 8), fg="#b2bec3", bg="white").pack(anchor='w', pady=(0, 16))

        msg_lbl = tk.Label(card, text="", font=("Segoe UI", 9), bg="white")
        msg_lbl.pack()

        def do_activate():
            key = entry.get().strip().upper()
            if activate(key):
                msg_lbl.configure(text="✓ Lisans aktif! Açılıyor...", fg="#2b579a")
                root.after(1500, lambda: (frame.destroy(), AutoFlowApp(root)))
            else:
                msg_lbl.configure(text="Geçersiz lisans kodu!", fg="#c42b1c")

        btn = tk.Button(card, text="Etkinleştir", font=("Segoe UI", 12, "bold"),
                        bg="#2b579a", fg="white",
                        activebackground="#1e3f73", activeforeground="white",
                        relief='flat', cursor='hand2', bd=0, padx=20, pady=10,
                        command=do_activate)
        btn.pack(fill='x', pady=(10, 0))

        tk.Label(center, text="Lisans kodu satın almak için: autoflow.com.tr",
                 font=("Segoe UI", 9), fg="#636e72", bg="#f5f6fa").pack(pady=(20, 0))

    if check_license():
        AutoFlowApp(root)
    else:
        show_license_screen()

    root.mainloop()


if __name__ == '__main__':
    main()

