import time

from openpyxl import load_workbook

try:
    from new_parser.utils.fsa_api import extract_record_fields, fetch_declaration_record, fetch_nsi_labels
except ModuleNotFoundError:
    from utils.fsa_api import extract_record_fields, fetch_declaration_record, fetch_nsi_labels


def execute_all_passes(host, path_xlsx, path_manifest, token):
    book = load_workbook(path_xlsx)
    grid = book.active

    with open(path_manifest, 'r', encoding='utf-8-sig') as fh:
        manifest_lines = [line.strip() for line in fh if line.strip()]

    for pub_id in manifest_lines:
        if pub_id in [str(grid[f'O{k}'].value) for k in range(2, grid.max_row + 1)]:
            host.slot_done += 1
            host.progress_q.put((host.slot_done, host.slot_total))
            continue

        anchor_row = None
        for row_idx in range(2, grid.max_row + 2):
            if grid[f'C{row_idx}'].value is None:
                anchor_row = row_idx
                break

        if anchor_row is None:
            anchor_row = grid.max_row + 1

        try:
            record = fetch_declaration_record(token, pub_id)
            fields = extract_record_fields(record)
            labels = fetch_nsi_labels(
                token,
                scheme_ref=fields.get('scheme_ref'),
                declaration_id=pub_id,
            )

            title = fields.get('declaration_period') or fields.get('number') or pub_id

            grid[f'C{anchor_row}'] = title
            grid[f'D{anchor_row}'] = labels.get('scheme')
            grid[f'E{anchor_row}'] = fields.get('status')
            grid[f'F{anchor_row}'] = fields.get('applicant')
            grid[f'G{anchor_row}'] = fields.get('inn')
            grid[f'H{anchor_row}'] = fields.get('manufacturer')
            grid[f'I{anchor_row}'] = fields.get('address')
            grid[f'J{anchor_row}'] = fields.get('product_name')
            grid[f'K{anchor_row}'] = fields.get('document')
            grid[f'L{anchor_row}'] = fields.get('standards')
            grid[f'M{anchor_row}'] = fields.get('testing_labs')
            grid[f'N{anchor_row}'] = fields.get('testing_protocols')
            grid[f'O{anchor_row}'] = pub_id
            grid[f'P{anchor_row}'] = fields.get('object_type')

            host.slot_done += 1
            host.progress_q.put((host.slot_done, host.slot_total))
            book.save(path_xlsx)
            time.sleep(0.2)

        except Exception as exc:
            host.progress_q.put(('error', f'Ошибка по ID {pub_id}: {exc}'))
            return

    book.save(path_xlsx)
