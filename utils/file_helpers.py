from pathlib import Path


def measure_linecount_bom(path: str | Path) -> int:
    with open(path, 'r', encoding='utf-8-sig') as fh:
        return len([line for line in fh if line.strip()])
