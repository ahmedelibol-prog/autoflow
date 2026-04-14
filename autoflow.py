#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoFlow v4.0 - EBYS Otomasyon
Windows native API ile klavye/fare kayit (Ctrl+C, Ctrl+V vb tam destek)
Ctrl+D = Durdur
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

try:
    from pynput.mouse import Button as MouseButton, Controller as MouseController, Listener as MouseListener
    from pynput.keyboard import Key, KeyCode, Controller as KeyboardController
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pynput'])
    from pynput.mouse import Button as MouseButton, Controller as MouseController, Listener as MouseListener
    from pynput.keyboard import Key, KeyCode, Controller as KeyboardController


# ══════════════════════════════════════════
#  WINDOWS KLAVYE HOOK - CTRL+C/V TAM DESTEK
# ══════════════════════════════════════════
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Virtual key kodlari
VK_CTRL = 0x11
VK_SHIFT = 0x10
VK_ALT = 0x12
VK_D = 0x44

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_ulong),
        ("scanCode", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(KBDLLHOOKSTRUCT))


class WinKeyboardHook:
    """Windows low-level klavye hook - TUM tuslar yakalanir"""

    def __init__(self):
        self.hook = None
        self.on_key_down = None  # callback(vk_code)
        self.on_key_up = None    # callback(vk_code)
        self._hook_proc = HOOKPROC(self._hook_callback)
        self._thread = None

    def _hook_callback(self, nCode, wParam, lParam):
        if nCode >= 0:
            vk = lParam.contents.vkCode
            if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if self.on_key_down:
                    self.on_key_down(vk)
            elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                if self.on_key_up:
                    self.on_key_up(vk)
        return user32.CallNextHookEx(self.hook, nCode, wParam, lParam)

    def start(self):
        def run():
            self.hook = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self._hook_proc,
                kernel32.GetModuleHandleW(None), 0
            )
            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        if self.hook:
            user32.UnhookWindowsHookEx(self.hook)
            self.hook = None


# ══════════════════════════════════════════
#  MAKRO MOTORU
# ══════════════════════════════════════════
class MacroEngine:
    def __init__(self):
        self.events = []
        self.recording = False
        self.playing = False
        self.start_time = 0
        self.speed = 1.0
        self.loops = 1
        self.stop_flag = False

        # Fare
        self.mc = MouseController()
        self.ml = None
        self.last_move = 0

        # Klavye - Windows native
        self.kc = KeyboardController()
        self.kb_hook = WinKeyboardHook()
        self.kb_hook.on_key_down = self._on_vk_down
        self.kb_hook.on_key_up = self._on_vk_up
        self.kb_hook.start()

        # Aktif tuslar (Ctrl+D algilama icin)
        self.active_vks = set()

        # Durdurma callback
        self.on_stop = None

    def _ts(self):
        return time.time() - self.start_time

    # ── Klavye olaylari (Windows VK kodlari) ──
    def _on_vk_down(self, vk):
        self.active_vks.add(vk)

        # Ctrl+D = durdur (her zaman)
        if VK_CTRL in self.active_vks and vk == VK_D:
            if self.on_stop:
                self.on_stop()
            return

        if self.recording:
            self.events.append({'t': 'vkd', 'vk': vk, 's': self._ts()})

    def _on_vk_up(self, vk):
        self.active_vks.discard(vk)

        if self.recording:
            self.events.append({'t': 'vku', 'vk': vk, 's': self._ts()})

    # ── Fare olaylari ──
    def _on_move(self, x, y):
        if not self.recording:
            return
        now = time.time()
        if now - self.last_move < 0.02:
            return
        self.last_move = now
        self.events.append({'t': 'mv', 'x': int(x), 'y': int(y), 's': self._ts()})

    def _on_click(self, x, y, btn, pressed):
        if not self.recording:
            return
        self.events.append({
            't': 'cl', 'x': int(x), 'y': int(y),
            'b': btn.name, 'p': pressed, 's': self._ts()
        })

    def _on_scroll(self, x, y, dx, dy):
        if not self.recording:
            return
        self.events.append({
            't': 'sc', 'x': int(x), 'y': int(y),
            'dx': dx, 'dy': dy, 's': self._ts()
        })

    # ── Kayit ──
    def rec_start(self):
        self.events = []
        self.recording = True
        self.start_time = time.time()
        self.last_move = 0
        self.active_vks = set()

        # Fare dinleyici
        self.ml = MouseListener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll
        )
        self.ml.start()
        # Klavye hook zaten calisiyor

    def rec_stop(self):
        self.recording = False
        if self.ml:
            self.ml.stop()
            self.ml = None

    # ── Oynatma ──
    def play(self, on_prog=None, on_done=None):
        if not self.events:
            return
        self.playing = True
        self.stop_flag = False

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
                            time.sleep(min(0.015, delay - w))
                            w += 0.015
                    if self.stop_flag:
                        break
                    prev = ev['s']
                    try:
                        self._execute(ev)
                    except Exception:
                        pass
                    if on_prog:
                        on_prog(i + 1, total, lp + 1)

            self.playing = False
            if on_done:
                on_done()

        threading.Thread(target=worker, daemon=True).start()

    def stop(self):
        self.stop_flag = True
        self.playing = False

    def _execute(self, ev):
        t = ev['t']
        if t == 'mv':
            self.mc.position = (ev['x'], ev['y'])
        elif t == 'cl':
            self.mc.position = (ev['x'], ev['y'])
            btn = getattr(MouseButton, ev['b'])
            if ev['p']:
                self.mc.press(btn)
            else:
                self.mc.release(btn)
        elif t == 'sc':
            self.mc.position = (ev['x'], ev['y'])
            self.mc.scroll(ev['dx'], ev['dy'])
        elif t == 'vkd':
            # Windows SendInput ile tus bas
            self._send_key(ev['vk'], down=True)
        elif t == 'vku':
            self._send_key(ev['vk'], down=False)

    def _send_key(self, vk, down=True):
        """Windows SendInput API ile tus gonder - EN GUVENILIR YONTEM"""
        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        KEYEVENTF_SCANCODE = 0x0008

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", ctypes.c_ushort),
                        ("wScan", ctypes.c_ushort),
                        ("dwFlags", ctypes.c_ulong),
                        ("time", ctypes.c_ulong),
                        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

        class INPUT(ctypes.Structure):
            class _INPUT_UNION(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT)]
            _fields_ = [("type", ctypes.c_ulong),
                        ("union", _INPUT_UNION)]

        flags = 0
        if not down:
            flags |= KEYEVENTF_KEYUP

        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = vk
        inp.union.ki.wScan = 0
        inp.union.ki.dwFlags = flags
        inp.union.ki.time = 0
        inp.union.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'v': '4.0', 'n': len(self.events), 'e': self.events}, f)

    def load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.events = d['e']
        return d.get('n', len(self.events))


# ══════════════════════════════════════════
#  ARAYUZ
# ══════════════════════════════════════════
class AutoFlowApp:
    BG = "#f0f4f8"
    CARD = "#ffffff"
    BLUE = "#2563eb"
    RED = "#dc2626"
    GREEN = "#16a34a"
    ORANGE = "#ea580c"
    PURPLE = "#7c3aed"
    TEAL = "#0d9488"
    TEXT = "#1e293b"
    TEXT2 = "#64748b"
    TEXT3 = "#94a3b8"
    BORDER = "#e2e8f0"

    # Kayitli makrolar (EBYS islemleri icin)
    MACROS_DIR = os.path.join(os.path.expanduser("~"), ".autoflow_macros")

    def __init__(self, root):
        self.root = root
        self.engine = MacroEngine()
        self.engine.on_stop = lambda: self.root.after(0, self._stop)

        # Makro klasoru olustur
        os.makedirs(self.MACROS_DIR, exist_ok=True)

        self._build()

    def _build(self):
        self.root.configure(bg=self.BG)
        main = tk.Frame(self.root, bg=self.BG, padx=20, pady=10)
        main.pack(fill='both', expand=True)

        # Baslik
        hdr = tk.Frame(main, bg=self.BG)
        hdr.pack(fill='x', pady=(0, 10))
        tk.Label(hdr, text="AutoFlow", font=("Segoe UI", 20, "bold"),
                 fg=self.BLUE, bg=self.BG).pack(side='left')
        tk.Label(hdr, text="EBYS Otomasyon", font=("Segoe UI", 9),
                 fg=self.TEXT3, bg=self.BG).pack(side='left', padx=(8, 0), pady=(8, 0))

        # ══════════════════════════════════
        #  EBYS HAZIR BUTONLAR
        # ══════════════════════════════════
        ebys_card = tk.Frame(main, bg="#f5f3ff", highlightbackground="#c4b5fd",
                             highlightthickness=2, padx=16, pady=12)
        ebys_card.pack(fill='x', pady=(0, 8))

        tk.Label(ebys_card, text="EBYS Islemleri", font=("Segoe UI", 12, "bold"),
                 fg="#5b21b6", bg="#f5f3ff").pack(anchor='w', pady=(0, 8))

        # ── Evrak Kayit Butonu ──
        ek_frame = tk.Frame(ebys_card, bg="#f5f3ff")
        ek_frame.pack(fill='x', pady=(0, 6))

        self.btn_evrak_kayit = tk.Button(ek_frame,
            text="Evrak Kayit Tekrari",
            font=("Segoe UI", 11, "bold"),
            bg=self.PURPLE, fg="white",
            activebackground="#6d28d9", activeforeground="white",
            relief='flat', cursor='hand2', padx=12, pady=8,
            command=lambda: self._ebys_play("evrak_kayit"))
        self.btn_evrak_kayit.pack(side='left', padx=(0, 6))

        self.btn_evrak_kayit_set = tk.Button(ek_frame,
            text="Kaydet",
            font=("Segoe UI", 9),
            bg="#ede9fe", fg="#5b21b6",
            relief='flat', cursor='hand2', padx=10, pady=8,
            command=lambda: self._ebys_record("evrak_kayit"))
        self.btn_evrak_kayit_set.pack(side='left', padx=(0, 6))

        self.lbl_ek = tk.Label(ek_frame, text=self._macro_status("evrak_kayit"),
                                font=("Segoe UI", 8), fg="#7c3aed", bg="#f5f3ff")
        self.lbl_ek.pack(side='left')

        # ── Evrak Havale Butonu ──
        eh_frame = tk.Frame(ebys_card, bg="#f5f3ff")
        eh_frame.pack(fill='x', pady=(0, 6))

        self.btn_evrak_havale = tk.Button(eh_frame,
            text="Evrak Havale Tekrari",
            font=("Segoe UI", 11, "bold"),
            bg=self.TEAL, fg="white",
            activebackground="#0f766e", activeforeground="white",
            relief='flat', cursor='hand2', padx=12, pady=8,
            command=lambda: self._ebys_play("evrak_havale"))
        self.btn_evrak_havale.pack(side='left', padx=(0, 6))

        self.btn_evrak_havale_set = tk.Button(eh_frame,
            text="Kaydet",
            font=("Segoe UI", 9),
            bg="#ccfbf1", fg="#0d9488",
            relief='flat', cursor='hand2', padx=10, pady=8,
            command=lambda: self._ebys_record("evrak_havale"))
        self.btn_evrak_havale_set.pack(side='left', padx=(0, 6))

        self.lbl_eh = tk.Label(eh_frame, text=self._macro_status("evrak_havale"),
                                font=("Segoe UI", 8), fg="#0d9488", bg="#f5f3ff")
        self.lbl_eh.pack(side='left')

        # Evrak sayisi
        cnt_frame = tk.Frame(ebys_card, bg="#f5f3ff")
        cnt_frame.pack(fill='x', pady=(4, 0))

        tk.Label(cnt_frame, text="Kac evrak?",
                 font=("Segoe UI", 10, "bold"), fg="#5b21b6", bg="#f5f3ff").pack(side='left')

        self.ebys_count = tk.StringVar(value="100")
        for v in ["10", "50", "100", "200", "500"]:
            tk.Button(cnt_frame, text=v, font=("Segoe UI", 9),
                      bg="#ede9fe", fg="#5b21b6", relief='flat', cursor='hand2',
                      width=4, pady=2,
                      command=lambda x=v: self.ebys_count.set(x)
                      ).pack(side='left', padx=2)

        tk.Entry(cnt_frame, textvariable=self.ebys_count, font=("Segoe UI", 11, "bold"),
                 width=5, bg="white", fg=self.TEXT, relief='solid', bd=1,
                 justify='center').pack(side='left', padx=(8, 0), ipady=2)

        # ══════════════════════════════════
        #  STANDART KAYIT / OYNAT
        # ══════════════════════════════════
        std_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                            highlightthickness=1, padx=16, pady=12)
        std_card.pack(fill='x', pady=(0, 8))

        tk.Label(std_card, text="Standart Kayit/Oynat", font=("Segoe UI", 10, "bold"),
                 fg=self.TEXT2, bg=self.CARD).pack(anchor='w', pady=(0, 6))

        btns = tk.Frame(std_card, bg=self.CARD)
        btns.pack(fill='x')

        self.btn_rec = tk.Button(btns, text="KAYDET",
            font=("Segoe UI", 11, "bold"), bg=self.RED, fg="white",
            activebackground="#ef4444", activeforeground="white",
            relief='flat', cursor='hand2', pady=8,
            command=self._toggle_rec)
        self.btn_rec.pack(side='left', expand=True, fill='x', padx=(0, 3))

        self.btn_play = tk.Button(btns, text="OYNAT",
            font=("Segoe UI", 11, "bold"), bg=self.GREEN, fg="white",
            activebackground="#22c55e", activeforeground="white",
            relief='flat', cursor='hand2', pady=8,
            command=self._toggle_play)
        self.btn_play.pack(side='left', expand=True, fill='x', padx=(3, 3))

        self.btn_stop = tk.Button(btns, text="DURDUR (Ctrl+D)",
            font=("Segoe UI", 10, "bold"), bg="#f1f5f9", fg=self.RED,
            activebackground="#fee2e2", activeforeground=self.RED,
            relief='flat', cursor='hand2', pady=8,
            command=self._stop, state='disabled')
        self.btn_stop.pack(side='left', expand=True, fill='x', padx=(3, 0))

        # Tekrar + Hiz
        set_row = tk.Frame(std_card, bg=self.CARD)
        set_row.pack(fill='x', pady=(8, 0))

        tk.Label(set_row, text="Tekrar:", font=("Segoe UI", 9),
                 fg=self.TEXT2, bg=self.CARD).pack(side='left')
        self.loop_var = tk.StringVar(value="1")
        tk.Entry(set_row, textvariable=self.loop_var, font=("Segoe UI", 10),
                 width=4, bg="#f8fafc", fg=self.TEXT, relief='solid', bd=1,
                 justify='center').pack(side='left', padx=(4, 12), ipady=1)

        tk.Label(set_row, text="Hiz:", font=("Segoe UI", 9),
                 fg=self.TEXT2, bg=self.CARD).pack(side='left')
        self.speed_var = tk.StringVar(value="1.0")
        for l, v in [("1x", "1.0"), ("2x", "2.0"), ("5x", "5.0")]:
            tk.Button(set_row, text=l, font=("Segoe UI", 8),
                      bg="#f1f5f9", fg=self.TEXT, relief='flat', cursor='hand2',
                      padx=6, pady=1,
                      command=lambda x=v: self.speed_var.set(x)
                      ).pack(side='left', padx=2)

        # ══════════════════════════════════
        #  DOSYA
        # ══════════════════════════════════
        f_row = tk.Frame(main, bg=self.BG)
        f_row.pack(fill='x', pady=(0, 8))
        for txt, cmd in [("Kaydet", self._save), ("Yukle", self._load), ("Temizle", self._clear)]:
            fg = self.RED if txt == "Temizle" else self.TEXT2
            tk.Button(f_row, text=txt, font=("Segoe UI", 9),
                      bg="#e2e8f0", fg=fg, relief='flat', cursor='hand2',
                      padx=12, pady=3, command=cmd).pack(side='left', padx=(0, 4))

        # ══════════════════════════════════
        #  DURUM
        # ══════════════════════════════════
        s_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                          highlightthickness=1, padx=16, pady=10)
        s_card.pack(fill='x')

        self.lbl_status = tk.Label(s_card, text="Hazir",
                                    font=("Segoe UI", 11), fg=self.BLUE, bg=self.CARD)
        self.lbl_status.pack(anchor='w')

        self.lbl_detail = tk.Label(s_card, text="Ctrl+C/V tam destekli | Ctrl+D = durdur",
                                    font=("Segoe UI", 9), fg=self.TEXT3, bg=self.CARD)
        self.lbl_detail.pack(anchor='w')

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("P.Horizontal.TProgressbar",
                         troughcolor="#e2e8f0", background=self.BLUE, thickness=6)
        self.progress = ttk.Progressbar(s_card, mode='determinate',
                                         style="P.Horizontal.TProgressbar")

    # ══════════════════════════════════
    #  EBYS ISLEMLERI
    # ══════════════════════════════════
    def _macro_path(self, name):
        return os.path.join(self.MACROS_DIR, f"{name}.autoflow")

    def _macro_status(self, name):
        path = self._macro_path(name)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    d = json.load(f)
                return f"({d.get('n', '?')} hareket kayitli)"
            except:
                pass
        return "(henuz kayit yok)"

    def _update_ebys_labels(self):
        self.lbl_ek.configure(text=self._macro_status("evrak_kayit"))
        self.lbl_eh.configure(text=self._macro_status("evrak_havale"))

    def _ebys_record(self, name):
        """EBYS islemi icin kayit baslat"""
        if self.engine.recording or self.engine.playing:
            return

        self.current_ebys_name = name
        label = "Evrak Kayit" if name == "evrak_kayit" else "Evrak Havale"

        messagebox.showinfo("Kayit Basliyor",
            f"{label} islemi kaydedilecek.\n\n"
            f"1. Tamam'a basin\n"
            f"2. EBYS'de islemi bir kez yapin\n"
            f"3. Bitince Ctrl+D basin\n\n"
            f"Kayit 3 saniye sonra baslar...")

        self.lbl_status.configure(text="3 saniye sonra kayit basliyor...", fg=self.ORANGE)
        self.lbl_detail.configure(text=f"{label} islemi icin hazirlanin")

        # 3 saniye bekle
        self.root.after(3000, self._ebys_record_start)

    def _ebys_record_start(self):
        self.engine.rec_start()
        self.btn_rec.configure(state='disabled')
        self.btn_play.configure(state='disabled')
        self.btn_stop.configure(state='normal')
        self.btn_evrak_kayit.configure(state='disabled')
        self.btn_evrak_havale.configure(state='disabled')
        self.btn_evrak_kayit_set.configure(state='disabled')
        self.btn_evrak_havale_set.configure(state='disabled')
        self.lbl_status.configure(text="KAYDEDILIYOR...", fg=self.RED)
        self.lbl_detail.configure(text="Islemleri yapin, bitince Ctrl+D basin")
        self._tick()

        # Ctrl+D gelince otomatik kaydet
        original_stop = self.engine.on_stop
        def ebys_stop():
            self.root.after(0, self._ebys_record_finish)
        self.engine.on_stop = ebys_stop

    def _ebys_record_finish(self):
        if not self.engine.recording:
            return
        self.engine.rec_stop()
        name = self.current_ebys_name

        # Makroyu otomatik kaydet
        try:
            self.engine.save(self._macro_path(name))
        except Exception as e:
            messagebox.showerror("Hata", str(e))

        # Arayuzu guncelle
        self.btn_rec.configure(state='normal')
        self.btn_play.configure(state='normal')
        self.btn_stop.configure(state='disabled')
        self.btn_evrak_kayit.configure(state='normal')
        self.btn_evrak_havale.configure(state='normal')
        self.btn_evrak_kayit_set.configure(state='normal')
        self.btn_evrak_havale_set.configure(state='normal')

        # Stop callback geri yukle
        self.engine.on_stop = lambda: self.root.after(0, self._stop)

        n = len(self.engine.events)
        label = "Evrak Kayit" if name == "evrak_kayit" else "Evrak Havale"
        self.lbl_status.configure(text=f"{label} kaydedildi! ({n} hareket)", fg=self.GREEN)
        self.lbl_detail.configure(text="Artik butona basarak istediginiz kadar tekrarlayabilirsiniz")
        self._update_ebys_labels()

    def _ebys_play(self, name):
        """EBYS makrosunu yukle ve calistir"""
        if self.engine.recording or self.engine.playing:
            return

        path = self._macro_path(name)
        if not os.path.exists(path):
            label = "Evrak Kayit" if name == "evrak_kayit" else "Evrak Havale"
            messagebox.showinfo("Bilgi",
                f"{label} icin henuz kayit yok!\n\n"
                f"Yandaki 'Kaydet' butonuna basarak islemi kaydedin.")
            return

        try:
            self.engine.load(path)
        except Exception as e:
            messagebox.showerror("Hata", f"Makro yuklenemedi: {e}")
            return

        try:
            count = max(1, int(self.ebys_count.get()))
        except ValueError:
            count = 100

        self.engine.loops = count
        self.engine.speed = 1.0
        self._start_play()

    # ══════════════════════════════════
    #  STANDART ISLEMLER
    # ══════════════════════════════════
    def _sync(self):
        try:
            self.engine.loops = max(1, int(self.loop_var.get()))
        except ValueError:
            self.engine.loops = 1
        try:
            self.engine.speed = float(self.speed_var.get())
        except ValueError:
            self.engine.speed = 1.0

    def _toggle_rec(self):
        if self.engine.playing:
            return
        if not self.engine.recording:
            self.engine.rec_start()
            self.btn_rec.configure(text="DURDUR", bg=self.ORANGE)
            self.btn_play.configure(state='disabled')
            self.btn_stop.configure(state='normal')
            self.btn_evrak_kayit.configure(state='disabled')
            self.btn_evrak_havale.configure(state='disabled')
            self.lbl_status.configure(text="KAYDEDILIYOR...", fg=self.RED)
            self.lbl_detail.configure(text="Ctrl+D veya DURDUR butonuna basin")
            self._tick()
        else:
            self._stop_rec()

    def _stop_rec(self):
        if not self.engine.recording:
            return
        self.engine.rec_stop()
        n = len(self.engine.events)
        d = self.engine.events[-1]['s'] if self.engine.events else 0
        self.btn_rec.configure(text="KAYDET", bg=self.RED)
        self.btn_play.configure(state='normal')
        self.btn_stop.configure(state='disabled')
        self.btn_evrak_kayit.configure(state='normal')
        self.btn_evrak_havale.configure(state='normal')
        self.lbl_status.configure(text=f"Kayit tamam! {n} hareket, {d:.1f}s", fg=self.GREEN)
        self.lbl_detail.configure(text="")

    def _toggle_play(self):
        if self.engine.recording or self.engine.playing:
            return
        if not self.engine.events:
            messagebox.showinfo("Bilgi", "Once bir kayit yapin!")
            return
        self._sync()
        self._start_play()

    def _start_play(self):
        self.btn_rec.configure(state='disabled')
        self.btn_play.configure(state='disabled')
        self.btn_stop.configure(state='normal')
        self.btn_evrak_kayit.configure(state='disabled')
        self.btn_evrak_havale.configure(state='disabled')
        self.progress.pack(fill='x', pady=(8, 0))
        self.progress['maximum'] = len(self.engine.events)
        self.progress['value'] = 0
        lt = f" ({self.engine.loops}x)" if self.engine.loops > 1 else ""
        self.lbl_status.configure(text=f"Calisiyor{lt}...", fg=self.BLUE)
        self.lbl_detail.configure(text="Ctrl+D = durdur")
        self.engine.play(on_prog=self._prog, on_done=self._done)

    def _prog(self, cur, tot, lp):
        def u():
            self.progress['value'] = cur
            lt = f" [{lp}/{self.engine.loops}]" if self.engine.loops > 1 else ""
            self.lbl_status.configure(text=f"Calisiyor %{int(cur/tot*100)}{lt}", fg=self.BLUE)
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
            self._enable_all()
            self.progress.pack_forget()
            self.lbl_status.configure(text="Durduruldu.", fg=self.ORANGE)
            self.lbl_detail.configure(text="")

    def _enable_all(self):
        self.btn_rec.configure(state='normal', text="KAYDET", bg=self.RED)
        self.btn_play.configure(state='normal')
        self.btn_stop.configure(state='disabled')
        self.btn_evrak_kayit.configure(state='normal')
        self.btn_evrak_havale.configure(state='normal')
        self.btn_evrak_kayit_set.configure(state='normal')
        self.btn_evrak_havale_set.configure(state='normal')

    def _save(self):
        if not self.engine.events:
            messagebox.showinfo("Bilgi", "Kaydedilecek makro yok!")
            return
        fp = filedialog.asksaveasfilename(title="Kaydet", defaultextension=".autoflow",
            filetypes=[("AutoFlow", "*.autoflow"), ("Hepsi", "*.*")])
        if fp:
            self.engine.save(fp)
            self.lbl_status.configure(text=f"Kaydedildi", fg=self.GREEN)

    def _load(self):
        fp = filedialog.askopenfilename(title="Yukle",
            filetypes=[("AutoFlow", "*.autoflow"), ("Hepsi", "*.*")])
        if fp:
            n = self.engine.load(fp)
            self.lbl_status.configure(text=f"Yuklendi: {n} hareket", fg=self.GREEN)

    def _clear(self):
        if self.engine.events and messagebox.askyesno("Onay", "Silinsin mi?"):
            self.engine.events = []
            self.lbl_status.configure(text="Temizlendi", fg=self.TEXT2)

    def _tick(self):
        if self.engine.recording:
            el = time.time() - self.engine.start_time
            n = len(self.engine.events)
            self.lbl_detail.configure(text=f"{el:.1f}s | {n} hareket | Ctrl+D = durdur")
            self.root.after(100, self._tick)


# ══════════════════════════════════════════
def main():
    root = tk.Tk()
    root.title("AutoFlow - EBYS Otomasyon")
    root.geometry("560x680")
    root.minsize(480, 620)
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
