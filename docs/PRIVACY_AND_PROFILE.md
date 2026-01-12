# Управление Профилем и Приватностью

Документация по управлению пользовательским профилем и биометрическими данными в Face2Phase.

---

## 📋 Содержание

- [Управление биометрией](#управление-биометрией)
- [Управление приватностью](#управление-приватностью)
- [Безопасность данных](#безопасность-данных)
- [GDPR Compliance](#gdpr-compliance)

---

## Управление биометрией

### GET /auth/biometrics

Получить информацию о текущей биометрии.

**Авторизация:** Требуется JWT токен

**Ответ:**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "has_biometrics": true,
  "source_image_path": "biometrics/user-id.jpg",
  "created_at": "2025-01-12T10:30:00Z"
}
```

**Использование:**
```bash
curl -X GET "http://localhost:8000/auth/biometrics" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### POST /auth/biometrics

Первичная загрузка селфи для биометрической идентификации.

**Авторизация:** Требуется JWT токен

**Требования к фото:**
- ✅ Ровно одно лицо на фото
- ✅ Четкое изображение (confidence > 0.8)
- ✅ Хорошее освещение
- ✅ Формат: JPEG, PNG
- ✅ Размер: до 10 МБ

**Запрос:**
```bash
curl -X POST "http://localhost:8000/auth/biometrics" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@selfie.jpg"
```

**Ответ:**
```json
{
  "status": "success",
  "message": "Биометрия успешно сохранена в облаке",
  "confidence": 0.95
}
```

**Ошибки:**

| Код | Сообщение | Причина |
|-----|-----------|---------|
| 400 | Лицо не обнаружено | Плохое качество или нет лица на фото |
| 400 | Более одного человека | На фото несколько лиц |
| 409 | Биометрия уже существует | Используйте PUT для обновления |

---

### PUT /auth/biometrics

Обновить селфи (например, при изменении внешности).

**Авторизация:** Требуется JWT токен

**Когда использовать:**
- 🔄 Изменилась прическа
- 🔄 Появилась/исчезла борода
- 🔄 Изменился цвет волос
- 🔄 Значительные изменения внешности

**Запрос:**
```bash
curl -X PUT "http://localhost:8000/auth/biometrics" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@new_selfie.jpg"
```

**Ответ:**
```json
{
  "status": "success",
  "message": "Биометрия успешно обновлена",
  "confidence": 0.93
}
```

**Что происходит:**
1. Старое селфи в R2 перезаписывается
2. Эмбеддинг обновляется в базе данных
3. Поиск "Мои моменты" начнет использовать новый эмбеддинг

---

### DELETE /auth/biometrics

Удалить все биометрические данные (Hard Delete).

**Авторизация:** Требуется JWT токен

**⚠️ Внимание:** Это действие необратимо!

**Что удаляется:**
- ❌ 512-мерный эмбеддинг лица из PostgreSQL
- ❌ Исходное селфи из Cloudflare R2
- ✅ Аккаунт остается активным

**Запрос:**
```bash
curl -X DELETE "http://localhost:8000/auth/biometrics" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Ответ:**
```json
{
  "status": "success",
  "message": "Все биометрические данные удалены безвозвратно",
  "deleted_biometrics": true,
  "deleted_image_from_storage": true
}
```

**После удаления:**
- ❌ "Мои моменты" перестанут работать (404 ошибка)
- ✅ Можно заново загрузить селфи через POST /auth/biometrics
- ✅ Аккаунт и все остальные данные сохранены

---

## Управление приватностью

### DELETE /auth/profile

Полное удаление профиля и всех данных (Hard Delete).

**Авторизация:** Требуется JWT токен

**⚠️⚠️⚠️ КРИТИЧЕСКОЕ ВНИМАНИЕ ⚠️⚠️⚠️**

Это действие **НЕОБРАТИМО** и удаляет **ВСЕ** ваши данные!

**Что удаляется:**

| Данные | Описание |
|--------|----------|
| 👤 Аккаунт | Email, пароль, профиль |
| 🧬 Биометрия | Эмбеддинги и селфи |
| 🎉 Мероприятия | Все созданные события (если организатор) |
| 📸 Медиафайлы | Фото/видео из R2 и метаданные |
| 👁️ Найденные лица | Детекции лиц на медиафайлах |

**Запрос:**
```bash
curl -X DELETE "http://localhost:8000/auth/profile" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Ответ:**
```json
{
  "status": "success",
  "message": "Профиль и все связанные данные удалены безвозвратно",
  "deleted_user_id": "uuid",
  "deleted_biometrics": true,
  "deleted_events_count": 5,
  "deleted_media_count": 150
}
```

**После удаления:**
- ❌ Невозможно войти в систему (JWT токен недействителен)
- ❌ Все файлы удалены из Cloudflare R2
- ❌ Все записи удалены из базы данных (CASCADE)
- ❌ Восстановление невозможно

---

## Безопасность данных

### Что мы храним

#### В PostgreSQL:
```sql
-- Таблица user_biometrics
{
  "id": "uuid",
  "user_id": "uuid (FK)",
  "embedding": "vector(512)",  -- 512 чисел float
  "source_image_path": "string",  -- Ключ в R2
  "created_at": "timestamp"
}
```

**Важно:**
- ✅ Эмбеддинг - это не изображение, а числовой вектор
- ✅ Невозможно восстановить лицо из эмбеддинга
- ✅ Эмбеддинг используется только для сравнения похожести

#### В Cloudflare R2:
```
biometrics/
  └── {user_id}.jpg  -- Исходное селфи
```

**Важно:**
- ✅ Файлы не публичные (требуется авторизация)
- ✅ Используются Presigned URLs (TTL = 15-60 минут)
- ✅ Шифрование на стороне R2 (AES-256)

### Что мы НЕ храним

- ❌ Исходные фотографии лиц пользователей с мероприятий
- ❌ История поиска "Мои моменты"
- ❌ IP-адреса и геолокацию
- ❌ Данные об устройствах

---

## GDPR Compliance

Face2Phase полностью соответствует требованиям GDPR (EU) и CCPA (California).

### Право на доступ (Right to Access)

**GET /auth/biometrics** - Получить свои биометрические данные

```bash
curl -X GET "http://localhost:8000/auth/biometrics" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Право на исправление (Right to Rectification)

**PUT /auth/biometrics** - Обновить селфи

```bash
curl -X PUT "http://localhost:8000/auth/biometrics" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@new_selfie.jpg"
```

### Право на удаление (Right to Erasure / "Right to be Forgotten")

**DELETE /auth/biometrics** - Удалить биометрию

```bash
curl -X DELETE "http://localhost:8000/auth/biometrics" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**DELETE /auth/profile** - Удалить весь профиль

```bash
curl -X DELETE "http://localhost:8000/auth/profile" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Право на переносимость (Right to Data Portability)

**GET /auth/me** - Экспорт данных профиля (JSON)

```bash
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Право на ограничение обработки (Right to Restriction)

Пользователь может удалить биометрию, но сохранить аккаунт:

```bash
# 1. Удалить биометрию
DELETE /auth/biometrics

# 2. Аккаунт остается активным
# 3. "Мои моменты" перестают работать
# 4. Можно восстановить позже через POST /auth/biometrics
```

---

## Рекомендации для фронтенда

### UI для управления биометрией

```jsx
// React пример
function BiometricsSettings() {
  const [hasBiometrics, setHasBiometrics] = useState(false);
  
  // Проверка наличия биометрии
  useEffect(() => {
    fetch('/auth/biometrics', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => res.ok ? setHasBiometrics(true) : setHasBiometrics(false))
    .catch(() => setHasBiometrics(false));
  }, []);
  
  // Обновление селфи
  const handleUpdate = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    
    await fetch('/auth/biometrics', {
      method: hasBiometrics ? 'PUT' : 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
  };
  
  // Удаление биометрии
  const handleDelete = async () => {
    if (confirm('⚠️ Удалить биометрию? Вы потеряете доступ к "Мои моменты"')) {
      await fetch('/auth/biometrics', {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      setHasBiometrics(false);
    }
  };
  
  return (
    <div>
      <h2>Биометрическая идентификация</h2>
      
      {hasBiometrics ? (
        <>
          <p>✅ Биометрия настроена</p>
          <button onClick={() => fileInput.click()}>
            🔄 Обновить селфи
          </button>
          <button onClick={handleDelete}>
            🗑️ Удалить биометрию
          </button>
        </>
      ) : (
        <>
          <p>❌ Биометрия не настроена</p>
          <button onClick={() => fileInput.click()}>
            📸 Загрузить селфи
          </button>
        </>
      )}
      
      <input
        type="file"
        ref={fileInput}
        accept="image/*"
        onChange={(e) => handleUpdate(e.target.files[0])}
        style={{ display: 'none' }}
      />
    </div>
  );
}
```

### Диалог удаления профиля

```jsx
function DeleteAccountDialog() {
  const [confirmText, setConfirmText] = useState('');
  
  const handleDeleteProfile = async () => {
    const response = await fetch('/auth/profile', {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (response.ok) {
      const data = await response.json();
      alert(`Удалено:
        - Биометрия: ${data.deleted_biometrics ? 'Да' : 'Нет'}
        - Мероприятий: ${data.deleted_events_count}
        - Медиафайлов: ${data.deleted_media_count}
      `);
      
      // Выход из системы
      localStorage.removeItem('token');
      window.location.href = '/';
    }
  };
  
  return (
    <Dialog>
      <h2>⚠️ Удалить профиль</h2>
      
      <p><strong>Это действие НЕОБРАТИМО!</strong></p>
      
      <ul>
        <li>❌ Аккаунт будет удален</li>
        <li>❌ Биометрия будет удалена</li>
        <li>❌ Мероприятия будут удалены</li>
        <li>❌ Медиафайлы будут удалены</li>
      </ul>
      
      <p>Введите <code>DELETE</code> для подтверждения:</p>
      <input
        value={confirmText}
        onChange={(e) => setConfirmText(e.target.value)}
        placeholder="DELETE"
      />
      
      <button
        onClick={handleDeleteProfile}
        disabled={confirmText !== 'DELETE'}
        style={{ backgroundColor: 'red' }}
      >
        Удалить профиль навсегда
      </button>
    </Dialog>
  );
}
```

---

## FAQ

### Q: Можно ли восстановить удаленную биометрию?

**A:** Нет. DELETE /auth/biometrics выполняет hard delete из БД и R2. Нужно заново загрузить селфи.

### Q: Что происходит с "Мои моменты" после удаления биометрии?

**A:** Эндпоинт GET /feed/my-moments вернет 404 ошибку. Найденные лица на фото остаются в БД, но поиск невозможен без эталонного эмбеддинга пользователя.

### Q: Можно ли удалить аккаунт, но сохранить мероприятия?

**A:** Нет. DELETE /auth/profile удаляет ВСЕ данные пользователя включая мероприятия (если он организатор). Это CASCADE delete на уровне БД.

### Q: Как часто нужно обновлять селфи?

**A:** Рекомендуем обновлять при значительных изменениях внешности (новая прическа, борода, очки). В остальных случаях InsightFace хорошо справляется с естественными изменениями.

### Q: Безопасно ли хранить селфи в R2?

**A:** Да. Файлы не публичные, используются Presigned URLs с TTL, применяется шифрование AES-256. Доступ только у владельца через JWT токен.

### Q: Соответствует ли Face2Phase GDPR?

**A:** Да. Реализованы все требуемые права: доступ, исправление, удаление, переносимость, ограничение обработки. Hard delete гарантирует полное удаление данных.

---

**Stop searching. Start sharing.** ✨
