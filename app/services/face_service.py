"""
Сервис распознавания лиц с использованием InsightFace.

Этот модуль предоставляет функциональность для детекции и векторизации лиц на изображениях.
"""

from typing import List, Optional
from pathlib import Path
import cv2
import numpy as np
from insightface.app import FaceAnalysis
from pydantic import BaseModel, Field, field_validator


class FaceDetectionResult(BaseModel):
    """
    Результат детекции одного лица на изображении.
    
    Attributes:
        embedding: Вектор лица (512 float значений). Используется для поиска похожих лиц.
        bbox: Координаты ограничивающего прямоугольника [x1, y1, x2, y2].
              x1, y1 - левый верхний угол, x2, y2 - правый нижний угол.
        confidence: Уверенность модели в том, что это лицо (0.0 - 1.0).
        landmarks: Координаты 5 ключевых точек лица [[x, y], [x, y], ...].
                   Порядок: левый глаз, правый глаз, нос, левый угол рта, правый угол рта.
    """
    embedding: List[float] = Field(..., description="Вектор лица (512 значений)")
    bbox: List[int] = Field(..., min_length=4, max_length=4, description="Координаты [x1, y1, x2, y2]")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность модели (0.0-1.0)")
    landmarks: List[List[int]] = Field(..., description="5 ключевых точек [[x,y], ...]")
    
    @field_validator('embedding')
    @classmethod
    def validate_embedding_size(cls, v: List[float]) -> List[float]:
        """Проверка размерности вектора (должно быть ровно 512 значений)."""
        if len(v) != 512:
            raise ValueError(f"Embedding должен содержать 512 значений, получено {len(v)}")
        return v
    
    @field_validator('landmarks')
    @classmethod
    def validate_landmarks_count(cls, v: List[List[int]]) -> List[List[int]]:
        """Проверка количества ключевых точек (должно быть ровно 5)."""
        if len(v) != 5:
            raise ValueError(f"Landmarks должен содержать 5 точек, получено {len(v)}")
        for point in v:
            if len(point) != 2:
                raise ValueError(f"Каждая точка должна содержать [x, y], получено {point}")
        return v


class FaceService:
    """
    Сервис для работы с распознаванием лиц.
    """
    
    def __init__(self):
        """
        Инициализирует FaceAnalysis с моделью buffalo_l.
        Использует CPU для вычислений.
        """
        self.app = FaceAnalysis(
            name='buffalo_l',
            providers=['CPUExecutionProvider']
        )
        self.app.prepare(ctx_id=0, det_size=(640, 640))
    
    def process_image(
        self, 
        file_path: str, 
        min_confidence: float = 0.6
    ) -> List[dict]:
        """
        Обрабатывает изображение и находит лица.
        
        Args:
            file_path: Путь к файлу изображения на диске.
            min_confidence: Минимальный порог уверенности для фильтрации лиц (по умолчанию 0.6).
        
        Returns:
            Список словарей, каждый из которых содержит информацию о найденном лице:
            - embedding: list[float] - Вектор лица (512 значений)
            - bbox: list[int] - Координаты [x1, y1, x2, y2]
            - confidence: float - Оценка уверенности (0.0 - 1.0)
            - landmarks: list[list[int]] - 5 ключевых точек [[x,y], [x,y]...]
        
        Raises:
            FileNotFoundError: Если файл не найден.
            ValueError: Если изображение не удалось прочитать.
        """
        # Проверка существования файла
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")
        
        # Чтение изображения
        img = cv2.imread(file_path)
        if img is None:
            raise ValueError(f"Failed to read image: {file_path}")
        
        # Детекция лиц
        faces = self.app.get(img)
        
        # Фильтрация и преобразование результатов
        results = []
        for face in faces:
            # Проверка порога уверенности
            confidence = float(face.det_score)
            if confidence < min_confidence:
                continue
            
            # Извлечение данных и преобразование numpy -> Python типы
            embedding = face.embedding.tolist()  # numpy array -> list
            bbox = face.bbox.astype(int).tolist()  # [x1, y1, x2, y2]
            landmarks = face.kps.astype(int).tolist()  # [[x, y], [x, y], ...]
            
            # Валидация через Pydantic
            face_result = FaceDetectionResult(
                embedding=embedding,
                bbox=bbox,
                confidence=confidence,
                landmarks=landmarks
            )
            
            results.append(face_result.model_dump())
        
        return results


# Singleton instance
_face_service: Optional[FaceService] = None

def get_face_service() -> FaceService:
    """
    Получить экземпляр FaceService (Singleton pattern).
    """
    global _face_service
    if _face_service is None:
        _face_service = FaceService()
    return _face_service


