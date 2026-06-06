import os

class Config:
    """Konfigurasi aplikasi Perpustakaan UKSW"""
    
    # Kunci rahasia untuk sesi dan keamanan
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'perpustakaan-uksw-secret-key-2024'
    
    # Konfigurasi Database TiDB Cloud
    # Format URI: mysql+pymysql://user:password@host:port/database
    SQLALCHEMY_DATABASE_URI = (
        'mysql+pymysql://2GtfVa4U4F7tAAK.root:49fEq3ndvaOO4zv3@'
        'gateway01.ap-southeast-1.prod.aws.tidbcloud.com:4000/perpustakaan_uksw'
    )
    
    # Agar tidak ada warning di console
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Konfigurasi sesi login
    PERMANENT_SESSION_LIFETIME = 3600  # 1 jam
    
    # Konstanta bisnis
    DENDA_PER_HARI = 500  # Rupiah
    DURASI_MAHASISWA = 14  # Hari
    DURASI_DOSEN = 30  # Hari
    KUOTA_MAHASISWA = 2  # Buku
    KUOTA_DOSEN = 10  # Buku
