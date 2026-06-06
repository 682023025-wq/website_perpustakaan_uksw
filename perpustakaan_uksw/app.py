from flask import Flask
from config import Config
from models import db
from flask_login import LoginManager

# Import blueprints
from blueprints.auth_bp import auth_bp
from blueprints.admin_bp import admin_bp
from blueprints.staf_bp import staf_bp
from blueprints.anggota_bp import anggota_bp


def create_app():
    """Fungsi factory untuk membuat aplikasi Flask"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Inisialisasi ekstensi
    db.init_app(app)
    
    # Setup Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu untuk mengakses halaman ini.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user berdasarkan ID untuk Flask-Login"""
        from models import Pengguna
        return Pengguna.query.get(int(user_id))
    
    # Custom decorator untuk role-based access control
    from functools import wraps
    from flask import abort, flash, redirect, url_for
    from flask_login import current_user
    
    def role_required(*roles):
        """Decorator untuk membatasi akses berdasarkan peran pengguna"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if current_user.peran not in roles:
                    flash('Anda tidak memiliki akses ke halaman ini.', 'error')
                    return redirect(url_for('auth.login'))
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    # Simpan decorator di app config agar bisa diakses blueprint
    app.role_required = role_required
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(staf_bp, url_prefix='/staf')
    app.register_blueprint(anggota_bp, url_prefix='/anggota')
    
    # Route default - redirect ke dashboard sesuai role
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.peran == 'super_petugas':
                return redirect(url_for('admin.dashboard'))
            elif current_user.peran == 'petugas':
                return redirect(url_for('staf.dashboard'))
            else:
                return redirect(url_for('anggota.katalog'))
        return redirect(url_for('auth.login'))
    
    # Buat tabel database jika belum ada
    with app.app_context():
        db.create_all()
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
