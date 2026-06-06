"""
Utility functions untuk upload dan compress gambar
"""
import os
import io
from PIL import Image
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename, extensions=None):
    """Cek apakah file memiliki ekstensi yang diizinkan"""
    if extensions is None:
        extensions = current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

def compress_image(image_file, max_size=(800, 800), quality=85):
    """
    Compress dan resize gambar
    
    Args:
        image_file: File object dari upload
        max_size: Tuple (width, height) maksimal
        quality: Kualitas JPEG (1-100)
    
    Returns:
        BytesIO object dengan gambar yang sudah di-compress
    """
    # Buka gambar
    img = Image.open(image_file)
    
    # Convert ke RGB jika perlu (untuk handle PNG dengan transparency)
    if img.mode in ('RGBA', 'LA', 'P'):
        # Buat background putih untuk transparency
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Resize jika lebih besar dari max_size
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # Simpan ke BytesIO
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True, progressive=True)
    output.seek(0)
    
    return output

def save_uploaded_file(file, folder, filename=None, compress=True, max_size=(800, 800)):
    """
    Simpan file upload dengan opsi compress
    
    Args:
        file: File object dari upload
        folder: Folder tujuan (relative path dari UPLOAD_FOLDER)
        filename: Nama file (optional, akan generate jika None)
        compress: Apakah akan compress gambar
        max_size: Ukuran maksimal untuk compress
    
    Returns:
        Path file yang disimpan (relative ke static folder) atau None jika gagal
    """
    if not file or file.filename == '':
        return None
    
    # Cek ekstensi file
    if not allowed_file(file.filename):
        return None
    
    # Generate filename unik jika tidak disediakan
    if filename is None:
        import uuid
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
        filename = f"{uuid.uuid4().hex}.{ext}"
    
    # Pastikan folder ada
    full_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], folder)
    os.makedirs(full_folder, exist_ok=True)
    
    # Simpan file
    filepath = os.path.join(full_folder, filename)
    
    try:
        if compress:
            # Compress dan simpan
            compressed = compress_image(file, max_size=max_size)
            with open(filepath, 'wb') as f:
                f.write(compressed.getvalue())
        else:
            # Simpan langsung
            file.seek(0)
            file.save(filepath)
        
        # Return path relative ke static folder
        return os.path.join('uploads', folder, filename)
    except Exception as e:
        current_app.logger.error(f"Error saving file: {e}")
        return None

def delete_file(relative_path):
    """
    Hapus file berdasarkan path relative ke static/uploads
    
    Args:
        relative_path: Path seperti 'profiles/foto.jpg' atau 'book_covers/cover.png'
    
    Returns:
        True jika berhasil dihapus, False jika gagal
    """
    if not relative_path:
        return False
    
    try:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
    except Exception as e:
        current_app.logger.error(f"Error deleting file: {e}")
    
    return False
