#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoFlow v9.0 - Otomatik Tekrar Yazilimi
Windows resmi renkleri, tek slot, DPI-aware mouse
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

# DPI AWARENESS - EN BASTA (mouse konumu icin cok onemli)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass


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

        self._mouse_recorded = []
        mouse.hook(self._mouse_hook)

        self._esc_hook = keyboard.on_press_key('esc', self._esc_pressed, suppress=False)

    def _mouse_hook(self, event):
        if self.recording:
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

        self._esc_hook = keyboard.on_press_key('esc', lambda e: self._esc_stop(), suppress=False)

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
        except Exception:
            try:
                if event.name:
                    if event.event_type == 'down':
                        keyboard.press(event.name)
                    elif event.event_type == 'up':
                        keyboard.release(event.name)
            except:
                pass

    def _play_mouse(self, event):
        """DPI-aware mouse playback - Windows SetCursorPos kullanir"""
        cls_name = event.__class__.__name__

        if cls_name == 'MoveEvent':
            # DIRECT Windows API - absolute pixel coordinates
            try:
                ctypes.windll.user32.SetCursorPos(int(event.x), int(event.y))
            except:
                mouse.move(event.x, event.y, absolute=True, duration=0)

        elif cls_name == 'ButtonEvent':
            btn = event.button
            et = event.event_type

            if et == 'down':
                mouse.press(button=btn)
            elif et == 'up':
                mouse.release(button=btn)
            elif et == 'double':
                mouse.double_click(button=btn)

        elif cls_name == 'WheelEvent':
            mouse.wheel(event.delta)

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
            'v': '9',
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
#  WINDOWS RESMI RENK ARAYUZU
# ══════════════════════════════════════════
class AutoFlowApp:
    # Windows 11 resmi renkler
    BG = "#f3f3f3"          # Windows arka plan
    CARD = "#ffffff"         # Kart beyazi
    WIN_BLUE = "#0078d4"     # Windows accent mavi
    WIN_BLUE_HOVER = "#106ebe"
    WIN_BLUE_LIGHT = "#e5f1fb"
    WIN_RED = "#c42b1c"      # Windows kirmizi
    WIN_RED_HOVER = "#a82a1f"
    WIN_GREEN = "#107c10"    # Windows yesil
    WIN_GREEN_HOVER = "#0e6e0e"
    WIN_ORANGE = "#ca5010"
    TEXT = "#323130"         # Windows koyu metin
    TEXT2 = "#605e5c"         # Windows gri metin
    TEXT3 = "#a19f9d"
    BORDER = "#d1d1d1"
    BORDER_LIGHT = "#edebe9"

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
        main = tk.Frame(self.root, bg=self.BG, padx=30, pady=24)
        main.pack(fill='both', expand=True)

        # ═══════════════════════════════
        #  BASLIK
        # ═══════════════════════════════
        hdr = tk.Frame(main, bg=self.BG)
        hdr.pack(fill='x', pady=(0, 20))

        title_frame = tk.Frame(hdr, bg=self.BG)
        title_frame.pack(side='left')

        tk.Label(title_frame, text="Auto", font=("Segoe UI", 28, "bold"),
                 fg=self.TEXT, bg=self.BG).pack(side='left')
        tk.Label(title_frame, text="Flow", font=("Segoe UI", 28, "bold"),
                 fg=self.WIN_BLUE, bg=self.BG).pack(side='left')

        tk.Label(hdr, text="Otomatik Tekrar Yazılımı", font=("Segoe UI", 11),
                 fg=self.TEXT2, bg=self.BG).pack(side='left', padx=(16, 0), pady=(14, 0))

        # ═══════════════════════════════
        #  TALIMAT KUTUSU
        # ═══════════════════════════════
        info_card = tk.Frame(main, bg=self.WIN_BLUE_LIGHT,
                             highlightbackground=self.WIN_BLUE, highlightthickness=1)
        info_card.pack(fill='x', pady=(0, 20))
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

        # ═══════════════════════════════
        #  TEK SLOT - KAYIT 1
        # ═══════════════════════════════
        slot_card = tk.Frame(main, bg=self.CARD,
                             highlightbackground=self.BORDER, highlightthickness=1)
        slot_card.pack(fill='x', pady=(0, 16))
        slot_inner = tk.Frame(slot_card, bg=self.CARD, padx=20, pady=16)
        slot_inner.pack(fill='x')

        # Ust
        top = tk.Frame(slot_inner, bg=self.CARD)
        top.pack(fill='x', pady=(0, 14))

        # Mavi dikdortgen + KAYIT 1
        canvas = tk.Canvas(top, width=4, height=24, bg=self.CARD, highlightthickness=0)
        canvas.pack(side='left', padx=(0, 12))
        canvas.create_rectangle(0, 0, 4, 24, fill=self.WIN_BLUE, outline="")

        tk.Label(top, text="KAYIT 1", font=("Segoe UI", 16, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(side='left')

        self.lbl_slot = tk.Label(top, text=self._slot_info(),
                                  font=("Segoe UI", 10), fg=self.TEXT2, bg=self.CARD)
        self.lbl_slot.pack(side='right')

        # Ana butonlar - KAYDET / OYNAT - BUYUK
        main_btns = tk.Frame(slot_inner, bg=self.CARD)
        main_btns.pack(fill='x', pady=(0, 10))

        self.btn_rec = tk.Button(main_btns, text="● KAYDET",
            font=("Segoe UI", 12, "bold"),
            bg=self.WIN_RED, fg="white",
            activebackground=self.WIN_RED_HOVER, activeforeground="white",
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

        # Dosya butonlari - KAYDET / AC
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

        # ═══════════════════════════════
        #  AYARLAR
        # ═══════════════════════════════
        set_card = tk.Frame(main, bg=self.CARD,
                            highlightbackground=self.BORDER, highlightthickness=1)
        set_card.pack(fill='x', pady=(0, 16))
        set_inner = tk.Frame(set_card, bg=self.CARD, padx=20, pady=14)
        set_inner.pack(fill='x')

        # Tekrar
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

        # Hiz
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

        # ═══════════════════════════════
        #  DURDUR
        # ═══════════════════════════════
        self.btn_stop = tk.Button(main,
            text="⏹  DURDUR  (ESC tuşu)",
            font=("Segoe UI", 13, "bold"),
            bg=self.WIN_RED, fg="white",
            activebackground=self.WIN_RED_HOVER, activeforeground="white",
            relief='flat', cursor='hand2', bd=0, pady=14,
            command=self._stop, state='disabled')
        self.btn_stop.pack(fill='x', pady=(0, 16))

        # ═══════════════════════════════
        #  DURUM
        # ═══════════════════════════════
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

        # Footer
        tk.Label(main, text="AutoFlow v9.0",
                 font=("Segoe UI", 8), fg=self.TEXT3, bg=self.BG).pack(pady=(12, 0))

    # ═══════════════════════════════════════
    #  KAYIT
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

    # ═══════════════════════════════════════
    #  OYNAT
    # ═══════════════════════════════════════
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

    # ═══════════════════════════════════════
    #  DOSYAYA KAYDET
    # ═══════════════════════════════════════
    def _save_file(self):
        if self.engine.recording or self.engine.playing:
            return

        path = self._slot_path()
        if not os.path.exists(path):
            messagebox.showinfo("Boş Slot", "KAYIT 1 boş, kaydedilecek bir şey yok!")
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
                self.lbl_status.configure(text=f"✓ Kaydedildi: {os.path.basename(fp)}",
                                           fg=self.WIN_GREEN)
                self.lbl_detail.configure(text="Kayıt dosyaya yazıldı")
            except Exception as e:
                messagebox.showerror("Hata", str(e))

    # ═══════════════════════════════════════
    #  DOSYADAN AC
    # ═══════════════════════════════════════
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

    # ═══════════════════════════════════════
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
    root.geometry("620x680")
    root.minsize(560, 620)
    root.configure(bg="#f3f3f3")

    AutoFlowApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
