from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, Pengguna

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Halaman login untuk semua aktor"""
    if current_user.is_authenticated:
        # Jika sudah login, redirect ke dashboard sesuai role
        if current_user.peran == 'super_petugas':
            return redirect(url_for('admin.dashboard'))
        elif current_user.peran == 'petugas':
            return redirect(url_for('staf.dashboard'))
        else:
            return redirect(url_for('anggota.katalog'))
    
    if request.method == 'POST':
        nomor_induk = request.form.get('nomor_induk')
        password = request.form.get('password')
        
        # Cari pengguna berdasarkan Nomor Induk (NIM/NIP)
        user = Pengguna.query.filter_by(nomor_induk=nomor_induk).first()
        
        if user and user.check_password(password):
            if not user.status_aktif:
                flash('Akun Anda telah dinonaktifkan. Hubungi admin untuk informasi lebih lanjut.', 'error')
                return render_template('auth/login.html')
            
            login_user(user)
            flash(f'Selamat datang kembali, {user.nama_lengkap}!', 'success')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            # Redirect berdasarkan role
            if user.peran == 'super_petugas':
                return redirect(url_for('admin.dashboard'))
            elif user.peran == 'petugas':
                return redirect(url_for('staf.dashboard'))
            else:
                return redirect(url_for('anggota.katalog'))
        else:
            flash('Nomor Induk atau password salah. Silakan coba lagi.', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout pengguna"""
    logout_user()
    flash('Anda telah berhasil logout. Sampai jumpa!', 'info')
    return redirect(url_for('auth.login'))
