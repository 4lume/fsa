API_BASE = 'https://pub.fsa.gov.ru'
API_DECLARATIONS_URL = f'{API_BASE}/api/v1/rds/common/declarations/get'
API_NSI_MULTI_URL = f'{API_BASE}/nsi/api/multi'

DELAY_BETWEEN_REQUESTS_SEC_MIN = 1.0
DELAY_BETWEEN_REQUESTS_SEC_MAX = 2.0

TECH_REG_TR_TS_010 = 'tr_ts_010'
TECH_REG_TR_TS_032 = 'tr_ts_032'

TECH_REG_PRESETS: dict[str, dict[str, list[int]]] = {
    TECH_REG_TR_TS_010: {
        'idGroupEEU': [717],
        'idTechReg': [14],
    },
    TECH_REG_TR_TS_032: {
        'idGroupEEU': [
            16555, 16557, 16559, 16561, 16563, 16565,
            16543, 16545, 16547, 16549, 16551, 16553,
            16443, 16445, 16447, 16449, 16451, 16453,
            16467, 16469, 16471, 16473, 16475,
            16457, 16459, 16461, 16463,
            16517, 16519, 16521,
            16487, 16489, 16491, 16493, 16495, 16497, 16499,
            16479, 16481, 16483,
            16525, 16527, 16529, 16531, 16533, 16537, 16539,
        ],
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
