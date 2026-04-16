#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoFlow v8.0 - Otomatik Tekrar Yazilimi
4 slotlu profesyonel arayuz
ESC = Durdur
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import json
import os
import sys

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

        # Klavye kaydi
        keyboard.start_recording()

        # Fare kaydi - mouse.record() yerine hook kullanarak
        self._mouse_recorded = []
        mouse.hook(self._mouse_hook)

        # ESC dinleyici
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

        # ESC olaylarini kayittan cikar
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

        # ESC ile durdurmak icin
        self._esc_hook = keyboard.on_press_key('esc', lambda e: self._esc_stop(), suppress=False)

        # Tum olaylari zamana gore siralayip birlestir
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
        """Klavye olayini oynat - scan_code ile en guvenilir"""
        try:
            if event.event_type == 'down':
                keyboard.press(event.scan_code)
            elif event.event_type == 'up':
                keyboard.release(event.scan_code)
        except Exception:
            # Yedek: name ile dene
            try:
                if event.name:
                    if event.event_type == 'down':
                        keyboard.press(event.name)
                    elif event.event_type == 'up':
                        keyboard.release(event.name)
            except:
                pass

    def _play_mouse(self, event):
        """Fare olayini oynat - her olay tipi icin"""
        cls_name = event.__class__.__name__

        if cls_name == 'MoveEvent':
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
            'v': '8',
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
#  PROFESYONEL ARAYUZ
# ══════════════════════════════════════════
class AutoFlowApp:
    BG = "#1e293b"
    BG2 = "#334155"
    BG3 = "#475569"
    PRIMARY = "#3b82f6"
    SUCCESS = "#10b981"
    DANGER = "#ef4444"
    WARNING = "#f59e0b"
    TEXT = "#f1f5f9"
    TEXT2 = "#cbd5e1"
    TEXT3 = "#94a3b8"

    SLOT_COLORS = ["#8b5cf6", "#3b82f6", "#10b981", "#f59e0b"]
    SLOT_NAMES = ["KAYIT 1", "KAYIT 2", "KAYIT 3", "KAYIT 4"]
    MACROS_DIR = os.path.join(os.path.expanduser("~"), ".autoflow")

    def __init__(self, root):
        self.root = root
        self.engine = MacroEngine()
        self.engine.on_stop = lambda: self.root.after(0, self._stop)
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
                total = len(d.get('kb', [])) + len(d.get('mouse', []))
                return f"● {total} hareket kayıtlı"
            except:
                pass
        return "○ Boş"

    def _build(self):
        self.root.configure(bg=self.BG)
        main = tk.Frame(self.root, bg=self.BG, padx=24, pady=20)
        main.pack(fill='both', expand=True)

        # BASLIK
        hdr = tk.Frame(main, bg=self.BG)
        hdr.pack(fill='x', pady=(0, 16))

        title_frame = tk.Frame(hdr, bg=self.BG)
        title_frame.pack(side='left')
        tk.Label(title_frame, text="Auto", font=("Segoe UI", 28, "bold"),
                 fg=self.TEXT, bg=self.BG).pack(side='left')
        tk.Label(title_frame, text="Flow", font=("Segoe UI", 28, "bold"),
                 fg=self.PRIMARY, bg=self.BG).pack(side='left')

        tk.Label(hdr, text="Otomatik Tekrar Yazılımı", font=("Segoe UI", 11),
                 fg=self.TEXT3, bg=self.BG).pack(side='left', padx=(16, 0), pady=(14, 0))

        # TALIMAT
        info_card = tk.Frame(main, bg="#1e3a5f", highlightbackground=self.PRIMARY,
                             highlightthickness=1)
        info_card.pack(fill='x', pady=(0, 16))
        info_inner = tk.Frame(info_card, bg="#1e3a5f", padx=16, pady=10)
        info_inner.pack(fill='x')

        tk.Label(info_inner, text="NASIL KULLANILIR?", font=("Segoe UI", 9, "bold"),
                 fg="#60a5fa", bg="#1e3a5f").pack(anchor='w')
        tk.Label(info_inner,
                 text="1) KAYDET butonuna basın   2) İşlemi bir kez yapın   3) ESC'e basın\n"
                      "4) Tekrar sayısını girin   5) OYNAT butonuna basın — otomatik tekrar eder",
                 font=("Segoe UI", 9), fg=self.TEXT2, bg="#1e3a5f",
                 justify='left').pack(anchor='w', pady=(4, 0))

        # SLOT BASLIGI
        tk.Label(main, text="KAYIT SLOTLARI", font=("Segoe UI", 10, "bold"),
                 fg=self.TEXT3, bg=self.BG).pack(anchor='w', pady=(0, 8))

        slots_container = tk.Frame(main, bg=self.BG)
        slots_container.pack(fill='x', pady=(0, 14))

        self.slot_labels = []
        self.slot_rec_btns = []
        self.slot_play_btns = []
        self.slot_save_btns = []
        self.slot_load_btns = []

        for i in range(4):
            color = self.SLOT_COLORS[i]

            card = tk.Frame(slots_container, bg=self.BG2,
                            highlightbackground=color, highlightthickness=2)
            card.pack(fill='x', pady=4)
            inner = tk.Frame(card, bg=self.BG2, padx=14, pady=10)
            inner.pack(fill='x')

            # Ust
            top = tk.Frame(inner, bg=self.BG2)
            top.pack(fill='x', pady=(0, 8))

            canvas = tk.Canvas(top, width=14, height=14, bg=self.BG2, highlightthickness=0)
            canvas.pack(side='left', padx=(0, 10))
            canvas.create_oval(2, 2, 12, 12, fill=color, outline="")

            tk.Label(top, text=self.SLOT_NAMES[i], font=("Segoe UI", 13, "bold"),
                     fg=self.TEXT, bg=self.BG2).pack(side='left')

            lbl = tk.Label(top, text=self._slot_info(i), font=("Segoe UI", 9),
                           fg=self.TEXT3, bg=self.BG2)
            lbl.pack(side='right')
            self.slot_labels.append(lbl)

            # Butonlar - 4 tane: KAYDET, OYNAT, KAYIT ET (dosyaya), AC (dosyadan)
            btns = tk.Frame(inner, bg=self.BG2)
            btns.pack(fill='x')

            btn_rec = tk.Button(btns, text="● KAYDET",
                font=("Segoe UI", 10, "bold"),
                bg=self.DANGER, fg="white",
                activebackground="#dc2626", activeforeground="white",
                relief='flat', cursor='hand2', bd=0, pady=9,
                command=lambda idx=i: self._rec_slot(idx))
            btn_rec.pack(side='left', fill='x', expand=True, padx=(0, 3))
            self.slot_rec_btns.append(btn_rec)

            btn_play = tk.Button(btns, text="▶ OYNAT",
                font=("Segoe UI", 10, "bold"),
                bg=self.SUCCESS, fg="white",
                activebackground="#059669", activeforeground="white",
                relief='flat', cursor='hand2', bd=0, pady=9,
                command=lambda idx=i: self._play_slot(idx))
            btn_play.pack(side='left', fill='x', expand=True, padx=3)
            self.slot_play_btns.append(btn_play)

            btn_save = tk.Button(btns, text="💾 KAYDET",
                font=("Segoe UI", 9, "bold"),
                bg=self.BG3, fg=self.TEXT,
                activebackground="#64748b", activeforeground="white",
                relief='flat', cursor='hand2', bd=0, pady=9, padx=10,
                command=lambda idx=i: self._save_slot(idx))
            btn_save.pack(side='left', padx=3)
            self.slot_save_btns.append(btn_save)

            btn_load = tk.Button(btns, text="📁 AÇ",
                font=("Segoe UI", 9, "bold"),
                bg=self.BG3, fg=self.TEXT,
                activebackground="#64748b", activeforeground="white",
                relief='flat', cursor='hand2', bd=0, pady=9, padx=10,
                command=lambda idx=i: self._load_slot(idx))
            btn_load.pack(side='left', padx=(3, 0))
            self.slot_load_btns.append(btn_load)

        # AYARLAR
        tk.Label(main, text="AYARLAR", font=("Segoe UI", 10, "bold"),
                 fg=self.TEXT3, bg=self.BG).pack(anchor='w', pady=(0, 8))

        set_card = tk.Frame(main, bg=self.BG2)
        set_card.pack(fill='x', pady=(0, 14))
        set_inner = tk.Frame(set_card, bg=self.BG2, padx=18, pady=12)
        set_inner.pack(fill='x')

        r1 = tk.Frame(set_inner, bg=self.BG2)
        r1.pack(fill='x', pady=(0, 10))

        tk.Label(r1, text="Tekrar sayısı:", font=("Segoe UI", 10, "bold"),
                 fg=self.TEXT, bg=self.BG2).pack(side='left', padx=(0, 10))

        self.loop_var = tk.StringVar(value="100")
        for v in ["1", "10", "50", "100", "500"]:
            tk.Button(r1, text=v, font=("Segoe UI", 10, "bold"),
                      bg=self.BG3, fg=self.TEXT,
                      activebackground=self.PRIMARY, activeforeground="white",
                      relief='flat', cursor='hand2', bd=0, width=4, pady=4,
                      command=lambda x=v: self.loop_var.set(x)
                      ).pack(side='left', padx=2)

        tk.Entry(r1, textvariable=self.loop_var, font=("Segoe UI", 12, "bold"),
                 width=6, bg=self.BG3, fg=self.TEXT,
                 insertbackground=self.TEXT, relief='flat', bd=0,
                 justify='center').pack(side='left', padx=(10, 0), ipady=5)

        r2 = tk.Frame(set_inner, bg=self.BG2)
        r2.pack(fill='x')

        tk.Label(r2, text="Oynatma hızı:", font=("Segoe UI", 10, "bold"),
                 fg=self.TEXT, bg=self.BG2).pack(side='left', padx=(0, 10))

        self.speed_var = tk.StringVar(value="1.0")
        for l, v in [("Yavaş", "0.5"), ("Normal", "1.0"), ("Hızlı", "2.0"), ("Maksimum", "5.0")]:
            tk.Button(r2, text=l, font=("Segoe UI", 9, "bold"),
                      bg=self.BG3, fg=self.TEXT,
                      activebackground=self.PRIMARY, activeforeground="white",
                      relief='flat', cursor='hand2', bd=0, padx=14, pady=4,
                      command=lambda x=v: self.speed_var.set(x)
                      ).pack(side='left', padx=2)

        # BUYUK DURDUR BUTONU
        self.btn_stop = tk.Button(main,
            text="⏹  DURDUR  (ESC tuşu)",
            font=("Segoe UI", 13, "bold"),
            bg=self.DANGER, fg="white",
            activebackground="#dc2626", activeforeground="white",
            relief='flat', cursor='hand2', bd=0, pady=12,
            command=self._stop, state='disabled')
        self.btn_stop.pack(fill='x', pady=(0, 14))

        # DURUM
        stat_card = tk.Frame(main, bg=self.BG2)
        stat_card.pack(fill='x')
        stat_inner = tk.Frame(stat_card, bg=self.BG2, padx=20, pady=12)
        stat_inner.pack(fill='x')

        self.lbl_status = tk.Label(stat_inner, text="✓ Hazır",
                                    font=("Segoe UI", 13, "bold"),
                                    fg=self.SUCCESS, bg=self.BG2)
        self.lbl_status.pack(anchor='w')

        self.lbl_detail = tk.Label(stat_inner,
                                    text="Bir slotun KAYDET butonuna basarak başlayın",
                                    font=("Segoe UI", 9), fg=self.TEXT3, bg=self.BG2)
        self.lbl_detail.pack(anchor='w', pady=(2, 0))

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Success.Horizontal.TProgressbar",
                         troughcolor=self.BG3, background=self.SUCCESS,
                         borderwidth=0, thickness=10)
        self.progress = ttk.Progressbar(stat_inner, mode='determinate',
                                         style="Success.Horizontal.TProgressbar")

        footer = tk.Frame(main, bg=self.BG)
        footer.pack(fill='x', pady=(10, 0))
        tk.Label(footer, text="AutoFlow v8.0",
                 font=("Segoe UI", 8), fg=self.TEXT3, bg=self.BG).pack()

    # ═══════════════════════════════════════
    #  KAYIT
    # ═══════════════════════════════════════
    def _rec_slot(self, idx):
        if self.engine.recording or self.engine.playing:
            return

        self.recording_slot = idx
        name = self.SLOT_NAMES[idx]

        self.lbl_status.configure(text="⏱ 3 saniye sonra kayıt başlıyor...", fg=self.WARNING)
        self.lbl_detail.configure(text=f"{name} için hazırlanın")
        self._disable_all()

        self.root.after(3000, lambda: self._rec_start_now(idx))

    def _rec_start_now(self, idx):
        try:
            self.engine.rec_start()
        except Exception as e:
            messagebox.showerror("Hata", f"Kayıt başlatılamadı: {e}\n\nProgramı YÖNETİCİ olarak çalıştırın!")
            self._enable_all()
            return

        self.btn_stop.configure(state='normal')
        name = self.SLOT_NAMES[idx]
        self.lbl_status.configure(text=f"● KAYDEDİLİYOR — {name}", fg=self.DANGER)
        self.lbl_detail.configure(text="İşlemlerinizi yapın, bitince ESC tuşuna basın")
        self._tick()

    def _stop_rec(self):
        if not self.engine.recording:
            return

        self.engine.rec_stop()
        idx = self.recording_slot

        if idx is not None and self.engine.has_recording():
            try:
                self.engine.save(self._slot_path(idx))
                self.slot_labels[idx].configure(text=self._slot_info(idx))
                name = self.SLOT_NAMES[idx]
                n = self.engine.event_count()
                self.lbl_status.configure(text=f"✓ {name} kaydedildi!", fg=self.SUCCESS)
                self.lbl_detail.configure(text=f"{n} hareket — OYNAT ile çalıştırabilirsiniz")
            except Exception as e:
                messagebox.showerror("Hata", str(e))
        else:
            self.lbl_status.configure(text="⚠ Kayıt iptal edildi", fg=self.WARNING)
            self.lbl_detail.configure(text="Hareket kaydedilmedi")

        self.recording_slot = None
        self._enable_all()

    # ═══════════════════════════════════════
    #  OYNAT
    # ═══════════════════════════════════════
    def _play_slot(self, idx):
        if self.engine.recording or self.engine.playing:
            return

        path = self._slot_path(idx)
        if not os.path.exists(path):
            messagebox.showinfo("Boş Slot",
                f"{self.SLOT_NAMES[idx]} boş!\n\nÖnce KAYDET butonuna basıp işlem kaydedin.")
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

        name = self.SLOT_NAMES[idx]
        lt = f" ({self.engine.loops}x tekrar)" if self.engine.loops > 1 else ""
        self.lbl_status.configure(text=f"▶ {name} çalışıyor{lt}", fg=self.PRIMARY)
        self.lbl_detail.configure(text="Durdurmak için ESC tuşuna basın")

        self.engine.play(on_prog=self._prog, on_done=self._done)

    # ═══════════════════════════════════════
    #  KAYDET (dosyaya)
    # ═══════════════════════════════════════
    def _save_slot(self, idx):
        if self.engine.recording or self.engine.playing:
            return

        path = self._slot_path(idx)
        if not os.path.exists(path):
            messagebox.showinfo("Boş Slot",
                f"{self.SLOT_NAMES[idx]} boş, kaydedilecek bir şey yok!")
            return

        fp = filedialog.asksaveasfilename(
            title=f"{self.SLOT_NAMES[idx]} - dosyaya kaydet",
            defaultextension=".autoflow",
            filetypes=[("AutoFlow Makro", "*.autoflow"), ("Hepsi", "*.*")])

        if fp:
            try:
                # Slot dosyasini secilen yere kopyala
                with open(path, 'r') as f:
                    data = json.load(f)
                with open(fp, 'w') as f:
                    json.dump(data, f)
                self.lbl_status.configure(text=f"✓ Kaydedildi: {os.path.basename(fp)}",
                                           fg=self.SUCCESS)
                self.lbl_detail.configure(text=f"{self.SLOT_NAMES[idx]} dosyaya yazıldı")
            except Exception as e:
                messagebox.showerror("Hata", str(e))

    # ═══════════════════════════════════════
    #  AC (dosyadan)
    # ═══════════════════════════════════════
    def _load_slot(self, idx):
        if self.engine.recording or self.engine.playing:
            return

        fp = filedialog.askopenfilename(
            title=f"{self.SLOT_NAMES[idx]} - dosya aç",
            filetypes=[("AutoFlow Makro", "*.autoflow"), ("Hepsi", "*.*")])

        if fp:
            try:
                with open(fp, 'r') as f:
                    data = json.load(f)
                with open(self._slot_path(idx), 'w') as f:
                    json.dump(data, f)
                self.slot_labels[idx].configure(text=self._slot_info(idx))
                self.lbl_status.configure(text=f"✓ {self.SLOT_NAMES[idx]} yüklendi",
                                           fg=self.SUCCESS)
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
            self.lbl_status.configure(text="✓ Tamamlandı!", fg=self.SUCCESS)
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
            self.lbl_status.configure(text="⏹ Durduruldu", fg=self.WARNING)
            self.lbl_detail.configure(text="")

    def _disable_all(self):
        for b in (self.slot_rec_btns + self.slot_play_btns +
                  self.slot_save_btns + self.slot_load_btns):
            b.configure(state='disabled')

    def _enable_all(self):
        for b in (self.slot_rec_btns + self.slot_play_btns +
                  self.slot_save_btns + self.slot_load_btns):
            b.configure(state='normal')
        self.btn_stop.configure(state='disabled')

    def _tick(self):
        if self.engine.recording:
            n = self.engine.event_count()
            self.lbl_detail.configure(text=f"{n} hareket kaydedildi — ESC = durdur")
            self.root.after(200, self._tick)


def main():
    root = tk.Tk()
    root.title("AutoFlow — Otomatik Tekrar Yazılımı")
    root.geometry("680x880")
    root.minsize(620, 800)
    root.configure(bg="#1e293b")

    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    AutoFlowApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
