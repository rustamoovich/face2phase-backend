"""
Тестовый скрипт для проверки работы InsightFace.
"""

import sys
from pathlib import Path

print("🔍 Проверка установки InsightFace...")

try:
    import insightface
    print(f"✅ InsightFace импортирован успешно")
    print(f"   Версия: {insightface.__version__ if hasattr(insightface, '__version__') else 'unknown'}")
except ImportError as e:
    print(f"❌ Ошибка импорта InsightFace: {e}")
    sys.exit(1)

try:
    from insightface.app import FaceAnalysis
    print("✅ FaceAnalysis импортирован успешно")
except ImportError as e:
    print(f"❌ Ошибка импорта FaceAnalysis: {e}")
    sys.exit(1)

try:
    import cv2
    print(f"✅ OpenCV импортирован успешно (версия: {cv2.__version__})")
except ImportError as e:
    print(f"❌ Ошибка импорта OpenCV: {e}")
    sys.exit(1)

try:
    import onnxruntime
    print(f"✅ ONNX Runtime импортирован успешно")
except ImportError as e:
    print(f"❌ Ошибка импорта ONNX Runtime: {e}")
    sys.exit(1)

print("\n🧪 Попытка инициализации FaceAnalysis...")
try:
    app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
    print("✅ FaceAnalysis инициализирован успешно")
    print("   ⚠️  Первый запуск может занять время (скачивание модели ~500MB)")
except Exception as e:
    print(f"❌ Ошибка инициализации: {e}")
    print("   Это нормально при первом запуске - модель скачается автоматически")
    sys.exit(1)

print("\n✅ Все проверки пройдены! InsightFace готов к работе.")
print("\n💡 Следующий шаг: Запустите сервер и попробуйте загрузить фото с лицами.")

