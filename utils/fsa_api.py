import re
from typing import Any

import requests

try:
    from new_parser.utils.fsa_constants import API_BASE, API_DECLARATIONS_URL, API_NSI_MULTI_URL, BASE_PUBLISH_VIEW, DEFAULT_HEADERS
except ModuleNotFoundError:
    from utils.fsa_constants import API_BASE, API_DECLARATIONS_URL, API_NSI_MULTI_URL, BASE_PUBLISH_VIEW, DEFAULT_HEADERS


def normalize_token(token: str) -> str:
    token = (token or '').strip()
    if not token:
        return token
    if token.lower().startswith('bearer '):
        return token
    return f'Bearer {token}'


def build_declaration_referer(record_id: Any) -> str:
    value = _text(record_id)
    if not value:
        return f'{API_BASE}/rds/declaration/view'
    return f'{API_BASE}/rds/declaration/view/{value}/common'


def find_items_in_response(data: Any):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ('items', 'content', 'data', 'records', 'result', 'rows', 'declarations', 'list'):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = find_items_in_response(value)
            if nested:
                return nested

    for value in data.values():
        if isinstance(value, dict):
            nested = find_items_in_response(value)
            if nested:
                return nested
    return []


def build_list_payload(page: int = 0, start_date: str | None = None, end_date: str | None = None, *, number: str | None = None):
    filter_block = {
        'status': [],
        'idDeclType': [],
        'idCertObjectType': [],
        'idProductType': [],
        'idGroupRU': [],
        'idGroupEEU': [],
        'idTechReg': [],
        'idApplicantType': [],
        'regDate': {'minDate': start_date, 'maxDate': end_date},
        'endDate': {'minDate': None, 'maxDate': None},
        'columnsSearch': [{'name': 'number', 'search': None, 'type': 0}],
        'number': number,
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
    }
    return {
        'size': 100,
        'page': page,
        'count': 0,
        'filter': filter_block,
        'columnsSort': [{'column': 'declDate', 'sort': 'DESC'}],
    }


def fetch_declaration_list(token: str, *, page: int = 0, start_date: str | None = None, end_date: str | None = None, number: str | None = None):
    session = requests.Session()
    session.headers.update({**DEFAULT_HEADERS, 'Authorization': normalize_token(token), 'Content-Type': 'application/json'})
    payload = build_list_payload(page=page, start_date=start_date, end_date=end_date, number=number)
    response = session.post(API_DECLARATIONS_URL, json=payload, timeout=40)
    if response.status_code != 200:
        raise RuntimeError(f'HTTP {response.status_code}: {response.text[:500]}')
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f'API response is not valid JSON: {response.text[:500]}') from exc
    return find_items_in_response(data)


def fetch_declaration_scheme_name(token: str, scheme_ref: Any, *, declaration_id: Any = None) -> str | None:
    scheme_value = _text(scheme_ref)
    if not scheme_value:
        return None

    try:
        numeric_id = int(str(scheme_value).strip())
    except ValueError:
        numeric_id = scheme_value

    payload = {
        'items': {
            'validationScheme2': [
                {
                    'id': [numeric_id],
                    'fields': ['id', 'masterId', 'name', 'validityTerm', 'isSeriesProduction', 'isBatchProduction', 'isOneOffProduction', 'isProductSampleTesting', 'isBatchProductTesting', 'isOneOffProductTesting', 'isAccreditationLab', 'isApplicantManufacturer', 'isApplicantProvider', 'isPresenceOfProxy', 'isApplicantForeign', 'isApplicantEeuMember'],
                }
            ]
        }
    }

    headers = {
        **DEFAULT_HEADERS,
        'Authorization': normalize_token(token),
        'Content-Type': 'application/json',
        'Referer': build_declaration_referer(declaration_id),
    }

    try:
        response = requests.post(API_NSI_MULTI_URL, json=payload, timeout=40, headers=headers)
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    def extract_items(node: Any):
        if isinstance(node, list):
            return node
        if isinstance(node, dict):
            for key in ('validationScheme2', 'items', 'result', 'data'):
                value = node.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    nested = extract_items(value)
                    if nested:
                        return nested
            for value in node.values():
                if isinstance(value, dict):
                    nested = extract_items(value)
                    if nested:
                        return nested
        return []

    items = extract_items(data)
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return None

    for item in items:
        if not isinstance(item, dict):
            continue
        name = _text(item.get('name')) or _text(item.get('value')) or _text(item.get('label'))
        if name:
            return name

    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip() or None


def _first_list_item(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _join_text(values: list[Any]) -> str | None:
    cleaned = []
    for item in values:
        text = _text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    if not cleaned:
        return None
    return ', '.join(cleaned)


def _join_identification_blocks(identifications: Any) -> str | None:
    if not identifications:
        return None
    if isinstance(identifications, dict):
        identifications = [identifications]
    if not isinstance(identifications, list):
        return None

    blocks = []
    for item in identifications:
        if not isinstance(item, dict):
            continue
        lines = []
        for key in ('name', 'description', 'article'):
            text = _text(item.get(key))
            if text:
                lines.append(text)
        if lines:
            blocks.append('\n'.join(lines))

    if not blocks:
        return None
    return '\n\n'.join(blocks)


def _join_document_blocks(identifications: Any) -> str | None:
    if not identifications:
        return None
    if isinstance(identifications, dict):
        identifications = [identifications]
    if not isinstance(identifications, list):
        return None

    blocks = []
    for item in identifications:
        if not isinstance(item, dict):
            continue
        documents = item.get('documents') or []
        if isinstance(documents, dict):
            documents = [documents]
        if not isinstance(documents, list):
            continue
        for document in documents:
            if not isinstance(document, dict):
                continue
            parts = []
            for key in ('name', 'number'):
                text = _text(document.get(key))
                if text:
                    parts.append(text)
            if parts:
                block = ', '.join(parts)
                if block and block not in blocks:
                    blocks.append(block)

    if not blocks:
        return None
    return '\n\n'.join(blocks)


def _join_standard_blocks(identifications: Any) -> str | None:
    if not identifications:
        return None
    if isinstance(identifications, dict):
        identifications = [identifications]
    if not isinstance(identifications, list):
        return None

    blocks = []
    for item in identifications:
        if not isinstance(item, dict):
            continue
        standards = item.get('standards') or []
        if isinstance(standards, dict):
            standards = [standards]
        if not isinstance(standards, list):
            continue
        for standard in standards:
            if not isinstance(standard, dict):
                continue
            parts = []
            for key in ('designation', 'name'):
                text = _text(standard.get(key))
                if text:
                    parts.append(text)
            if parts:
                block = ', '.join(parts)
                if block and block not in blocks:
                    blocks.append(block)

    if not blocks:
        return None
    return '\n\n'.join(blocks)


def _join_testing_lab_blocks(testing_labs: Any) -> str | None:
    if not testing_labs:
        return None
    if isinstance(testing_labs, dict):
        testing_labs = [testing_labs]
    if not isinstance(testing_labs, list):
        return None

    blocks = []
    for lab in testing_labs:
        if not isinstance(lab, dict):
            continue
        lines = []
        for key in ('fullName', 'fullAddress'):
            text = _text(lab.get(key))
            if text:
                lines.append(text)
        if lines:
            blocks.append('\n'.join(lines))

    if not blocks:
        return None
    return '\n\n'.join(blocks)


def _join_testing_protocol_blocks(testing_labs: Any) -> str | None:
    if not testing_labs:
        return None
    if isinstance(testing_labs, dict):
        testing_labs = [testing_labs]
    if not isinstance(testing_labs, list):
        return None

    blocks = []
    for lab in testing_labs:
        if not isinstance(lab, dict):
            continue
        protocols = lab.get('protocols') or []
        if isinstance(protocols, dict):
            protocols = [protocols]
        if not isinstance(protocols, list):
            continue
        for protocol in protocols:
            if not isinstance(protocol, dict):
                continue
            parts = []
            for key in ('number', 'date'):
                text = _text(protocol.get(key))
                if text:
                    parts.append(text)
            if parts:
                block = ', '.join(parts)
                if block and block not in blocks:
                    blocks.append(block)

    if not blocks:
        return None
    return '\n\n'.join(blocks)


def _format_date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    if len(text) >= 10 and text[4] == '-' and text[7] == '-':
        try:
            from datetime import datetime
            return datetime.strptime(text[:10], '%Y-%m-%d').strftime('%d.%m.%Y')
        except ValueError:
            pass
    return text


def _build_declaration_period(number: Any, start_date: Any, end_date: Any) -> str | None:
    number_text = _text(number)
    start_text = _format_date(start_date)
    end_text = _format_date(end_date)
    if not number_text and not start_text and not end_text:
        return None
    if number_text and start_text and end_text:
        return f'{number_text} от {start_text} действует до {end_text}'
    if number_text and start_text:
        return f'{number_text} от {start_text}'
    if number_text and end_text:
        return f'{number_text} действует до {end_text}'
    if start_text and end_text:
        return f'от {start_text} действует до {end_text}'
    if number_text:
        return number_text
    if start_text and end_text:
        return f'от {start_text} действует до {end_text}'
    if start_text:
        return f'от {start_text}'
    return end_text


def _status_name(status_value: Any) -> str | None:
    if isinstance(status_value, str):
        text = status_value.strip()
        if text:
            return text

    if isinstance(status_value, dict):
        text = _text(status_value.get('name')) or _text(status_value.get('title')) or _text(status_value.get('value'))
        if text:
            return text

    if isinstance(status_value, (int, float)):
        mapping = {
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
        return mapping.get(int(status_value))

    return None


OBJECT_DECLARATION_TYPE_MAP = {
    1: 'Единичное изделие',
    2: 'Партия',
    3: 'Серийный выпуск',
}

DECLARATION_TYPE_MAP: dict[int, str] = {}


def _lookup_declaration_scheme(value: Any) -> str | None:
    return _text(value)


def _lookup_mapped_value(value: Any, mapping: dict[int, str]) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        lowered = value.lower()
        if lowered in {'единичное изделие', 'singleproduction'}:
            return 'Единичное изделие'
        if lowered in {'партия', 'batchproduction'}:
            return 'Партия'
        if lowered in {'серийный выпуск', 'seriesproduction'}:
            return 'Серийный выпуск'
        if value.isdigit():
            numeric = int(value)
            return mapping.get(numeric)
        return value

    if isinstance(value, (int, float)):
        return mapping.get(int(value))

    return _text(value)


def _lookup_object_type(value: Any) -> str | None:
    return _lookup_mapped_value(value, OBJECT_DECLARATION_TYPE_MAP)


def _deep_lookup(data: Any, *candidates):
    if isinstance(data, dict):
        for key in candidates:
            if key in data:
                val = data[key]
                if isinstance(val, dict):
                    for subkey in ('name', 'title', 'value', 'text', 'fullName', 'shortName', 'number', 'designation'):
                        if subkey in val:
                            subval = val[subkey]
                            if subval is not None:
                                text = _text(subval)
                                if text:
                                    return text
                if isinstance(val, (str, int, float)) and _text(val):
                    return _text(val)
        for value in data.values():
            found = _deep_lookup(value, *candidates)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _deep_lookup(item, *candidates)
            if found is not None:
                return found
    return None


def extract_record_fields(record: dict):
    if not isinstance(record, dict):
        return {}

    applicant = record.get('applicant') or {}
    manufacturer = record.get('manufacturer') or {}
    product = record.get('product') or {}
    identifications = product.get('identifications') or []
    identification = _first_list_item(identifications) or {}
    standards_summary = _join_standard_blocks(identifications)
    standards = []
    for standard in identification.get('standards', []) or []:
        if isinstance(standard, dict):
            designation = _text(standard.get('designation')) or _text(standard.get('name'))
            if designation:
                standards.append(designation)
    documents = identification.get('documents', []) or []
    document = _first_list_item(documents)
    status_changes = record.get('statusChanges') or []
    last_status_change = _first_list_item(status_changes)

    address = None
    if isinstance(manufacturer, dict):
        address = _first_list_item(manufacturer.get('addresses'))
        if isinstance(address, dict):
            address = address.get('fullAddress')
    if not address and isinstance(applicant, dict):
        address = _first_list_item(applicant.get('addresses'))
        if isinstance(address, dict):
            address = address.get('fullAddress')

    status = _status_name(_first_list_item(status_changes) and (status_changes[0].get('status') if isinstance(status_changes[0], dict) else None))
    if not status and isinstance(last_status_change, dict):
        status = _status_name(last_status_change.get('idStatus'))
    if not status:
        status = _deep_lookup(record, 'status', 'statusName', 'state', 'stateName')

    applicant_name = _text(applicant.get('shortName')) or _text(applicant.get('fullName')) or _deep_lookup(applicant, 'shortName', 'fullName', 'name', 'title')
    manufacturer_name = _text(manufacturer.get('fullName')) or _text(manufacturer.get('shortName')) or _deep_lookup(manufacturer, 'fullName', 'shortName', 'name', 'title')
    product_name = (
        _join_identification_blocks(identifications)
        or _text(product.get('fullName'))
        or _deep_lookup(product, 'fullName', 'name', 'productName')
        or _text(identification.get('name'))
    )
    testing_labs_summary = _join_testing_lab_blocks(record.get('testingLabs'))
    testing_protocols_summary = _join_testing_protocol_blocks(record.get('testingLabs'))
    document_summary = _join_document_blocks(identifications)
    document_name = document_summary or (_text(document.get('name')) if isinstance(document, dict) else None)
    document_number = None if document_summary else (_text(document.get('number')) if isinstance(document, dict) else None)
    raw_scheme = record.get('scheme') or record.get('declScheme') or record.get('idDeclScheme')
    scheme = None
    if raw_scheme is not None and _text(raw_scheme) and str(_text(raw_scheme)).strip().lower() not in {'none', 'null'}:
        scheme = None
    decl_raw = _deep_lookup(record, 'declType', 'declarationType', 'type', 'idDeclType') or _text(record.get('idDeclType'))
    decl_type = _lookup_mapped_value(decl_raw, DECLARATION_TYPE_MAP)
    raw_obj_type = _deep_lookup(record, 'objectType', 'declObjectType', 'idObjectDeclType') or _text(record.get('idObjectDeclType'))
    obj_type = _lookup_object_type(raw_obj_type)
    number_value = _text(record.get('number')) or _deep_lookup(record, 'number', 'regNumber', 'declNumber', 'declarationNumber', 'regNum', 'code', 'id')
    declaration_period = _build_declaration_period(number_value, record.get('declRegDate'), record.get('declEndDate'))

    return {
        'number': number_value,
        'declaration_period': declaration_period,
        'status': status,
        'product_name': product_name,
        'applicant': applicant_name,
        'inn': _text(applicant.get('inn')) or _text(manufacturer.get('inn')),
        'manufacturer': manufacturer_name,
        'address': address,
        'scheme': scheme,
        'decl_type': decl_type,
        'object_type': obj_type,
        'document_name': document_name,
        'document_number': document_number,
        'standards': standards_summary or _join_text(standards),
        'testing_labs': testing_labs_summary,
        'testing_protocols': testing_protocols_summary,
    }


def fetch_declaration_record(token: str, record_id: str):
    detail_url = f'{API_BASE}/api/v1/rds/common/declarations/{record_id}'
    try:
        response = requests.get(
            detail_url,
            timeout=40,
            headers={**DEFAULT_HEADERS, 'Authorization': normalize_token(token)},
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data:
            return data[0]
    except Exception:
        pass

    try:
        items = fetch_declaration_list(token, number=str(record_id))
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get('id') or item.get('declarationId') or item.get('uid') or item.get('recordId') or item.get('idDeclaration')
            if str(item_id) == str(record_id):
                return item
        if items:
            return items[0]
    except Exception:
        pass

    html_url = f'{BASE_PUBLISH_VIEW}/{record_id}/common'
    try:
        response = requests.get(html_url, timeout=30, headers={**DEFAULT_HEADERS})
        response.raise_for_status()
        html = response.text
        match_title = re.search(r'<title>(.*?)</title>', html, flags=re.I | re.S)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        return {
            'id': record_id,
            'number': match_title.group(1).strip() if match_title else record_id,
            'title_text': text[:2000],
            'raw_html': html,
        }
    except Exception:
        return {'id': record_id}
