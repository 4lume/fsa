import re
import time
from pathlib import Path

from openpyxl import load_workbook

try:
    from new_parser.utils.fsa_api import extract_record_fields, fetch_declaration_record, fetch_declaration_scheme_name
except ModuleNotFoundError:
    from utils.fsa_api import extract_record_fields, fetch_declaration_record, fetch_declaration_scheme_name


def _text(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value).strip() or None


def execute_publication_pass(host, path_xlsx, path_manifest, token):
    book = load_workbook(path_xlsx)
    grid = book.active

    with open(path_manifest, 'r', encoding='utf-8-sig') as fh:
        manifest_lines = [line.strip() for line in fh if line.strip()]

    for pub_id in manifest_lines:
        if pub_id in [str(grid[f'P{k}'].value) for k in range(2, grid.max_row + 1)]:
            host.progress_q.put((host.slot_done, host.slot_total))
            continue

        anchor_row = None
        for row_idx in range(2, grid.max_row + 2):
            if grid[f'C{row_idx}'].value is None:
                anchor_row = row_idx
                break

        if anchor_row is None:
            anchor_row = grid.max_row + 1

        host.progress_q.put((host.slot_done, host.slot_total))
        try:
            record = fetch_declaration_record(token, pub_id)
            fields = extract_record_fields(record)

            title = _text(fields.get('declaration_period')) or _text(fields.get('number')) or _text(record.get('number')) or pub_id
            status = _text(fields.get('status'))
            decl_type = _text(fields.get('decl_type'))
            object_type = _text(fields.get('object_type'))
            applicant = _text(fields.get('applicant'))
            inn = _text(fields.get('inn'))
            manufacturer = _text(fields.get('manufacturer'))
            address = _text(fields.get('address'))
            product_name = _text(fields.get('product_name'))
            document_name = _text(fields.get('document_name'))
            document_number = _text(fields.get('document_number'))
            standards = _text(fields.get('standards'))
            testing_labs = _text(fields.get('testing_labs'))
            testing_protocols = _text(fields.get('testing_protocols'))

            grid[f'C{anchor_row}'] = title
            grid[f'D{anchor_row}'] = None
            grid[f'E{anchor_row}'] = status
            grid[f'F{anchor_row}'] = applicant
            grid[f'G{anchor_row}'] = inn
            grid[f'H{anchor_row}'] = manufacturer
            grid[f'I{anchor_row}'] = address
            grid[f'J{anchor_row}'] = product_name
            grid[f'M{anchor_row}'] = testing_labs
            grid[f'N{anchor_row}'] = testing_protocols

            document_value = document_name
            if document_number:
                if document_value:
                    document_value = f'{document_value}, {document_number}'
                else:
                    document_value = document_number
            grid[f'K{anchor_row}'] = document_value
            grid[f'L{anchor_row}'] = standards
            grid[f'P{anchor_row}'] = pub_id
            grid[f'Q{anchor_row}'] = object_type
            grid[f'R{anchor_row}'] = decl_type

            host.slot_done += 1
            host.progress_q.put(('first', host.slot_done, host.slot_total))
            book.save(path_xlsx)
            time.sleep(0.2)

        except Exception as exc:
            host.progress_q.put((host.slot_done, host.slot_total))
            raise RuntimeError(f'Ошибка по ID {pub_id}: {exc}') from exc

    if hasattr(host, 'slot_total'):
        host.progress_q.put((host.slot_done, host.slot_total))

    book.save(path_xlsx)


def execute_scheme_pass(host, path_xlsx, path_manifest, token):
    book = load_workbook(path_xlsx)
    grid = book.active

    with open(path_manifest, 'r', encoding='utf-8-sig') as fh:
        manifest_lines = [line.strip() for line in fh if line.strip()]

    host.slot_done = 0
    for pub_id in manifest_lines:
        row_candidates = [k for k in range(2, grid.max_row + 1) if str(grid[f'P{k}'].value or '').strip() == str(pub_id).strip()]
        if not row_candidates:
            continue
        row_idx = row_candidates[0]
        if grid[f'D{row_idx}'].value not in (None, ''):
            host.slot_done += 1
            host.progress_q.put(('second', host.slot_done, host.slot_total))
            continue

        try:
            record = fetch_declaration_record(token, pub_id)
            scheme_ref = record.get('idDeclScheme') or record.get('scheme') or record.get('declScheme')
            scheme_name = fetch_declaration_scheme_name(token, scheme_ref, declaration_id=pub_id)
            if scheme_name:
                grid[f'D{row_idx}'] = scheme_name
                book.save(path_xlsx)
        except Exception:
            scheme_name = None
        host.slot_done += 1
        host.progress_q.put(('second', host.slot_done, host.slot_total))

    if hasattr(host, 'slot_total'):
        host.progress_q.put(('second', host.slot_total, host.slot_total))


def execute_all_passes(host, path_xlsx, path_manifest, token):
    execute_publication_pass(host, path_xlsx, path_manifest, token)
    execute_scheme_pass(host, path_xlsx, path_manifest, token)
