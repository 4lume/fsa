API_BASE = 'https://pub.fsa.gov.ru'
API_DECLARATIONS_URL = f'{API_BASE}/api/v1/rds/common/declarations/get'
API_CERTIFICATES_URL = f'{API_BASE}/api/v1/rss/common/certificates/get'
API_NSI_MULTI_URL = f'{API_BASE}/nsi/api/multi'

DOC_TYPE_DECLARATION = 'declaration'
DOC_TYPE_CERTIFICATE = 'certificate'

DELAY_BETWEEN_REQUESTS_SEC_MIN = 1.0
DELAY_BETWEEN_REQUESTS_SEC_MAX = 2.0

TECH_REG_TR_TS_010 = 'tr_ts_010'
TECH_REG_TR_TS_032 = 'tr_ts_032'

EEU_GROUP_ALL = 'all'
EEU_GROUP_ALL_LABEL = 'Все группы'

TECH_REG_PRESETS: dict[str, dict[str, list[int]]] = {
    TECH_REG_TR_TS_010: {
        'idTechReg': [14],
    },
    TECH_REG_TR_TS_032: {
        'idTechReg': [5],
    },
}

DEFAULT_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Origin': 'https://pub.fsa.gov.ru',
    'Referer': 'https://pub.fsa.gov.ru/rds/declaration/view',
    'User-Agent': 'Mozilla/5.0',
}


def get_eeu_groups(tech_key: str) -> list[dict]:
    from utils.eeu_groups_data import EEU_GROUPS_BY_TECH
    return list(EEU_GROUPS_BY_TECH.get(tech_key) or [])
