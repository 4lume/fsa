import random
import time
from datetime import datetime
from typing import Any, Callable

import requests

from utils.fsa_constants import (
    API_BASE,
    API_CERTIFICATES_URL,
    API_DECLARATIONS_URL,
    API_NSI_MULTI_URL,
    DEFAULT_HEADERS,
    DELAY_BETWEEN_REQUESTS_SEC_MAX,
    DELAY_BETWEEN_REQUESTS_SEC_MIN,
    DOC_TYPE_CERTIFICATE,
    DOC_TYPE_DECLARATION,
    TECH_REG_PRESETS,
    TECH_REG_TR_TS_010,
)


STATUS_MAP = {
    1: 'Черновик',
    2: 'На проверке',
    3: 'Отклонена',
    4: 'Архивная',
    5: 'Приостановлена',
    6: 'Действует',
    7: 'Архивная',
    8: 'Прекращена',
    9: 'Приостановлена',
}

OBJECT_TYPE_MAP = {
    1: 'Единичное изделие',
    2: 'Партия',
    3: 'Серийный выпуск',
}


def normalize_token(token: str) -> str:
    token = (token or '').strip()
    if not token:
        return token
    if token.lower().startswith('bearer '):
        return token
    return f'Bearer {token}'


def _is_certificate(doc_type: str | None) -> bool:
    return doc_type == DOC_TYPE_CERTIFICATE


def build_record_referer(record_id: Any, doc_type: str = DOC_TYPE_DECLARATION) -> str:
    value = _text(record_id)
    if _is_certificate(doc_type):
        if not value:
            return f'{API_BASE}/rss/certificate/view'
        return f'{API_BASE}/rss/certificate/view/{value}/common'
    if not value:
        return f'{API_BASE}/rds/declaration/view'
    return f'{API_BASE}/rds/declaration/view/{value}/common'


def build_declaration_referer(record_id: Any) -> str:
    return build_record_referer(record_id, DOC_TYPE_DECLARATION)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip() or None


def _as_list(value: Any) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _first(value: Any) -> Any:
    items = _as_list(value)
    return items[0] if items else None


def _mapped_int(value: Any, mapping: dict[int, str]) -> str | None:
    if value is None:
        return None
    try:
        return mapping.get(int(value))
    except (TypeError, ValueError):
        return None


def _format_date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    if len(text) >= 10 and text[4] == '-' and text[7] == '-':
        try:
            return datetime.strptime(text[:10], '%Y-%m-%d').strftime('%d.%m.%Y')
        except ValueError:
            pass
    return text


def _build_doc_period(number: Any, start_date: Any, end_date: Any) -> str | None:
    number_text = _text(number)
    start_text = _format_date(start_date)
    end_text = _format_date(end_date)
    if number_text and start_text and end_text:
        return f'{number_text} от {start_text} действует до {end_text}'
    if number_text and start_text:
        return f'{number_text} от {start_text}'
    if number_text and end_text:
        return f'{number_text} действует до {end_text}'
    if number_text:
        return number_text
    if start_text and end_text:
        return f'от {start_text} действует до {end_text}'
    if start_text:
        return f'от {start_text}'
    return end_text


def _full_address(entity: Any) -> str | None:
    if not isinstance(entity, dict):
        return None
    address = _first(entity.get('addresses'))
    if isinstance(address, dict):
        return _text(address.get('fullAddress'))
    return None


def _join_identification_blocks(identifications: Any) -> str | None:
    blocks = []
    for item in _as_list(identifications):
        if not isinstance(item, dict):
            continue
        lines = []
        for key in ('name', 'description', 'article'):
            text = _text(item.get(key))
            if text:
                lines.append(text)
        if lines:
            blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks) if blocks else None


def _join_document_blocks(identifications: Any) -> str | None:
    blocks = []
    for item in _as_list(identifications):
        if not isinstance(item, dict):
            continue
        for document in _as_list(item.get('documents')):
            if not isinstance(document, dict):
                continue
            parts = [text for key in ('name', 'number') if (text := _text(document.get(key)))]
            if parts:
                block = ', '.join(parts)
                if block not in blocks:
                    blocks.append(block)
    return '\n\n'.join(blocks) if blocks else None


def _join_standard_blocks(identifications: Any) -> str | None:
    blocks = []
    for item in _as_list(identifications):
        if not isinstance(item, dict):
            continue
        for standard in _as_list(item.get('standards')):
            if not isinstance(standard, dict):
                continue
            parts = [text for key in ('designation', 'name') if (text := _text(standard.get(key)))]
            if parts:
                block = ', '.join(parts)
                if block not in blocks:
                    blocks.append(block)
    return '\n\n'.join(blocks) if blocks else None


def _join_testing_lab_blocks(testing_labs: Any) -> str | None:
    blocks = []
    for lab in _as_list(testing_labs):
        if not isinstance(lab, dict):
            continue
        lines = []
        name = _text(lab.get('fullName'))
        if name:
            lines.append(name)
        address = lab.get('address')
        if isinstance(address, dict):
            address_text = _text(address.get('fullAddress'))
            if address_text:
                lines.append(address_text)
        if lines:
            blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks) if blocks else None


def _join_testing_protocol_blocks(testing_labs: Any) -> str | None:
    blocks = []
    for lab in _as_list(testing_labs):
        if not isinstance(lab, dict):
            continue
        for protocol in _as_list(lab.get('protocols')):
            if not isinstance(protocol, dict):
                continue
            parts = [text for key in ('number', 'date') if (text := _text(protocol.get(key)))]
            if parts:
                block = ', '.join(parts)
                if block not in blocks:
                    blocks.append(block)
    return '\n\n'.join(blocks) if blocks else None


def _nsi_name(data: Any, key: str) -> str | None:
    if not isinstance(data, dict):
        return None
    for item in _as_list(data.get(key)):
        if isinstance(item, dict):
            name = _text(item.get('name'))
            if name:
                return name
    return None


def fetch_nsi_labels(
    token: str,
    *,
    scheme_ref: Any = None,
    record_id: Any = None,
    declaration_id: Any = None,
    doc_type: str = DOC_TYPE_DECLARATION,
) -> dict[str, str | None]:
    result = {'scheme': None}

    scheme_value = _text(scheme_ref)
    if not scheme_value:
        return result

    try:
        scheme_id = int(scheme_value)
    except ValueError:
        scheme_id = scheme_value

    headers = {
        **DEFAULT_HEADERS,
        'Authorization': normalize_token(token),
        'Content-Type': 'application/json',
        'Referer': build_record_referer(record_id if record_id is not None else declaration_id, doc_type),
    }

    payload = {
        'items': {
            'validationScheme2': [{'id': [scheme_id], 'fields': ['name']}],
        }
    }

    try:
        response = requests.post(API_NSI_MULTI_URL, json=payload, timeout=40, headers=headers)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return result

    result['scheme'] = _nsi_name(data, 'validationScheme2')
    return result


def extract_record_fields(record: dict):
    if not isinstance(record, dict):
        return {}

    applicant = record.get('applicant') if isinstance(record.get('applicant'), dict) else {}
    manufacturer = record.get('manufacturer') if isinstance(record.get('manufacturer'), dict) else {}
    product = record.get('product') if isinstance(record.get('product'), dict) else {}
    identifications = product.get('identifications') or []

    status = _mapped_int(record.get('idStatus'), STATUS_MAP)
    if status is None:
        change = _first(record.get('statusChanges'))
        if isinstance(change, dict):
            status = _mapped_int(change.get('idStatus'), STATUS_MAP)

    start_date = record.get('declRegDate')
    if start_date is None:
        start_date = record.get('certRegDate')
    end_date = record.get('declEndDate')
    if end_date is None:
        end_date = record.get('certEndDate')

    scheme_ref = record.get('idDeclScheme')
    if scheme_ref is None:
        scheme_ref = record.get('idCertScheme')

    object_type_ref = record.get('idObjectDeclType')
    if object_type_ref is None:
        object_type_ref = record.get('idObjectCertType')

    return {
        'number': _text(record.get('number')),
        'declaration_period': _build_doc_period(record.get('number'), start_date, end_date),
        'status': status,
        'product_name': _join_identification_blocks(identifications) or _text(product.get('fullName')),
        'applicant': _text(applicant.get('shortName')) or _text(applicant.get('fullName')),
        'inn': _text(applicant.get('inn')) or _text(manufacturer.get('inn')),
        'manufacturer': _text(manufacturer.get('fullName')) or _text(manufacturer.get('shortName')),
        'address': _full_address(manufacturer) or _full_address(applicant),
        'scheme_ref': scheme_ref,
        'object_type': _mapped_int(object_type_ref, OBJECT_TYPE_MAP),
        'document': _join_document_blocks(identifications),
        'standards': _join_standard_blocks(identifications),
        'testing_labs': _join_testing_lab_blocks(record.get('testingLabs')),
        'testing_protocols': _join_testing_protocol_blocks(record.get('testingLabs')),
    }


def build_list_payload(
    page: int,
    start_date: str,
    end_date: str | None,
    *,
    id_group_eeu: list[int],
    id_tech_reg: list[int],
    doc_type: str = DOC_TYPE_DECLARATION,
):
    if _is_certificate(doc_type):
        return {
            'size': LIST_PAGE_SIZE,
            'page': page,
            'count': 0,
            'filter': {
                'status': [],
                'idCertType': [],
                'idObjectCertType': [],
                'idProductType': [],
                'idGroupRU': [],
                'idGroupEEU': list(id_group_eeu),
                'idTechReg': list(id_tech_reg),
                'idApplicantType': [],
                'regDate': {
                    'minDate': start_date,
                    'maxDate': end_date or None,
                },
                'endDate': {
                    'minDate': None,
                    'maxDate': None,
                },
                'columnsSearch': [{'name': 'number', 'search': '', 'type': 0}],
                'number': None,
                'idProductOrigin': [],
                'idProductEEU': [],
                'idProductRU': [],
                'idCertScheme': [],
                'awaitOperatorCheck': None,
                'editApp': None,
            },
            'columnsSort': [{'column': 'date', 'sort': 'DESC'}],
        }

    return {
        'size': LIST_PAGE_SIZE,
        'page': page,
        'count': 0,
        'filter': {
            'status': [],
            'idDeclType': [],
            'idCertObjectType': [],
            'idProductType': [],
            'idGroupRU': [],
            'idGroupEEU': list(id_group_eeu),
            'idTechReg': list(id_tech_reg),
            'idApplicantType': [],
            'regDate': {
                'minDate': start_date,
                'maxDate': end_date or None,
            },
            'endDate': {
                'minDate': None,
                'maxDate': None,
            },
            'columnsSearch': [{'name': 'number', 'search': None, 'type': 0}],
            'number': None,
            'idProductOrigin': [],
            'idProductEEU': [],
            'idProductRU': [],
            'idDeclScheme': [],
            'awaitOperatorCheck': None,
            'editApp': None,
            'violationSendDate': None,
            'isProtocolInvalid': None,
            'checkerAIResult': None,
            'checkerAIProtocolsResults': None,
            'checkerAIProtocolsMistakes': None,
            'hiddenFromOpen': None,
        },
        'columnsSort': [{'column': 'declDate', 'sort': 'DESC'}],
    }


def _list_items(data: Any) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ('items', 'content', 'data'):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def collect_record_ids(
    token: str,
    start_date: str,
    end_date: str | None,
    tech_key: str,
    doc_type: str = DOC_TYPE_DECLARATION,
    group_id: int | None = None,
    group_ids: list[int] | None = None,
    on_count: Callable[[int, int | None], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> list[str]:
    preset = TECH_REG_PRESETS.get(tech_key) or TECH_REG_PRESETS[TECH_REG_TR_TS_010]
    list_url = API_CERTIFICATES_URL if _is_certificate(doc_type) else API_DECLARATIONS_URL
    list_referer = f'{API_BASE}/rss/certificate' if _is_certificate(doc_type) else f'{API_BASE}/rds/declaration'
    label = 'сертификатов' if _is_certificate(doc_type) else 'деклараций'
    if group_ids is not None:
        id_group_eeu = [int(x) for x in group_ids]
    elif group_id is not None:
        id_group_eeu = [int(group_id)]
    else:
        id_group_eeu = []

    session = requests.Session()
    session.headers.update({
        **DEFAULT_HEADERS,
        'Authorization': normalize_token(token),
        'Content-Type': 'application/json',
        'Referer': list_referer,
    })

    all_ids: list[str] = []
    page = 0
    while page < LIST_MAX_PAGES:
        if should_stop and should_stop():
            break
        payload = build_list_payload(
            page=page,
            start_date=start_date,
            end_date=end_date,
            id_group_eeu=id_group_eeu,
            id_tech_reg=preset['idTechReg'],
            doc_type=doc_type,
        )
        try:
            response = session.post(list_url, json=payload, timeout=40)
        except requests.Timeout as exc:
            raise RuntimeError(f'Превышено время ожидания при сборе ID {label} (страница {page})') from exc
        except requests.RequestException as exc:
            raise RuntimeError(f'Ошибка сети при сборе ID {label} (страница {page})') from exc

        if response.status_code in (401, 403):
            raise RuntimeError('Токен недействителен или доступ запрещён')
        if response.status_code == 429:
            raise RuntimeError('Слишком много запросов. Подождите и повторите позже')
        if response.status_code != 200:
            detail = (response.text or '').strip().replace('\n', ' ')
            if len(detail) > 240:
                detail = detail[:240] + '…'
            suffix = f': {detail}' if detail else ''
            raise RuntimeError(f'Ошибка HTTP {response.status_code} при сборе ID {label} (страница {page}){suffix}')

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f'Некорректный JSON при сборе ID {label} (страница {page})') from exc

        items = _list_items(data)
        if not items:
            break

        for item in items:
            if isinstance(item, dict) and item.get('id') is not None:
                all_ids.append(str(item['id']))
        if on_count:
            # Знаменатель — лимит API (20×100), а не неточный count из ответа.
            on_count(len(all_ids), LIST_MAX_IDS)

        page += 1
        time.sleep(random.uniform(DELAY_BETWEEN_REQUESTS_SEC_MIN, DELAY_BETWEEN_REQUESTS_SEC_MAX))

    return list(dict.fromkeys(all_ids))


def collect_declaration_ids(
    token: str,
    start_date: str,
    end_date: str | None,
    tech_key: str,
    on_count: Callable[[int, int | None], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> list[str]:
    return collect_record_ids(
        token,
        start_date,
        end_date,
        tech_key,
        DOC_TYPE_DECLARATION,
        on_count=on_count,
        should_stop=should_stop,
    )


def fetch_record(token: str, record_id: str, doc_type: str = DOC_TYPE_DECLARATION):
    if _is_certificate(doc_type):
        detail_url = f'{API_BASE}/api/v1/rss/common/certificates/{record_id}'
        label = 'сертификата'
    else:
        detail_url = f'{API_BASE}/api/v1/rds/common/declarations/{record_id}'
        label = 'декларации'

    try:
        response = requests.get(
            detail_url,
            timeout=40,
            headers={**DEFAULT_HEADERS, 'Authorization': normalize_token(token)},
        )
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as exc:
        raise RuntimeError(f'Превышено время ожидания при загрузке {label} {record_id}') from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else '?'
        raise RuntimeError(f'Ошибка HTTP {status} при загрузке {label} {record_id}') from exc
    except requests.RequestException as exc:
        raise RuntimeError(f'Ошибка сети при загрузке {label} {record_id}') from exc
    except ValueError as exc:
        raise RuntimeError(f'Некорректный JSON в ответе API для ID {record_id}') from exc

    if not isinstance(data, dict):
        raise RuntimeError(f'Неожиданный формат ответа API для ID {record_id}')
    return data


def fetch_declaration_record(token: str, record_id: str):
    return fetch_record(token, record_id, DOC_TYPE_DECLARATION)
