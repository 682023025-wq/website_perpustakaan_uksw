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
    # Cek apakah user adalah admin
    if current_user.peran != 'admin':
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
    if current_user.peran != 'admin':
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
                Pengguna.nama.ilike(f'%{search_query}%'),
                Pengguna.nim_nip.ilike(f'%{search_query}%'),
                Pengguna.prodi.ilike(f'%{search_query}%')
            )
        )
    
    anggota_list = query.order_by(Pengguna.created_at.desc()).all()
    
    return render_template('super_petugas/kelola_anggota.html',
                         anggota_list=anggota_list,
                         filter_peran=filter_peran,
                         search_query=search_query)


@admin_bp.route('/kelola-anggota/tambah', methods=['POST'])
@login_required
def tambah_anggota():
    """Tambah anggota baru"""
    if current_user.peran != 'admin':
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    nim_nip = request.form.get('nim_nip')
    nama = request.form.get('nama')
    email = request.form.get('email')
    password = request.form.get('password')
    peran = request.form.get('peran')
    prodi = request.form.get('prodi')
    
    # Validasi
    if not all([nim_nip, nama, email, password, peran]):
        flash('Semua field wajib diisi!', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    # Cek apakah NIM/NIP sudah ada
    existing = Pengguna.query.filter_by(nim_nip=nim_nip).first()
    if existing:
        flash('NIM/NIP sudah terdaftar. Gunakan yang lain.', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    # Buat pengguna baru
    new_user = Pengguna(
        nim_nip=nim_nip,
        nama=nama,
        email=email,
        peran=peran,
        prodi=prodi if peran in ['mahasiswa', 'dosen'] else None,
        is_aktif=True
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    flash(f'Berhasil menambahkan {peran} baru: {nama}', 'success')
    return redirect(url_for('admin.kelola_anggota'))


@admin_bp.route('/kelola-anggota/edit/<int:id>', methods=['POST'])
@login_required
def edit_anggota(id):
    """Edit data anggota"""
    if current_user.peran != 'admin':
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    user = Pengguna.query.get_or_404(id)
    
    user.nama = request.form.get('nama', user.nama)
    user.email = request.form.get('email', user.email)
    user.prodi = request.form.get('prodi', user.prodi)
    
    # Update password jika diisi
    new_password = request.form.get('password')
    if new_password:
        user.set_password(new_password)
    
    db.session.commit()
    
    flash(f'Data {user.nama} berhasil diperbarui.', 'success')
    return redirect(url_for('admin.kelola_anggota'))


@admin_bp.route('/kelola-anggota/nonaktifkan/<int:id>', methods=['POST'])
@login_required
def nonaktifkan_anggota(id):
    """Nonaktifkan akun anggota"""
    if current_user.peran != 'admin':
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    user = Pengguna.query.get_or_404(id)
    user.is_aktif = False
    
    db.session.commit()
    
    flash(f'Akun {user.nama} telah dinonaktifkan.', 'warning')
    return redirect(url_for('admin.kelola_anggota'))


@admin_bp.route('/kelola-anggota/aktifkan/<int:id>', methods=['POST'])
@login_required
def aktifkan_anggota(id):
    """Aktifkan kembali akun anggota"""
    if current_user.peran != 'admin':
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('admin.kelola_anggota'))
    
    user = Pengguna.query.get_or_404(id)
    user.is_aktif = True
    
    db.session.commit()
    
    flash(f'Akun {user.nama} telah diaktifkan kembali.', 'success')
    return redirect(url_for('admin.kelola_anggota'))


@admin_bp.route('/bantuan-sandi', methods=['GET', 'POST'])
@login_required
def bantuan_sandi():
    """Reset password anggota yang lupa"""
    if current_user.peran != 'admin':
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    user_to_reset = None
    if request.method == 'POST':
        nim_nip = request.form.get('nim_nip')
        new_password = request.form.get('new_password')
        
        user_to_reset = Pengguna.query.filter_by(nim_nip=nim_nip).first()
        
        if user_to_reset and new_password:
            user_to_reset.set_password(new_password)
            db.session.commit()
            flash(f'Password untuk {user_to_reset.nama} berhasil direset.', 'success')
            return redirect(url_for('admin.bantuan_sandi'))
        elif not user_to_reset:
            flash('NIM/NIP tidak ditemukan.', 'error')
    
    return render_template('super_petugas/bantuan_sandi.html', user_to_reset=user_to_reset)
