from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Pengguna, Buku, Peminjaman, Reservasi
from datetime import datetime, timedelta
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__)


def get_role_required():
    """Dapatkan decorator role_required dari app"""
    from app import create_app
    app = create_app()
    return app.role_required


@admin_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard admin - pantauan umum perpustakaan"""
    # Cek apakah user adalah super_petugas
    if current_user.peran != 'super_petugas':
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    # Statistik umum
    total_anggota = Pengguna.query.filter(Pengguna.peran.in_(['mahasiswa', 'dosen'])).count()
    total_buku = Buku.query.count()
    peminjaman_aktif = Peminjaman.query.filter_by(tgl_kembali=None).count()
    reservasi_menunggu = Reservasi.query.filter_by(status='menunggu').count()
    
    # Anggota dengan denda belum lunas
    anggota_berdenda = db.session.query(Pengguna).join(Peminjaman).filter(
        Peminjaman.status_denda == 'belum_lunas',
        Peminjaman.denda > 0
    ).distinct().limit(5).all()
    
    # Buku paling banyak dipinjam
    buku_populer = db.session.query(Buku, func.count(Peminjaman.buku_id).label('jumlah_pinjam')).join(
        Peminjaman
    ).group_by(Buku.id).order_by(func.count(Peminjaman.buku_id).desc()).limit(5).all()
    
    return render_template('super_petugas/dashboard.html',
                         total_anggota=total_anggota,
                         total_buku=total_buku,
                         peminjaman_aktif=peminjaman_aktif,
                         reservasi_menunggu=reservasi_menunggu,
                         anggota_berdenda=anggota_berdenda,
                         buku_populer=buku_populer)


@admin_bp.route('/kelola-anggota', methods=['GET', 'POST'])
@login_required
def kelola_anggota():
    """Kelola data anggota (mahasiswa & dosen)"""
    if current_user.peran != 'super_petugas':
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    # Filter dan pencarian
    filter_peran = request.args.get('peran', '')
    search_query = request.args.get('search', '')
    
    query = Pengguna.query.filter(Pengguna.peran.in_(['mahasiswa', 'dosen']))
    
    if filter_peran:
        query = query.filter_by(peran=filter_peran)
    
    if search_query:
        query = query.filter(
            db.or_(
                Pengguna.nama_lengkap.ilike(f'%{search_query}%'),
                Pengguna.nomor_induk.ilike(f'%{search_query}%'),
                Pengguna.program_studi.ilike(f'%{search_query}%')
            )
        )
    
    anggota_list = query.order_by(Pengguna.tanggal_dibuat.desc()).all()
    
    return render_template('super_petugas/kelola_anggota.html',
                         anggota_list=anggota_list,
                         filter_peran=filter_peran,
                         search_query=search_query)


@admin_bp.route('/kelola-anggota/tambah', methods=['POST'])
@login_required
def tambah_anggota():
    """Tambah anggota baru"""
    if current_user.peran != 'super_petugas':
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    nomor_induk = request.form.get('nomor_induk')
    nama_lengkap = request.form.get('nama_lengkap')
    email = request.form.get('email')
    password = request.form.get('password')
    peran = request.form.get('peran')
    program_studi = request.form.get('program_studi')
    fakultas = request.form.get('fakultas')
    
    # Validasi
    if not all([nomor_induk, nama_lengkap, email, password, peran]):
        flash('Semua field wajib diisi!', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    # Cek apakah Nomor Induk sudah ada
    existing = Pengguna.query.filter_by(nomor_induk=nomor_induk).first()
    if existing:
        flash('Nomor Induk sudah terdaftar. Gunakan yang lain.', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    # Buat pengguna baru
    new_user = Pengguna(
        nomor_induk=nomor_induk,
        nama_lengkap=nama_lengkap,
        email=email,
        peran=peran,
        program_studi=program_studi if peran in ['mahasiswa', 'dosen'] else None,
        fakultas=fakultas if peran in ['mahasiswa', 'dosen'] else None,
        status_aktif=True
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    flash(f'Berhasil menambahkan {peran} baru: {nama_lengkap}', 'success')
    return redirect(url_for('admin.kelola_anggota'))


@admin_bp.route('/kelola-anggota/edit/<int:id>', methods=['POST'])
@login_required
def edit_anggota(id):
    """Edit data anggota"""
    if current_user.peran != 'super_petugas':
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    user = Pengguna.query.get_or_404(id)
    
    user.nama_lengkap = request.form.get('nama_lengkap', user.nama_lengkap)
    user.email = request.form.get('email', user.email)
    user.program_studi = request.form.get('program_studi', user.program_studi)
    user.fakultas = request.form.get('fakultas', user.fakultas)
    
    # Update password jika diisi
    new_password = request.form.get('password')
    if new_password:
        user.set_password(new_password)
    
    db.session.commit()
    
    flash(f'Data {user.nama_lengkap} berhasil diperbarui.', 'success')
    return redirect(url_for('admin.kelola_anggota'))


@admin_bp.route('/kelola-anggota/nonaktifkan/<int:id>', methods=['POST'])
@login_required
def nonaktifkan_anggota(id):
    """Nonaktifkan akun anggota"""
    if current_user.peran != 'super_petugas':
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    user = Pengguna.query.get_or_404(id)
    user.status_aktif = False
    
    db.session.commit()
    
    flash(f'Akun {user.nama_lengkap} telah dinonaktifkan.', 'warning')
    return redirect(url_for('admin.kelola_anggota'))


@admin_bp.route('/kelola-anggota/aktifkan/<int:id>', methods=['POST'])
@login_required
def aktifkan_anggota(id):
    """Aktifkan kembali akun anggota"""
    if current_user.peran != 'super_petugas':
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    user = Pengguna.query.get_or_404(id)
    user.status_aktif = True
    
    db.session.commit()
    
    flash(f'Akun {user.nama_lengkap} telah diaktifkan kembali.', 'success')
    return redirect(url_for('admin.kelola_anggota'))


@admin_bp.route('/bantuan-sandi', methods=['GET', 'POST'])
@login_required
def bantuan_sandi():
    """Reset password anggota yang lupa"""
    if current_user.peran != 'super_petugas':
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    user_to_reset = None
    if request.method == 'POST':
        nomor_induk = request.form.get('nomor_induk')
        new_password = request.form.get('new_password')
        
        user_to_reset = Pengguna.query.filter_by(nomor_induk=nomor_induk).first()
        
        if user_to_reset and new_password:
            user_to_reset.set_password(new_password)
            db.session.commit()
            flash(f'Password untuk {user_to_reset.nama_lengkap} berhasil direset.', 'success')
            return redirect(url_for('admin.bantuan_sandi'))
        elif not user_to_reset:
            flash('Nomor Induk tidak ditemukan.', 'error')
    
    return render_template('super_petugas/bantuan_sandi.html', user_to_reset=user_to_reset)
