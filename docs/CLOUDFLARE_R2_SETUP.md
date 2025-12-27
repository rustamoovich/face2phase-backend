# Настройка Cloudflare R2

Cloudflare R2 - это S3-совместимое объектное хранилище с нулевой стоимостью исходящего трафика.

## Почему R2?

1. **Бесплатный исходящий трафик** - в отличие от AWS S3, вы не платите за загрузку файлов пользователями
2. **Низкая стоимость хранения** - $0.015 за ГБ в месяц
3. **S3-совместимый API** - легко мигрировать с/на AWS S3
4. **Интеграция с Cloudflare CDN** - быстрая доставка контента по всему миру

## Шаг 1: Создание аккаунта

1. Зарегистрируйтесь на [Cloudflare](https://dash.cloudflare.com/sign-up)
2. Перейдите в раздел **R2** в боковом меню
3. Создайте bucket с именем `face2phase` (или любым другим)

## Шаг 2: Получение ключей доступа

1. В разделе R2 перейдите в **R2 API Tokens**
2. Нажмите **Create API Token**
3. Выберите права:
   - Object Read & Write
   - Bucket Read
4. Сохраните:
   - **Access Key ID** (например: `4f6ba8a1c7d2e9f3a5b6c7d8e9f0a1b2`)
   - **Secret Access Key** (показывается только один раз!)

## Шаг 3: Получение Endpoint URL

1. В разделе R2 перейдите в ваш bucket
2. Скопируйте **S3 API Endpoint**
   - Формат: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
   - Пример: `https://1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d.r2.cloudflarestorage.com`

## Шаг 4: Настройка публичного доступа (опционально)

Если вы хотите, чтобы пользователи могли напрямую скачивать файлы:

### Вариант 1: Custom Domain (рекомендуется)

1. В настройках bucket выберите **Connect Custom Domain**
2. Введите домен (например, `cdn.face2phase.com`)
3. Следуйте инструкциям по настройке DNS

### Вариант 2: Публичный bucket

1. В настройках bucket включите **Public Access**
2. URL будет вида: `https://pub-<hash>.r2.dev/<file-key>`

## Шаг 5: Обновление .env

Заполните переменные окружения в `.env`:

```env
# Cloudflare R2 (S3-compatible storage)
R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your-access-key-id-here
R2_SECRET_ACCESS_KEY=your-secret-access-key-here
R2_BUCKET_NAME=face2phase
R2_PUBLIC_URL=https://cdn.yourdomain.com  # или https://pub-<hash>.r2.dev
```

## Шаг 6: Установка зависимостей

```bash
pip install boto3 aioboto3
```

Или если используете весь `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Шаг 7: Проверка работы

Запустите сервер и попробуйте загрузить медиафайл через эндпоинт:

```bash
POST /events/{event_id}/upload
```

Если все настроено правильно, файл будет загружен в R2, а в базе данных появится запись с ключом `events/{event_id}/original/{uuid}.jpg`.

## Структура хранения

```
face2phase/
├── events/
│   └── {event_id}/
│       └── original/
│           ├── {uuid1}.jpg
│           ├── {uuid2}.jpg
│           └── {uuid3}.mp4
├── biometrics/
│   ├── {user_id1}.jpg
│   ├── {user_id2}.jpg
│   └── {user_id3}.jpg
└── thumbnails/  (будущая функциональность)
    └── {event_id}/
        ├── {uuid1}_thumb.jpg
        └── {uuid2}_thumb.jpg
```

## Получение URL файла

Для получения публичного URL используйте метод из `storage_service.py`:

```python
from app.services.storage_service import get_storage_service

storage = get_storage_service()
public_url = storage.get_public_url("events/123/original/abc.jpg")
# Результат: https://cdn.yourdomain.com/events/123/original/abc.jpg
```

## Миграция с локального хранилища

Если у вас уже есть файлы в папке `uploads/`, используйте скрипт миграции:

```bash
python scripts/migrate_to_r2.py
```

## Troubleshooting

### Ошибка: "Failed to upload file to R2"

1. Проверьте правильность `R2_ENDPOINT_URL` (должен содержать ваш ACCOUNT_ID)
2. Убедитесь, что API токен имеет права на запись
3. Проверьте, что bucket существует и имя совпадает с `R2_BUCKET_NAME`

### Ошибка: "Access Denied"

1. Пересоздайте API токен с правами **Object Read & Write**
2. Убедитесь, что `R2_SECRET_ACCESS_KEY` скопирован полностью

### Файлы загружаются, но не доступны по публичному URL

1. Убедитесь, что включен Public Access для bucket
2. Или настройте Custom Domain
3. Проверьте `R2_PUBLIC_URL` в `.env`

## Стоимость (примерная)

Для проекта с 10,000 пользователей и 1M фотографий:

- Хранение: 100 ГБ × $0.015 = **$1.50/мес**
- Операции записи: 1M × $0.0045/1000 = **$4.50**
- Операции чтения: 10M × $0.0036/10000 = **$3.60**
- Исходящий трафик: **$0** (бесплатно!)

**Итого: ~$10/мес** вместо ~$100/мес на AWS S3

## Альтернативы

Если R2 не подходит, можно использовать:

1. **AWS S3** - больше функций, дороже
2. **Backblaze B2** - дешевле, но меньше регионов
3. **DigitalOcean Spaces** - S3-совместимый, фиксированная цена
4. **MinIO** - self-hosted, полный контроль

Для замены нужно изменить только `storage_service.py` и переменные окружения.

