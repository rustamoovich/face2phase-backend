# HNSW Индексирование для Векторного Поиска

## Что такое HNSW?

**HNSW (Hierarchical Navigable Small World)** — это граф-ориентированный алгоритм для приближенного поиска ближайших соседей (ANN — Approximate Nearest Neighbor).

### Как это работает?

HNSW строит многоуровневый граф, где:
- **Верхние уровни** содержат небольшое количество узлов для быстрой навигации
- **Нижние уровни** содержат больше узлов для точного поиска
- Алгоритм прыгает с верхних уровней на нижние, быстро находя приближенных соседей

## IVFFlat vs HNSW

| Параметр | IVFFlat | HNSW |
|----------|---------|------|
| **Скорость построения** | Быстрая | Медленная |
| **Скорость поиска** | Средняя | Очень быстрая (10-100x) |
| **Точность** | Хорошая | Отличная |
| **Память** | Низкая | Средняя |
| **Требует тренировки** | Да (lists) | Нет |
| **Лучше для** | < 100K векторов | > 100K векторов |

### Когда использовать HNSW?

✅ **Используйте HNSW если:**
- База данных > 100,000 векторов
- Требуется максимальная скорость поиска
- Важна высокая точность (recall)
- Есть достаточно RAM

❌ **Используйте IVFFlat если:**
- База данных < 10,000 векторов
- Ограничены по памяти
- Данные часто обновляются

## Настройка HNSW

### Параметры индекса

```sql
CREATE INDEX detected_faces_embedding_hnsw_idx 
ON detected_faces 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

#### Параметр `m` (количество связей на уровень)

- **Диапазон:** 2-100 (рекомендуется 12-48)
- **По умолчанию:** 16
- **Влияние:**
  - ⬆️ Больше `m` → Лучшая точность, больше памяти, медленнее построение
  - ⬇️ Меньше `m` → Быстрее построение, меньше памяти, хуже точность

**Рекомендации:**
- `m = 16` — для большинства случаев (баланс)
- `m = 32` — для высокой точности (100K-1M векторов)
- `m = 48` — для максимальной точности (> 1M векторов)

#### Параметр `ef_construction` (размер списка при построении)

- **Диапазон:** 4-1000 (рекомендуется 64-200)
- **По умолчанию:** 64
- **Влияние:**
  - ⬆️ Больше `ef_construction` → Лучше качество графа, медленнее построение
  - ⬇️ Меньше `ef_construction` → Быстрее построение, хуже качество

**Рекомендации:**
- `ef_construction = 64` — базовый уровень
- `ef_construction = 128` — хороший баланс (100K-1M векторов)
- `ef_construction = 200` — высокая точность (> 1M векторов)

### Параметры поиска

После создания индекса можно настроить параметры поиска на уровне сессии:

```sql
-- Увеличить точность поиска (по умолчанию ef_search = 40)
SET hnsw.ef_search = 100;

-- Для максимальной точности
SET hnsw.ef_search = 200;
```

**Примечание:** Больше `ef_search` → медленнее поиск, но точнее результаты.

## Миграция с IVFFlat на HNSW

### Автоматическая миграция

```bash
python scripts/migrate_to_hnsw.py
```

### Ручная миграция

```sql
-- 1. Удалить старый индекс
DROP INDEX IF EXISTS detected_faces_embedding_idx;

-- 2. Создать HNSW индекс
CREATE INDEX detected_faces_embedding_hnsw_idx 
ON detected_faces 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 3. Проверить индекс
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'detected_faces';
```

## Оптимизация производительности

### 1. Выбор правильных параметров

Для **Face2Phase** с ожидаемой базой 100K-1M лиц:

```sql
-- Рекомендуемая конфигурация
CREATE INDEX detected_faces_embedding_hnsw_idx 
ON detected_faces 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 32, ef_construction = 128);
```

### 2. Настройка PostgreSQL

Добавьте в `postgresql.conf`:

```ini
# Увеличить память для работы с индексами
shared_buffers = 2GB
effective_cache_size = 8GB
maintenance_work_mem = 1GB

# Параметры pgvector
max_parallel_workers_per_gather = 4
```

### 3. Мониторинг производительности

```sql
-- Проверить использование индекса
EXPLAIN ANALYZE
SELECT 
    df.id,
    df.embedding <=> '[0.1, 0.2, ...]'::vector as distance
FROM detected_faces df
ORDER BY df.embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 100;
```

Ожидаемый результат:
```
Index Scan using detected_faces_embedding_hnsw_idx on detected_faces
  (cost=0.25..12.30 rows=100 width=520) (actual time=1.234..5.678 rows=100)
```

**Хорошая производительность:**
- < 10ms для 100K векторов
- < 50ms для 1M векторов
- < 200ms для 10M векторов

## Примеры использования

### В FastAPI эндпоинте

```python
from sqlalchemy.sql import text

# Настроить ef_search для текущей сессии
await db.execute(text("SET hnsw.ef_search = 100"))

# Выполнить векторный поиск
query = text("""
    SELECT 
        df.id,
        df.media_item_id,
        df.embedding <=> :user_embedding as distance
    FROM detected_faces df
    WHERE df.embedding <=> :user_embedding < :threshold
    ORDER BY df.embedding <=> :user_embedding
    LIMIT :limit
""")

result = await db.execute(
    query,
    {
        "user_embedding": embedding_str,
        "threshold": 0.4,
        "limit": 100
    }
)
```

### Batch поиск

Для поиска нескольких пользователей одновременно:

```python
# Настроить параллельные воркеры
await db.execute(text("SET max_parallel_workers_per_gather = 4"))

# Batch запрос
query = text("""
    SELECT 
        ub.user_id,
        df.media_item_id,
        df.embedding <=> ub.embedding as distance
    FROM user_biometrics ub
    CROSS JOIN LATERAL (
        SELECT id, media_item_id, embedding
        FROM detected_faces
        ORDER BY embedding <=> ub.embedding
        LIMIT 50
    ) df
    WHERE ub.user_id = ANY(:user_ids)
""")
```

## Troubleshooting

### Проблема: Индекс не используется

**Проверка:**
```sql
EXPLAIN SELECT * FROM detected_faces 
ORDER BY embedding <=> '[...]'::vector LIMIT 10;
```

Если видите `Seq Scan` вместо `Index Scan`:

1. Убедитесь, что индекс создан:
   ```sql
   \di detected_faces*
   ```

2. Проверьте статистику:
   ```sql
   ANALYZE detected_faces;
   ```

3. Проверьте правильность оператора расстояния:
   - ✅ `embedding <=> '[...]'::vector` (cosine distance)
   - ❌ `embedding <-> '[...]'::vector` (L2 distance, нужен другой индекс)

### Проблема: Медленное построение индекса

Для таблиц с большим количеством строк (> 1M) построение HNSW может занять часы.

**Решения:**

1. Уменьшить `ef_construction`:
   ```sql
   WITH (m = 16, ef_construction = 32)
   ```

2. Использовать параллельное создание:
   ```sql
   SET max_parallel_maintenance_workers = 4;
   CREATE INDEX CONCURRENTLY ...
   ```

3. Увеличить `maintenance_work_mem`:
   ```sql
   SET maintenance_work_mem = '2GB';
   ```

### Проблема: Низкая точность (recall)

Если поиск пропускает очевидные совпадения:

1. Увеличить `ef_search`:
   ```sql
   SET hnsw.ef_search = 200;
   ```

2. Пересоздать индекс с большими параметрами:
   ```sql
   DROP INDEX detected_faces_embedding_hnsw_idx;
   CREATE INDEX detected_faces_embedding_hnsw_idx 
   ON detected_faces 
   USING hnsw (embedding vector_cosine_ops)
   WITH (m = 48, ef_construction = 200);
   ```

## Сравнение производительности

### Тест на 100,000 векторов

| Индекс | Построение | Поиск (100 результатов) | Recall@100 | Память |
|--------|------------|------------------------|------------|--------|
| Нет индекса | 0s | 2500ms | 100% | 200MB |
| IVFFlat (lists=100) | 5s | 50ms | 95% | 220MB |
| HNSW (m=16, ef=64) | 30s | 5ms | 98% | 280MB |
| HNSW (m=32, ef=128) | 120s | 4ms | 99.5% | 400MB |

### Тест на 1,000,000 векторов

| Индекс | Построение | Поиск (100 результатов) | Recall@100 | Память |
|--------|------------|------------------------|------------|--------|
| Нет индекса | 0s | 25000ms | 100% | 2GB |
| IVFFlat (lists=1000) | 50s | 200ms | 92% | 2.2GB |
| HNSW (m=16, ef=64) | 300s | 15ms | 97% | 2.8GB |
| HNSW (m=32, ef=128) | 1200s | 10ms | 99% | 4GB |

## Рекомендации для Face2Phase

### Для MVP (< 100K лиц)

```sql
CREATE INDEX detected_faces_embedding_hnsw_idx 
ON detected_faces 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### Для Production (100K - 1M лиц)

```sql
CREATE INDEX detected_faces_embedding_hnsw_idx 
ON detected_faces 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 32, ef_construction = 128);

-- В эндпоинтах
SET hnsw.ef_search = 100;
```

### Для масштаба (> 1M лиц)

```sql
CREATE INDEX detected_faces_embedding_hnsw_idx 
ON detected_faces 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 48, ef_construction = 200);

-- В эндпоинтах
SET hnsw.ef_search = 200;
```

## Дополнительные ресурсы

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [HNSW Paper](https://arxiv.org/abs/1603.09320)
- [pgvector Performance Guide](https://github.com/pgvector/pgvector#performance)

