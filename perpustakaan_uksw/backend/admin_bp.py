"""
Blueprint untuk Admin (Super Petugas)
Fitur: Kelola anggota, bantuan sandi, dashboard admin
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Pengguna
from backend.auth_bp import role_required
from werkzeug.security import generate_password_hash

admin_bp = Blueprint('admin', __name__, template_folder='../templates/super_petugas')


@admin_bp.route('/dashboard')
@role_required('super_petugas')
def dashboard():
    """
    Dashboard Super Petugas
    Menampilkan statistik dan ringkasan sistem
    """
    # Hitung statistik
    total_anggota = Pengguna.query.filter(
        Pengguna.peran.in_(['mahasiswa', 'dosen']),
        Pengguna.status_aktif == True
    ).count()
    
    total_petugas = Pengguna.query.filter(
        Pengguna.peran.in_(['petugas', 'super_petugas']),
        Pengguna.status_aktif == True
    ).count()
    
    # Ambil 5 anggota terbaru
    anggota_terbaru = Pengguna.query.filter(
        Pengguna.peran.in_(['mahasiswa', 'dosen'])
    ).order_by(Pengguna.tanggal_dibuat.desc()).limit(5).all()
    
    return render_template('super_petugas/dashboard.html',
                         total_anggota=total_anggota,
                         total_petugas=total_petugas,
                         anggota_terbaru=anggota_terbaru)


@admin_bp.route('/kelola-anggota', methods=['GET', 'POST'])
@role_required('super_petugas')
def kelola_anggota():
    """
    CRUD Anggota (Mahasiswa & Dosen)
    Soft delete dengan mengubah status_aktif=False
    """
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'tambah':
            # Tambah anggota baru
            nama_lengkap = request.form.get('nama_lengkap', '').strip()
            nomor_induk = request.form.get('nomor_induk', '').strip()
            peran = request.form.get('peran')
            program_studi = request.form.get('program_studi', '').strip()
            fakultas = request.form.get('fakultas', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            
            # Validasi
            if not all([nama_lengkap, nomor_induk, peran, password]):
                flash('Semua field wajib harus diisi.', 'error')
                return redirect(url_for('admin.kelola_anggota'))
            
            # Cek duplikasi nomor_induk
            if Pengguna.query.filter_by(nomor_induk=nomor_induk).first():
                flash('Nomor Induk sudah terdaftar. Gunakan yang lain.', 'error')
                return redirect(url_for('admin.kelola_anggota'))
            
            # Buat pengguna baru
            anggota_baru = Pengguna(
                nama_lengkap=nama_lengkap,
                nomor_induk=nomor_induk,
                peran=peran,
                program_studi=program_studi,
                fakultas=fakultas,
                email=email if email else None,
                status_aktif=True
            )
            anggota_baru.set_password(password)
            
            db.session.add(anggota_baru)
            db.session.commit()
            
            flash(f'Anggota {nama_lengkap} berhasil ditambahkan!', 'success')
        
        elif action == 'edit':
            # Edit anggota
            id_pengguna = request.form.get('id_pengguna')
            pengguna = Pengguna.query.get(id_pengguna)
            
            if pengguna:
                pengguna.nama_lengkap = request.form.get('nama_lengkap', '').strip()
                pengguna.program_studi = request.form.get('program_studi', '').strip()
                pengguna.fakultas = request.form.get('fakultas', '').strip()
                pengguna.email = request.form.get('email', '').strip() or None
                
                db.session.commit()
                flash('Data anggota berhasil diperbarui.', 'success')
        
        elif action == 'nonaktifkan':
            # Soft delete - nonaktifkan anggota
            id_pengguna = request.form.get('id_pengguna')
            pengguna = Pengguna.query.get(id_pengguna)
            
            if pengguna:
                pengguna.status_aktif = False
                db.session.commit()
                flash(f'Akun {pengguna.nama_lengkap} telah dinonaktifkan.', 'warning')
        
        elif action == 'aktifkan':
            # Aktifkan kembali anggota
            id_pengguna = request.form.get('id_pengguna')
            pengguna = Pengguna.query.get(id_pengguna)
            
            if pengguna:
                pengguna.status_aktif = True
                db.session.commit()
                flash(f'Akun {pengguna.nama_lengkap} telah diaktifkan.', 'success')
        
        return redirect(url_for('admin.kelola_anggota'))
    
    # GET - tampilkan semua anggota
    filter_status = request.args.get('status', 'aktif')
    
    if filter_status == 'aktif':
        anggota = Pengguna.query.filter(
            Pengguna.peran.in_(['mahasiswa', 'dosen']),
            Pengguna.status_aktif == True
        ).order_by(Pengguna.nomor_induk).all()
    elif filter_status == 'nonaktif':
        anggota = Pengguna.query.filter(
            Pengguna.peran.in_(['mahasiswa', 'dosen']),
            Pengguna.status_aktif == False
        ).order_by(Pengguna.nomor_induk).all()
    else:
        anggota = Pengguna.query.filter(
            Pengguna.peran.in_(['mahasiswa', 'dosen'])
        ).order_by(Pengguna.nomor_induk).all()
    
    return render_template('super_petugas/kelola_anggota.html', anggota=anggota)


@admin_bp.route('/bantuan-sandi', methods=['GET', 'POST'])
@role_required('super_petugas')
def bantuan_sandi():
    """
    Reset password anggota
    Generate hash baru dari input manual admin
    """
    if request.method == 'POST':
        nomor_induk = request.form.get('nomor_induk', '').strip()
        password_baru = request.form.get('password_baru', '')
        konfirmasi_password = request.form.get('konfirmasi_password', '')
        
        # Validasi
        if not nomor_induk or not password_baru:
            flash('Nomor Induk dan Password Baru harus diisi.', 'error')
            return redirect(url_for('admin.bantuan_sandi'))
        
        if password_baru != konfirmasi_password:
            flash('Password baru dan konfirmasi tidak cocok.', 'error')
            return redirect(url_for('admin.bantuan_sandi'))
        
        # Cari pengguna
        pengguna = Pengguna.query.filter_by(nomor_induk=nomor_induk).first()
        
        if not pengguna:
            flash('Pengguna dengan Nomor Induk tersebut tidak ditemukan.', 'error')
            return redirect(url_for('admin.bantuan_sandi'))
        
        # Reset password
        pengguna.set_password(password_baru)
        db.session.commit()
        
        flash(f'Password untuk {pengguna.nama_lengkap} ({pengguna.nomor_induk}) berhasil direset.', 'success')
        return redirect(url_for('admin.bantuan_sandi'))
    
    # GET - tampilkan form
    return render_template('super_petugas/bantuan_sandi.html')


@admin_bp.route('/detail-anggota/<int:id>')
@role_required('super_petugas')
def detail_anggota(id):
    """
    Lihat detail lengkap seorang anggota
    """
    pengguna = Pengguna.query.get_or_404(id)
    
    # Dapatkan riwayat peminjaman
    riwayat_peminjaman = pengguna.peminjaman_sebagai_peminjam.order_by(
        Peminjaman.tgl_pinjam.desc()
    ).limit(10).all()
    
    return render_template('super_petugas/detail_anggota.html',
                         pengguna=pengguna,
                         riwayat_peminjaman=riwayat_peminjaman)
