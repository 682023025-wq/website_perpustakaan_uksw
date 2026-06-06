"""
Blueprint untuk Anggota (Dosen & Mahasiswa)
Fitur: Katalog, peminjaman saya, reservasi, profil
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Pengguna, Buku, Peminjaman, Reservasi, KategoriBuku, Wishlist
from datetime import date, timedelta

anggota_bp = Blueprint('anggota', __name__, template_folder='../templates/anggota')


@anggota_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard Anggota (Mahasiswa/Dosen)
    Menampilkan ringkasan aktivitas peminjaman
    """
    # Dapatkan data pengguna saat ini
    user = current_user

    # Hitung statistik pribadi
    peminjaman_aktif = user.peminjaman_sebagai_peminjam.filter(
        Peminjaman.status_transaksi.in_(['dipinjam', 'terlambat'])
    ).count()

    kuota = user.get_quota()
    sisa_kuota = kuota - peminjaman_aktif

    # Reservasi aktif
    reservasi_aktif = user.reservasi.filter(
        Reservasi.status_antrian.in_(['menunggu', 'siap_diambil'])
    ).count()

    # Riwayat peminjaman terakhir
    riwayat_terakhir = user.peminjaman_sebagai_peminjam.order_by(
        Peminjaman.tgl_pinjam.desc()
    ).limit(5).all()

    # Hitung jumlah wishlist
    wishlist_count = user.wishlist_items.count()

    return render_template('anggota/dashboard.html',
                         user=user,
                         peminjaman_aktif=peminjaman_aktif,
                         kuota=kuota,
                         sisa_kuota=sisa_kuota,
                         reservasi_aktif=reservasi_aktif,
                         wishlist_count=wishlist_count,
                         riwayat_terakhir=riwayat_terakhir)


@anggota_bp.route('/katalog')
@login_required
def katalog():
    """
    Katalog Buku Perpustakaan
    Grid buku responsive dengan fitur pencarian dan filter
    Tombol "Pinjam" jika stok>0, "Wishlist" jika stok=0
    """
    search = request.args.get('search', '')
    kategori_id = request.args.get('kategori', type=int)
    ketersediaan = request.args.get('ketersediaan', '')

    query = Buku.query

    if search:
        query = query.filter(
            db.or_(
                Buku.judul.ilike(f'%{search}%'),
                Buku.penulis.ilike(f'%{search}%'),
                Buku.isbn.ilike(f'%{search}%')
            )
        )

    if kategori_id:
        query = query.filter(Buku.id_kategori == kategori_id)

    # Filter ketersediaan
    if ketersediaan == 'tersedia':
        query = query.filter(Buku.stok_tersedia > 0)
    elif ketersediaan == 'habis':
        query = query.filter(Buku.stok_tersedia == 0)

    buku_list = query.order_by(Buku.judul).all()
    kategori_list = KategoriBuku.query.order_by(KategoriBuku.nama_kategori).all()

    # Dapatkan daftar ID buku yang sudah di wishlist user
    wishlist_buku_ids = set()
    if current_user.is_authenticated:
        wishlist_items = current_user.wishlist_items.all()
        wishlist_buku_ids = {item.id_buku for item in wishlist_items}

    return render_template('anggota/katalog.html',
                         buku_list=buku_list,
                         kategori_list=kategori_list,
                         search=search,
                         selected_kategori=kategori_id,
                         selected_ketersediaan=ketersediaan,
                         wishlist_buku_ids=wishlist_buku_ids)


@anggota_bp.route('/detail_buku/<int:id>')
@login_required
def detail_buku(id):
    """
    Detail Lengkap Buku
    Sinopsis, lokasi rak, tombol aksi (pinjam/reservasi/wishlist)
    """
    buku = Buku.query.get_or_404(id)

    # Cek apakah user sedang meminjam buku ini
    sedang_meminjam = Peminjaman.query.filter(
        Peminjaman.id_peminjam == current_user.id,
        Peminjaman.id_buku == id,
        Peminjaman.status_transaksi.in_(['dipinjam', 'terlambat'])
    ).first() is not None

    # Cek apakah ada reservasi menunggu untuk buku ini
    ada_reservasi_menunggu = buku.has_pending_reservation()

    # Cek apakah buku sudah ada di wishlist user
    sudah_di_wishlist = Wishlist.query.filter(
        Wishlist.id_anggota == current_user.id,
        Wishlist.id_buku == id
    ).first() is not None

    return render_template('anggota/detail_buku.html',
                         buku=buku,
                         sedang_meminjam=sedang_meminjam,
                         ada_reservasi_menunggu=ada_reservasi_menunggu,
                         sudah_di_wishlist=sudah_di_wishlist)


@anggota_bp.route('/peminjaman-saya', methods=['GET', 'POST'])
@login_required
def peminjaman_saya():
    """
    Daftar Peminjaman Aktif Saya
    Tombol "Perpanjang" hanya muncul jika:
    - sudah_diperpanjang==False
    - Tidak ada reservasi menunggu untuk buku tsb
    Extend +5 hari (Mhs) / +7 hari (Dosen)
    """
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'perpanjang':
            id_peminjaman = request.form.get('id_peminjaman')
            peminjaman = Peminjaman.query.get(id_peminjaman)

            if not peminjaman:
                flash('Peminjaman tidak ditemukan.', 'error')
                return redirect(url_for('anggota.peminjaman_saya'))

            # Validasi: hanya bisa perpanjang peminjaman sendiri
            if peminjaman.id_peminjam != current_user.id:
                flash('Anda tidak dapat memperpanjang peminjaman orang lain.', 'error')
                return redirect(url_for('anggota.peminjaman_saya'))

            # Cek apakah bisa diperpanjang
            if not peminjaman.can_extend():
                if peminjaman.sudah_diperpanjang:
                    flash('Peminjaman ini sudah pernah diperpanjang sebelumnya.', 'warning')
                else:
                    flash('Tidak dapat memperpanjang karena ada anggota lain yang mengantri buku ini.', 'warning')
                return redirect(url_for('anggota.peminjaman_saya'))

            # Hitung extension berdasarkan peran
            if current_user.peran == 'mahasiswa':
                tambahan_hari = 5
            elif current_user.peran == 'dosen':
                tambahan_hari = 7
            else:
                tambahan_hari = 5

            # Extend jatuh tempo
            peminjaman.tgl_jatuh_tempo = peminjaman.tgl_jatuh_tempo + timedelta(days=tambahan_hari)
            peminjaman.sudah_diperpanjang = True

            db.session.commit()

            flash(f'Peminjaman berhasil diperpanjang {tambahan_hari} hari. Jatuh tempo baru: {peminjaman.tgl_jatuh_tempo.strftime("%d %B %Y")}', 'success')
            return redirect(url_for('anggota.peminjaman_saya'))

    # GET - tampilkan semua peminjaman
    filter_status = request.args.get('status', 'aktif')

    if filter_status == 'aktif':
        peminjaman_list = current_user.peminjaman_sebagai_peminjam.filter(
            Peminjaman.status_transaksi.in_(['dipinjam', 'terlambat'])
        ).order_by(Peminjaman.tgl_jatuh_tempo.asc()).all()
    elif filter_status == 'riwayat':
        peminjaman_list = current_user.peminjaman_sebagai_peminjam.filter(
            Peminjaman.status_transaksi == 'kembali'
        ).order_by(Peminjaman.tgl_kembali_realisasi.desc()).all()
    else:
        peminjaman_list = current_user.peminjaman_sebagai_peminjam.order_by(
            Peminjaman.tgl_pinjam.desc()
        ).all()

    return render_template('anggota/peminjaman_saya.html',
                         peminjaman_list=peminjaman_list)


@anggota_bp.route('/reservasi-saya', methods=['GET', 'POST'])
@login_required
def reservasi_saya():
    """
    Daftar Reservasi Saya
    Status antrian: menunggu/siap_diambil/diambil/kadaluarsa/batal
    Mendukung parameter GET: id_buku dan action=reservasi_from_katalog untuk reservasi langsung dari katalog
    """
    # Handle reservasi via GET parameter dari katalog
    if request.method == 'GET':
        id_buku = request.args.get('id_buku', type=int)
        action = request.args.get('action')
        
        if action == 'reservasi_from_katalog' and id_buku:
            buku = Buku.query.get(id_buku)
            
            if not buku:
                flash('Buku tidak ditemukan.', 'error')
                return redirect(url_for('anggota.katalog'))
            
            # Cek apakah buku tersedia (jika tersedia, sebaiknya pinjam langsung)
            if buku.stok_tersedia > 0:
                flash('Buku ini tersedia. Silakan pinjam langsung di perpustakaan.', 'info')
                return redirect(url_for('anggota.detail_buku', id=id_buku))
            
            # Cek apakah user sudah punya reservasi aktif untuk buku ini
            existing = Reservasi.query.filter(
                Reservasi.id_pemesan == current_user.id,
                Reservasi.id_buku == id_buku,
                Reservasi.status_antrian.in_(['menunggu', 'siap_diambil'])
            ).first()
            
            if existing:
                flash('Anda sudah memiliki reservasi aktif untuk buku ini.', 'warning')
                return redirect(url_for('anggota.reservasi_saya'))
            
            # Buat reservasi baru
            reservasi_baru = Reservasi(
                id_pemesan=current_user.id,
                id_buku=id_buku,
                status_antrian='menunggu'
            )
            
            db.session.add(reservasi_baru)
            db.session.commit()
            
            flash(f'Reservasi berhasil! Anda akan mendapat notifikasi ketika buku "{buku.judul}" tersedia.', 'success')
            return redirect(url_for('anggota.reservasi_saya'))
    
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'reservasi':
            # Buat reservasi baru
            id_buku = request.form.get('id_buku')
            buku = Buku.query.get(id_buku)

            if not buku:
                flash('Buku tidak ditemukan.', 'error')
                return redirect(url_for('anggota.reservasi_saya'))

            # Cek apakah buku tersedia (jika tersedia, sebaiknya pinjam langsung)
            if buku.stok_tersedia > 0:
                flash('Buku ini tersedia. Silakan pinjam langsung di perpustakaan.', 'info')
                return redirect(url_for('anggota.katalog'))

            # Cek apakah user sudah punya reservasi aktif untuk buku ini
            existing = Reservasi.query.filter(
                Reservasi.id_pemesan == current_user.id,
                Reservasi.id_buku == id_buku,
                Reservasi.status_antrian.in_(['menunggu', 'siap_diambil'])
            ).first()

            if existing:
                flash('Anda sudah memiliki reservasi aktif untuk buku ini.', 'warning')
                return redirect(url_for('anggota.reservasi_saya'))

            # Buat reservasi baru
            reservasi_baru = Reservasi(
                id_pemesan=current_user.id,
                id_buku=id_buku,
                status_antrian='menunggu'
            )

            db.session.add(reservasi_baru)
            db.session.commit()

            flash(f'Reservasi berhasil! Anda akan mendapat notifikasi ketika buku "{buku.judul}" tersedia.', 'success')
            return redirect(url_for('anggota.reservasi_saya'))

        elif action == 'batal':
            # Batalkan reservasi
            id_reservasi = request.form.get('id_reservasi')
            reservasi = Reservasi.query.get(id_reservasi)

            if not reservasi:
                flash('Reservasi tidak ditemukan.', 'error')
                return redirect(url_for('anggota.reservasi_saya'))

            if reservasi.id_pemesan != current_user.id:
                flash('Anda tidak dapat membatalkan reservasi orang lain.', 'error')
                return redirect(url_for('anggota.reservasi_saya'))

            if reservasi.status_antrian not in ['menunggu', 'siap_diambil']:
                flash('Reservasi ini tidak dapat dibatalkan.', 'warning')
                return redirect(url_for('anggota.reservasi_saya'))

            reservasi.status_antrian = 'batal'
            db.session.commit()

            flash('Reservasi berhasil dibatalkan.', 'info')
            return redirect(url_for('anggota.reservasi_saya'))

    # GET - tampilkan semua reservasi
    filter_status = request.args.get('status', 'aktif')

    if filter_status == 'aktif':
        reservasi_list = current_user.reservasi.filter(
            Reservasi.status_antrian.in_(['menunggu', 'siap_diambil'])
        ).order_by(Reservasi.tgl_pemesanan.desc()).all()
    elif filter_status == 'riwayat':
        reservasi_list = current_user.reservasi.filter(
            Reservasi.status_antrian.in_(['diambil', 'kadaluarsa', 'batal'])
        ).order_by(Reservasi.tgl_pemesanan.desc()).all()
    else:
        reservasi_list = current_user.reservasi.order_by(
            Reservasi.tgl_pemesanan.desc()
        ).all()

    return render_template('anggota/reservasi_saya.html',
                         reservasi_list=reservasi_list)


@anggota_bp.route('/wishlist', methods=['POST'])
@login_required
def wishlist_action():
    """
    Tambah/Hapus buku dari wishlist (alias untuk toggle_wishlist)
    """
    return toggle_wishlist()


@anggota_bp.route('/toggle-wishlist/<int:id_buku>', methods=['POST'])
@login_required
def toggle_wishlist(id_buku):
    """
    Toggle wishlist: tambah jika belum ada, hapus jika sudah ada
    Mencegah duplikasi dengan validasi ketat
    """
    buku = Buku.query.get_or_404(id_buku)

    # Cek apakah sudah ada di wishlist
    existing = Wishlist.query.filter(
        Wishlist.id_anggota == current_user.id,
        Wishlist.id_buku == id_buku
    ).first()

    if existing:
        # Hapus dari wishlist
        db.session.delete(existing)
        db.session.commit()
        flash(f'Buku "{buku.judul}" dihapus dari wishlist.', 'info')
    else:
        # Validasi ganda untuk mencegah duplikasi (race condition)
        existing_check = Wishlist.query.filter_by(
            id_anggota=current_user.id,
            id_buku=id_buku
        ).first()
        
        if not existing_check:
            # Tambahkan ke wishlist
            wishlist_baru = Wishlist(
                id_anggota=current_user.id,
                id_buku=id_buku
            )
            db.session.add(wishlist_baru)
            db.session.commit()
            flash(f'Buku "{buku.judul}" berhasil ditambahkan ke wishlist!', 'success')
        else:
            flash(f'Buku "{buku.judul}" sudah ada di wishlist.', 'info')

    # Redirect kembali ke halaman sebelumnya
    next_page = request.form.get('next_page', request.referrer or url_for('anggota.katalog'))
    return redirect(next_page)


@anggota_bp.route('/wishlist-saya')
@login_required
def wishlist_saya():
    """
    Daftar Wishlist Saya
    Menampilkan semua buku yang ada di wishlist
    """
    wishlist_items = current_user.wishlist_items.order_by(
        Wishlist.tanggal_ditambahkan.desc()
    ).all()

    return render_template('anggota/wishlist_saya.html',
                         wishlist_items=wishlist_items)


@anggota_bp.route('/profil', methods=['GET', 'POST'])
@login_required
def profil():
    """
    Profil Pengguna
    Lihat data diri, ganti password sendiri, upload foto profil
    """
    from backend.upload_utils import save_uploaded_file, delete_file

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profil':
            # Update data profil
            user = current_user
            user.program_studi = request.form.get('program_studi', '').strip()
            user.fakultas = request.form.get('fakultas', '').strip()
            user.email = request.form.get('email', '').strip() or None

            # Handle foto profil dari URL atau upload
            foto_url = request.form.get('foto_url', '').strip()
            foto_upload = request.files.get('foto_upload')

            # Jika ada URL foto, gunakan URL tersebut
            if foto_url:
                user.foto_profil = foto_url
            # Jika ada file upload, simpan dan compress
            elif foto_upload and foto_upload.filename:
                # Hapus foto lama jika ada
                if user.foto_profil:
                    delete_file(user.foto_profil)

                # Simpan foto baru
                foto_path = save_uploaded_file(foto_upload, 'profiles', compress=True, max_size=(400, 400))
                if foto_path:
                    user.foto_profil = foto_path

            db.session.commit()
            flash('Profil berhasil diperbarui.', 'success')
            return redirect(url_for('anggota.profil'))

        elif action == 'ganti_password':
            # Ganti password
            password_lama = request.form.get('password_lama', '')
            password_baru = request.form.get('password_baru', '')
            konfirmasi_password = request.form.get('konfirmasi_password', '')

            user = current_user

            # Verifikasi password lama
            if not user.check_password(password_lama):
                flash('Password lama salah.', 'error')
                return redirect(url_for('anggota.profil'))

            # Validasi password baru
            if not password_baru:
                flash('Password baru harus diisi.', 'error')
                return redirect(url_for('anggota.profil'))

            if password_baru != konfirmasi_password:
                flash('Password baru dan konfirmasi tidak cocok.', 'error')
                return redirect(url_for('anggota.profil'))

            # Update password
            user.set_password(password_baru)
            db.session.commit()

            flash('Password berhasil diubah.', 'success')
            return redirect(url_for('anggota.profil'))

    # GET - tampilkan form profil
    return render_template('anggota/profil.html')   
