"""
Servicio de Cloudinary para almacenamiento de PDFs
"""
import cloudinary
import cloudinary.uploader
from pathlib import Path
from typing import Optional
import os

from config import (
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    USE_CLOUDINARY
)


def configure_cloudinary():
    """Configura las credenciales de Cloudinary"""
    if not USE_CLOUDINARY:
        return False
    
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )
    return True


def upload_pdf_to_cloudinary(file_path: Path, public_id: Optional[str] = None) -> Optional[str]:
    """
    Sube un PDF a Cloudinary y retorna la URL de descarga.
    
    Args:
        file_path: Ruta local del archivo PDF
        public_id: ID público opcional para el archivo en Cloudinary
    
    Returns:
        URL del PDF en Cloudinary, o None si falla
    """
    if not configure_cloudinary():
        print("⚠ Cloudinary no configurado, usando almacenamiento local")
        return None
    
    try:
        # Usar el nombre del archivo sin extensión como public_id si no se proporciona
        if public_id is None:
            public_id = file_path.stem
        else:
            # Remover el prefijo de carpeta si existe (lo manejaremos con folder)
            public_id = public_id.split("/")[-1] if "/" in public_id else public_id
        
        # Subir como RAW para mantener el PDF intacto
        result = cloudinary.uploader.upload(
            str(file_path),
            public_id=public_id,
            folder="contratos_fuec",    # Carpeta dedicada para contratos
            resource_type="raw",        # RAW para archivos que no son imágenes/videos
            overwrite=True,
            invalidate=True
        )
        
        url = result.get("secure_url")
        print(f"✓ PDF subido a Cloudinary: {url}")
        return url
        
    except Exception as e:
        print(f"⚠ Error subiendo PDF a Cloudinary: {e}")
        return None


def delete_pdf_from_cloudinary(public_id: str) -> bool:
    """
    Elimina un archivo de Cloudinary (PDF o imagen).
    
    Args:
        public_id: ID público del archivo en Cloudinary
    """
    if not configure_cloudinary():
        return False
    
    try:
        # Intentar borrar como raw (PDF)
        result = cloudinary.uploader.destroy(public_id, resource_type="raw")
        if result.get("result") == "ok":
            return True
            
        # Si falla, intentar borrar como imagen
        result = cloudinary.uploader.destroy(public_id, resource_type="image")
        return result.get("result") == "ok"
    except Exception as e:
        print(f"⚠ Error eliminando archivo de Cloudinary: {e}")
        return False


def upload_image_to_cloudinary(file_obj, folder: str = "fotos_usuarios", public_id: Optional[str] = None) -> Optional[str]:
    """
    Sube una imagen a Cloudinary (desde UploadFile.file, bytes o path).
    
    Args:
        file_obj: Objeto file-like, bytes o path string
        folder: Carpeta destino en Cloudinary
        public_id: ID público opcional
        
    Returns:
        URL segura de la imagen o None si falla
    """
    if not configure_cloudinary():
        print("⚠ Cloudinary no configurado")
        return None
        
    try:
        # Configuración de subida
        upload_options = {
            "folder": folder,
            "resource_type": "image",
            "format": "jpg",           # Convertir a JPG para estandarizar
            "quality": "auto",         # Optimización automática
            "fetch_format": "auto",    # WebP/AVIF si el navegador soporta
            "overwrite": True
        }
        
        if public_id:
            upload_options["public_id"] = public_id

        # Subir archivo
        result = cloudinary.uploader.upload(file_obj, **upload_options)
        
        url = result.get("secure_url")
        print(f"✓ Imagen subida a Cloudinary: {url}")
        return url
        
    except Exception as e:
        print(f"⚠ Error subiendo imagen a Cloudinary: {e}")
        return None


def delete_image_from_cloudinary(public_id: str) -> bool:
    """
    Elimina una imagen de Cloudinary.
    
    Args:
        public_id: ID público de la imagen en Cloudinary
    
    Returns:
        True si se eliminó correctamente, False si falló
    """
    if not configure_cloudinary():
        return False
    
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type="image")
        return result.get("result") == "ok"
    except Exception as e:
        print(f"⚠ Error eliminando imagen de Cloudinary: {e}")
        return False
