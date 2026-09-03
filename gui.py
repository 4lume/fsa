import queue
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

try:
    from new_parser.utils.file_helpers import measure_linecount_bom
    from new_parser.utils.worker import execute_all_passes
except ModuleNotFoundError:
    from utils.file_helpers import measure_linecount_bom
    from utils.worker import execute_all_passes

COLOR_BG = '#0c0e14'
COLOR_SURFACE = '#151922'
COLOR_SURFACE_ELEVATED = '#1c2230'
COLOR_BORDER = '#2a3142'
COLOR_TEXT = '#e8eaef'
COLOR_TEXT_MUTED = '#8b93a7'
COLOR_ACCENT = '#7c6cf0'
COLOR_ACCENT_HOVER = '#9488ff'
COLOR_SUCCESS = '#34d399'


def _font(size: int, weight: str = 'normal') -> ctk.CTkFont:
    return ctk.CTkFont(size=size, weight=weight)


class APIHarvestTkShell:
    def __init__(self, shell: ctk.CTk):
        self.shell = shell
        self.shell.title('Парсер FSA')
        self.shell.geometry('880x700')
        self.shell.minsize(760, 560)
        self.shell.configure(fg_color=COLOR_BG)

        self.path_xlsx = None
        self.path_ids = None
        self.token_var = ctk.StringVar()
        self.progress_q = queue.Queue()
        self.worker_thread = None
        self.slot_total = 0
        self.slot_done = 0
        self._run_locked = False

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
        root = ctk.CTkFrame(self.shell, fg_color='transparent')
        root.pack(fill='both', expand=True, padx=40, pady=36)

        hero = ctk.CTkFrame(root, fg_color='transparent')
        hero.pack(fill='x', pady=(0, 8))
        ctk.CTkLabel(
            hero,
            text='Парсер FSA',
            font=_font(26, 'bold'),
            text_color=COLOR_TEXT,
        ).pack(anchor='w')

        token_card = ctk.CTkFrame(root, fg_color=COLOR_SURFACE, corner_radius=18, border_width=1, border_color=COLOR_BORDER)
        token_card.pack(fill='x', pady=(20, 14))
        inner_token = ctk.CTkFrame(token_card, fg_color='transparent')
        inner_token.pack(fill='both', expand=True, padx=22, pady=18)
        ctk.CTkLabel(inner_token, text='Bearer-токен', font=_font(13, 'bold'), text_color=COLOR_TEXT_MUTED).pack(anchor='w', pady=(0, 8))
        self.entry_token = ctk.CTkEntry(
            inner_token,
            textvariable=self.token_var,
            placeholder_text='Вставь токен',
            height=40,
            corner_radius=12,
            fg_color=COLOR_SURFACE_ELEVATED,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=_font(14),
        )
        self.entry_token.pack(fill='x')

        card_file = ctk.CTkFrame(root, fg_color=COLOR_SURFACE, corner_radius=18, border_width=1, border_color=COLOR_BORDER)
        card_file.pack(fill='x', pady=(0, 14))
        inner_f = ctk.CTkFrame(card_file, fg_color='transparent')
        inner_f.pack(fill='both', expand=True, padx=22, pady=18)
        ctk.CTkLabel(inner_f, text='Выберите файл Excel', font=_font(13, 'bold'), text_color=COLOR_TEXT_MUTED).pack(anchor='w', pady=(0, 10))
        row = ctk.CTkFrame(inner_f, fg_color='transparent')
        row.pack(fill='x')
        self.btn_workbook = ctk.CTkButton(row, text='Выбрать файл', width=150, height=44, corner_radius=12, fg_color=COLOR_SURFACE_ELEVATED, hover_color=COLOR_BORDER, border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT, font=_font(14, 'bold'), command=self.on_take_file)
        self.btn_workbook.pack(side='left', padx=(0, 16))
        self.lbl_file = ctk.CTkLabel(row, text='Файл не выбран', font=_font(13), text_color=COLOR_TEXT_MUTED, anchor='w', justify='left', wraplength=520)
        self.lbl_file.pack(side='left', fill='x', expand=True)

        card_ids = ctk.CTkFrame(root, fg_color=COLOR_SURFACE, corner_radius=18, border_width=1, border_color=COLOR_BORDER)
        card_ids.pack(fill='x', pady=(0, 14))
        inner_ids = ctk.CTkFrame(card_ids, fg_color='transparent')
        inner_ids.pack(fill='both', expand=True, padx=22, pady=18)
        ctk.CTkLabel(inner_ids, text='Список идентификаторов', font=_font(13, 'bold'), text_color=COLOR_TEXT_MUTED).pack(anchor='w', pady=(0, 10))
        row_ids = ctk.CTkFrame(inner_ids, fg_color='transparent')
        row_ids.pack(fill='x')
        self.btn_ids = ctk.CTkButton(row_ids, text='Выбрать список', width=150, height=44, corner_radius=12, fg_color=COLOR_SURFACE_ELEVATED, hover_color=COLOR_BORDER, border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT, font=_font(14, 'bold'), command=self.on_take_ids_file)
        self.btn_ids.pack(side='left', padx=(0, 16))
        self.lbl_ids = ctk.CTkLabel(row_ids, text='Файл не выбран', font=_font(13), text_color=COLOR_TEXT_MUTED, anchor='w', justify='left', wraplength=520)
        self.lbl_ids.pack(side='left', fill='x', expand=True)

        card_run = ctk.CTkFrame(root, fg_color=COLOR_SURFACE, corner_radius=18, border_width=1, border_color=COLOR_BORDER)
        card_run.pack(fill='x', pady=(0, 20))
        inner_r = ctk.CTkFrame(card_run, fg_color='transparent')
        inner_r.pack(fill='both', expand=True, padx=22, pady=18)
        ctk.CTkLabel(inner_r, text='Запуск', font=_font(13, 'bold'), text_color=COLOR_TEXT_MUTED).pack(anchor='w', pady=(0, 12))
        run_row = ctk.CTkFrame(inner_r, fg_color='transparent')
        run_row.pack(fill='x')
        self.btn_run = ctk.CTkButton(run_row, text='Старт', width=140, height=46, corner_radius=12, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color='#ffffff', font=_font(15, 'bold'), command=self.on_submit_job)
        self.btn_run.pack(side='left', padx=(0, 20))
        bar_col = ctk.CTkFrame(run_row, fg_color='transparent')
        bar_col.pack(side='left', fill='x', expand=True)
        self.progress = ctk.CTkProgressBar(bar_col, height=14, corner_radius=7, progress_color=COLOR_ACCENT, fg_color=COLOR_SURFACE_ELEVATED)
        self.progress.pack(fill='x', pady=(16, 0))
        self.progress.set(0)
        self.lbl_counter = ctk.CTkLabel(root, text='0 из 0', font=_font(14, 'bold'), text_color=COLOR_SUCCESS)
        self.lbl_counter.pack(anchor='w', pady=(4, 0))

    def on_take_file(self):
        chosen = filedialog.askopenfilename(parent=self.shell, title='Книга Excel', filetypes=[('Excel', '*.xlsx'), ('Все файлы', '*.*')])
        if chosen:
            self.path_xlsx = chosen
            self.lbl_file.configure(text=self._short_path(chosen), text_color=COLOR_TEXT)
        else:
            self.lbl_file.configure(text='Файл не выбран', text_color=COLOR_TEXT_MUTED)

    def on_take_ids_file(self):
        chosen = filedialog.askopenfilename(parent=self.shell, title='Список идентификаторов', filetypes=[('Текст', '*.txt'), ('Все файлы', '*.*')])
        if chosen:
            self.path_ids = chosen
            self.lbl_ids.configure(text=self._short_path(chosen), text_color=COLOR_TEXT)
        else:
            self.lbl_ids.configure(text='Файл не выбран', text_color=COLOR_TEXT_MUTED)

    @staticmethod
    def _short_path(path: str, head: int = 32, tail: int = 40) -> str:
        if len(path) <= head + tail + 3:
            return path
        return path[:head] + '…' + path[-tail:]

    def on_submit_job(self):
        if not self.path_xlsx:
            messagebox.showwarning('Нет выбранного файла Excel', 'Сначала выберите файл .xlsx.', parent=self.shell)
            return
        if not self.path_ids:
            messagebox.showwarning('Нет выбранного файла списка идентификаторов', 'Выберите текстовый файл с идентификаторами.', parent=self.shell)
            return
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror('Ошибка', 'Нужен Bearer-токен для API.', parent=self.shell)
            return
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo('Текущий запуск уже выполняется', 'Дождитесь завершения текущего запуска.', parent=self.shell)
            return

        self.slot_total = measure_linecount_bom(self.path_ids)
        self.slot_done = 0
        self.progress_q.queue.clear()
        self.progress_q.put((self.slot_done, self.slot_total))
        self.worker_thread = threading.Thread(
            target=execute_all_passes,
            args=(self, self.path_xlsx, self.path_ids, token),
            daemon=True,
        )
        self.worker_thread.start()
        self._run_locked = True
        self.btn_run.configure(state='disabled', text='Выполняется…', fg_color=COLOR_BORDER)
        self.btn_workbook.configure(state='disabled')
        self.btn_ids.configure(state='disabled')
        self.entry_token.configure(state='disabled')

    def _release_run_ui(self):
        self._run_locked = False
        self.btn_run.configure(state='normal', text='Старт', fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.btn_workbook.configure(state='normal')
        self.btn_ids.configure(state='normal')
        self.entry_token.configure(state='normal')

    def _tick_meter(self):
        if not self.progress_q.empty():
            item = self.progress_q.get()
            if isinstance(item, tuple) and len(item) == 2 and item[0] == 'error':
                self._release_run_ui()
                messagebox.showerror('Ошибка', item[1], parent=self.shell)
            elif isinstance(item, tuple) and len(item) == 2:
                self.slot_done, self.slot_total = item
                total = max(self.slot_total, 1)
                frac = min(1.0, max(0.0, self.slot_done / total))
                self.progress.set(frac)
                self.lbl_counter.configure(text=f'{self.slot_done} из {self.slot_total}')

        if self._run_locked and self.worker_thread and not self.worker_thread.is_alive() and self.progress_q.empty():
            self.progress.set(1.0)
            self.lbl_counter.configure(text=f'{self.slot_total} из {self.slot_total}')
            self._release_run_ui()

        self.shell.after(100, self._tick_meter)


def main():
    ctk.set_appearance_mode('dark')
    ctk.set_default_color_theme('dark-blue')
    shell = ctk.CTk()
    APIHarvestTkShell(shell)
    shell.mainloop()


if __name__ == '__main__':
    main()
