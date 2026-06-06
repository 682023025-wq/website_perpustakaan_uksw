"""
Konfigurasi Aplikasi Perpustakaan UKSW
Menggunakan TiDB Cloud dengan koneksi SSL/TLS wajib
"""
import os

class Config:
    # Konfigurasi Secret Key untuk session dan CSRF
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-rahasia-perpustakaan-uksw-2024'
    
    # Konfigurasi Database TiDB Cloud
    # Host: gateway01.ap-southeast-1.prod.aws.tidbcloud.com
    # Port: 4000
    # User: 2GtfVa4U4F7tAAK.root
    # Pass: 49fEq3ndvaOO4zv3
    # DB: perpustakaan_uksw
    
    SQLALCHEMY_DATABASE_URI = (
        "mysql+pymysql://2GtfVa4U4F7tAAK.root:49fEq3ndvaOO4zv3@"
        "gateway01.ap-southeast-1.prod.aws.tidbcloud.com:4000/perpustakaan_uksw"
    )
    
    # WAJIB: Konfigurasi SSL untuk TiDB Cloud
    # Mencegah error "insecure transport" dengan memaksa koneksi terenkripsi
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'ssl': {
                'ca': None,  # TiDB menggunakan sertifikat publik yang diverifikasi otomatis
                'cert': None,
                'key': None,
            },
            'ssl_verify_cert': True,
        }
    }
    
    # Opsi SQLAlchemy tambahan
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = 280  # Recycle koneksi sebelum timeout TiDB (300 detik)
    SQLALCHEMY_POOL_PRE_PING = True  # Ping sebelum pakai koneksi untuk hindari stale connection
    
    # Konfigurasi Flask-Login
    LOGIN_VIEW = 'auth.login'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 jam
    
    # Konfigurasi Upload File
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    PROFILE_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'profiles')
    BOOK_COVER_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'book_covers')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # Max 5MB per file
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
