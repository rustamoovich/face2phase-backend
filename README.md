# Face2Phase Backend

**Version:** 1.0  
**Status:** 🚀 Production Ready (MVP)

Бэкенд для платформы автоматизированного поиска фотографий с мероприятий с использованием распознавания лиц.

---

## 📋 Содержание

- [О проекте](#о-проекте)
- [Технологический стек](#технологический-стек)
- [Быстрый старт](#быстрый-старт)
- [Структура проекта](#структура-проекта)
- [API Endpoints](#api-endpoints)
- [Настройка Cloudflare R2](#настройка-cloudflare-r2)
- [Развертывание](#развертывание)

---

## О проекте

**Face2Phase** — SaaS-платформа для автоматизированного поиска медиаконтента с мероприятий.

**Ключевая фича:** Участник делает селфи → Система мгновенно выдает все фото, где он присутствует.

### Как это работает?

1. **Организатор** загружает фото с мероприятия
2. **AI Worker** находит лица и создает векторные эмбеддинги (InsightFace)
3. **Участник** загружает селфи → система ищет похожие лица через pgvector
4. **Результат:** Персональная лента фото с мероприятия за 2 секунды

---

## Технологический стек

- **FastAPI** - асинхронный веб-фреймворк
- **PostgreSQL 15+ + pgvector** - база данных с векторным поиском
- **InsightFace (buffalo_l)** - детекция и векторизация лиц
- **Cloudflare R2** - S3-совместимое облачное хранилище
- **SQLAlchemy (Async)** - ORM
- **Pydantic** - валидация данных
- **JWT** - аутентификация

---

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/yourusername/face2phase-backend.git
cd face2phase-backend
```

### 2. Запуск PostgreSQL с pgvector

```bash
docker-compose up -d
```

### 3. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
```

### 4. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 5. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и заполните:

```env
# Database
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=face2phase_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# JWT Security
SECRET_KEY=your-super-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Cloudflare R2
R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your-r2-access-key-id
R2_SECRET_ACCESS_KEY=your-r2-secret-access-key
R2_BUCKET_NAME=face2phase
R2_PUBLIC_URL=https://cdn.yourdomain.com
```

### 6. Инициализация базы данных

```bash
python scripts/init_db.py
```

### 7. Запуск сервера

```bash
uvicorn app.main:app --reload
```

Сервер доступен по адресу: **http://localhost:8000**

Swagger документация: **http://localhost:8000/docs**

---

## Структура проекта

```
face2phase-backend/
├── app/
│   ├── api/
│   │   ├── endpoints/
│   │   │   ├── auth.py         # Регистрация, логин
│   │   │   ├── events.py       # Управление мероприятиями
│   │   │   ├── media.py        # Загрузка медиафайлов
│   │   │   └── biometrics.py   # Биометрия, поиск "Мои моменты"
│   │   └── deps.py             # Зависимости (get_current_user)
│   ├── core/
│   │   └── security.py         # JWT, хэширование паролей
│   ├── services/
│   │   ├── face_service.py            # InsightFace обработка
│   │   ├── storage_service.py         # Cloudflare R2 интеграция
│   │   └── media_processing_service.py # Thumbnails и PDF превью
│   ├── database.py             # Конфигурация БД
│   ├── models.py               # SQLAlchemy модели
│   ├── schemas.py              # Pydantic схемы
│   └── main.py                 # Точка входа FastAPI
├── scripts/
│   ├── migrate_to_hnsw.py         # Миграция IVFFlat → HNSW
│   └── migrate_media_structure.py # Добавление полей для thumbnails
├── docs/
│   ├── CLOUDFLARE_R2_SETUP.md     # Инструкция по настройке R2
│   ├── HNSW_INDEXING.md           # HNSW индексирование для pgvector
│   ├── PRIVACY_AND_PROFILE.md     # Управление профилем и приватностью
│   └── BIOMETRIC_SECURITY_POLICY.md # Политика безопасности биометрии
├── docker-compose.yml          # PostgreSQL + pgvector
├── requirements.txt            # Зависимости Python
├── init_db.py                  # Скрипт инициализации БД
├── .env                        # Переменные окружения (не в git)
└── README.md                   # Этот файл
```

---

## API Endpoints

### 🔐 Аутентификация

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/auth/register` | Регистрация пользователя |
| POST | `/auth/login` | Вход (получение JWT токена, автоматическая реактивация) |
| GET | `/auth/me` | Получить текущего пользователя (включая статус is_active) |
| GET | `/auth/biometrics` | Получить информацию о биометрии |
| POST | `/auth/biometrics` | Загрузить селфи (первичная загрузка) |
| PUT | `/auth/biometrics` | Обновить селфи |
| DELETE | `/auth/biometrics` | Удалить биометрию (hard delete) |
| DELETE | `/auth/profile` | Удалить профиль полностью (⚠️ только для обычных пользователей) |
| DELETE | `/auth/deactivate` | Деактивировать профиль (⚠️ только для организаторов) |

### 🎉 Мероприятия

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/events/` | Создать мероприятие (только организатор) |
| GET | `/events/` | Получить список своих мероприятий |
| GET | `/events/{event_id}/media` | Список медиафайлов мероприятия |

### 📸 Медиафайлы

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/events/{event_id}/upload` | Загрузить фото/видео/PDF (с автогенерацией thumbnails) |
| GET | `/events/media/{media_item_id}/faces` | Получить найденные лица на фото |
| GET | `/events/media/{media_item_id}/download` | Скачать оригинальный файл (полный размер) |

### 🔍 Поиск

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/feed/my-moments` | Получить все фото, где найдено лицо пользователя |

---

## Настройка Cloudflare R2

**Cloudflare R2** — это S3-совместимое хранилище с **нулевой стоимостью исходящего трафика**.

### Почему R2, а не AWS S3?

| Параметр | AWS S3 | Cloudflare R2 |
|----------|--------|---------------|
| Хранение (за ГБ) | $0.023 | $0.015 |
| Исходящий трафик | $0.09/ГБ | **$0 (бесплатно!)** |
| S3 API | ✅ | ✅ |
| Интеграция с CDN | CloudFront ($) | Cloudflare (бесплатно) |

**Экономия для проекта с 1 ТБ трафика в месяц: ~$90/мес**

### Подробная инструкция

Смотрите полную инструкцию: **[docs/CLOUDFLARE_R2_SETUP.md](docs/CLOUDFLARE_R2_SETUP.md)**

---

## Развертывание

### Production (Docker)

1. Соберите образ:
```bash
docker build -t face2phase-backend .
```

2. Запустите контейнеры:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### CI/CD (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build and Deploy
        run: |
          docker build -t face2phase-backend .
          docker push your-registry/face2phase-backend:latest
```

---

## 📝 Лицензия

MIT License

---

## 👥 Команда

- **Backend:** FastAPI + InsightFace
- **Database:** PostgreSQL + pgvector
- **Storage:** Cloudflare R2
- **Deploy:** Docker + Kubernetes

---

**Stop searching. Start sharing.** ✨
