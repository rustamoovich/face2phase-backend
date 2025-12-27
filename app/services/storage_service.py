"""
Сервис для работы с облачным хранилищем Cloudflare R2.

Cloudflare R2 - это S3-совместимое объектное хранилище с нулевой стоимостью исходящего трафика.
"""

import uuid
from pathlib import Path
from typing import BinaryIO, Optional
import aioboto3
from botocore.exceptions import ClientError

from app.database import settings


class StorageService:
    """
    Сервис для работы с Cloudflare R2 через S3-совместимый API.
    
    Использует aioboto3 для асинхронных операций.
    """
    
    def __init__(self):
        self.session = aioboto3.Session()
        self.endpoint_url = settings.R2_ENDPOINT_URL
        self.access_key_id = settings.R2_ACCESS_KEY_ID
        self.secret_access_key = settings.R2_SECRET_ACCESS_KEY
        self.bucket_name = settings.R2_BUCKET_NAME
        self.public_url = settings.R2_PUBLIC_URL
    
    async def upload_file(
        self, 
        file_data: bytes, 
        file_key: str, 
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Загрузить файл в R2.
        
        Args:
            file_data: Бинарные данные файла
            file_key: Ключ (путь) файла в bucket, например "events/123/photo.jpg"
            content_type: MIME-тип файла
        
        Returns:
            Ключ загруженного файла (file_key)
        
        Raises:
            Exception: Если загрузка не удалась
        """
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto"  # R2 использует "auto"
        ) as s3_client:
            try:
                await s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=file_key,
                    Body=file_data,
                    ContentType=content_type
                )
                return file_key
            except ClientError as e:
                raise Exception(f"Failed to upload file to R2: {str(e)}")
    
    async def delete_file(self, file_key: str) -> None:
        """
        Удалить файл из R2.
        
        Args:
            file_key: Ключ файла в bucket
        
        Raises:
            Exception: Если удаление не удалось
        """
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto"
        ) as s3_client:
            try:
                await s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_key
                )
            except ClientError as e:
                raise Exception(f"Failed to delete file from R2: {str(e)}")
    
    def get_public_url(self, file_key: str) -> str:
        """
        Получить публичный URL файла.
        
        Args:
            file_key: Ключ файла в bucket
        
        Returns:
            Публичный URL файла
        """
        if self.public_url:
            return f"{self.public_url}/{file_key}"
        return f"{self.endpoint_url}/{self.bucket_name}/{file_key}"
    
    async def file_exists(self, file_key: str) -> bool:
        """
        Проверить, существует ли файл в R2.
        
        Args:
            file_key: Ключ файла в bucket
        
        Returns:
            True если файл существует, False иначе
        """
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto"
        ) as s3_client:
            try:
                await s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=file_key
                )
                return True
            except ClientError:
                return False


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """
    Получить синглтон StorageService.
    
    Returns:
        Экземпляр StorageService
    """
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service

