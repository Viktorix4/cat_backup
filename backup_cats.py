import os
import json
import requests
from datetime import datetime
from urllib.parse import quote

# Конфигурация
GROUP_FOLDER = "SPD-138"
CAT_API_BASE = "https://cataas.com/cat/says/"  # ← убраны лишние пробелы!


def sanitize_filename(text: str) -> str:
    """Заменяет недопустимые символы в имени файла."""
    invalid = '<>:"/\\|?*'
    for char in invalid:
        text = text.replace(char, '_')
    return text.strip()[:100]  # ограничим длину


def fetch_cat_image(url: str) -> bytes:
    """Получает изображение кота по URL и возвращает его содержимое в виде байтов."""
    print(f"Запрашиваем изображение: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Не удалось загрузить изображение: {e}")


def save_image_locally(content: bytes, path: str) -> int:
    """Сохраняет байты изображения в локальный файл и возвращает размер файла."""
    with open(path, "wb") as f:
        f.write(content)
    return os.path.getsize(path)


def create_folder_on_yadisk(folder_name: str, token: str):
    """Создаёт папку на Яндекс.Диске, если её нет."""
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {"Authorization": f"OAuth {token}"}
    params = {"path": folder_name}
    response = requests.put(url, headers=headers, params=params)
    if response.status_code not in (201, 409):  # 409 = уже существует
        response.raise_for_status()


def upload_to_yadisk(file_path: str, remote_path: str, token: str):
    """Загружает файл на Яндекс.Диск."""
    upload_url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
    headers = {"Authorization": f"OAuth {token}"}
    params = {"path": remote_path, "overwrite": "true"}

    response = requests.get(upload_url, headers=headers, params=params)
    response.raise_for_status()
    upload_link = response.json().get("href")

    with open(file_path, "rb") as f:
        upload_response = requests.put(upload_link, data=f)
        upload_response.raise_for_status()


def update_backup_log(metadata: dict, log_filename: str = "backup_log.json"):
    """Добавляет запись в JSON-лог резервного копирования."""
    log_data = []

    if os.path.exists(log_filename):
        with open(log_filename, "r", encoding="utf-8") as f:
            try:
                log_data = json.load(f)
            except json.JSONDecodeError:
                log_data = []

    log_data.append(metadata)

    with open(log_filename, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=4)


def main():
    print("=== Резервное копирование картинок с cataas.com на Яндекс.Диск ===")
    text = input("Введите текст для надписи на картинке: ").strip()
    if not text:
        print("Текст не может быть пустым!")
        return

    token = input("Введите OAuth-токен Яндекс.Диска: ").strip()
    if not token:
        print("Токен обязателен!")
        return

    # Подготовка путей
    safe_text = sanitize_filename(text)
    local_image_path = f"{safe_text}.jpg"
    remote_path = f"{GROUP_FOLDER}/{safe_text}.jpg"

    # 1. Получаем изображение
    encoded_text = quote(text)
    cat_url = f"{CAT_API_BASE}{encoded_text}"
    try:
        image_content = fetch_cat_image(cat_url)
        file_size = save_image_locally(image_content, local_image_path)
        print(f"Изображение сохранено локально: {local_image_path} ({file_size} байт)")
    except RuntimeError as e:
        print(f"❌ Ошибка: {e}")
        return

    # 2. Создаём папку на Яндекс.Диске
    try:
        create_folder_on_yadisk(GROUP_FOLDER, token)
        print(f"Папка '{GROUP_FOLDER}' готова на Яндекс.Диске")
    except requests.exceptions.RequestException as e:
        print(f"❌ Не удалось создать папку на Яндекс.Диске: {e}")
        return

    # 3. Загружаем файл
    try:
        upload_to_yadisk(local_image_path, remote_path, token)
        print(f"Файл загружен на Яндекс.Диск: {remote_path}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при загрузке на Яндекс.Диск: {e}")
        return

    # 4. Сохраняем метаданные
    metadata = {
        "filename": safe_text + ".jpg",
        "original_text": text,
        "file_size_bytes": file_size,
        "uploaded_at": datetime.now().isoformat(),
        "remote_path": remote_path
    }

    update_backup_log(metadata)
    print(f"Информация сохранена в backup_log.json")

    # Удаляем временный файл
    os.remove(local_image_path)


if __name__ == "__main__":
    main()