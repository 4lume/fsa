from pathlib import Path


def measure_linecount_bom(path: str | Path) -> int:
    with open(path, 'r', encoding='utf-8-sig') as fh:
        return len(fh.readlines())


def save_ids_txt(output_dir: Path, ids: list[str]) -> tuple[Path, int]:
    unique_ids = list(dict.fromkeys(ids))
    path = output_dir / 'fsa_declaration_ids.txt'
    with open(path, 'w', encoding='utf-8') as fh:
        for item in unique_ids:
            fh.write(f'{item}\n')
    return path, len(unique_ids)
