"""
Skrip untuk reset password pengguna di database
Jalankan ini sekali untuk memperbaiki masalah login
"""
import sys
import os

# Tambahkan parent directory ke path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Pengguna
from werkzeug.security import generate_password_hash

def reset_passwords():
    """Reset password semua pengguna ke password default"""
    with app.app_context():
        # Ambil semua pengguna
        users = Pengguna.query.all()
        
        if not users:
            print("❌ Tidak ada pengguna di database!")
            print("Silakan tambahkan pengguna terlebih dahulu.")
            return
        
        print(f"✅ Ditemukan {len(users)} pengguna")
        print("\nMengupdate password semua pengguna menjadi: 'password123'")
        print("-" * 50)
        
        for user in users:
            # Set password baru
            user.set_password('password123')
            print(f"  ✓ Updated: {user.nama_lengkap} ({user.nomor_induk}) - Role: {user.peran}")
        
        # Commit semua perubahan
        db.session.commit()
        
        print("\n" + "=" * 50)
        print("✅ SELESAI! Semua password telah direset.")
        print("\n📝 Informasi Login:")
        print("   Username: Gunakan nomor_induk (NIM/NIP)")
        print("   Password: password123")
        print("\n⚠️  PENTING: Segera ganti password setelah login!")
        print("=" * 50)

if __name__ == '__main__':
    reset_passwords()
