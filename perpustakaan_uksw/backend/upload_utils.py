"""
Utility functions untuk upload dan compress gambar dengan Cloudinary
"""
import os
import io
from PIL import Image
from werkzeug.utils import secure_filename
from flask import current_app

# Import Cloudinary
try:
    import cloudinary
    import cloudinary.uploader
    from cloudinary.utils import cloudinary_url
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

def init_cloudinary():
    """Inisialisasi konfigurasi Cloudinary dari app config"""
    if CLOUDINARY_AVAILABLE and cloudinary:
        cloudinary.config(
            cloud_name=current_app.config.get('CLOUDINARY_CLOUD_NAME'),
            api_key=current_app.config.get('CLOUDINARY_API_KEY'),
            api_secret=current_app.config.get('CLOUDINARY_API_SECRET'),
            secure=True
        )
        return True
    return False

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

def save_uploaded_file(file, folder, filename=None, compress=True, max_size=(400, 400), use_cloudinary=True):
    """
    Simpan file upload dengan opsi compress ke Cloudinary atau lokal
    
    Args:
        file: File object dari upload
        folder: Folder tujuan (relative path dari UPLOAD_FOLDER) - untuk cloudinary ini jadi tag
        filename: Nama file (optional, akan generate jika None)
        compress: Apakah akan compress gambar
        max_size: Ukuran maksimal untuk compress
        use_cloudinary: Gunakan Cloudinary untuk upload (default True)
    
    Returns:
        URL Cloudinary atau path file yang disimpan (relative ke static folder) atau None jika gagal
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
    
    # Jika Cloudinary tersedia dan diaktifkan, gunakan Cloudinary
    if use_cloudinary and CLOUDINARY_AVAILABLE:
        try:
            # Inisialisasi Cloudinary
            init_cloudinary()
            
            # Upload ke Cloudinary dengan transformasi otomatis (compress & resize)
            # Transformasi: auto format, quality auto, max ukuran 400x400
            upload_result = cloudinary.uploader.upload(
                file,
                folder=f"perpustakaan_uksw/{folder}",
                public_id=filename.rsplit('.', 1)[0] if filename else None,
                transformation=[
                    {'width': 400, 'height': 400, 'crop': 'limit'},  # Resize max 400x400
                    {'quality': 'auto:good'},  # Compress dengan kualitas otomatis bagus
                    {'fetch_format': 'auto'}  # Format otomatis optimal
                ],
                tags=[folder]
            )
            
            # Return URL secure dari Cloudinary
            return upload_result.get('secure_url')
        except Exception as e:
            current_app.logger.error(f"Cloudinary upload error: {e}")
            # Fallback ke penyimpanan lokal jika Cloudinary gagal
            pass
    
    # Fallback: Simpan lokal jika Cloudinary tidak tersedia/gagal
    try:
        # Pastikan folder ada
        full_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], folder)
        os.makedirs(full_folder, exist_ok=True)
        
        # Simpan file
        filepath = os.path.join(full_folder, filename)
        
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
        current_app.logger.error(f"Error saving file locally: {e}")
        return None

def delete_file(relative_path):
    """
    Hapus file berdasarkan path relative ke static/uploads atau URL Cloudinary
    
    Args:
        relative_path: Path seperti 'profiles/foto.jpg' atau 'book_covers/cover.png' atau URL Cloudinary
    
    Returns:
        True jika berhasil dihapus, False jika gagal
    """
    if not relative_path:
        return False
    
    # Cek apakah ini URL Cloudinary
    if relative_path.startswith('http') and 'cloudinary.com' in relative_path:
        try:
            # Inisialisasi Cloudinary
            init_cloudinary()
            
            # Ekstrak public_id dari URL Cloudinary
            # Format URL: https://res.cloudinary.com/<cloud_name>/image/upload/v1234567890/folder/public_id.jpg
            import re
            match = re.search(r'/upload/(?:v\d+/)?(.+?)(?:\.[a-zA-Z]+)?$', relative_path)
            if match:
                public_id = match.group(1)
                # Hapus ekstensi file jika ada
                public_id = public_id.rsplit('.', 1)[0]
                
                result = cloudinary.uploader.destroy(public_id)
                return result.get('result') == 'ok'
        except Exception as e:
            current_app.logger.error(f"Cloudinary delete error: {e}")
            return False
    
    # Hapus file lokal
    try:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
    except Exception as e:
        current_app.logger.error(f"Error deleting file locally: {e}")
    
    return False
