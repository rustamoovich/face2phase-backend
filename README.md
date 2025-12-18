# Техническое Задание на разработку платформы Face2Phase

**Версия:** 1.0  
**Дата:** 19.12.2025  
**Название проекта:** Face2Phase  
**Слоган:** Stop searching. Start sharing.

---

## 1. Общее описание проекта
**Face2Phase** — это SaaS-платформа для автоматизированного поиска и дистрибуции медиаконтента (фото/видео) с мероприятий с использованием технологий компьютерного зрения.

**Ключевая ценность:** Участники мероприятий не ищут свои фото вручную. Они делают селфи, а система мгновенно выдает им персональную ленту контента, где они присутствуют.

### 1.1. Архитектура системы
Система состоит из трех изолированных приложений и общего бэкенда:
1. **Mobile App (iOS/Android):** Клиентская часть для участников (поиск фото, скачивание).
2. **Web Dashboard:** Кабинет для организаторов и фотографов (загрузка контента, аналитика).
3. **Backend API + AI Worker:** Серверная часть, база данных, очереди задач и модуль распознавания лиц.

---

## 2. Технологический стек (Жесткие требования)

### 2.1. Backend & Infrastructure
- **Язык:** Python 3.11+
- **Framework:** FastAPI (асинхронный).
- **Database:** PostgreSQL 15+ с расширением `pgvector`.
- **Task Queue:** Redis + Celery (для фоновой обработки фото).
- **AI Engine:** InsightFace (ArcFace) + ONNX Runtime (для ускорения).
- **Storage:** Cloudflare R2 (S3-compatible API).
- **Deploy:** Docker, Docker Compose (для Dev), Kubernetes/Docker Swarm (для Prod).

### 2.2. Frontend (Web)
- **Framework:** Vue.js 3 (Composition API) + Vite.
- **UI Kit:** Tailwind CSS или PrimeVue.

### 2.3. Mobile App
- **Framework:** Flutter (Dart).
- **Target:** iOS, Android.

---

## 3. Функциональные требования

### 3.1. Мобильное приложение (Гость/Участник)
#### 3.1.1. Регистрация и Онбординг
- Вход через Apple ID / Google / Email.
- **Биометрический онбординг:** Пользователь должен сделать селфи или загрузить портретное фото.
- **Валидация селфи:** AI должен проверить, что на фото одно лицо, оно четкое и открытое.

#### 3.1.2. Лента "Мои моменты" (Main Feed)
- Приложение запрашивает у бэкенда список медиафайлов, совпадающих с вектором лица пользователя.
- Отображение фото в виде ленты (как в Instagram) или сетки.
- Водяные знаки на превью (если контент платный — опционально на будущее).

#### 3.1.3. Взаимодействие с контентом
- **Просмотр:** Открытие фото на полный экран (зум, пан).
- **Скачивание:** Сохранение оригинала в галерею телефона.
- **Шаринг:** Нативная кнопка "Поделиться" (отправка в Instagram Stories, Telegram и т.д.).
- **Жалоба:** "Это не я" (для дообучения модели или скрытия фото).

#### 3.1.4. Профиль
- **Управление биометрией:** "Обновить мое селфи".
- **Управление приватностью:** "Удалить все мои биометрические данные" (Hard delete из базы).

### 3.2. Веб-панель (Организатор/Фотограф)
#### 3.2.1. Управление мероприятиями
- Создание мероприятия (Название, Дата, Место, Обложка).
- Генерация QR-кода мероприятия (для приглашения участников скачать приложение).

#### 3.2.2. Загрузка контента (Uploader)
- Drag-n-Drop интерфейс для загрузки папок с фото/видео.
- Поддержка мультизагрузки (1000+ файлов за раз).
- Отображение прогресса загрузки и статуса обработки (Processing / Done).

#### 3.2.3. Аналитика
- **Дашборд:**
  - Всего фото загружено.
  - Количество уникальных лиц найдено.
  - Сколько пользователей нашли себя (Match rate).

### 3.3. Backend и AI (Логика работы)
#### 3.3.1. Пайплайн обработки фото (Worker)
1. Получение задачи из очереди (путь к файлу в R2).
2. Загрузка изображения в память.
3. **Детекция:** Обнаружение всех лиц на фото (Bounding Boxes).
4. **Векторизация:** Генерация эмбеддинга (512 float) для каждого лица.
5. **Quality Check:** Отсеивание слишком размытых или мелких лиц (порог качества настраиваемый).
6. **Сохранение:** Запись метаданных и векторов в таблицу `detected_faces`.

#### 3.3.2. Алгоритм поиска (Matching)
- Использование оператора `<=>` (cosine distance) из `pgvector`.
- Поиск должен занимать не более 2 секунд при базе до 1 млн векторов.

---

## 4. Структура Базы Данных (Схема)

Исполнитель обязан реализовать схему БД с использованием UUID для идентификаторов.

### Подготовка БД
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Таблицы

#### 1. Пользователи и Организаторы (`users`)
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'user', -- 'user', 'organizer', 'admin'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. Биометрия пользователя (`user_biometrics`)
```sql
CREATE TABLE user_biometrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- Цифровой слепок лица (модель InsightFace)
    embedding vector(512), 
    
    -- Ссылка на исходное селфи в Cloudflare R2
    source_image_path VARCHAR(255), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### 3. Мероприятия (`events`)
```sql
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizer_id UUID REFERENCES users(id),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    event_date DATE,
    location VARCHAR(200),
    cover_image_path VARCHAR(255),
    status VARCHAR(20) DEFAULT 'draft', -- 'draft', 'published', 'archived'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### 4. Медиафайлы (`media_items`)
```sql
CREATE TABLE media_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES events(id) ON DELETE CASCADE,
    original_path VARCHAR(255) NOT NULL,
    thumbnail_path VARCHAR(255),
    media_type VARCHAR(10) DEFAULT 'image', -- 'image' или 'video'
    ai_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processed', 'failed'
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### 5. Найденные лица (`detected_faces`)
```sql
CREATE TABLE detected_faces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    media_item_id UUID REFERENCES media_items(id) ON DELETE CASCADE,
    embedding vector(512),
    bounding_box JSONB, -- {"x": 100, "y": 200, "w": 50, "h": 60}
    confidence FLOAT
);

-- Индекс для молниеносного поиска (IVFFlat)
CREATE INDEX ON detected_faces USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

---

## 5. Логика работы поиска ("Под капотом")

При запросе ленты "Мои моменты" бэкенд выполняет поиск совпадений по вектору лица:

```sql
SELECT 
    media_items.original_path, 
    media_items.thumbnail_path,
    events.title
FROM detected_faces
JOIN media_items ON detected_faces.media_item_id = media_items.id
JOIN events ON media_items.event_id = events.id
JOIN user_biometrics ON user_biometrics.user_id = :current_user_id
WHERE 
    -- Оператор <=> считает косинусное расстояние
    -- 0.4 — порог схожести (калибруется)
    detected_faces.embedding <=> user_biometrics.embedding < 0.4
ORDER BY 
    detected_faces.embedding <=> user_biometrics.embedding ASC
LIMIT 100;
```

---

## 6. Требования к безопасности
- **Биометрия:** Запрещено хранить исходные фото лиц пользователей в открытом виде. Хранить только векторные представления (числовые массивы).
- **API Security:** Все запросы должны быть подписаны JWT токеном.
- **Доступ к файлам:** Прямые ссылки на S3/R2 запрещены. Использовать Presigned URLs со временем жизни (TTL) 15-60 минут. В базе хранить только относительные пути.

---

## 7. Нефункциональные требования
- **Производительность:** Система должна обрабатывать 1 фотографию (детекция + векторизация) не дольше 1-2 секунд на GPU (T4/Tesla) или 3-5 секунд на быстром CPU.
- **Масштабируемость:** Архитектура должна позволять запуск нескольких AI-воркеров параллельно.
- **Отказоустойчивость:** При ошибке обработки одного фото (битый файл) весь процесс загрузки не должен останавливаться.

---

## 8. Рекомендации для разработчиков
- **Вектор (512):** Обязательно согласовать размерность вектора в базе и в модели InsightFace. Несовпадение вызовет ошибку БД.
- **Порог (Threshold):** Значение `0.4` — ориентировочное. Требуется калибровка на реальных данных для минимизации False Positives/Negatives.
- **Cloudflare R2:** Используйте Presigned URLs для выдачи контента клиентам. Никогда не делайте бакет публичным.

---

## 9. Этапы сдачи работ (Milestones)

### Этап 1: Прототип (Backend + AI)
- Развернут сервер FastAPI + Postgres.
- Реализован скрипт загрузки фото и векторизации.
- Работает поиск "похожих" через API (Swagger).

### Этап 2: MVP (Web + Mobile базовый)
- Готов веб-кабинет: можно создать ивент и залить фото.
- Готово моб. приложение: можно сделать селфи и увидеть ленту.
- Интеграция с Cloudflare R2.

### Этап 3: Релиз
- Полировка UI/UX.
- Тестирование нагрузки (10 000 фото).
- Публикация в App Store / Google Play.
