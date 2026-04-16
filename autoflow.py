#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoFlow v7.0 - Profesyonel EBYS Otomasyon
keyboard + mouse kutuphaneleri ile tam destek
ESC = Durdur
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import json
import os
import sys

# Kutuphane kontrolu
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
                    except:
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
        if event.event_type == 'down':
            keyboard.press(event.scan_code)
        elif event.event_type == 'up':
            keyboard.release(event.scan_code)

    def _play_mouse(self, event):
        cls_name = event.__class__.__name__

        if cls_name == 'MoveEvent':
            mouse.move(event.x, event.y)
        elif cls_name == 'ButtonEvent':
            if event.event_type == 'down':
                mouse.press(event.button)
            elif event.event_type == 'up':
                mouse.release(event.button)
            elif event.event_type == 'double':
                mouse.double_click(event.button)
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
            'v': '7',
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
        return self.event_count()

    def _kb_to_dict(self, e):
        return {
            'event_type': e.event_type,
            'scan_code': e.scan_code,
            'name': e.name,
            'time': e.time
        }

    def _dict_to_kb(self, d):
        ke = keyboard.KeyboardEvent(
            event_type=d['event_type'],
            scan_code=d['scan_code'],
            name=d.get('name')
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
        if cls_name == 'MoveEvent':
            e = mouse.MoveEvent(x=d['x'], y=d['y'], time=t)
        elif cls_name == 'ButtonEvent':
            e = mouse.ButtonEvent(event_type=d['event_type'], button=d['button'], time=t)
        elif cls_name == 'WheelEvent':
            e = mouse.WheelEvent(delta=d['delta'], time=t)
        else:
            return None
        return e


# ══════════════════════════════════════════
#  PROFESYONEL ARAYUZ
# ══════════════════════════════════════════
class AutoFlowApp:
    # Renkler
    BG = "#1e293b"       # Koyu arka plan
    BG2 = "#334155"      # Kart arka plan
    BG3 = "#475569"      # Input arka plan
    PRIMARY = "#3b82f6"  # Mavi
    SUCCESS = "#10b981"  # Yesil
    DANGER = "#ef4444"   # Kirmizi
    WARNING = "#f59e0b"  # Turuncu
    TEXT = "#f1f5f9"
    TEXT2 = "#cbd5e1"
    TEXT3 = "#94a3b8"
    BORDER = "#475569"

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

        # ═══════════════════════════════
        #  BASLIK - BUYUK VE DIKKATA CEKICI
        # ═══════════════════════════════
        hdr = tk.Frame(main, bg=self.BG)
        hdr.pack(fill='x', pady=(0, 20))

        title_frame = tk.Frame(hdr, bg=self.BG)
        title_frame.pack(side='left')

        tk.Label(title_frame, text="Auto", font=("Segoe UI", 28, "bold"),
                 fg=self.TEXT, bg=self.BG).pack(side='left')
        tk.Label(title_frame, text="Flow", font=("Segoe UI", 28, "bold"),
                 fg=self.PRIMARY, bg=self.BG).pack(side='left')

        tk.Label(hdr, text="EBYS Otomasyon Sistemi", font=("Segoe UI", 11),
                 fg=self.TEXT3, bg=self.BG).pack(side='left', padx=(16, 0), pady=(14, 0))

        # ═══════════════════════════════
        #  TALIMAT KUTUSU
        # ═══════════════════════════════
        info_card = tk.Frame(main, bg="#1e3a5f", highlightbackground=self.PRIMARY,
                             highlightthickness=1)
        info_card.pack(fill='x', pady=(0, 20))
        info_inner = tk.Frame(info_card, bg="#1e3a5f", padx=16, pady=10)
        info_inner.pack(fill='x')

        tk.Label(info_inner, text="NASIL KULLANILIR?", font=("Segoe UI", 9, "bold"),
                 fg="#60a5fa", bg="#1e3a5f").pack(anchor='w')
        tk.Label(info_inner,
                 text="1) Bir slotta KAYDET butonuna basın    "
                      "2) EBYS'de işlemi bir kez yapın    "
                      "3) ESC tuşuna basın\n"
                      "4) Tekrar sayısını girin    "
                      "5) OYNAT butonuna basın - otomatik tekrar edecek",
                 font=("Segoe UI", 9), fg=self.TEXT2, bg="#1e3a5f",
                 justify='left').pack(anchor='w', pady=(4, 0))

        # ═══════════════════════════════
        #  4 SLOT - BUYUK KARTLAR
        # ═══════════════════════════════
        tk.Label(main, text="KAYIT SLOTLARI", font=("Segoe UI", 10, "bold"),
                 fg=self.TEXT3, bg=self.BG).pack(anchor='w', pady=(0, 8))

        slots_container = tk.Frame(main, bg=self.BG)
        slots_container.pack(fill='x', pady=(0, 16))

        self.slot_labels = []
        self.slot_play_btns = []
        self.slot_rec_btns = []
        self.slot_load_btns = []

        for i in range(4):
            color = self.SLOT_COLORS[i]

            # Slot karti
            card = tk.Frame(slots_container, bg=self.BG2, highlightbackground=color,
                            highlightthickness=2)
            card.pack(fill='x', pady=4)
            inner = tk.Frame(card, bg=self.BG2, padx=16, pady=12)
            inner.pack(fill='x')

            # Ust: isim ve durum
            top = tk.Frame(inner, bg=self.BG2)
            top.pack(fill='x', pady=(0, 10))

            # Renk dairesi
            canvas = tk.Canvas(top, width=14, height=14, bg=self.BG2,
                              highlightthickness=0)
            canvas.pack(side='left', padx=(0, 10))
            canvas.create_oval(2, 2, 12, 12, fill=color, outline="")

            tk.Label(top, text=self.SLOT_NAMES[i], font=("Segoe UI", 13, "bold"),
                     fg=self.TEXT, bg=self.BG2).pack(side='left')

            lbl = tk.Label(top, text=self._slot_info(i), font=("Segoe UI", 9),
                           fg=self.TEXT3, bg=self.BG2)
            lbl.pack(side='right')
            self.slot_labels.append(lbl)

            # Alt: butonlar - BUYUK VE NET
            btns = tk.Frame(inner, bg=self.BG2)
            btns.pack(fill='x')

            btn_rec = tk.Button(btns,
                text="● KAYDET",
                font=("Segoe UI", 11, "bold"),
                bg=self.DANGER, fg="white",
                activebackground="#dc2626", activeforeground="white",
                relief='flat', cursor='hand2', bd=0, pady=10,
                command=lambda idx=i: self._rec_slot(idx))
            btn_rec.pack(side='left', fill='x', expand=True, padx=(0, 4))
            self.slot_rec_btns.append(btn_rec)

            btn_play = tk.Button(btns,
                text="▶ OYNAT",
                font=("Segoe UI", 11, "bold"),
                bg=self.SUCCESS, fg="white",
                activebackground="#059669", activeforeground="white",
                relief='flat', cursor='hand2', bd=0, pady=10,
                command=lambda idx=i: self._play_slot(idx))
            btn_play.pack(side='left', fill='x', expand=True, padx=4)
            self.slot_play_btns.append(btn_play)

            btn_load = tk.Button(btns,
                text="📁 AÇ",
                font=("Segoe UI", 10, "bold"),
                bg=self.BG3, fg=self.TEXT,
                activebackground="#64748b", activeforeground="white",
                relief='flat', cursor='hand2', bd=0, pady=10, padx=12,
                command=lambda idx=i: self._load_slot(idx))
            btn_load.pack(side='left', padx=(4, 0))
            self.slot_load_btns.append(btn_load)

        # ═══════════════════════════════
        #  AYARLAR (TEKRAR + HIZ)
        # ═══════════════════════════════
        tk.Label(main, text="AYARLAR", font=("Segoe UI", 10, "bold"),
                 fg=self.TEXT3, bg=self.BG).pack(anchor='w', pady=(0, 8))

        set_card = tk.Frame(main, bg=self.BG2)
        set_card.pack(fill='x', pady=(0, 16))
        set_inner = tk.Frame(set_card, bg=self.BG2, padx=20, pady=14)
        set_inner.pack(fill='x')

        # Tekrar
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

        # Hiz
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

        # ═══════════════════════════════
        #  BUYUK DURDUR BUTONU
        # ═══════════════════════════════
        self.btn_stop = tk.Button(main,
            text="⏹  DURDUR  (ESC tuşu)",
            font=("Segoe UI", 13, "bold"),
            bg=self.DANGER, fg="white",
            activebackground="#dc2626", activeforeground="white",
            relief='flat', cursor='hand2', bd=0, pady=12,
            command=self._stop, state='disabled')
        self.btn_stop.pack(fill='x', pady=(0, 16))

        # ═══════════════════════════════
        #  DURUM
        # ═══════════════════════════════
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

        # Alt bilgi
        footer = tk.Frame(main, bg=self.BG)
        footer.pack(fill='x', pady=(12, 0))
        tk.Label(footer, text="AutoFlow v7.0 — Lütfen yönetici olarak çalıştırın",
                 font=("Segoe UI", 8), fg=self.TEXT3, bg=self.BG).pack()

    # ═══════════════════════════════════════
    #  KAYIT (SLOT)
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
                self.lbl_detail.configure(text=f"{n} hareket kaydedildi — OYNAT ile çalıştırabilirsiniz")
            except Exception as e:
                messagebox.showerror("Hata", str(e))
        else:
            self.lbl_status.configure(text="⚠ Kayıt iptal edildi", fg=self.WARNING)
            self.lbl_detail.configure(text="Hareket kaydedilmedi")

        self.recording_slot = None
        self._enable_all()

    # ═══════════════════════════════════════
    #  OYNAT (SLOT)
    # ═══════════════════════════════════════
    def _play_slot(self, idx):
        if self.engine.recording or self.engine.playing:
            return

        path = self._slot_path(idx)
        if not os.path.exists(path):
            messagebox.showinfo("Boş Slot",
                f"{self.SLOT_NAMES[idx]} boş!\n\n"
                "Önce KAYDET butonuna basıp bir işlem kaydedin.")
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
    #  YUKLE (DOSYADAN)
    # ═══════════════════════════════════════
    def _load_slot(self, idx):
        if self.engine.recording or self.engine.playing:
            return

        fp = filedialog.askopenfilename(
            title=f"{self.SLOT_NAMES[idx]} için dosya seç",
            filetypes=[("AutoFlow Makro", "*.autoflow"), ("Hepsi", "*.*")])

        if fp:
            try:
                with open(fp, 'r') as f:
                    data = json.load(f)
                with open(self._slot_path(idx), 'w') as f:
                    json.dump(data, f)
                self.slot_labels[idx].configure(text=self._slot_info(idx))
                self.lbl_status.configure(text=f"✓ {self.SLOT_NAMES[idx]} yüklendi", fg=self.SUCCESS)
                self.lbl_detail.configure(text=os.path.basename(fp))
            except Exception as e:
                messagebox.showerror("Hata", str(e))

    # ═══════════════════════════════════════
    #  ORTAK
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
        for b in self.slot_play_btns + self.slot_rec_btns + self.slot_load_btns:
            b.configure(state='disabled')

    def _enable_all(self):
        for b in self.slot_play_btns + self.slot_rec_btns + self.slot_load_btns:
            b.configure(state='normal')
        self.btn_stop.configure(state='disabled')

    def _tick(self):
        if self.engine.recording:
            n = self.engine.event_count()
            self.lbl_detail.configure(text=f"{n} hareket kaydedildi — ESC = durdur")
            self.root.after(200, self._tick)


def main():
    root = tk.Tk()
    root.title("AutoFlow — EBYS Otomasyon")
    root.geometry("640x880")
    root.minsize(580, 800)
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
