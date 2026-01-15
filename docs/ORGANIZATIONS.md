# 🏢 Organizations & Photographer Management

**Version:** 2.0  
**Date:** 15.01.2026

---

## 📋 Overview

Face2Phase теперь поддерживает **организации** (компании/сообщества) с системой управления фотографами.

### Roles

| Роль | Описание | Права |
|------|----------|-------|
| **user** | Обычный участник | Ищет свои фото через биометрию |
| **photographer** | Фотограф | Загружает медиа в assigned события |
| **organizer** | Администратор организации | Создает события, управляет фотографами |
| **admin** | Суперадмин платформы | Полный доступ |

---

## 🏗️ Architecture

```
Organization (компания/сообщество)
├── Organizers (администраторы)
├── Photographers (фотографы)
└── Events (мероприятия)
    ├── Media (фото/видео/PDF)
    └── Photographer Access (права доступа)
```

**Логика:**
1. Admin создает Organization
2. Admin создает первого organizer для организации (через `/organizations/{id}/users`)
3. Organizer создает Event
4. Organizer создает photographers внутри организации (через `/organizations/{id}/users`)
5. Organizer предоставляет доступ photographers к событию
6. Photographer загружает медиа в события, к которым у него есть доступ

**Важно:**
- Обычные пользователи (role=user) регистрируются через `/auth/register` (без организации)
- Organizer и photographer создаются организацией через `/organizations/{id}/users`
- Организация сама управляет своими пользователями

---

## 🚀 Quick Start

### 1. Миграция БД

```bash
python scripts/migrate_organizations.py
```

### 2. Создание организации (Admin)

```http
POST /organizations
{
  "name": "PhotoStudio Pro",
  "slug": "photostudio-pro",
  "description": "Professional event photography",
  "website": "https://photostudio.com",
  "contact_email": "info@photostudio.com"
}
```

### 3. Создание organizer (Admin)

```http
POST /organizations/{organization_id}/users
Authorization: Bearer {admin_token}
{
  "email": "organizer@photostudio.com",
  "password": "secure_password",
  "full_name": "John Organizer",
  "role": "organizer"
}
```

### 4. Создание photographer (Organizer)

```http
POST /organizations/{organization_id}/users
Authorization: Bearer {organizer_token}
{
  "email": "photographer@photostudio.com",
  "password": "secure_password",
  "full_name": "Jane Photographer",
  "role": "photographer"
}
```

> **Примечание:** `organization_id` автоматически устанавливается из URL, не нужно указывать в body.

### 5. Создание события (Organizer)

```http
POST /events
{
  "organization_id": "org-uuid-here",
  "title": "Corporate Conference 2026",
  "description": "Annual tech conference",
  "event_date": "2026-03-15",
  "location": "Convention Center",
  "status": "draft"
}
```

### 6. Предоставление доступа фотографу (Organizer)

```http
POST /events/{event_id}/photographers
{
  "photographer_id": "photographer-uuid-here"
}
```

### 7. Загрузка медиа (Photographer)

```http
POST /events/{event_id}/upload
Content-Type: multipart/form-data

files: [photo1.jpg, photo2.jpg, ...]
```

---

## 📡 API Endpoints

### Organizations

```http
POST   /organizations                      # Create (admin only)
GET    /organizations                      # List all
GET    /organizations/{id}                 # Get details
PATCH  /organizations/{id}                 # Update
POST   /organizations/{id}/logo            # Upload logo
DELETE /organizations/{id}                 # Deactivate (admin only)
POST   /organizations/{id}/users           # Create user (organizer/photographer)
GET    /organizations/{id}/users           # List organization users
PATCH  /organizations/{id}/users/{user_id}/role  # Change user role
```

### Photographer Access

```http
POST   /events/{event_id}/photographers                      # Grant access
GET    /events/{event_id}/photographers                      # List photographers
DELETE /events/{event_id}/photographers/{photographer_id}   # Revoke access
GET    /events/my-events                                     # Get accessible events (photographer)
```

### Event Assets

```http
POST /events/{event_id}/assets/cover    # Upload cover image
POST /events/{event_id}/assets/map      # Upload location map
```

---

## 🔒 Permissions Matrix

| Action | User | Photographer | Organizer | Admin |
|--------|------|--------------|-----------|-------|
| View published events | ✅ | ✅ | ✅ | ✅ |
| View org events | ❌ | ❌ | ✅ (own org) | ✅ |
| Create event | ❌ | ❌ | ✅ (own org) | ✅ |
| Update event | ❌ | ❌ | ✅ (own org) | ✅ |
| Upload media | ❌ | ✅ (assigned) | ✅ (own org) | ✅ |
| Grant photographer access | ❌ | ❌ | ✅ (own org) | ✅ |
| Create organization | ❌ | ❌ | ❌ | ✅ |

---

## 💾 Database Schema

### organizations

```sql
id UUID PRIMARY KEY
name VARCHAR(200) UNIQUE NOT NULL
slug VARCHAR(200) UNIQUE NOT NULL
description TEXT
logo_path VARCHAR(255)
website VARCHAR(255)
contact_email VARCHAR(255)
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP
```

### users (updated)

```sql
-- New fields:
organization_id UUID REFERENCES organizations(id)
role VARCHAR(20)  -- user/photographer/organizer/admin
```

### events (updated)

```sql
-- New fields:
organization_id UUID REFERENCES organizations(id) NOT NULL
map_image_path VARCHAR(255)
partners_data JSONB
```

### event_access (new)

```sql
id UUID PRIMARY KEY
event_id UUID REFERENCES events(id) ON DELETE CASCADE
photographer_id UUID REFERENCES users(id) ON DELETE CASCADE
granted_by UUID REFERENCES users(id)
granted_at TIMESTAMP
UNIQUE(event_id, photographer_id)
```

---

## 📦 R2 Storage Structure

```
face2phase-bucket/
├── organizations/
│   └── {organization_id}/
│       └── logo.{ext}
│
└── events/
    └── {event_id}/
        ├── assets/
        │   ├── cover.{ext}
        │   └── map.{ext}
        ├── photos/...
        ├── videos/...
        └── documents/...
```

---

## 👥 User Management

### Создание пользователей

**Обычные пользователи (user):**
```http
POST /auth/register
{
  "email": "user@example.com",
  "password": "password",
  "full_name": "John User"
}
```
- Роль автоматически `user`
- Без привязки к организации
- Могут искать свои фото через биометрию
- **Простая регистрация** - только email, password, full_name
- ⚠️ Поля `role` и `organization_id` игнорируются, если указаны

**Organizer/Photographer:**
```http
POST /organizations/{organization_id}/users
Authorization: Bearer {organizer_token}
{
  "email": "photographer@org.com",
  "password": "password",
  "full_name": "Jane Photographer",
  "role": "photographer"  # или "organizer"
}
```
- Создается внутри организации
- Автоматически привязывается к `organization_id`
- Только organizer этой организации или admin может создавать

### Управление ролями

```http
PATCH /organizations/{organization_id}/users/{user_id}/role?new_role=organizer
```
- Можно менять между `organizer` и `photographer`
- Нельзя изменить на `user` или `admin` (только через БД)

### Список пользователей организации

```http
GET /organizations/{organization_id}/users?role=photographer
```
- Фильтр по роли (optional)
- Только organizer или admin

---

## 🔄 Migration from Old System

Если у вас есть existing events без organization_id:

```python
# 1. Создайте default организацию
POST /organizations
{
  "name": "Default Organization",
  "slug": "default-org"
}

# 2. Обновите existing events вручную через SQL
UPDATE events 
SET organization_id = 'default-org-uuid'
WHERE organization_id IS NULL;

# 3. Обновите existing organizers
UPDATE users 
SET organization_id = 'default-org-uuid'
WHERE role = 'organizer';
```

---

## 📊 Example Workflow

### Сценарий: Wedding Photography Company

1. **Admin создает организацию** "Royal Weddings"
2. **Admin назначает organizer** (владелец компании)
3. **Organizer создает событие** "Anna & Bob Wedding"
4. **Organizer добавляет 3 фотографов** к событию
5. **Фотографы загружают фото** во время свадьбы
6. **Гости ищут свои фото** через селфи
7. **Organizer публикует событие** (status: published)
8. **Все фото доступны** гостям через "Мои моменты"

---

## 🐛 Troubleshooting

### Photographer can't upload media

**Проблема:** 403 Forbidden при загрузке

**Решение:**
1. Проверьте, что photographer назначен к организации
2. Убедитесь, что organizer предоставил доступ к событию
3. Проверьте доступные события: `GET /events/my-events`

### Event creation fails

**Проблема:** Organization not found

**Решение:**
1. Убедитесь, что организация существует и активна
2. Organizer должен принадлежать к этой организации
3. Проверьте `organization_id` в запросе

---

## 📚 Related Docs

- [README.md](../README.md) - General documentation
- [docs/PROJECT_STATUS.md](./PROJECT_STATUS.md) - Project status
- [docs/CLOUDFLARE_R2_SETUP.md](./CLOUDFLARE_R2_SETUP.md) - Storage setup
