import queue
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

try:
    from new_parser.utils.fsa_constants import (
        DOC_TYPE_CERTIFICATE,
        DOC_TYPE_DECLARATION,
        EEU_GROUP_ALL_LABEL,
        TECH_REG_TR_TS_010,
        TECH_REG_TR_TS_032,
        get_eeu_groups,
    )
    from new_parser.utils.worker import execute_all_passes
except ModuleNotFoundError:
    from utils.fsa_constants import (
        DOC_TYPE_CERTIFICATE,
        DOC_TYPE_DECLARATION,
        EEU_GROUP_ALL_LABEL,
        TECH_REG_TR_TS_010,
        TECH_REG_TR_TS_032,
        get_eeu_groups,
    )
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


class ScrollableOptionButton(ctk.CTkFrame):
    """Выпадающий мультивыбор с поиском — нормально работает с длинными списками в exe."""

    def __init__(
        self,
        master,
        values: list[str],
        *,
        height: int = CONTROL_H,
        max_popup_height: int = 360,
        font=None,
        fg_color=COLOR_SURFACE_ELEVATED,
        button_color=COLOR_ACCENT,
        button_hover_color=COLOR_ACCENT_HOVER,
        text_color=COLOR_TEXT,
        dropdown_fg_color=COLOR_SURFACE,
        dropdown_hover_color=COLOR_ACCENT_SOFT,
        dropdown_text_color=COLOR_TEXT,
        border_color=COLOR_BORDER,
        all_label: str = EEU_GROUP_ALL_LABEL,
    ):
        super().__init__(master, fg_color='transparent')
        self._all_label = all_label
        self._values = list(values)
        self._selected: set[str] = {all_label}
        self._max_popup_height = max_popup_height
        self._popup: ctk.CTkToplevel | None = None
        self._scroll: ctk.CTkScrollableFrame | None = None
        self._search_entry: ctk.CTkEntry | None = None
        self._done_button: ctk.CTkButton | None = None
        self._search_var = ctk.StringVar(value='')
        self._item_rows: list[tuple[str, ctk.CTkCheckBox, ctk.BooleanVar]] = []
        self._popup_visible = False
        self._values_dirty = True
        self._font = font
        self._dropdown_fg_color = dropdown_fg_color
        self._dropdown_hover_color = dropdown_hover_color
        self._dropdown_text_color = dropdown_text_color
        self._border_color = border_color
        self._button_color = button_color
        self._button_hover_color = button_hover_color

        self._button = ctk.CTkButton(
            self,
            text=self._summary_text(),
            height=height,
            corner_radius=RADIUS,
            fg_color=fg_color,
            hover_color=COLOR_ACCENT_SOFT,
            border_width=1,
            border_color=border_color,
            text_color=text_color,
            font=font,
            anchor='w',
            command=self._toggle_popup,
        )
        self._button.pack(fill='x', expand=True)
        chevron_font = ctk.CTkFont(size=22, weight='bold')
        self._chevron = ctk.CTkLabel(
            self._button,
            text='▾',
            width=36,
            height=height - 6,
            fg_color='transparent',
            text_color=button_color,
            font=chevron_font,
            anchor='center',
            cursor='hand2',
        )
        self._chevron.place(relx=1.0, rely=0.5, x=-6, anchor='e')
        self._chevron.bind('<Button-1>', lambda _e: self._toggle_popup())
        self._search_trace = self._search_var.trace_add('write', self._apply_filter)
        self.bind('<Destroy>', self._on_destroy)

    def selected_labels(self) -> list[str]:
        concrete = [v for v in self._values if v in self._selected and v != self._all_label]
        if not concrete:
            return [self._all_label]
        return concrete

    def selected_ids(self, label_to_id: dict[str, int | None]) -> list[int]:
        ids: list[int] = []
        for label in self.selected_labels():
            group_id = label_to_id.get(label)
            if group_id is not None:
                ids.append(int(group_id))
        return ids

    def _summary_text(self, limit: int = 42) -> str:
        labels = self.selected_labels()
        if labels == [self._all_label]:
            text = self._all_label
        elif len(labels) == 1:
            text = labels[0]
        else:
            text = f'Выбрано: {len(labels)}'
        if len(text) > limit:
            text = text[: limit - 1] + '…'
        return text

    def _sync_button_text(self):
        self._button.configure(text=self._summary_text())

    def configure(self, **kwargs):
        if 'values' in kwargs:
            self._values = list(kwargs.pop('values'))
            self._selected = {self._all_label}
            self._values_dirty = True
            self._sync_button_text()
            if self._popup_visible:
                self._hide_popup()
        if 'state' in kwargs:
            self._button.configure(state=kwargs.pop('state'))
        if kwargs:
            super().configure(**kwargs)

    def cget(self, attribute_name: str):
        if attribute_name == 'values':
            return list(self._values)
        return super().cget(attribute_name)

    def _toggle_popup(self):
        if self._popup_visible:
            self._hide_popup()
            return
        self._show_popup()

    def _hide_popup(self):
        popup = self._popup
        self._popup_visible = False
        self._sync_button_text()
        if popup is None:
            return
        if not popup.winfo_exists():
            self._popup = None
            self._scroll = None
            self._search_entry = None
            self._done_button = None
            self._item_rows = []
            return
        try:
            popup.grab_release()
        except Exception:
            pass
        popup.withdraw()
        self._search_var.set('')

    def _destroy_popup(self):
        self._hide_popup()
        popup = self._popup
        self._popup = None
        self._scroll = None
        self._search_entry = None
        self._done_button = None
        self._item_rows = []
        self._values_dirty = True
        if popup is not None and popup.winfo_exists():
            popup.destroy()

    def _on_destroy(self, event):
        if event.widget is self:
            self._destroy_popup()

    def _popup_geometry(self) -> tuple[int, int, int, int]:
        self.update_idletasks()
        width = max(self.winfo_width(), 380)
        row_h = 34
        chrome_h = 48 + 48
        content_h = min(
            max(len(self._values), 1) * row_h + chrome_h + 16,
            self._max_popup_height,
        )
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        screen_h = self.winfo_screenheight()
        if y + content_h > screen_h - 40:
            y = max(40, self.winfo_rooty() - content_h - 2)
        return width, content_h, x, y

    def _on_toggle(self, value: str):
        row = next((r for r in self._item_rows if r[0] == value), None)
        if row is None:
            return
        _, _cb, var = row
        checked = bool(var.get())
        if value == self._all_label:
            if checked:
                self._selected = {self._all_label}
                for other_value, _other_cb, other_var in self._item_rows:
                    if other_value != self._all_label:
                        other_var.set(False)
            else:
                # Оставляем выбранным хотя бы «Все группы».
                var.set(True)
                self._selected = {self._all_label}
        else:
            if checked:
                self._selected.discard(self._all_label)
                self._selected.add(value)
                for other_value, _other_cb, other_var in self._item_rows:
                    if other_value == self._all_label:
                        other_var.set(False)
                        break
            else:
                self._selected.discard(value)
                if not any(v != self._all_label and v in self._selected for v in self._values):
                    self._selected = {self._all_label}
                    for other_value, _other_cb, other_var in self._item_rows:
                        if other_value == self._all_label:
                            other_var.set(True)
                            break
        self._sync_button_text()

    def _rebuild_items(self):
        if self._scroll is None:
            return
        for child in self._scroll.winfo_children():
            child.destroy()
        self._item_rows = []
        if self._all_label in self._values and not self._selected.intersection(
            v for v in self._values if v != self._all_label
        ):
            self._selected = {self._all_label}
        for value in self._values:
            checked = value in self._selected or (
                value == self._all_label and self.selected_labels() == [self._all_label]
            )
            var = ctk.BooleanVar(value=checked)
            item = ctk.CTkCheckBox(
                self._scroll,
                text=value,
                variable=var,
                height=28,
                corner_radius=6,
                fg_color=self._button_color,
                hover_color=self._button_hover_color,
                border_color=self._border_color,
                text_color=self._dropdown_text_color,
                font=self._font,
                command=lambda v=value: self._on_toggle(v),
            )
            item.pack(fill='x', padx=8, pady=2)
            self._item_rows.append((value, item, var))
        self._values_dirty = False
        self._apply_filter()
        self._sync_button_text()

    def _apply_filter(self, *_args):
        if not self._item_rows:
            return
        query = (self._search_var.get() or '').strip().casefold()
        for _value, item, _var in self._item_rows:
            item.pack_forget()
        for value, item, _var in self._item_rows:
            keep = (
                value == self._all_label
                or not query
                or query in value.casefold()
            )
            if keep:
                item.pack(fill='x', padx=8, pady=2)

    def _ensure_popup(self):
        if self._popup is not None and self._popup.winfo_exists():
            if self._values_dirty:
                self._rebuild_items()
            else:
                # Синхронизируем чекбоксы с текущим выбором.
                for value, _item, var in self._item_rows:
                    want = value in self._selected or (
                        value == self._all_label and self.selected_labels() == [self._all_label]
                    )
                    if bool(var.get()) != want:
                        var.set(want)
            return

        popup = ctk.CTkToplevel(self)
        popup.withdraw()
        popup.title('Группы EEU')
        popup.configure(fg_color=self._dropdown_fg_color)
        popup.transient(self.winfo_toplevel())
        popup.minsize(300, 200)
        popup.resizable(True, True)
        popup.protocol('WM_DELETE_WINDOW', self._hide_popup)
        popup.bind('<Escape>', lambda _e: self._hide_popup())

        search = ctk.CTkEntry(
            popup,
            textvariable=self._search_var,
            placeholder_text='Поиск группы…',
            height=36,
            corner_radius=RADIUS,
            border_width=1,
            border_color=self._border_color,
            fg_color=COLOR_SURFACE_ELEVATED,
            text_color=COLOR_TEXT,
            font=self._font,
        )
        search.pack(fill='x', padx=8, pady=(8, 4))

        scroll = ctk.CTkScrollableFrame(
            popup,
            fg_color=self._dropdown_fg_color,
            corner_radius=0,
            border_width=1,
            border_color=self._border_color,
        )
        scroll.pack(fill='both', expand=True, padx=1, pady=(0, 4))

        done = ctk.CTkButton(
            popup,
            text='Готово',
            height=36,
            corner_radius=RADIUS,
            fg_color=self._button_color,
            hover_color=self._button_hover_color,
            text_color='#ffffff',
            font=self._font,
            command=self._hide_popup,
        )
        done.pack(fill='x', padx=8, pady=(0, 8))

        self._popup = popup
        self._scroll = scroll
        self._search_entry = search
        self._done_button = done
        self._rebuild_items()

    def _show_popup(self):
        self._ensure_popup()
        popup = self._popup
        if popup is None:
            return
        self._search_var.set('')
        width, content_h, x, y = self._popup_geometry()
        popup.geometry(f'{width}x{content_h}+{x}+{y}')
        popup.deiconify()
        popup.lift()
        try:
            popup.grab_set()
        except Exception:
            pass
        if self._search_entry is not None:
            self._search_entry.focus_force()
        self._popup_visible = True


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
        self.doc_type_var = ctk.StringVar(value=DOC_TYPE_DECLARATION)
        self.tech_reg_var = ctk.StringVar(value=TECH_REG_TR_TS_010)
        self._eeu_label_to_id: dict[str, int | None] = {EEU_GROUP_ALL_LABEL: None}
        self.progress_q = queue.Queue()
        self.worker_thread = None
        self.slot_total = 0
        self.slot_done = 0
        self._run_locked = False
        self._cancel_requested = threading.Event()
        self._param_entries: list[ctk.CTkEntry] = []
        self._option_radios: list[ctk.CTkRadioButton] = []
        self._option_menus: list = []
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

        top = ctk.CTkFrame(inner_p, fg_color='transparent')
        top.pack(fill='x')
        top.grid_columnconfigure(0, weight=1, uniform='top')
        top.grid_columnconfigure(1, weight=1, uniform='top')
        top.grid_columnconfigure(2, weight=1, uniform='top')

        start_col = ctk.CTkFrame(top, fg_color='transparent')
        start_col.grid(row=0, column=0, sticky='nsew', padx=(0, GAP // 2))
        end_col = ctk.CTkFrame(top, fg_color='transparent')
        end_col.grid(row=0, column=1, sticky='nsew', padx=(GAP // 2, GAP // 2))
        file_col = ctk.CTkFrame(top, fg_color='transparent')
        file_col.grid(row=0, column=2, sticky='nsew', padx=(GAP // 2, 0))

        self._add_date_field(start_col, 'Дата начала, YYYY-MM-DD', self.start_date_var)
        self._add_date_field(end_col, 'Дата конца, YYYY-MM-DD', self.end_date_var)

        self._label(file_col, 'Файл Excel')
        file_row = ctk.CTkFrame(file_col, fg_color='transparent')
        file_row.pack(fill='x')
        self.btn_workbook = self._button(file_row, 'Выбрать файл', command=self.on_take_file, secondary=True, width=140)
        self.btn_workbook.pack(side='left', padx=(0, GAP // 2))
        self.lbl_file = ctk.CTkLabel(
            file_row,
            text='Файл не выбран',
            font=self.font_body,
            text_color=COLOR_TEXT_MUTED,
            anchor='w',
            justify='left',
            height=CONTROL_H,
            width=1,
        )
        self.lbl_file.pack(side='left', fill='x', expand=True)

        options = ctk.CTkFrame(inner_p, fg_color='transparent')
        options.pack(fill='x', pady=(GAP, 0))
        options.grid_columnconfigure(0, weight=1, uniform='options')
        options.grid_columnconfigure(1, weight=1, uniform='options')
        options.grid_columnconfigure(2, weight=1, uniform='options')
        options.grid_rowconfigure(1, weight=0)

        self._label(options, 'Тип документа', pack=False).grid(row=0, column=0, sticky='nw', padx=(0, GAP // 2), pady=(0, GAP))
        self._label(options, 'Технический регламент', pack=False).grid(row=0, column=1, sticky='nw', padx=(GAP // 2, GAP // 2), pady=(0, GAP))
        self._label(options, 'Группы EEU', pack=False).grid(row=0, column=2, sticky='nw', padx=(GAP // 2, 0), pady=(0, GAP))

        doc_radios = ctk.CTkFrame(options, fg_color='transparent', height=CONTROL_H)
        doc_radios.grid(row=1, column=0, sticky='new', padx=(0, GAP // 2))
        doc_radios.pack_propagate(False)
        rb_decl = self._radio(doc_radios, 'Декларации', DOC_TYPE_DECLARATION, variable=self.doc_type_var)
        rb_decl.pack(side='left', pady=(CONTROL_H - 24) // 2)
        rb_cert = self._radio(doc_radios, 'Сертификаты', DOC_TYPE_CERTIFICATE, variable=self.doc_type_var)
        rb_cert.pack(side='left', padx=(GAP, 0), pady=(CONTROL_H - 24) // 2)
        self._option_radios.extend([rb_decl, rb_cert])

        radios = ctk.CTkFrame(options, fg_color='transparent', height=CONTROL_H)
        radios.grid(row=1, column=1, sticky='new', padx=(GAP // 2, GAP // 2))
        radios.pack_propagate(False)
        rb010 = self._radio(radios, 'ТР ТС 010', TECH_REG_TR_TS_010, variable=self.tech_reg_var)
        rb010.pack(side='left', pady=(CONTROL_H - 24) // 2)
        rb032 = self._radio(radios, 'ТР ТС 032', TECH_REG_TR_TS_032, variable=self.tech_reg_var)
        rb032.pack(side='left', padx=(GAP, 0), pady=(CONTROL_H - 24) // 2)
        self._option_radios.extend([rb010, rb032])

        self.cmb_eeu = ScrollableOptionButton(
            options,
            values=[EEU_GROUP_ALL_LABEL],
            height=CONTROL_H,
            max_popup_height=360,
            font=self.font_body,
            fg_color=COLOR_SURFACE_ELEVATED,
            button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT,
            dropdown_fg_color=COLOR_SURFACE,
            dropdown_hover_color=COLOR_ACCENT_SOFT,
            dropdown_text_color=COLOR_TEXT,
            border_color=COLOR_BORDER,
        )
        self.cmb_eeu.grid(row=1, column=2, sticky='new', padx=(GAP // 2, 0))
        self._option_menus.append(self.cmb_eeu)
        self.tech_reg_var.trace_add('write', lambda *_: self._refresh_eeu_groups())
        self._refresh_eeu_groups()

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

    def _label(
        self,
        parent,
        text: str,
        *,
        color: str = COLOR_TEXT_MUTED,
        side: str | None = None,
        expand: bool = False,
        pack: bool = True,
    ):
        widget = ctk.CTkLabel(parent, text=text, font=self.font_ui, text_color=color, anchor='w', height=20)
        if pack:
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

    def _radio(self, parent, text: str, value: str, *, variable: ctk.StringVar) -> ctk.CTkRadioButton:
        return ctk.CTkRadioButton(
            parent,
            text=text,
            variable=variable,
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

    def _refresh_eeu_groups(self):
        tech_key = self.tech_reg_var.get()
        groups = get_eeu_groups(tech_key)
        labels = [EEU_GROUP_ALL_LABEL]
        mapping: dict[str, int | None] = {EEU_GROUP_ALL_LABEL: None}
        for group in groups:
            label = str(group.get('name') or group.get('id'))
            if label in mapping:
                label = f"{label} [{group.get('id')}]"
            mapping[label] = int(group['id'])
            labels.append(label)
        self._eeu_label_to_id = mapping
        self.cmb_eeu.configure(values=labels)

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
            args=(
                self,
                self.path_xlsx,
                token,
                start_date,
                end_date,
                self.tech_reg_var.get(),
                self.doc_type_var.get(),
                self.cmb_eeu.selected_ids(self._eeu_label_to_id),
            ),
            daemon=True,
        )
        self.worker_thread.start()
        self._run_locked = True
        self.btn_run.configure(state='disabled', text='Выполняется…', fg_color=COLOR_ACCENT)
        self.btn_workbook.configure(state='disabled')
        self.entry_token.configure(state='disabled')
        for entry in self._param_entries:
            entry.configure(state='disabled')
        for radio in self._option_radios:
            radio.configure(state='disabled')
        for menu in self._option_menus:
            menu.configure(state='disabled')

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
        for radio in self._option_radios:
            radio.configure(state='normal')
        for menu in self._option_menus:
            menu.configure(state='normal')

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
