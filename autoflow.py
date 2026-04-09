#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoFlow v1.0 - Otomatik Tekrar Yazilimi
Basit arayuz - bilgisayar bilmeyen kullanicilar icin
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import json
import os
import sys
import hashlib
import uuid
from datetime import datetime, timedelta

# pynput otomatik kur
try:
    from pynput import mouse, keyboard
    from pynput.mouse import Button as MouseButton, Controller as MouseController
    from pynput.keyboard import Key, Controller as KeyboardController
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pynput'])
    from pynput import mouse, keyboard
    from pynput.mouse import Button as MouseButton, Controller as MouseController
    from pynput.keyboard import Key, Controller as KeyboardController


# ══════════════════════════════════════════
#  LISANS SISTEMI
# ══════════════════════════════════════════
class LicenseManager:
    LICENSE_FILE = os.path.join(os.path.expanduser("~"), ".autoflow_license")
    # Basit sifreleme anahtari - gercek uretimde daha guclu olacak
    SECRET = "AutoFlow2025SecretKey"

    @staticmethod
    def get_machine_id():
        raw = str(uuid.getnode()) + os.environ.get('COMPUTERNAME', 'PC')
        return hashlib.md5(raw.encode()).hexdigest()[:12].upper()

    @staticmethod
    def validate_key(key):
        """Lisans anahtarini dogrula. Format: AF-XXXX-XXXX-XXXX"""
        if not key:
            return False
        key = key.strip().upper()
        parts = key.split('-')
        if len(parts) != 4:
            return False
        if parts[0] != 'AF':
            return False
        # Her parca 4 karakter olmali
        for p in parts[1:]:
            if len(p) != 4:
                return False
            # Sadece harf ve rakam
            if not p.isalnum():
                return False
        return True

    def activate(self, key):
        """Lisansi etkinlestir"""
        key = key.strip().upper()
        if not self.validate_key(key):
            return False, "Gecersiz lisans kodu!\nFormat: AF-XXXX-XXXX-XXXX"
        data = {
            'key': key,
            'machine': self.get_machine_id(),
            'activated': datetime.now().isoformat(),
            'expires': (datetime.now() + timedelta(days=365)).isoformat(),
            'checksum': hashlib.sha256((key + self.SECRET).encode()).hexdigest()[:16]
        }
        try:
            with open(self.LICENSE_FILE, 'w') as f:
                json.dump(data, f)
            return True, "Lisans basariyla etkinlestirildi!"
        except Exception as e:
            return False, f"Hata: {e}"

    def check(self):
        """Lisans durumunu kontrol et"""
        if not os.path.exists(self.LICENSE_FILE):
            return False, "Lisans bulunamadi"
        try:
            with open(self.LICENSE_FILE, 'r') as f:
                data = json.load(f)
            # Checksum dogrula
            expected = hashlib.sha256((data['key'] + self.SECRET).encode()).hexdigest()[:16]
            if data.get('checksum') != expected:
                return False, "Lisans gecersiz"
            # Sure kontrol
            expires = datetime.fromisoformat(data['expires'])
            if datetime.now() > expires:
                return False, "Lisans suresi dolmus"
            days_left = (expires - datetime.now()).days
            return True, f"{days_left} gun kaldi"
        except Exception:
            return False, "Lisans okunamadi"

    def get_expiry_text(self):
        try:
            with open(self.LICENSE_FILE, 'r') as f:
                data = json.load(f)
            expires = datetime.fromisoformat(data['expires'])
            days_left = (expires - datetime.now()).days
            return f"Lisans: {days_left} gun kaldi ({expires.strftime('%d.%m.%Y')})"
        except:
            return ""


# ══════════════════════════════════════════
#  MAKRO MOTORU
# ══════════════════════════════════════════
class MacroEngine:
    def __init__(self):
        self.events = []
        self.recording = False
        self.playing = False
        self.start_time = 0
        self.ml = None  # mouse listener
        self.kl = None  # keyboard listener
        self.record_mouse = True
        self.speed = 1.0
        self.loops = 1
        self.stop_flag = False
        self.mc = MouseController()
        self.kc = KeyboardController()
        self.last_move = 0

    def rec_start(self):
        self.events = []
        self.recording = True
        self.start_time = time.time()
        self.last_move = 0
        self.ml = mouse.Listener(on_move=self._mv, on_click=self._cl, on_scroll=self._sc)
        self.kl = keyboard.Listener(on_press=self._kp, on_release=self._kr)
        self.ml.start()
        self.kl.start()

    def rec_stop(self):
        self.recording = False
        if self.ml: self.ml.stop(); self.ml = None
        if self.kl: self.kl.stop(); self.kl = None

    def _t(self): return time.time() - self.start_time

    def _mv(self, x, y):
        if not self.recording or not self.record_mouse: return
        now = time.time()
        if now - self.last_move < 0.015: return
        self.last_move = now
        self.events.append({'t': 'mv', 'x': int(x), 'y': int(y), 's': self._t()})

    def _cl(self, x, y, btn, pressed):
        if not self.recording: return
        self.events.append({'t': 'cl', 'x': int(x), 'y': int(y), 'b': btn.name, 'p': pressed, 's': self._t()})

    def _sc(self, x, y, dx, dy):
        if not self.recording: return
        self.events.append({'t': 'sc', 'x': int(x), 'y': int(y), 'dx': dx, 'dy': dy, 's': self._t()})

    def _kp(self, key):
        if not self.recording: return
        self.events.append({'t': 'kp', 'k': self._ks(key), 's': self._t()})

    def _kr(self, key):
        if not self.recording: return
        self.events.append({'t': 'kr', 'k': self._ks(key), 's': self._t()})

    def _ks(self, key):
        try: return {'c': 1, 'v': key.char}
        except: return {'c': 0, 'v': key.name}

    def _kd(self, d):
        if d['c']: return d['v']
        return getattr(Key, d['v'], None)

    def play(self, on_prog=None, on_done=None):
        if not self.events: return
        self.playing = True
        self.stop_flag = False

        def go():
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
                            time.sleep(min(0.03, dly - w)); w += 0.03
                    if self.stop_flag: break
                    prev = ev['s']
                    try: self._run(ev)
                    except: pass
                    if on_prog: on_prog(i+1, tot, lp+1)
            self.playing = False
            if on_done: on_done()
        threading.Thread(target=go, daemon=True).start()

    def stop(self):
        self.stop_flag = True
        self.playing = False

    def _run(self, ev):
        t = ev['t']
        if t == 'mv': self.mc.position = (ev['x'], ev['y'])
        elif t == 'cl':
            self.mc.position = (ev['x'], ev['y'])
            b = getattr(MouseButton, ev['b'])
            if ev['p']: self.mc.press(b)
            else: self.mc.release(b)
        elif t == 'sc':
            self.mc.position = (ev['x'], ev['y'])
            self.mc.scroll(ev['dx'], ev['dy'])
        elif t == 'kp':
            k = self._kd(ev['k'])
            if k: self.kc.press(k)
        elif t == 'kr':
            k = self._kd(ev['k'])
            if k: self.kc.release(k)

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'v': '1.0', 'n': len(self.events), 'e': self.events}, f)

    def load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.events = d['e']
        return d.get('n', len(self.events))


# ══════════════════════════════════════════
#  LISANS EKRANI
# ══════════════════════════════════════════
class LicenseScreen:
    BG = "#f0f4f8"
    CARD = "#ffffff"
    BLUE = "#2563eb"
    BLUE2 = "#3b82f6"
    TEXT = "#1e293b"
    TEXT2 = "#64748b"
    BORDER = "#e2e8f0"
    GREEN = "#16a34a"
    RED = "#dc2626"

    def __init__(self, root, on_success):
        self.root = root
        self.on_success = on_success
        self.lm = LicenseManager()
        self.frame = tk.Frame(root, bg=self.BG)
        self.frame.pack(fill='both', expand=True)
        self._build()

    def _build(self):
        # Ortala
        center = tk.Frame(self.frame, bg=self.BG)
        center.place(relx=0.5, rely=0.5, anchor='center')

        # Logo
        tk.Label(center, text="AutoFlow", font=("Segoe UI", 28, "bold"),
                 fg=self.BLUE, bg=self.BG).pack(pady=(0, 5))
        tk.Label(center, text="Otomatik Tekrar Yazilimi",
                 font=("Segoe UI", 11), fg=self.TEXT2, bg=self.BG).pack(pady=(0, 30))

        # Kart
        card = tk.Frame(center, bg=self.CARD, highlightbackground=self.BORDER,
                        highlightthickness=1, padx=40, pady=30)
        card.pack()

        tk.Label(card, text="Lisans Kodunuzu Girin", font=("Segoe UI", 13, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(anchor='w', pady=(0, 15))

        tk.Label(card, text="Lisans Kodu", font=("Segoe UI", 9),
                 fg=self.TEXT2, bg=self.CARD).pack(anchor='w', pady=(0, 4))

        self.entry = tk.Entry(card, font=("Consolas", 14), width=22,
                              bg="#f8fafc", fg=self.TEXT, insertbackground=self.TEXT,
                              relief='solid', bd=1, highlightcolor=self.BLUE)
        self.entry.pack(fill='x', ipady=8, pady=(0, 5))
        self.entry.insert(0, "AF-")
        self.entry.focus()

        tk.Label(card, text="Ornek: AF-A2B4-C6D8-E9F1", font=("Segoe UI", 8),
                 fg="#94a3b8", bg=self.CARD).pack(anchor='w', pady=(0, 15))

        self.btn = tk.Button(card, text="Etkinlestir", font=("Segoe UI", 12, "bold"),
                             bg=self.BLUE, fg="white", activebackground=self.BLUE2,
                             activeforeground="white", relief='flat', cursor='hand2',
                             padx=20, pady=10, command=self._activate)
        self.btn.pack(fill='x', pady=(0, 10))

        self.msg = tk.Label(card, text="", font=("Segoe UI", 9), bg=self.CARD)
        self.msg.pack()

        # Alt bilgi
        tk.Label(center, text="Lisans kodu satin almak icin: autoflow.com.tr",
                 font=("Segoe UI", 9), fg=self.TEXT2, bg=self.BG).pack(pady=(20, 0))

    def _activate(self):
        key = self.entry.get().strip().upper()
        ok, msg = self.lm.activate(key)
        if ok:
            self.msg.configure(text="Basarili! Program aciliyor...", fg=self.GREEN)
            self.root.after(1500, self._go)
        else:
            self.msg.configure(text=msg, fg=self.RED)

    def _go(self):
        self.frame.destroy()
        self.on_success()


# ══════════════════════════════════════════
#  ANA UYGULAMA - BASIT ARAYUZ
# ══════════════════════════════════════════
class AutoFlowApp:
    BG = "#f0f4f8"
    CARD = "#ffffff"
    BLUE = "#2563eb"
    BLUE2 = "#3b82f6"
    RED = "#dc2626"
    RED2 = "#ef4444"
    GREEN = "#16a34a"
    GREEN2 = "#22c55e"
    ORANGE = "#ea580c"
    TEXT = "#1e293b"
    TEXT2 = "#64748b"
    TEXT3 = "#94a3b8"
    BORDER = "#e2e8f0"

    def __init__(self, root):
        self.root = root
        self.engine = MacroEngine()
        self.lm = LicenseManager()
        self._build()
        self._setup_hotkeys()

    def _build(self):
        self.root.configure(bg=self.BG)
        main = tk.Frame(self.root, bg=self.BG, padx=24, pady=16)
        main.pack(fill='both', expand=True)

        # ── BASLIK ──
        hdr = tk.Frame(main, bg=self.BG)
        hdr.pack(fill='x', pady=(0, 16))
        tk.Label(hdr, text="AutoFlow", font=("Segoe UI", 22, "bold"),
                 fg=self.BLUE, bg=self.BG).pack(side='left')

        lic_text = self.lm.get_expiry_text()
        if lic_text:
            tk.Label(hdr, text=lic_text, font=("Segoe UI", 8),
                     fg=self.TEXT3, bg=self.BG).pack(side='right', pady=(10, 0))

        # ══════════════════════════════════
        #  BUYUK BUTONLAR - ANA KONTROL
        # ══════════════════════════════════
        btn_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                            highlightthickness=1, padx=20, pady=20)
        btn_card.pack(fill='x', pady=(0, 12))

        # Aciklama
        tk.Label(btn_card, text="Ne yapmak istiyorsunuz?", font=("Segoe UI", 13, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(anchor='w', pady=(0, 12))

        btns = tk.Frame(btn_card, bg=self.CARD)
        btns.pack(fill='x')

        # KAYDET butonu - BUYUK
        self.btn_rec = tk.Button(btns, text="KAYDET\n\nFare ve klavye\nhareketlerini kaydet",
                                  font=("Segoe UI", 12, "bold"),
                                  bg=self.RED, fg="white",
                                  activebackground=self.RED2, activeforeground="white",
                                  relief='flat', cursor='hand2', width=18, height=5,
                                  command=self._toggle_rec)
        self.btn_rec.pack(side='left', expand=True, fill='both', padx=(0, 6))

        # OYNAT butonu - BUYUK
        self.btn_play = tk.Button(btns, text="OYNAT\n\nKaydedilen hareketi\ntekrar calistir",
                                   font=("Segoe UI", 12, "bold"),
                                   bg=self.GREEN, fg="white",
                                   activebackground=self.GREEN2, activeforeground="white",
                                   relief='flat', cursor='hand2', width=18, height=5,
                                   command=self._toggle_play)
        self.btn_play.pack(side='left', expand=True, fill='both', padx=(6, 0))

        # DURDUR butonu
        self.btn_stop = tk.Button(main, text="DURDUR",
                                   font=("Segoe UI", 11, "bold"),
                                   bg="#f1f5f9", fg=self.TEXT2,
                                   activebackground=self.BORDER, activeforeground=self.TEXT,
                                   relief='flat', cursor='hand2', pady=10,
                                   command=self._stop, state='disabled')
        self.btn_stop.pack(fill='x', pady=(0, 12))

        # ══════════════════════════════════
        #  TEKRAR SAYISI - COK BASIT
        # ══════════════════════════════════
        loop_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                             highlightthickness=1, padx=20, pady=16)
        loop_card.pack(fill='x', pady=(0, 12))

        tk.Label(loop_card, text="Kac kez tekrar etsin?", font=("Segoe UI", 12, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(anchor='w', pady=(0, 8))

        loop_row = tk.Frame(loop_card, bg=self.CARD)
        loop_row.pack(fill='x')

        self.loop_var = tk.StringVar(value="10")

        # Hizli secim butonlari
        for val in ["1", "5", "10", "50", "100", "500"]:
            b = tk.Button(loop_row, text=val, font=("Segoe UI", 11, "bold"),
                          bg="#f1f5f9", fg=self.TEXT, relief='flat', cursor='hand2',
                          width=5, pady=6,
                          command=lambda v=val: self._set_loop(v))
            b.pack(side='left', padx=(0, 4))

        tk.Label(loop_row, text="veya:", font=("Segoe UI", 10),
                 fg=self.TEXT2, bg=self.CARD).pack(side='left', padx=(8, 4))

        self.loop_entry = tk.Entry(loop_row, textvariable=self.loop_var,
                                    font=("Segoe UI", 12), width=5,
                                    bg="#f8fafc", fg=self.TEXT, relief='solid', bd=1,
                                    justify='center')
        self.loop_entry.pack(side='left', ipady=4)

        tk.Label(loop_row, text="kez", font=("Segoe UI", 10),
                 fg=self.TEXT2, bg=self.CARD).pack(side='left', padx=(4, 0))

        # ══════════════════════════════════
        #  HIZ AYARI
        # ══════════════════════════════════
        speed_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                              highlightthickness=1, padx=20, pady=16)
        speed_card.pack(fill='x', pady=(0, 12))

        tk.Label(speed_card, text="Hiz", font=("Segoe UI", 12, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(anchor='w', pady=(0, 8))

        speed_row = tk.Frame(speed_card, bg=self.CARD)
        speed_row.pack(fill='x')

        self.speed_var = tk.StringVar(value="1.0")
        speeds = [("Yavas", "0.5"), ("Normal", "1.0"), ("Hizli", "2.0"), ("Cok Hizli", "5.0")]

        for label, val in speeds:
            b = tk.Button(speed_row, text=f"{label}\n({val}x)", font=("Segoe UI", 10),
                          bg="#f1f5f9", fg=self.TEXT, relief='flat', cursor='hand2',
                          width=10, pady=6,
                          command=lambda v=val: self._set_speed(v))
            b.pack(side='left', padx=(0, 4), expand=True, fill='x')

        # ══════════════════════════════════
        #  DOSYA ISLEMLERI
        # ══════════════════════════════════
        file_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                             highlightthickness=1, padx=20, pady=12)
        file_card.pack(fill='x', pady=(0, 12))

        file_row = tk.Frame(file_card, bg=self.CARD)
        file_row.pack(fill='x')

        tk.Button(file_row, text="Makroyu Kaydet", font=("Segoe UI", 10),
                  bg="#f1f5f9", fg=self.TEXT, relief='flat', cursor='hand2',
                  padx=16, pady=6, command=self._save).pack(side='left', padx=(0, 6))

        tk.Button(file_row, text="Makro Yukle", font=("Segoe UI", 10),
                  bg="#f1f5f9", fg=self.TEXT, relief='flat', cursor='hand2',
                  padx=16, pady=6, command=self._load).pack(side='left', padx=(0, 6))

        tk.Button(file_row, text="Temizle", font=("Segoe UI", 10),
                  bg="#f1f5f9", fg=self.RED, relief='flat', cursor='hand2',
                  padx=16, pady=6, command=self._clear).pack(side='left')

        # ══════════════════════════════════
        #  DURUM CUBUGU
        # ══════════════════════════════════
        stat_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                             highlightthickness=1, padx=20, pady=12)
        stat_card.pack(fill='x')

        self.lbl_status = tk.Label(stat_card, text="Hazir. KAYDET butonuna basin.",
                                    font=("Segoe UI", 11),
                                    fg=self.BLUE, bg=self.CARD)
        self.lbl_status.pack(anchor='w')

        self.lbl_detail = tk.Label(stat_card, text="",
                                    font=("Segoe UI", 9),
                                    fg=self.TEXT3, bg=self.CARD)
        self.lbl_detail.pack(anchor='w')

        # Progress bar
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Blue.Horizontal.TProgressbar",
                         troughcolor="#e2e8f0", background=self.BLUE, thickness=8)
        self.progress = ttk.Progressbar(stat_card, mode='determinate',
                                         style="Blue.Horizontal.TProgressbar")

        # ── Kisayol bilgisi ──
        tk.Label(main, text="Kisayollar:  F9 = Kaydet/Durdur    F10 = Oynat    F11 = Durdur",
                 font=("Segoe UI", 8), fg=self.TEXT3, bg=self.BG).pack(pady=(8, 0))

    def _set_loop(self, val):
        self.loop_var.set(val)

    def _set_speed(self, val):
        self.speed_var.set(val)

    def _sync(self):
        try: self.engine.loops = max(1, int(self.loop_var.get()))
        except: self.engine.loops = 1
        try: self.engine.speed = float(self.speed_var.get())
        except: self.engine.speed = 1.0

    # ── Hotkeys ──
    def _setup_hotkeys(self):
        def handler(key):
            try:
                if key == Key.f9: self.root.after(0, self._toggle_rec)
                elif key == Key.f10: self.root.after(0, self._toggle_play)
                elif key == Key.f11: self.root.after(0, self._stop)
            except: pass
        self.hk = keyboard.Listener(on_press=handler)
        self.hk.daemon = True
        self.hk.start()

    # ── Kayit ──
    def _toggle_rec(self):
        if self.engine.playing: return
        if not self.engine.recording:
            self.engine.rec_start()
            self.btn_rec.configure(text="KAYDI DURDUR\n\n(kayit devam ediyor...)",
                                    bg=self.ORANGE)
            self.btn_play.configure(state='disabled')
            self.btn_stop.configure(state='normal')
            self.lbl_status.configure(text="KAYDEDILIYOR - islemlerinizi yapin...", fg=self.RED)
            self._tick()
        else:
            self.engine.rec_stop()
            n = len(self.engine.events)
            d = self.engine.events[-1]['s'] if self.engine.events else 0
            self.btn_rec.configure(text="KAYDET\n\nFare ve klavye\nhareketlerini kaydet",
                                    bg=self.RED)
            self.btn_play.configure(state='normal')
            self.btn_stop.configure(state='disabled')
            self.lbl_status.configure(
                text=f"Kayit tamamlandi! {n} hareket kaydedildi.", fg=self.GREEN)
            self.lbl_detail.configure(text=f"Sure: {d:.1f} saniye | Simdi OYNAT butonuna basin")

    # ── Oynat ──
    def _toggle_play(self):
        if self.engine.recording or self.engine.playing: return
        if not self.engine.events:
            messagebox.showinfo("Bilgi", "Once bir kayit yapin!\n\nKAYDET butonuna basin,\nislemlerinizi yapin,\nsonra tekrar KAYDET butonuna basin.")
            return
        self._sync()
        self.btn_rec.configure(state='disabled')
        self.btn_play.configure(state='disabled')
        self.btn_stop.configure(state='normal', bg=self.RED, fg="white")
        self.progress.pack(fill='x', pady=(8, 0))
        self.progress['maximum'] = len(self.engine.events)
        self.progress['value'] = 0
        lt = f" ({self.engine.loops} kez)" if self.engine.loops > 1 else ""
        self.lbl_status.configure(text=f"Calisiyor...{lt}", fg=self.BLUE)
        self.lbl_detail.configure(text="Durdurmak icin F11 tusuna basin")
        self.engine.play(on_prog=self._prog, on_done=self._done)

    def _prog(self, cur, tot, lp):
        def u():
            self.progress['value'] = cur
            lt = f" (Dongu {lp}/{self.engine.loops})" if self.engine.loops > 1 else ""
            self.lbl_status.configure(text=f"Calisiyor... {cur}/{tot}{lt}", fg=self.BLUE)
        self.root.after(0, u)

    def _done(self):
        def u():
            self.btn_rec.configure(state='normal')
            self.btn_play.configure(state='normal')
            self.btn_stop.configure(state='disabled', bg="#f1f5f9", fg=self.TEXT2)
            self.progress.pack_forget()
            self.lbl_status.configure(text="Tamamlandi!", fg=self.GREEN)
            self.lbl_detail.configure(text="Tekrar calistirmak icin OYNAT butonuna basin")
        self.root.after(0, u)

    def _stop(self):
        if self.engine.recording:
            self._toggle_rec()
        if self.engine.playing:
            self.engine.stop()
            self.btn_rec.configure(state='normal')
            self.btn_play.configure(state='normal')
            self.btn_stop.configure(state='disabled', bg="#f1f5f9", fg=self.TEXT2)
            self.progress.pack_forget()
            self.lbl_status.configure(text="Durduruldu.", fg=self.ORANGE)
            self.lbl_detail.configure(text="")

    def _save(self):
        if not self.engine.events:
            messagebox.showinfo("Bilgi", "Kaydedilecek makro yok!")
            return
        fp = filedialog.asksaveasfilename(title="Makroyu Kaydet", defaultextension=".autoflow",
            filetypes=[("AutoFlow Makro", "*.autoflow"), ("Hepsi", "*.*")])
        if fp:
            try:
                self.engine.save(fp)
                self.lbl_status.configure(text=f"Kaydedildi: {os.path.basename(fp)}", fg=self.GREEN)
            except Exception as e:
                messagebox.showerror("Hata", str(e))

    def _load(self):
        fp = filedialog.askopenfilename(title="Makro Yukle",
            filetypes=[("AutoFlow Makro", "*.autoflow"), ("Hepsi", "*.*")])
        if fp:
            try:
                n = self.engine.load(fp)
                self.lbl_status.configure(text=f"Yuklendi: {n} hareket", fg=self.GREEN)
                self.lbl_detail.configure(text=f"Dosya: {os.path.basename(fp)} | OYNAT butonuna basin")
            except Exception as e:
                messagebox.showerror("Hata", str(e))

    def _clear(self):
        if self.engine.events:
            if messagebox.askyesno("Onay", "Kayitli hareketler silinsin mi?"):
                self.engine.events = []
                self.lbl_status.configure(text="Temizlendi.", fg=self.TEXT2)
                self.lbl_detail.configure(text="")

    def _tick(self):
        if self.engine.recording:
            el = time.time() - self.engine.start_time
            n = len(self.engine.events)
            self.lbl_detail.configure(text=f"Sure: {el:.1f}s | {n} hareket kaydedildi")
            self.root.after(100, self._tick)


# ══════════════════════════════════════════
#  BASLAT
# ══════════════════════════════════════════
def main():
    root = tk.Tk()
    root.title("AutoFlow - Otomatik Tekrar Yazilimi")
    root.geometry("600x720")
    root.minsize(500, 650)
    root.configure(bg="#f0f4f8")

    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass

    lm = LicenseManager()
    ok, _ = lm.check()

    if ok:
        AutoFlowApp(root)
    else:
        LicenseScreen(root, lambda: AutoFlowApp(root))

    root.mainloop()


if __name__ == '__main__':
    main()
