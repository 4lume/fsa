import queue
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

try:
    from new_parser.utils.fsa_constants import TECH_REG_TR_TS_010, TECH_REG_TR_TS_032
    from new_parser.utils.worker import execute_all_passes
except ModuleNotFoundError:
    from utils.fsa_constants import TECH_REG_TR_TS_010, TECH_REG_TR_TS_032
    from utils.worker import execute_all_passes

COLOR_BG = '#ffffff'
COLOR_SURFACE = '#ffffff'
COLOR_SURFACE_ELEVATED = '#f5f5f5'
COLOR_BORDER = '#e2e2e2'
COLOR_TEXT = '#1a1a1a'
COLOR_TEXT_MUTED = '#6b6b6b'
COLOR_ACCENT = '#A01E1E'
COLOR_ACCENT_HOVER = '#821818'
COLOR_ACCENT_SOFT = '#F8EAEA'
COLOR_SUCCESS = '#A01E1E'
COLOR_DISABLED = '#cfcfcf'
PAD = 28
GAP = 16
RADIUS = 12
CONTROL_H = 40
FONT_SIZE = 13


def _asset_path(name: str) -> Path:
    if getattr(sys, 'frozen', False):
        base = Path(getattr(sys, '_MEIPASS', Path(sys.executable).resolve().parent))
    else:
        base = Path(__file__).resolve().parent
    return base / 'assets' / name


class APIHarvestTkShell:
    def __init__(self, shell: ctk.CTk):
        self.shell = shell
        self.shell.title('Баукен и партнеры - fsa.gov')
        self.shell.geometry('880x820')
        self.shell.minsize(760, 680)
        self.shell.configure(fg_color=COLOR_BG)

        self.path_xlsx = None
        self.token_var = ctk.StringVar()
        self.start_date_var = ctk.StringVar(value='2024-01-01')
        self.end_date_var = ctk.StringVar(value='2024-02-01')
        self.tech_reg_var = ctk.StringVar(value=TECH_REG_TR_TS_010)
        self.progress_q = queue.Queue()
        self.worker_thread = None
        self.slot_total = 0
        self.slot_done = 0
        self._run_locked = False
        self._cancel_requested = threading.Event()
        self._param_entries: list[ctk.CTkEntry] = []
        self._tech_reg_radios: list[ctk.CTkRadioButton] = []
        self.font_ui = ctk.CTkFont(size=FONT_SIZE, weight='bold')
        self.font_body = ctk.CTkFont(size=FONT_SIZE)
        self.font_header = ctk.CTkFont(size=22, weight='bold')

        self._build_layout()
        self._center_window()
        self._tick_meter()

    def _center_window(self):
        self.shell.update_idletasks()
        w, h = self.shell.winfo_width(), self.shell.winfo_height()
        x = (self.shell.winfo_screenwidth() - w) // 2
        y = (self.shell.winfo_screenheight() - h) // 2
        self.shell.geometry(f'+{max(0, x)}+{max(0, y)}')

    def _build_layout(self):
        header = ctk.CTkFrame(self.shell, fg_color=COLOR_ACCENT, corner_radius=0)
        header.pack(fill='x')
        hero = ctk.CTkFrame(header, fg_color='transparent')
        hero.pack(fill='x', padx=PAD * 2, pady=GAP)
        logo_path = _asset_path('logo.png')
        logo_h = 0
        if logo_path.is_file():
            logo_src = Image.open(logo_path)
            logo_h = logo_src.size[1]
            self._logo_image = ctk.CTkImage(
                light_image=logo_src,
                dark_image=logo_src,
                size=logo_src.size,
            )
            ctk.CTkLabel(hero, text='', image=self._logo_image, height=logo_h).pack(side='left', anchor='center')
        ctk.CTkLabel(
            hero,
            text='fsa.gov',
            font=self.font_header,
            text_color='#ffffff',
            height=logo_h or 28,
            anchor='e',
        ).pack(side='right', anchor='center')

        root = ctk.CTkFrame(self.shell, fg_color='transparent')
        root.pack(fill='both', expand=True, padx=PAD, pady=PAD)

        inner_token = self._card(root)
        self._label(inner_token, 'Bearer-токен')
        self.entry_token = self._entry(inner_token, self.token_var, 'Вставь токен')

        inner_p = self._card(root)
        dates = ctk.CTkFrame(inner_p, fg_color='transparent')
        dates.pack(fill='x')
        dates.grid_columnconfigure(0, weight=1)
        dates.grid_columnconfigure(1, weight=1)
        start_col = ctk.CTkFrame(dates, fg_color='transparent')
        start_col.grid(row=0, column=0, sticky='new', padx=(0, GAP // 2))
        end_col = ctk.CTkFrame(dates, fg_color='transparent')
        end_col.grid(row=0, column=1, sticky='new', padx=(GAP // 2, 0))
        self._add_date_field(start_col, 'Дата начала, YYYY-MM-DD', self.start_date_var)
        self._add_date_field(end_col, 'Дата конца, YYYY-MM-DD', self.end_date_var)

        tech_block = ctk.CTkFrame(start_col, fg_color='transparent')
        tech_block.pack(fill='x', pady=(GAP, 0))
        self._label(tech_block, 'Технический регламент')
        radios = ctk.CTkFrame(tech_block, fg_color='transparent')
        radios.pack(fill='x')
        rb010 = self._radio(radios, 'ТР ТС 010', TECH_REG_TR_TS_010)
        rb010.pack(side='left')
        rb032 = self._radio(radios, 'ТР ТС 032', TECH_REG_TR_TS_032)
        rb032.pack(side='left', padx=(GAP, 0))
        self._tech_reg_radios.extend([rb010, rb032])

        file_block = ctk.CTkFrame(end_col, fg_color='transparent')
        file_block.pack(fill='x', pady=(GAP, 0))
        self._label(file_block, 'Файл Excel')
        file_row = ctk.CTkFrame(file_block, fg_color='transparent')
        file_row.pack(fill='x')
        self.btn_workbook = self._button(file_row, 'Выбрать файл', command=self.on_take_file, secondary=True, width=150)
        self.btn_workbook.pack(side='left', padx=(0, GAP))
        self.lbl_file = ctk.CTkLabel(
            file_row,
            text='Файл не выбран',
            font=self.font_body,
            text_color=COLOR_TEXT_MUTED,
            anchor='w',
            justify='left',
            height=CONTROL_H,
            wraplength=280,
        )
        self.lbl_file.pack(side='left', fill='x', expand=True)

        inner_pr = self._card(root)
        self.progress_harvest, self.lbl_harvest = self._add_progress_row(inner_pr, 'Сбор ID')
        self.progress_parse, self.lbl_parse = self._add_progress_row(inner_pr, 'Парсинг', pady_top=GAP)

        actions = ctk.CTkFrame(root, fg_color='transparent')
        actions.pack(fill='x', pady=(GAP, 0))
        self.btn_cancel = self._button(actions, 'Отменить', command=self.on_cancel_job, secondary=True, width=200)
        self.btn_cancel.pack(side='left')
        self.btn_run = self._button(actions, 'Запустить', command=self.on_submit_job, width=200)
        self.btn_run.pack(side='right')

    def _card(self, parent, last: bool = False) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, corner_radius=RADIUS, border_width=1, border_color=COLOR_BORDER)
        card.pack(fill='x', pady=(0, 0 if last else GAP))
        inner = ctk.CTkFrame(card, fg_color='transparent')
        inner.pack(fill='x', padx=PAD, pady=PAD)
        return inner

    def _label(self, parent, text: str, *, color: str = COLOR_TEXT_MUTED, side: str | None = None, expand: bool = False):
        widget = ctk.CTkLabel(parent, text=text, font=self.font_ui, text_color=color, anchor='w', height=20)
        if side:
            widget.pack(side=side, fill='x' if expand else None, expand=expand)
        else:
            widget.pack(anchor='w', pady=(0, GAP))
        return widget

    def _entry(self, parent, variable: ctk.StringVar, placeholder: str = '') -> ctk.CTkEntry:
        entry = ctk.CTkEntry(
            parent,
            textvariable=variable,
            placeholder_text=placeholder,
            height=CONTROL_H,
            corner_radius=RADIUS,
            fg_color=COLOR_SURFACE_ELEVATED,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=self.font_body,
        )
        entry.pack(fill='x')
        return entry

    def _button(self, parent, text: str, command, *, secondary: bool = False, width: int = 150) -> ctk.CTkButton:
        if secondary:
            return ctk.CTkButton(
                parent,
                text=text,
                width=width,
                height=CONTROL_H,
                corner_radius=RADIUS,
                fg_color=COLOR_SURFACE,
                hover_color=COLOR_ACCENT_SOFT,
                border_width=2,
                border_color=COLOR_ACCENT,
                text_color=COLOR_TEXT,
                font=self.font_ui,
                command=command,
            )
        return ctk.CTkButton(
            parent,
            text=text,
            width=width,
            height=CONTROL_H,
            corner_radius=RADIUS,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color='#ffffff',
            text_color_disabled='#ffffff',
            font=self.font_ui,
            command=command,
        )

    def _radio(self, parent, text: str, value: str) -> ctk.CTkRadioButton:
        return ctk.CTkRadioButton(
            parent,
            text=text,
            variable=self.tech_reg_var,
            value=value,
            font=self.font_body,
            text_color=COLOR_TEXT,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            border_color=COLOR_BORDER,
        )

    def _add_progress_row(self, parent, title: str, pady_top: int = 0):
        wrap = ctk.CTkFrame(parent, fg_color='transparent')
        wrap.pack(fill='x', pady=(pady_top, 0))
        head = ctk.CTkFrame(wrap, fg_color='transparent')
        head.pack(fill='x', pady=(0, GAP))
        ctk.CTkLabel(head, text=title, font=self.font_ui, text_color=COLOR_TEXT_MUTED, anchor='w', height=20).pack(side='left')
        counter = ctk.CTkLabel(head, text='0 из 0', font=self.font_ui, text_color=COLOR_SUCCESS, anchor='e', height=20)
        counter.pack(side='right')
        bar = ctk.CTkProgressBar(wrap, height=10, corner_radius=5, progress_color=COLOR_ACCENT, fg_color=COLOR_SURFACE_ELEVATED)
        bar.pack(fill='x')
        bar.set(0)
        return bar, counter

    def _add_date_field(self, parent, title: str, variable: ctk.StringVar):
        self._label(parent, title)
        entry = self._entry(parent, variable)
        self._param_entries.append(entry)

    def on_take_file(self):
        chosen = filedialog.askopenfilename(parent=self.shell, title='Книга Excel', filetypes=[('Excel', '*.xlsx'), ('Все файлы', '*.*')])
        if chosen:
            self.path_xlsx = chosen
            self.lbl_file.configure(text=self._short_path(chosen), text_color=COLOR_TEXT)
        else:
            self.lbl_file.configure(text='Файл не выбран', text_color=COLOR_TEXT_MUTED)

    @staticmethod
    def _short_path(path: str, head: int = 32, tail: int = 40) -> str:
        if len(path) <= head + tail + 3:
            return path
        return path[:head] + '…' + path[-tail:]

    def on_submit_job(self):
        if not self.path_xlsx:
            messagebox.showwarning('Нет выбранного файла Excel', 'Сначала выберите файл .xlsx.', parent=self.shell)
            return
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror('Ошибка', 'Нужен Bearer-токен для API.', parent=self.shell)
            return
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()
        if not start_date:
            messagebox.showerror('Ошибка', 'Укажите дату начала.', parent=self.shell)
            return
        if not end_date:
            messagebox.showerror('Ошибка', 'Укажите дату конца.', parent=self.shell)
            return
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo('Текущий запуск уже выполняется', 'Дождитесь завершения текущего запуска.', parent=self.shell)
            return

        self.slot_total = 0
        self.slot_done = 0
        self._cancel_requested.clear()
        self.progress_harvest.set(0)
        self.progress_parse.set(0)
        self.lbl_harvest.configure(text='0 из 0')
        self.lbl_parse.configure(text='0 из 0')
        self.progress_q.queue.clear()
        self.worker_thread = threading.Thread(
            target=execute_all_passes,
            args=(self, self.path_xlsx, token, start_date, end_date, self.tech_reg_var.get()),
            daemon=True,
        )
        self.worker_thread.start()
        self._run_locked = True
        self.btn_run.configure(state='disabled', text='Выполняется…', fg_color=COLOR_ACCENT)
        self.btn_workbook.configure(state='disabled')
        self.entry_token.configure(state='disabled')
        for entry in self._param_entries:
            entry.configure(state='disabled')
        for radio in self._tech_reg_radios:
            radio.configure(state='disabled')

    def on_cancel_job(self):
        if not self._run_locked:
            messagebox.showwarning('Отмена', 'Программа еще не запущена', parent=self.shell)
            return
        self._cancel_requested.set()

    def is_cancelled(self) -> bool:
        return self._cancel_requested.is_set()

    def _release_run_ui(self):
        self._run_locked = False
        self._cancel_requested.clear()
        self.btn_run.configure(state='normal', text='Запустить', fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.btn_workbook.configure(state='normal')
        self.entry_token.configure(state='normal')
        for entry in self._param_entries:
            entry.configure(state='normal')
        for radio in self._tech_reg_radios:
            radio.configure(state='normal')

    def _tick_meter(self):
        while not self.progress_q.empty():
            item = self.progress_q.get()
            if isinstance(item, tuple) and len(item) >= 2 and item[0] == 'error':
                self._release_run_ui()
                messagebox.showerror('Ошибка', item[1], parent=self.shell)
            elif isinstance(item, tuple) and item and item[0] == 'cancelled':
                self._release_run_ui()
            elif isinstance(item, tuple) and item and item[0] == 'harvest':
                done = item[1]
                total = item[2] if len(item) > 2 else None
                if total:
                    self.progress_harvest.set(min(1.0, max(0.0, done / total)))
                    self.lbl_harvest.configure(text=f'{done} из {total}')
                else:
                    self.lbl_harvest.configure(text=str(done))
            elif isinstance(item, tuple) and item and item[0] == 'parse':
                self.slot_done, self.slot_total = item[1], item[2]
                total = max(self.slot_total, 1)
                self.progress_parse.set(min(1.0, max(0.0, self.slot_done / total)))
                self.lbl_parse.configure(text=f'{self.slot_done} из {self.slot_total}')

        if self._run_locked and self.worker_thread and not self.worker_thread.is_alive() and self.progress_q.empty():
            if self.slot_total and not self.is_cancelled():
                self.progress_harvest.set(1.0)
                self.progress_parse.set(1.0)
                self.lbl_parse.configure(text=f'{self.slot_total} из {self.slot_total}')
            self._release_run_ui()

        self.shell.after(100, self._tick_meter)


def main():
    ctk.set_appearance_mode('light')
    ctk.set_default_color_theme('dark-blue')
    shell = ctk.CTk()
    APIHarvestTkShell(shell)
    shell.mainloop()


if __name__ == '__main__':
    main()
