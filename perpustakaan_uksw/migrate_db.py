"""
Script Migrasi Database
Menambahkan kolom yang hilang ke tabel pengguna
"""
import sys
import os

# Tambahkan parent directory ke path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set working directory ke perpustakaan_uksw
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db
from sqlalchemy import text

def migrate_database():
    app = create_app()
    
    with app.app_context():
        try:
            # Buat connection
            conn = db.engine.connect()
            
            # Cek apakah kolom foto_profil sudah ada
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'pengguna' 
                AND COLUMN_NAME = 'foto_profil'
            """))
            
            column_exists = result.scalar() > 0
            
            if not column_exists:
                print("Menambahkan kolom foto_profil ke tabel pengguna...")
                conn.execute(text("""
                    ALTER TABLE pengguna 
                    ADD COLUMN foto_profil VARCHAR(255)
                """))
                conn.commit()
                print("✓ Kolom foto_profil berhasil ditambahkan")
            else:
                print("✓ Kolom foto_profil sudah ada")
            
            # Cek apakah kolom url_cover di tabel buku sudah ada
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'buku' 
                AND COLUMN_NAME = 'url_cover'
            """))
            
            column_exists = result.scalar() > 0
            
            if not column_exists:
                print("Menambahkan kolom url_cover ke tabel buku...")
                conn.execute(text("""
                    ALTER TABLE buku 
                    ADD COLUMN url_cover VARCHAR(255)
                """))
                conn.commit()
                print("✓ Kolom url_cover berhasil ditambahkan")
            else:
                print("✓ Kolom url_cover sudah ada")
            
            conn.close()
            print("\n✓ Migrasi database selesai!")
            
        except Exception as e:
            print(f"✗ Error saat migrasi: {e}")
            raise

if __name__ == '__main__':
    migrate_database()
