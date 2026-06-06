"""
Inisialisasi Aplikasi Flask untuk Perpustakaan UKSW
Hanya berisi init app, db, login_manager & register blueprints
"""
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from config import Config
from models import db, Pengguna
from backend.auth_bp import auth_bp
from backend.admin_bp import admin_bp
from backend.staf_bp import staf_bp
from backend.anggota_bp import anggota_bp


def create_app():
    """Factory function untuk membuat aplikasi Flask"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Inisialisasi ekstensi
    db.init_app(app)
    
    # Inisialisasi Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu untuk mengakses halaman ini.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user berdasarkan ID untuk Flask-Login"""
        return Pengguna.query.get(int(user_id))
    
    @login_manager.unauthorized_handler
    def unauthorized():
        """Handler untuk user yang belum login"""
        return redirect(url_for('auth.login'))
    
    # Register blueprints dari folder backend/
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(staf_bp, url_prefix='/staf')
    app.register_blueprint(anggota_bp, url_prefix='/anggota')
    
    # Route utama - redirect ke dashboard sesuai role
    @app.route('/')
    def index():
        """Halaman utama - redirect ke dashboard sesuai peran pengguna"""
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.peran == 'super_petugas':
                return redirect(url_for('admin.dashboard'))
            elif current_user.peran == 'petugas':
                return redirect(url_for('staf.dashboard'))
            else:  # dosen atau mahasiswa
                return redirect(url_for('anggota.dashboard'))
        return redirect(url_for('auth.login'))
    
    return app


# Membuat instance aplikasi
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Buat semua tabel database (hanya untuk development)
        db.create_all()
        print("✅ Database tables created successfully!")
    
    # Jalankan aplikasi
    app.run(debug=True, host='0.0.0.0', port=5000)
