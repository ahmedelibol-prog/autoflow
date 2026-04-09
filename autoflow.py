#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoFlow v2.0 - EBYS Otomasyon Yazilimi
Fare + Klavye (Ctrl kombinasyonlari dahil) kaydet ve tekrarla
Ctrl+D = Kaydi durdur
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import json
import os
import sys

try:
    from pynput import mouse, keyboard
    from pynput.mouse import Button as MouseButton, Controller as MouseController
    from pynput.keyboard import Key, KeyCode, Controller as KeyboardController
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pynput'])
    from pynput import mouse, keyboard
    from pynput.mouse import Button as MouseButton, Controller as MouseController
    from pynput.keyboard import Key, KeyCode, Controller as KeyboardController


# ══════════════════════════════════════════
#  MAKRO MOTORU - KLAVYE KOMBINASYONLARI DESTEKLI
# ══════════════════════════════════════════
class MacroEngine:
    def __init__(self):
        self.events = []
        self.recording = False
        self.playing = False
        self.start_time = 0
        self.ml = None
        self.kl = None
        self.speed = 1.0
        self.loops = 1
        self.stop_flag = False
        self.mc = MouseController()
        self.kc = KeyboardController()
        self.last_move = 0
        # Aktif tuslari takip et (Ctrl, Shift, Alt kombinasyonlari icin)
        self.pressed_keys = set()
        # Ctrl+D durdurmak icin callback
        self.on_ctrl_d = None

    def rec_start(self):
        self.events = []
        self.recording = True
        self.start_time = time.time()
        self.last_move = 0
        self.pressed_keys = set()
        self.ml = mouse.Listener(on_move=self._mv, on_click=self._cl, on_scroll=self._sc)
        self.kl = keyboard.Listener(on_press=self._kp, on_release=self._kr, suppress=False)
        self.ml.start()
        self.kl.start()

    def rec_stop(self):
        self.recording = False
        if self.ml:
            self.ml.stop()
            self.ml = None
        if self.kl:
            self.kl.stop()
            self.kl = None
        self.pressed_keys = set()

    def _t(self):
        return time.time() - self.start_time

    def _mv(self, x, y):
        if not self.recording:
            return
        now = time.time()
        if now - self.last_move < 0.02:
            return
        self.last_move = now
        self.events.append({'t': 'mv', 'x': int(x), 'y': int(y), 's': self._t()})

    def _cl(self, x, y, btn, pressed):
        if not self.recording:
            return
        self.events.append({
            't': 'cl', 'x': int(x), 'y': int(y),
            'b': btn.name, 'p': pressed, 's': self._t()
        })

    def _sc(self, x, y, dx, dy):
        if not self.recording:
            return
        self.events.append({
            't': 'sc', 'x': int(x), 'y': int(y),
            'dx': dx, 'dy': dy, 's': self._t()
        })

    def _kp(self, key):
        # Ctrl+D kontrolu - kaydi durdur
        key_name = self._get_key_name(key)
        self.pressed_keys.add(key_name)

        # Ctrl+D = durdur
        if ('ctrl_l' in self.pressed_keys or 'ctrl_r' in self.pressed_keys):
            if key_name == 'd':
                if self.on_ctrl_d:
                    self.on_ctrl_d()
                return

        if not self.recording:
            return

        self.events.append({
            't': 'kp',
            'k': self._key_serialize(key),
            's': self._t()
        })

    def _kr(self, key):
        key_name = self._get_key_name(key)
        self.pressed_keys.discard(key_name)

        if not self.recording:
            return

        self.events.append({
            't': 'kr',
            'k': self._key_serialize(key),
            's': self._t()
        })

    def _get_key_name(self, key):
        """Tus adini al - karsilastirma icin"""
        try:
            return key.char.lower() if key.char else str(key)
        except AttributeError:
            return key.name.lower() if hasattr(key, 'name') else str(key)

    def _key_serialize(self, key):
        """Tusu kaydetmek icin serializasyon - TUM tuslar desteklenir"""
        try:
            if key.char is not None:
                return {'type': 'char', 'char': key.char}
        except AttributeError:
            pass

        # Ozel tuslar (Ctrl, Shift, Alt, Enter, Tab, vb)
        if hasattr(key, 'name'):
            return {'type': 'special', 'name': key.name}

        # vk kodlu tuslar (bazi ozel karakterler)
        if hasattr(key, 'vk'):
            return {'type': 'vk', 'vk': key.vk}

        return {'type': 'unknown', 'str': str(key)}

    def _key_deserialize(self, data):
        """Kaydedilmis tusu geri coz - TUM tuslar desteklenir"""
        ktype = data.get('type', '')

        if ktype == 'char':
            ch = data.get('char')
            if ch is not None:
                return KeyCode.from_char(ch)
            return None

        elif ktype == 'special':
            name = data.get('name', '')
            return getattr(Key, name, None)

        elif ktype == 'vk':
            vk = data.get('vk')
            if vk is not None:
                return KeyCode.from_vk(vk)
            return None

        return None

    def play(self, on_prog=None, on_done=None):
        if not self.events:
            return
        self.playing = True
        self.stop_flag = False

        def go():
            for lp in range(self.loops):
                if self.stop_flag:
                    break
                prev = 0
                tot = len(self.events)
                for i, ev in enumerate(self.events):
                    if self.stop_flag:
                        break
                    dly = (ev['s'] - prev) / self.speed
                    if dly > 0:
                        w = 0.0
                        while w < dly and not self.stop_flag:
                            time.sleep(min(0.03, dly - w))
                            w += 0.03
                    if self.stop_flag:
                        break
                    prev = ev['s']
                    try:
                        self._run(ev)
                    except Exception:
                        pass
                    if on_prog:
                        on_prog(i + 1, tot, lp + 1)
            self.playing = False
            if on_done:
                on_done()

        threading.Thread(target=go, daemon=True).start()

    def stop(self):
        self.stop_flag = True
        self.playing = False

    def _run(self, ev):
        t = ev['t']
        if t == 'mv':
            self.mc.position = (ev['x'], ev['y'])
        elif t == 'cl':
            self.mc.position = (ev['x'], ev['y'])
            b = getattr(MouseButton, ev['b'])
            if ev['p']:
                self.mc.press(b)
            else:
                self.mc.release(b)
        elif t == 'sc':
            self.mc.position = (ev['x'], ev['y'])
            self.mc.scroll(ev['dx'], ev['dy'])
        elif t == 'kp':
            k = self._key_deserialize(ev['k'])
            if k is not None:
                self.kc.press(k)
        elif t == 'kr':
            k = self._key_deserialize(ev['k'])
            if k is not None:
                self.kc.release(k)

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'v': '2.0', 'n': len(self.events), 'e': self.events}, f)

    def load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.events = d['e']
        return d.get('n', len(self.events))


# ══════════════════════════════════════════
#  ANA UYGULAMA
# ══════════════════════════════════════════
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
        # Ctrl+D callback
        self.engine.on_ctrl_d = lambda: self.root.after(0, self._stop)
        self._build()
        self._setup_hotkeys()

    def _build(self):
        self.root.configure(bg=self.BG)
        main = tk.Frame(self.root, bg=self.BG, padx=24, pady=14)
        main.pack(fill='both', expand=True)

        # ── BASLIK ──
        hdr = tk.Frame(main, bg=self.BG)
        hdr.pack(fill='x', pady=(0, 12))
        tk.Label(hdr, text="AutoFlow", font=("Segoe UI", 22, "bold"),
                 fg=self.BLUE, bg=self.BG).pack(side='left')
        tk.Label(hdr, text="v2.0", font=("Segoe UI", 9),
                 fg=self.TEXT3, bg=self.BG).pack(side='left', padx=(8, 0), pady=(10, 0))

        # ══════════════════════════════════
        #  EBYS OZEL BUTON
        # ══════════════════════════════════
        ebys_card = tk.Frame(main, bg="#f5f3ff", highlightbackground="#c4b5fd",
                             highlightthickness=2, padx=20, pady=16)
        ebys_card.pack(fill='x', pady=(0, 12))

        tk.Label(ebys_card, text="EBYS Evrak Islemleri", font=("Segoe UI", 13, "bold"),
                 fg="#5b21b6", bg="#f5f3ff").pack(anchor='w', pady=(0, 8))

        tk.Label(ebys_card, text="Once KAYDET ile islemi bir kez yapin, sonra bu butonla\n"
                 "tum evraklari otomatik isleme alin.",
                 font=("Segoe UI", 9), fg="#7c3aed", bg="#f5f3ff",
                 justify='left').pack(anchor='w', pady=(0, 10))

        ebys_row = tk.Frame(ebys_card, bg="#f5f3ff")
        ebys_row.pack(fill='x')

        self.btn_ebys = tk.Button(ebys_row,
            text="EVRAKLARI ISLE\n(Desimal Kaydet + Dongu)",
            font=("Segoe UI", 12, "bold"),
            bg="#7c3aed", fg="white",
            activebackground="#6d28d9", activeforeground="white",
            relief='flat', cursor='hand2', pady=12,
            command=self._ebys_start)
        self.btn_ebys.pack(side='left', fill='x', expand=True, padx=(0, 6))

        # EBYS evrak sayisi
        ebys_count = tk.Frame(ebys_card, bg="#f5f3ff")
        ebys_count.pack(fill='x', pady=(10, 0))

        tk.Label(ebys_count, text="Kac evrak islenecek?",
                 font=("Segoe UI", 10), fg="#5b21b6", bg="#f5f3ff").pack(side='left')

        self.ebys_count_var = tk.StringVar(value="100")
        ebys_entry = tk.Entry(ebys_count, textvariable=self.ebys_count_var,
                               font=("Segoe UI", 12, "bold"), width=6,
                               bg="white", fg=self.TEXT, relief='solid', bd=1,
                               justify='center')
        ebys_entry.pack(side='left', padx=(8, 4), ipady=4)

        tk.Label(ebys_count, text="adet",
                 font=("Segoe UI", 10), fg="#7c3aed", bg="#f5f3ff").pack(side='left')

        # ══════════════════════════════════
        #  KAYDET / OYNAT BUTONLARI
        # ══════════════════════════════════
        btn_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                            highlightthickness=1, padx=20, pady=16)
        btn_card.pack(fill='x', pady=(0, 10))

        tk.Label(btn_card, text="Makro Kayit", font=("Segoe UI", 11, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(anchor='w', pady=(0, 8))

        btns = tk.Frame(btn_card, bg=self.CARD)
        btns.pack(fill='x')

        self.btn_rec = tk.Button(btns,
            text="KAYDET\n(islemi bir kez yapin)",
            font=("Segoe UI", 11, "bold"),
            bg=self.RED, fg="white",
            activebackground="#ef4444", activeforeground="white",
            relief='flat', cursor='hand2', width=20, pady=10,
            command=self._toggle_rec)
        self.btn_rec.pack(side='left', expand=True, fill='both', padx=(0, 4))

        self.btn_play = tk.Button(btns,
            text="OYNAT\n(tekrar calistir)",
            font=("Segoe UI", 11, "bold"),
            bg=self.GREEN, fg="white",
            activebackground="#22c55e", activeforeground="white",
            relief='flat', cursor='hand2', width=20, pady=10,
            command=self._toggle_play)
        self.btn_play.pack(side='left', expand=True, fill='both', padx=(4, 0))

        # DURDUR
        self.btn_stop = tk.Button(main,
            text="DURDUR  (veya Ctrl+D basin)",
            font=("Segoe UI", 11, "bold"),
            bg="#fef2f2", fg=self.RED,
            activebackground="#fee2e2", activeforeground=self.RED,
            relief='flat', cursor='hand2', pady=8,
            command=self._stop, state='disabled')
        self.btn_stop.pack(fill='x', pady=(0, 10))

        # ══════════════════════════════════
        #  TEKRAR + HIZ
        # ══════════════════════════════════
        settings_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                                  highlightthickness=1, padx=20, pady=12)
        settings_card.pack(fill='x', pady=(0, 10))

        # Tekrar
        r1 = tk.Frame(settings_card, bg=self.CARD)
        r1.pack(fill='x', pady=(0, 8))

        tk.Label(r1, text="Tekrar:", font=("Segoe UI", 10, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(side='left')

        self.loop_var = tk.StringVar(value="10")
        for val in ["1", "5", "10", "50", "100"]:
            tk.Button(r1, text=val, font=("Segoe UI", 10),
                      bg="#f1f5f9", fg=self.TEXT, relief='flat', cursor='hand2',
                      width=4, pady=3,
                      command=lambda v=val: self.loop_var.set(v)
                      ).pack(side='left', padx=2)

        tk.Entry(r1, textvariable=self.loop_var, font=("Segoe UI", 11), width=5,
                 bg="#f8fafc", fg=self.TEXT, relief='solid', bd=1,
                 justify='center').pack(side='left', padx=(8, 2), ipady=2)
        tk.Label(r1, text="kez", font=("Segoe UI", 9),
                 fg=self.TEXT3, bg=self.CARD).pack(side='left')

        # Hiz
        r2 = tk.Frame(settings_card, bg=self.CARD)
        r2.pack(fill='x')

        tk.Label(r2, text="Hiz:", font=("Segoe UI", 10, "bold"),
                 fg=self.TEXT, bg=self.CARD).pack(side='left', padx=(0, 8))

        self.speed_var = tk.StringVar(value="1.0")
        for label, val in [("Yavas", "0.5"), ("Normal", "1.0"), ("Hizli", "2.0"), ("Max", "5.0")]:
            tk.Button(r2, text=f"{label}", font=("Segoe UI", 9),
                      bg="#f1f5f9", fg=self.TEXT, relief='flat', cursor='hand2',
                      padx=8, pady=3,
                      command=lambda v=val: self.speed_var.set(v)
                      ).pack(side='left', padx=2)

        # ══════════════════════════════════
        #  DOSYA + TEMIZLE
        # ══════════════════════════════════
        file_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                             highlightthickness=1, padx=20, pady=10)
        file_card.pack(fill='x', pady=(0, 10))

        file_row = tk.Frame(file_card, bg=self.CARD)
        file_row.pack(fill='x')

        for txt, cmd in [("Makroyu Kaydet", self._save), ("Makro Yukle", self._load), ("Temizle", self._clear)]:
            fg = self.RED if txt == "Temizle" else self.TEXT
            tk.Button(file_row, text=txt, font=("Segoe UI", 9),
                      bg="#f1f5f9", fg=fg, relief='flat', cursor='hand2',
                      padx=14, pady=5, command=cmd).pack(side='left', padx=(0, 4))

        # ══════════════════════════════════
        #  DURUM
        # ══════════════════════════════════
        stat_card = tk.Frame(main, bg=self.CARD, highlightbackground=self.BORDER,
                             highlightthickness=1, padx=20, pady=10)
        stat_card.pack(fill='x')

        self.lbl_status = tk.Label(stat_card, text="Hazir. KAYDET butonuna basin.",
                                    font=("Segoe UI", 11), fg=self.BLUE, bg=self.CARD)
        self.lbl_status.pack(anchor='w')

        self.lbl_detail = tk.Label(stat_card, text="",
                                    font=("Segoe UI", 9), fg=self.TEXT3, bg=self.CARD)
        self.lbl_detail.pack(anchor='w')

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Blue.Horizontal.TProgressbar",
                         troughcolor="#e2e8f0", background=self.BLUE, thickness=8)
        self.progress = ttk.Progressbar(stat_card, mode='determinate',
                                         style="Blue.Horizontal.TProgressbar")

        # Kisayollar
        tk.Label(main, text="Ctrl+D = Durdur  |  Kayit sirasinda Ctrl+C, Ctrl+V vb. hepsi kaydedilir",
                 font=("Segoe UI", 8), fg=self.TEXT3, bg=self.BG).pack(pady=(6, 0))

    def _sync(self):
        try:
            self.engine.loops = max(1, int(self.loop_var.get()))
        except ValueError:
            self.engine.loops = 1
        try:
            self.engine.speed = float(self.speed_var.get())
        except ValueError:
            self.engine.speed = 1.0

    # ── Hotkeys ──
    def _setup_hotkeys(self):
        # Ctrl+D zaten engine icinde yakalaniyor
        # F tuslari icin ayri listener
        def handler(key):
            try:
                if key == Key.f9:
                    self.root.after(0, self._toggle_rec)
                elif key == Key.f10:
                    self.root.after(0, self._toggle_play)
                elif key == Key.f11:
                    self.root.after(0, self._stop)
            except Exception:
                pass

        self.hk = keyboard.Listener(on_press=handler)
        self.hk.daemon = True
        self.hk.start()

    # ── EBYS Ozel ──
    def _ebys_start(self):
        if self.engine.recording or self.engine.playing:
            return
        if not self.engine.events:
            messagebox.showinfo("Bilgi",
                "Once KAYDET butonuna basip islemi bir kez yapin!\n\n"
                "1. KAYDET butonuna basin\n"
                "2. EBYS'de bir evraki acin, desimali kaydedin\n"
                "3. KAYDET butonuna tekrar basin (kaydi durdur)\n"
                "4. Sonra bu butona basin, otomatik tekrar eder")
            return

        try:
            count = max(1, int(self.ebys_count_var.get()))
        except ValueError:
            count = 100

        self.engine.loops = count
        self.loop_var.set(str(count))
        self._start_play()

    # ── Kayit ──
    def _toggle_rec(self):
        if self.engine.playing:
            return
        if not self.engine.recording:
            self.engine.rec_start()
            self.btn_rec.configure(text="KAYDI DURDUR\n(Ctrl+D veya tekrar tikla)",
                                    bg=self.ORANGE)
            self.btn_play.configure(state='disabled')
            self.btn_ebys.configure(state='disabled')
            self.btn_stop.configure(state='normal')
            self.lbl_status.configure(text="KAYDEDILIYOR...", fg=self.RED)
            self.lbl_detail.configure(text="Islemlerinizi yapin, bitince Ctrl+D basin")
            self._tick()
        else:
            self._stop_rec()

    def _stop_rec(self):
        if not self.engine.recording:
            return
        self.engine.rec_stop()
        n = len(self.engine.events)
        d = self.engine.events[-1]['s'] if self.engine.events else 0
        self.btn_rec.configure(text="KAYDET\n(islemi bir kez yapin)", bg=self.RED)
        self.btn_play.configure(state='normal')
        self.btn_ebys.configure(state='normal')
        self.btn_stop.configure(state='disabled')
        self.lbl_status.configure(text=f"Kayit tamam! {n} hareket, {d:.1f} saniye", fg=self.GREEN)
        self.lbl_detail.configure(text="OYNAT veya EVRAKLARI ISLE butonuna basin")

    # ── Oynat ──
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
        self.btn_ebys.configure(state='disabled')
        self.btn_stop.configure(state='normal', bg="#fef2f2", fg=self.RED)
        self.progress.pack(fill='x', pady=(8, 0))
        self.progress['maximum'] = len(self.engine.events)
        self.progress['value'] = 0
        lt = f" ({self.engine.loops} kez)" if self.engine.loops > 1 else ""
        self.lbl_status.configure(text=f"Calisiyor...{lt}", fg=self.BLUE)
        self.lbl_detail.configure(text="Durdurmak icin Ctrl+D basin")
        self.engine.play(on_prog=self._prog, on_done=self._done)

    def _prog(self, cur, tot, lp):
        def u():
            self.progress['value'] = cur
            lt = f" [Dongu {lp}/{self.engine.loops}]" if self.engine.loops > 1 else ""
            self.lbl_status.configure(text=f"Calisiyor... {cur}/{tot}{lt}", fg=self.BLUE)
        self.root.after(0, u)

    def _done(self):
        def u():
            self.btn_rec.configure(state='normal')
            self.btn_play.configure(state='normal')
            self.btn_ebys.configure(state='normal')
            self.btn_stop.configure(state='disabled')
            self.progress.pack_forget()
            self.lbl_status.configure(text="Tamamlandi!", fg=self.GREEN)
            self.lbl_detail.configure(text=f"{self.engine.loops} evrak basariyla islendi")
        self.root.after(0, u)

    def _stop(self):
        if self.engine.recording:
            self._stop_rec()
            return
        if self.engine.playing:
            self.engine.stop()
            self.btn_rec.configure(state='normal')
            self.btn_play.configure(state='normal')
            self.btn_ebys.configure(state='normal')
            self.btn_stop.configure(state='disabled')
            self.progress.pack_forget()
            self.lbl_status.configure(text="Durduruldu.", fg=self.ORANGE)
            self.lbl_detail.configure(text="")

    def _save(self):
        if not self.engine.events:
            messagebox.showinfo("Bilgi", "Kaydedilecek makro yok!")
            return
        fp = filedialog.asksaveasfilename(title="Makroyu Kaydet",
            defaultextension=".autoflow",
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
                self.lbl_detail.configure(text=f"{os.path.basename(fp)}")
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
            self.lbl_detail.configure(text=f"Sure: {el:.1f}s | {n} hareket | Ctrl+D = durdur")
            self.root.after(100, self._tick)


# ══════════════════════════════════════════
#  BASLAT
# ══════════════════════════════════════════
def main():
    root = tk.Tk()
    root.title("AutoFlow v2.0 - EBYS Otomasyon")
    root.geometry("580x760")
    root.minsize(500, 700)
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
