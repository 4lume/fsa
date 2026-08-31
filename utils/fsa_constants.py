API_BASE = 'https://pub.fsa.gov.ru'
API_DECLARATIONS_URL = f'{API_BASE}/api/v1/rds/common/declarations/get'
API_NSI_MULTI_URL = f'{API_BASE}/nsi/api/multi'
BASE_PUBLISH_VIEW = f'{API_BASE}/rds/declaration/view'

STATUS_LEXICON = ('Действует', 'Архивный', 'Прекращён', 'Приостановлен')

DEFAULT_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Origin': 'https://pub.fsa.gov.ru',
    'Referer': 'https://pub.fsa.gov.ru/rds/declaration/view',
    'User-Agent': 'Mozilla/5.0',
}
