"""
Поиск и нормализация телефонных номеров в тексте и на веб-странице.
Поддерживаемые префиксы: +7 и 8. Нормализация -> +7XXXXXXXXXX.
"""

import re
import argparse
import sys
import requests
import html as html_lib

# префикс +7 или 8, затем ровно 10 цифр, между цифрами допускаются пробелы, дефисы, скобки
PHONE_RE = re.compile(
    r'(?<!\d)'
    r'(?:\+7|8)'
    r'[\s\-\(]*'
    r'(?:\d[\s\-\(\)]*){10}'
    r'(?!\d)'
)

DIGITS_RE = re.compile(r'\D')


def find_phone_numbers(text: str, normalize: bool = True) -> list[str]:
    """Ищет номера в тексте. Возвращает нормализованные номера (+7XXXXXXXXXX) по умолчанию."""
    results = []
    for m in PHONE_RE.finditer(text):
        s = m.group(0)
        digits = DIGITS_RE.sub('', s)
        if len(digits) == 11 and digits[0] in ('7', '8'):
            if normalize:
                if digits[0] == '8':
                    digits = '7' + digits[1:]
                results.append('+' + digits)
            else:
                results.append(s)
    return results


def find_in_file(filename: str) -> list[str]:
    """Ищет номера в локальном файле (текстовом, utf-8)."""
    with open(filename, 'r', encoding='utf-8') as f:
        text = f.read()
    return find_phone_numbers(text)


def _strip_tags_and_scripts(html: str) -> str:
    """
    Примитивное извлечение видимого текста из HTML:
    - удаляет <script> и <style> блоки,
    - убирает HTML-теги,
    - разворачивает HTML-сущности.
    """
    # Убираем скрипты и стили
    html = re.sub(r'(?is)<script.*?>.*?</script>', ' ', html)
    html = re.sub(r'(?is)<style.*?>.*?</style>', ' ', html)
    # Убираем HTML-комментарии
    html = re.sub(r'(?is)<!--.*?-->', ' ', html)
    # Убираем теги
    text = re.sub(r'(?s)<[^>]+>', ' ', html)
    # Разворачиваем сущности и сжимаем пробелы
    text = html_lib.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def find_in_webpage(url: str, timeout: int = 10) -> list[str]:
    """
    Загружает страницу по URL, извлекает видимый текст и ищет номера.
    В случае ошибки HTTP будет поднято исключение requests.RequestException.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; PhoneFinder/1.0)'
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    html = resp.text
    text = _strip_tags_and_scripts(html)
    return find_phone_numbers(text)


def _cli():
    p = argparse.ArgumentParser(description='Поиск телефонных номеров (+7/8) в тексте, файле или на сайте.')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', '-u', help='URL страницы для поиска')
    group.add_argument('--file', '-f', help='Локальный файл для поиска')
    group.add_argument('--text', '-t', help='Текст, в котором искать номера')
    args = p.parse_args()

    try:
        if args.url:
            results = find_in_webpage(args.url)
        elif args.file:
            results = find_in_file(args.file)
        else:
            results = find_phone_numbers(args.text)
    except requests.RequestException as e:
        print(f'Ошибка при загрузке страницы: {e}', file=sys.stderr)
        sys.exit(2)

    if results:
        for r in results:
            print(r)
    else:
        print('Номеров не найдено.')


if __name__ == '__main__':
    _cli()