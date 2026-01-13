# 🖼️ Обработка медиафайлов

**Версия:** 1.2  
**Дата:** 13.01.2026

---

## 📋 Обзор

Face2Phase автоматически обрабатывает загруженные медиафайлы:
- **Фотографии**: Создание thumbnails (маленький + средний)
- **PDF презентации**: Извлечение первой страницы как превью
- **Видео**: Заглушка для будущей реализации (poster extraction)

---

## 🗂️ Структура хранения в R2

```
face2phase-bucket/
├── events/
│   └── {event_id}/
│       ├── photos/               # ФОТОГРАФИИ
│       │   ├── original/         # {uuid}.jpg (Исходники)
│       │   └── thumbnails/       # small_{uuid}.jpg, medium_{uuid}.jpg
│       │
│       ├── videos/               # ВИДЕО
│       │   ├── original/         # {uuid}.mp4 (Сами видеофайлы)
│       │   └── posters/          # {uuid}.jpg (Заставка - TODO)
│       │
│       └── documents/            # МАТЕРИАЛЫ
│           ├── files/            # {uuid}.pdf (Файлы презентаций)
│           └── previews/         # {uuid}.jpg (Обложка первого слайда)
```

---

## 🖼️ Thumbnails для фотографий

### Размеры

| Тип | Размер | Назначение | Путь |
|-----|--------|-----------|------|
| **Small** | 300×300px | Для ленты/грида (быстрая прокрутка) | `small_{uuid}.jpg` |
| **Medium** | 800×800px | Для просмотра (полноэкранный режим) | `medium_{uuid}.jpg` |
| **Original** | Оригинал | Только для кнопки "Скачать" | `{uuid}.jpg` |

### Параметры сжатия

- **Формат**: JPEG
- **Качество**: 85% (оптимальный баланс размер/качество)
- **Метод**: Lanczos resampling (высокое качество)
- **Преобразование**: Автоматическая конвертация RGBA/PNG → RGB

### Процесс обработки

1. **Загрузка оригинала** в `photos/original/`
2. **Создание small thumbnail** (300×300px) → `photos/thumbnails/small_*.jpg`
3. **Создание medium thumbnail** (800×800px) → `photos/thumbnails/medium_*.jpg`
4. **Запуск AI обработки лиц** (в фоновой задаче)

### Пример использования

**Лента фотографий (grid):**
```html
<img src="https://cdn.yourdomain.com/events/{id}/photos/thumbnails/small_{uuid}.jpg">
```

**Полноэкранный просмотр:**
```html
<img src="https://cdn.yourdomain.com/events/{id}/photos/thumbnails/medium_{uuid}.jpg">
```

**Скачивание оригинала:**
```javascript
fetch('/events/media/{media_item_id}/download')
  .then(res => res.json())
  .then(data => window.open(data.download_url))
```

---

## 📄 PDF презентации

### Извлечение превью

При загрузке PDF автоматически:
1. Извлекается **первая страница**
2. Рендерится в изображение (150 DPI)
3. Конвертируется в JPEG (качество 85%)
4. Сохраняется в `documents/previews/{uuid}.jpg`

### Библиотека

- **PyMuPDF (fitz)** - быстрая и надежная библиотека для работы с PDF
- Поддержка защищенных PDF
- Высокое качество рендеринга

### Пример использования

**Карточка презентации:**
```html
<div class="presentation-card">
  <img src="https://cdn.yourdomain.com/events/{id}/documents/previews/{uuid}.jpg">
  <button onclick="downloadPDF('{media_item_id}')">Скачать PDF</button>
</div>
```

---

## 🎬 Видео (TODO)

### Планируемая функциональность

- [ ] Извлечение первого кадра как poster
- [ ] Использование `ffmpeg-python` или `opencv-python`
- [ ] Сохранение в `videos/posters/{uuid}.jpg`

### Структура

```
videos/
├── original/
│   └── {uuid}.mp4      # Оригинальное видео
└── posters/
    └── {uuid}.jpg      # Первый кадр (заставка)
```

---

## 🚀 API Endpoints

### Загрузка медиа

```http
POST /events/{event_id}/upload
Content-Type: multipart/form-data

files: [file1.jpg, file2.pdf, ...]
```

**Ответ:**
```json
{
  "uploaded_count": 2,
  "media_ids": ["uuid1", "uuid2"]
}
```

### Получение информации о медиа

```http
GET /events/{event_id}/media
```

**Ответ:**
```json
[
  {
    "id": "uuid1",
    "event_id": "event_uuid",
    "original_path": "events/event_uuid/photos/original/uuid1.jpg",
    "small_thumbnail_path": "events/event_uuid/photos/thumbnails/small_uuid1.jpg",
    "medium_thumbnail_path": "events/event_uuid/photos/thumbnails/medium_uuid1.jpg",
    "preview_path": null,
    "media_type": "image",
    "file_type": "jpg",
    "ai_status": "processed",
    "uploaded_at": "2026-01-13T12:00:00Z"
  },
  {
    "id": "uuid2",
    "event_id": "event_uuid",
    "original_path": "events/event_uuid/documents/files/uuid2.pdf",
    "small_thumbnail_path": null,
    "medium_thumbnail_path": null,
    "preview_path": "events/event_uuid/documents/previews/uuid2.jpg",
    "media_type": "document",
    "file_type": "pdf",
    "ai_status": "pending",
    "uploaded_at": "2026-01-13T12:00:05Z"
  }
]
```

> **Примечание:** Поле `thumbnail_path` удалено из API. Используйте `small_thumbnail_path` для ленты и `medium_thumbnail_path` для просмотра.

### Скачивание оригинала

```http
GET /events/media/{media_item_id}/download
```

**Ответ:**
```json
{
  "media_item_id": "uuid1",
  "download_url": "https://cdn.yourdomain.com/events/event_uuid/photos/original/uuid1.jpg",
  "media_type": "image",
  "file_type": "jpg"
}
```

---

## ⚙️ Конфигурация

### MediaProcessingService

```python
class MediaProcessingService:
    # Thumbnail sizes
    SMALL_SIZE = (300, 300)  # Feed/grid
    MEDIUM_SIZE = (800, 800)  # Viewing
    
    # Quality settings
    JPEG_QUALITY = 85
    PDF_DPI = 150
```

### Поддерживаемые форматы

**Изображения:**
- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- WebP (.webp)

**Видео:**
- MP4 (.mp4)
- MOV (.mov)
- AVI (.avi)

**Документы:**
- PDF (.pdf)

---

## 🔧 Миграция существующих данных

Для добавления новых полей в базу данных:

```bash
python scripts/migrate_media_structure.py
```

Это добавит колонки:
- `small_thumbnail_path`
- `medium_thumbnail_path`
- `preview_path`
- `file_type`

**Важно:** Существующие файлы НЕ мигрируются. Только новые загрузки будут использовать новую структуру.

---

## 📊 Производительность

### Обработка изображений

| Операция | Время (средн.) | Размер |
|----------|---------------|--------|
| Загрузка в R2 | 50-100ms | Зависит от размера |
| Small thumbnail | 50-100ms | ~20-50KB |
| Medium thumbnail | 100-200ms | ~100-200KB |
| AI обработка | 1-2 сек | - |

### Обработка PDF

| Операция | Время (средн.) | Размер |
|----------|---------------|--------|
| Загрузка в R2 | 100-500ms | Зависит от размера |
| Извлечение страницы | 200-500ms | ~100-200KB |

---

## 💡 Best Practices

### Для фронтенда

1. **Ленты фото:** Всегда используйте `small_thumbnail_path`
2. **Модальное окно:** Загружайте `medium_thumbnail_path` по требованию
3. **Скачивание:** Используйте endpoint `/download` вместо прямой ссылки
4. **Lazy loading:** Загружайте thumbnails по мере прокрутки

### Для бэкенда

1. **Асинхронность:** Обработка thumbnails не блокирует загрузку
2. **Fallback:** Если thumbnail не создан, используйте оригинал
3. **Ошибки:** Логируйте, но не прерывайте загрузку при ошибке обработки
4. **Очистка:** Удаляйте временные файлы в `finally` блоках

---

## 🐛 Troubleshooting

### Thumbnails не создаются

**Проблема:** Загруженные фото не имеют `small_thumbnail_path`

**Решение:**
1. Проверьте логи сервера на ошибки Pillow
2. Убедитесь, что формат изображения поддерживается
3. Проверьте доступ к R2 (credentials)

### PDF превью пустое

**Проблема:** `preview_path` есть, но изображение не отображается

**Решение:**
1. Проверьте, что PDF не защищен паролем
2. Убедитесь, что PyMuPDF установлен корректно
3. Проверьте, что первая страница не пустая

### Медленная загрузка

**Проблема:** Загрузка медиа занимает много времени

**Решение:**
1. Используйте batch upload (до 10 файлов за раз)
2. Сжимайте изображения на клиенте перед загрузкой
3. Используйте async/await на клиенте для параллельной загрузки

---

## 📚 Связанные документы

- [README.md](../README.md) - Общая документация проекта
- [docs/CLOUDFLARE_R2_SETUP.md](./CLOUDFLARE_R2_SETUP.md) - Настройка Cloudflare R2
- [docs/PROJECT_STATUS.md](./PROJECT_STATUS.md) - Статус проекта
