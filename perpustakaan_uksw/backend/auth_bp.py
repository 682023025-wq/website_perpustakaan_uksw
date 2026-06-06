"""
Blueprint untuk autentikasi (login/logout) semua aktor
Menangani proses login dengan hash password dan redirect sesuai peran
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, Pengguna
from functools import wraps

auth_bp = Blueprint('auth', __name__, template_folder='../templates/auth')


def role_required(*roles):
    """
    Decorator untuk membatasi akses berdasarkan peran pengguna
    Args:
        *roles: Daftar peran yang diizinkan (misal: 'super_petugas', 'petugas')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask_login import current_user
            if not current_user.is_authenticated:
                flash('Silakan login terlebih dahulu.', 'warning')
                return redirect(url_for('auth.login'))
            
            if current_user.peran not in roles:
                flash('Anda tidak memiliki akses ke halaman ini.', 'error')
                return redirect(url_for('index'))
            
            # Cek juga status aktif pengguna
            if not current_user.status_aktif:
                logout_user()
                flash('Akun Anda telah dinonaktifkan. Hubungi administrator.', 'error')
                return redirect(url_for('auth.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Halaman login untuk semua aktor
    Menerima nomor_induk dan password
    """
    from flask_login import current_user
    
    # Jika sudah login, redirect ke dashboard sesuai role
    if current_user.is_authenticated:
        if current_user.peran == 'super_petugas':
            return redirect(url_for('admin.dashboard'))
        elif current_user.peran == 'petugas':
            return redirect(url_for('staf.dashboard'))
        else:
            return redirect(url_for('anggota.dashboard'))
    
    if request.method == 'POST':
        nomor_induk = request.form.get('nomor_induk', '').strip()
        password = request.form.get('password', '')
        
        # Validasi input tidak kosong
        if not nomor_induk or not password:
            flash('Nomor Induk dan Kata Sandi harus diisi.', 'error')
            return render_template('auth/login.html')
        
        # Cari pengguna berdasarkan nomor_induk
        user = Pengguna.query.filter_by(nomor_induk=nomor_induk).first()
        
        if user and user.check_password(password):
            # Cek status aktif
            if not user.status_aktif:
                flash('Akun Anda telah dinonaktifkan. Hubungi administrator.', 'error')
                return render_template('auth/login.html')
            
            # Login berhasil
            login_user(user, remember=True)
            flash(f'Selamat datang, {user.nama_lengkap}!', 'success')
            
            # Redirect berdasarkan peran
            if user.peran == 'super_petugas':
                return redirect(url_for('admin.dashboard'))
            elif user.peran == 'petugas':
                return redirect(url_for('staf.dashboard'))
            else:  # dosen atau mahasiswa
                return redirect(url_for('anggota.dashboard'))
        else:
            flash('Nomor Induk atau Kata Sandi salah. Silakan coba lagi.', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """
    Logout pengguna dan redirect ke halaman login
    """
    from flask_login import current_user
    nama = current_user.nama_lengkap
    logout_user()
    flash(f'Sampai jumpa, {nama}! Anda telah logout.', 'info')
    return redirect(url_for('auth.login'))
