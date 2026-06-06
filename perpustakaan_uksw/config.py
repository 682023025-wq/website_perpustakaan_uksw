import os
import ssl

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-rahasia-uksw'
    
    DB_USER = '2GtfVa4U4F7tAAK.root'
    DB_PASS = '49fEq3ndvaOO4zv3'
    DB_HOST = 'gateway01.ap-southeast-1.prod.aws.tidbcloud.com'
    DB_PORT = 4000
    DB_NAME = 'perpustakaan_uksw'
    
    # Base URI tanpa query string
    SQLALCHEMY_DATABASE_URI = (
        f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    )
    
    # Konfigurasi SSL khusus untuk PyMySQL
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'ssl': {
                'ca': None,  # Gunakan sertifikat sistem default
                'check_hostname': True,
                'verify_mode': ssl.CERT_REQUIRED
            }
        }
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
