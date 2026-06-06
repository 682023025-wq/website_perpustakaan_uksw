from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Pengguna, Buku, Peminjaman, Reservasi, KategoriBuku
from datetime import datetime, timedelta, date
from sqlalchemy import func

anggota_bp = Blueprint('anggota', __name__)


@anggota_bp.route('/katalog')
@login_required
def katalog():
    """Katalog buku - cari dan lihat detail buku"""
    if current_user.peran not in ['mahasiswa', 'dosen']:
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    # Pencarian dan filter
    search_query = request.args.get('search', '')
    kategori_filter = request.args.get('kategori', '')
    
    query = Buku.query
    
    if search_query:
        query = query.filter(
            db.or_(
                Buku.judul.ilike(f'%{search_query}%'),
                Buku.isbn.ilike(f'%{search_query}%'),
                Buku.penulis.ilike(f'%{search_query}%')
            )
        )
    
    if kategori_filter:
        query = query.filter_by(id_kategori=kategori_filter)
    
    buku_list = query.order_by(Buku.judul).all()
    
    # Ambil daftar kategori dari database
    categories = KategoriBuku.query.order_by(KategoriBuku.nama_kategori).all()
    
    return render_template('anggota/katalog.html',
                         buku_list=buku_list,
                         categories=categories,
                         search_query=search_query,
                         kategori_filter=kategori_filter)


@anggota_bp.route('/katalog/<int:id>')
@login_required
def detail_buku(id):
    """Detail buku tertentu"""
    if current_user.peran not in ['mahasiswa', 'dosen']:
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    buku = Buku.query.get_or_404(id)
    
    # Cek apakah user sedang meminjam buku ini
    sedang_meminjam = Peminjaman.query.filter_by(
        id_peminjam=current_user.id,
        id_buku=id,
        tgl_kembali_realisasi=None
    ).first()
    
    # Cek apakah user sudah mereservasi buku ini
    sudah_reservasi = Reservasi.query.filter_by(
        id_pemesan=current_user.id,
        id_buku=id,
        status_antrian='menunggu'
    ).first()
    
    # Hitung jumlah antrian reservasi
    antrian_reservasi = Reservasi.query.filter_by(
        id_buku=id,
        status_antrian='menunggu'
    ).count()
    
    return render_template('anggota/detail_buku.html',
                         buku=buku,
                         sedang_meminjam=sedang_meminjam,
                         sudah_reservasi=sudah_reservasi,
                         antrian_reservasi=antrian_reservasi)


@anggota_bp.route('/reservasi/<int:buku_id>', methods=['POST'])
@login_required
def buat_reservasi(buku_id):
    """Buat reservasi buku"""
    if current_user.peran not in ['mahasiswa', 'dosen']:
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('auth.login'))
    
    buku = Buku.query.get_or_404(buku_id)
    
    # Cek apakah sudah ada reservasi aktif
    existing = Reservasi.query.filter_by(
        id_pemesan=current_user.id,
        id_buku=buku_id,
        status_antrian='menunggu'
    ).first()
    
    if existing:
        flash('Anda sudah memesan buku ini sebelumnya.', 'warning')
        return redirect(url_for('anggota.detail_buku', id=buku_id))
    
    # Cek apakah sedang meminjam buku ini
    sedang_pinjam = Peminjaman.query.filter_by(
        id_peminjam=current_user.id,
        id_buku=buku_id,
        tgl_kembali_realisasi=None
    ).first()
    
    if sedang_pinjam:
        flash('Anda sedang meminjam buku ini. Tidak perlu reservasi.', 'warning')
        return redirect(url_for('anggota.detail_buku', id=buku_id))
    
    # Buat reservasi baru
    reservasi_baru = Reservasi(
        id_pemesan=current_user.id,
        id_buku=buku_id,
        status_antrian='menunggu'
    )
    
    db.session.add(reservasi_baru)
    db.session.commit()
    
    flash(f'Berhasil memesan "{buku.judul}".', 'success')
    return redirect(url_for('anggota.detail_buku', id=buku_id))


@anggota_bp.route('/peminjaman-saya')
@login_required
def peminjaman_saya():
    """Lihat peminjaman aktif user"""
    if current_user.peran not in ['mahasiswa', 'dosen']:
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    # Ambil semua peminjaman (aktif dan sudah dikembalikan)
    semua_peminjaman = Peminjaman.query.filter_by(
        id_peminjam=current_user.id
    ).order_by(Peminjaman.tgl_pinjam.desc()).all()
    
    return render_template('anggota/peminjaman_saya.html',
                         semua_peminjaman=semua_peminjaman)


@anggota_bp.route('/perpanjang/<int:id>', methods=['POST'])
@login_required
def perpanjang_peminjaman(id):
    """Perpanjang waktu peminjaman"""
    if current_user.peran not in ['mahasiswa', 'dosen']:
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('auth.login'))
    
    peminjaman = Peminjaman.query.get_or_404(id)
    
    # Validasi: hanya bisa perpanjang milik sendiri
    if peminjaman.id_peminjam != current_user.id:
        flash('Anda tidak memiliki akses ke peminjaman ini.', 'error')
        return redirect(url_for('anggota.peminjaman_saya'))
    
    # Validasi: hanya yang belum dikembalikan
    if peminjaman.tgl_kembali_realisasi:
        flash('Peminjaman ini sudah dikembalikan.', 'warning')
        return redirect(url_for('anggota.peminjaman_saya'))
    
    # Validasi: belum pernah diperpanjang
    if peminjaman.sudah_diperpanjang:
        flash('Peminjaman ini sudah pernah diperpanjang sebelumnya.', 'warning')
        return redirect(url_for('anggota.peminjaman_saya'))
    
    # Validasi: tidak ada yang reservasi buku ini
    ada_reservasi = Reservasi.query.filter_by(
        id_buku=peminjaman.id_buku,
        status_antrian='menunggu'
    ).first()
    
    if ada_reservasi:
        flash('Tidak dapat memperpanjang karena ada anggota lain yang memesan buku ini.', 'warning')
        return redirect(url_for('anggota.peminjaman_saya'))
    
    # Validasi: belum lewat dari jatuh tempo
    if date.today() > peminjaman.tgl_jatuh_tempo:
        flash('Tidak dapat memperpanjang karena sudah melewati batas waktu.', 'error')
        return redirect(url_for('anggota.peminjaman_saya'))
    
    # Tambahkan durasi sesuai role
    durasi_tambahan = 30 if current_user.peran == 'dosen' else 14
    peminjaman.tgl_jatuh_tempo = peminjaman.tgl_jatuh_tempo + timedelta(days=durasi_tambahan)
    peminjaman.sudah_diperpanjang = True
    
    db.session.commit()
    
    flash(f'Peminjaman berhasil diperpanjang hingga {peminjaman.tgl_jatuh_tempo.strftime("%d %B %Y")}', 'success')
    return redirect(url_for('anggota.peminjaman_saya'))


@anggota_bp.route('/reservasi-saya')
@login_required
def reservasi_saya():
    """Lihat reservasi/user"""
    if current_user.peran not in ['mahasiswa', 'dosen']:
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    semua_reservasi = Reservasi.query.filter_by(
        id_pemesan=current_user.id
    ).order_by(Reservasi.tgl_pemesanan.desc()).all()
    
    return render_template('anggota/reservasi_saya.html',
                         semua_reservasi=semua_reservasi)


@anggota_bp.route('/reservasi/batalkan/<int:id>', methods=['POST'])
@login_required
def batalkan_reservasi(id):
    """Batalkan reservasi"""
    if current_user.peran not in ['mahasiswa', 'dosen']:
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('auth.login'))
    
    reservasi = Reservasi.query.get_or_404(id)
    
    if reservasi.id_pemesan != current_user.id:
        flash('Anda tidak memiliki akses ke reservasi ini.', 'error')
        return redirect(url_for('anggota.reservasi_saya'))
    
    if reservasi.status_antrian != 'menunggu':
        flash('Reservasi ini tidak dapat dibatalkan.', 'warning')
        return redirect(url_for('anggota.reservasi_saya'))
    
    reservasi.status_antrian = 'batal'
    db.session.commit()
    
    flash('Reservasi berhasil dibatalkan.', 'success')
    return redirect(url_for('anggota.reservasi_saya'))


@anggota_bp.route('/profil')
@login_required
def profil():
    """Lihat dan edit profil user"""
    if current_user.peran not in ['mahasiswa', 'dosen']:
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('anggota/profil.html')


@anggota_bp.route('/profil/ganti-password', methods=['POST'])
@login_required
def ganti_password():
    """Ganti password sendiri"""
    if current_user.peran not in ['mahasiswa', 'dosen']:
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('auth.login'))
    
    password_lama = request.form.get('password_lama')
    password_baru = request.form.get('password_baru')
    konfirmasi_password = request.form.get('konfirmasi_password')
    
    # Validasi password lama
    if not current_user.check_password(password_lama):
        flash('Password lama salah.', 'error')
        return redirect(url_for('anggota.profil'))
    
    # Validasi password baru
    if password_baru != konfirmasi_password:
        flash('Password baru dan konfirmasi tidak cocok.', 'error')
        return redirect(url_for('anggota.profil'))
    
    if len(password_baru) < 6:
        flash('Password minimal 6 karakter.', 'error')
        return redirect(url_for('anggota.profil'))
    
    # Update password
    current_user.set_password(password_baru)
    db.session.commit()
    
    flash('Password berhasil diubah.', 'success')
    return redirect(url_for('anggota.profil'))
