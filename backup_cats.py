import os
import json
import requests
from datetime import datetime
from urllib.parse import quote

# Конфигурация
GROUP_FOLDER = "SPD-138"
CAT_API_BASE = "https://cataas.com/cat/says/"

def sanitize_filename(text: str) -> str:
    """Заменяет недопустимые символы в имени файла"""
    invalid = '<>:"/\\|?*'
    for char in invalid:
        text = text.replace(char, '_')
    return text.strip()[:100]  # ограничим длину

def upload_to_yadisk(file_path: str, remote_path: str, token: str):
    """Загружает файл на Яндекс.Диск"""
    upload_url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
    headers = {"Authorization": f"OAuth {token}"}
    params = {"path": remote_path, "overwrite": "true"}

    response = requests.get(upload_url, headers=headers, params=params)
    response.raise_for_status()
    upload_link = response.json().get("href")

    with open(file_path, "rb") as f:
        upload_response = requests.put(upload_link, files={"file": f})
    upload_response.raise_for_status()

def create_folder_on_yadisk(folder_name: str, token: str):
    """Создаёт папку на Яндекс.Диске, если её нет"""
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {"Authorization": f"OAuth {token}"}
    params = {"path": folder_name}
    response = requests.put(url, headers=headers, params=params)
    if response.status_code not in (201, 409):  # 409 = уже существует
        response.raise_for_status()

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

    # Подготовка имени файла
    safe_text = sanitize_filename(text)
    local_image_path = f"{safe_text}.jpg"
    remote_path = f"{GROUP_FOLDER}/{safe_text}.jpg"

    # 1. Получаем картинку
    encoded_text = quote(text)
    cat_url = f"{CAT_API_BASE}{encoded_text}"
    print(f"Запрашиваем изображение: {cat_url}")

    img_response = requests.get(cat_url)
    img_response.raise_for_status()

    with open(local_image_path, "wb") as f:
        f.write(img_response.content)
    file_size = os.path.getsize(local_image_path)
    print(f"Изображение сохранено локально: {local_image_path} ({file_size} байт)")

    # 2. Создаём папку на Яндекс.Диске
    create_folder_on_yadisk(GROUP_FOLDER, token)
    print(f"Папка '{GROUP_FOLDER}' готова на Яндекс.Диске")

    # 3. Загружаем файл
    upload_to_yadisk(local_image_path, remote_path, token)
    print(f"Файл загружен на Яндекс.Диск: {remote_path}")

    # 4. Сохраняем метаданные в JSON
    metadata = {
        "filename": safe_text + ".jpg",
        "original_text": text,
        "file_size_bytes": file_size,
        "uploaded_at": datetime.now().isoformat(),
        "remote_path": remote_path
    }

    json_filename = "backup_log.json"
    log_data = []

    # Если файл уже есть — добавляем запись
    if os.path.exists(json_filename):
        with open(json_filename, "r", encoding="utf-8") as f:
            try:
                log_data = json.load(f)
            except json.JSONDecodeError:
                log_data = []

    log_data.append(metadata)

    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=4)

    print(f"Информация сохранена в {json_filename}")

    # Удаляем временный локальный файл (опционально)
    os.remove(local_image_path)

if __name__ == "__main__":
    main()