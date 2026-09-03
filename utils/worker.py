import random
import time

from openpyxl import load_workbook

try:
    from new_parser.utils.fsa_api import collect_declaration_ids, extract_record_fields, fetch_declaration_record, fetch_nsi_labels
    from new_parser.utils.fsa_constants import DELAY_BETWEEN_REQUESTS_SEC_MAX, DELAY_BETWEEN_REQUESTS_SEC_MIN
except ModuleNotFoundError:
    from utils.fsa_api import collect_declaration_ids, extract_record_fields, fetch_declaration_record, fetch_nsi_labels
    from utils.fsa_constants import DELAY_BETWEEN_REQUESTS_SEC_MAX, DELAY_BETWEEN_REQUESTS_SEC_MIN


def _pause():
    time.sleep(random.uniform(DELAY_BETWEEN_REQUESTS_SEC_MIN, DELAY_BETWEEN_REQUESTS_SEC_MAX))


def _cancelled(host) -> bool:
    return bool(getattr(host, 'is_cancelled', lambda: False)())


def execute_all_passes(host, path_xlsx, token, start_date, end_date, tech_key):
    try:
        ids = collect_declaration_ids(
            token,
            start_date,
            end_date,
            tech_key,
            on_count=lambda count, total: host.progress_q.put(('harvest', count, total)),
            should_stop=lambda: _cancelled(host),
        )
        if _cancelled(host):
            host.progress_q.put(('cancelled',))
            return
        if not ids:
            host.progress_q.put(('error', 'По заданным параметрам ID не найдены'))
            return

        host.progress_q.put(('harvest', len(ids), len(ids)))

        try:
            book = load_workbook(path_xlsx)
        except Exception as exc:
            raise RuntimeError(f'Не удалось открыть файл Excel: {exc}') from exc
        grid = book.active
        host.slot_total = len(ids)
        host.slot_done = 0
        host.progress_q.put(('parse', 0, host.slot_total))

        for pub_id in ids:
            if _cancelled(host):
                book.save(path_xlsx)
                host.progress_q.put(('cancelled',))
                return
            try:
                if pub_id in [str(grid[f'O{k}'].value) for k in range(2, grid.max_row + 1)]:
                    host.slot_done += 1
                    host.progress_q.put(('parse', host.slot_done, host.slot_total))
                    continue

                anchor_row = None
                for row_idx in range(2, grid.max_row + 2):
                    if grid[f'C{row_idx}'].value is None:
                        anchor_row = row_idx
                        break
                if anchor_row is None:
                    anchor_row = grid.max_row + 1

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
                host.progress_q.put(('parse', host.slot_done, host.slot_total))
                book.save(path_xlsx)
                _pause()
            except Exception as exc:
                raise RuntimeError(f'Ошибка по ID {pub_id}: {exc}') from exc

        book.save(path_xlsx)
    except Exception as exc:
        if _cancelled(host):
            host.progress_q.put(('cancelled',))
            return
        host.progress_q.put(('error', str(exc)))
