"""
Blueprint untuk Staf (Petugas)
Fitur: Manajemen peminjaman, tagihan denda, koleksi buku
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Pengguna, Buku, Peminjaman, KategoriBuku, Reservasi
from backend.auth_bp import role_required
from datetime import date, timedelta

staf_bp = Blueprint('staf', __name__, template_folder='../templates/petugas')


@staf_bp.route('/dashboard')
@role_required('petugas', 'super_petugas')
def dashboard():
    """
    Dashboard Petugas
    Menampilkan ringkasan aktivitas perpustakaan
    """
    # Statistik hari ini
    today = date.today()
    
    peminjaman_hari_ini = Peminjaman.query.filter(
        Peminjaman.tgl_pinjam == today
    ).count()
    
    pengembalian_hari_ini = Peminjaman.query.filter(
        Peminjaman.tgl_kembali_realisasi == today
    ).count()
    
    # Peminjaman aktif
    peminjaman_aktif = Peminjaman.query.filter(
        Peminjaman.status_transaksi.in_(['dipinjam', 'terlambat'])
    ).count()
    
    # Buku dengan stok rendah (< 3)
    buku_stok_rendah = Buku.query.filter(Buku.stok_tersedia < 3).count()
    
    return render_template('petugas/dashboard.html',
                         peminjaman_hari_ini=peminjaman_hari_ini,
                         pengembalian_hari_ini=pengembalian_hari_ini,
                         peminjaman_aktif=peminjaman_aktif,
                         buku_stok_rendah=buku_stok_rendah)


@staf_bp.route('/manajemen-peminjaman', methods=['GET', 'POST'])
@role_required('petugas', 'super_petugas')
def manajemen_peminjaman():
    """
    Manajemen Peminjaman Buku
    - Input NIM/NIP → tampilkan nama, sisa kuota, buku aktif
    - VALIDASI KUOTA: Mhs max 2, Dosen max 10
    - Scan ISBN → cek stok > 0
    - Hitung jatuh tempo: tgl_pinjam + 14 hari (Mhs), +30 hari (Dosen)
    - Insert peminjaman, kurangi stok_tersedia
    """
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'cari_anggota':
            # Cari anggota berdasarkan nomor_induk
            nomor_induk = request.form.get('nomor_induk', '').strip()
            anggota = Pengguna.query.filter_by(nomor_induk=nomor_induk).first()
            
            if not anggota:
                flash('Anggota dengan Nomor Induk tersebut tidak ditemukan.', 'error')
                return render_template('petugas/manajemen_peminjaman.html', 
                                     anggota=None, 
                                     buku_selected=None)
            
            if not anggota.status_aktif:
                flash('Akun anggota ini telah dinonaktifkan.', 'error')
                return render_template('petugas/manajemen_peminjaman.html',
                                     anggota=None,
                                     buku_selected=None)
            
            if anggota.peran not in ['mahasiswa', 'dosen']:
                flash('Hanya mahasiswa dan dosen yang dapat meminjam buku.', 'error')
                return render_template('petugas/manajemen_peminjaman.html',
                                     anggota=None,
                                     buku_selected=None)
            
            # Hitung kuota dan peminjaman aktif
            quota = anggota.get_quota()
            active_loans = anggota.get_active_loans_count()
            sisa_kuota = quota - active_loans
            
            # Ambil peminjaman aktif
            peminjaman_aktif = anggota.peminjaman_sebagai_peminjam.filter(
                Peminjaman.status_transaksi.in_(['dipinjam', 'terlambat'])
            ).all()
            
            return render_template('petugas/manajemen_peminjaman.html',
                                 anggota=anggota,
                                 quota=quota,
                                 active_loans=active_loans,
                                 sisa_kuota=sisa_kuota,
                                 peminjaman_aktif=peminjaman_aktif,
                                 buku_selected=None)
        
        elif action == 'cari_buku':
            # Cari buku berdasarkan ISBN
            isbn = request.form.get('isbn', '').strip()
            id_anggota = request.form.get('id_anggota')
            
            anggota = Pengguna.query.get(id_anggota) if id_anggota else None
            
            if not isbn:
                flash('ISBN harus diisi.', 'error')
                return redirect(url_for('staf.manajemen_peminjaman'))
            
            buku = Buku.query.filter_by(isbn=isbn).first()
            
            if not buku:
                flash('Buku dengan ISBN tersebut tidak ditemukan.', 'error')
                return render_template('petugas/manajemen_peminjaman.html',
                                     anggota=anggota,
                                     buku_selected=None)
            
            return render_template('petugas/manajemen_peminjaman.html',
                                 anggota=anggota,
                                 buku_selected=buku)
        
        elif action == 'proses_pinjam':
            # Proses peminjaman
            id_anggota = request.form.get('id_anggota')
            id_buku = request.form.get('id_buku')
            tgl_pinjam_str = request.form.get('tgl_pinjam')
            
            anggota = Pengguna.query.get(id_anggota)
            buku = Buku.query.get(id_buku)
            
            if not anggota or not buku:
                flash('Data anggota atau buku tidak valid.', 'error')
                return redirect(url_for('staf.manajemen_peminjaman'))
            
            # Validasi kuota
            if not anggota.can_borrow_more():
                flash(f'Maaf, {anggota.nama_lengkap} sudah mencapai batas peminjaman ({anggota.get_quota()} buku).', 'error')
                return redirect(url_for('staf.manajemen_peminjaman'))
            
            # Validasi stok
            if buku.stok_tersedia <= 0:
                flash('Stok buku ini tidak tersedia.', 'error')
                return redirect(url_for('staf.manajemen_peminjaman'))
            
            # Parse tanggal pinjam
            try:
                tgl_pinjam = date.fromisoformat(tgl_pinjam_str) if tgl_pinjam_str else date.today()
            except ValueError:
                tgl_pinjam = date.today()
            
            # Hitung jatuh tempo berdasarkan peran
            if anggota.peran == 'mahasiswa':
                lama_pinjam = 14  # hari
            elif anggota.peran == 'dosen':
                lama_pinjam = 30  # hari
            else:
                lama_pinjam = 14
            
            tgl_jatuh_tempo = tgl_pinjam + timedelta(days=lama_pinjam)
            
            # Buat transaksi peminjaman
            peminjaman_baru = Peminjaman(
                id_peminjam=anggota.id,
                id_buku=buku.id,
                tgl_pinjam=tgl_pinjam,
                tgl_jatuh_tempo=tgl_jatuh_tempo,
                status_transaksi='dipinjam',
                id_petugas_pelayan=current_user.id,
                sudah_diperpanjang=False
            )
            
            # Kurangi stok buku
            buku.stok_tersedia -= 1
            
            db.session.add(peminjaman_baru)
            db.session.commit()
            
            flash(f'Peminjaman berhasil! Buku "{buku.judul}" dipinjam oleh {anggota.nama_lengkap}. Jatuh tempo: {tgl_jatuh_tempo.strftime("%d %B %Y")}', 'success')
            return redirect(url_for('staf.manajemen_peminjaman'))
    
    # GET - tampilkan form kosong
    return render_template('petugas/manajemen_peminjaman.html',
                         anggota=None,
                         buku_selected=None)


@staf_bp.route('/tagihan-denda', methods=['GET', 'POST'])
@role_required('petugas', 'super_petugas')
def tagihan_denda():
    """
    Tagihan Denda & Pengembalian Buku
    - Saat kembali: hitung denda = max(0, (tgl_kembali - tgl_jatuh_tempo).days) * 500
    - Update status_pembayaran_denda='lunas' saat tombol "Konfirmasi Lunas" ditekan
    """
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'kembalikan_buku':
            # Proses pengembalian buku
            id_peminjaman = request.form.get('id_peminjaman')
            tgl_kembali_str = request.form.get('tgl_kembali', '')
            
            peminjaman = Peminjaman.query.get(id_peminjaman)
            
            if not peminjaman:
                flash('Transaksi peminjaman tidak ditemukan.', 'error')
                return redirect(url_for('staf.tagihan_denda'))
            
            if peminjaman.status_transaksi == 'kembali':
                flash('Buku ini sudah dikembalikan sebelumnya.', 'warning')
                return redirect(url_for('staf.tagihan_denda'))
            
            # Parse tanggal kembali
            try:
                tgl_kembali = date.fromisoformat(tgl_kembali_str) if tgl_kembali_str else date.today()
            except ValueError:
                tgl_kembali = date.today()
            
            # Hitung denda
            denda = peminjaman.hitung_denda(tgl_kembali)
            
            # Update data peminjaman
            peminjaman.tgl_kembali_realisasi = tgl_kembali
            peminjaman.nominal_denda = denda
            
            if denda > 0:
                peminjaman.status_transaksi = 'terlambat'
                peminjaman.status_pembayaran_denda = 'belum_bayar'
            else:
                peminjaman.status_transaksi = 'kembali'
                peminjaman.status_pembayaran_denda = 'bebas_denda'
            
            # Kembalikan stok buku
            peminjaman.buku.stok_tersedia += 1
            
            db.session.commit()
            
            if denda > 0:
                flash(f'Buku dikembalikan. Terdapat denda keterlambatan sebesar Rp {denda:,}.', 'warning')
            else:
                flash('Buku dikembalikan tepat waktu. Tidak ada denda.', 'success')
            
            return redirect(url_for('staf.tagihan_denda'))
        
        elif action == 'bayar_denda':
            # Konfirmasi pembayaran denda
            id_peminjaman = request.form.get('id_peminjaman')
            
            peminjaman = Peminjaman.query.get(id_peminjaman)
            
            if not peminjaman:
                flash('Transaksi tidak ditemukan.', 'error')
                return redirect(url_for('staf.tagihan_denda'))
            
            if peminjaman.status_pembayaran_denda == 'lunas':
                flash('Denda sudah lunas.', 'info')
                return redirect(url_for('staf.tagihan_denda'))
            
            # Update status pembayaran
            peminjaman.status_pembayaran_denda = 'lunas'
            peminjaman.tgl_bayar_denda = date.today()
            peminjaman.status_transaksi = 'kembali'  # Ubah status transaksi jadi kembali
            
            db.session.commit()
            
            flash(f'Denda sebesar Rp {peminjaman.nominal_denda:,} telah dilunasi.', 'success')
            return redirect(url_for('staf.tagihan_denda'))
    
    # GET - tampilkan daftar peminjaman yang perlu dikembalikan atau belum bayar denda
    filter_status = request.args.get('status', 'aktif')
    
    if filter_status == 'aktif':
        # Peminjaman aktif (belum kembali)
        peminjaman_list = Peminjaman.query.filter(
            Peminjaman.status_transaksi.in_(['dipinjam', 'terlambat'])
        ).order_by(Peminjaman.tgl_jatuh_tempo.asc()).all()
    elif filter_status == 'belum_bayar':
        # Yang belum bayar denda
        peminjaman_list = Peminjaman.query.filter(
            Peminjaman.status_pembayaran_denda == 'belum_bayar'
        ).order_by(Peminjaman.tgl_kembali_realisasi.desc()).all()
    else:
        # Semua
        peminjaman_list = Peminjaman.query.order_by(
            Peminjaman.tgl_pinjam.desc()
        ).limit(50).all()
    
    return render_template('petugas/tagihan_denda.html',
                         peminjaman_list=peminjaman_list)


@staf_bp.route('/koleksi-buku', methods=['GET', 'POST'])
@role_required('petugas', 'super_petugas')
def koleksi_buku():
    """
    CRUD Koleksi Buku
    Tambah, edit, hapus buku dari katalog
    """
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'tambah':
            # Tambah buku baru
            judul = request.form.get('judul', '').strip()
            penulis = request.form.get('penulis', '').strip()
            penerbit = request.form.get('penerbit', '').strip()
            tahun_terbit = request.form.get('tahun_terbit')
            isbn = request.form.get('isbn', '').strip()
            bahasa = request.form.get('bahasa')
            jumlah_halaman = request.form.get('jumlah_halaman')
            sinopsis = request.form.get('sinopsis', '').strip()
            lokasi_rak = request.form.get('lokasi_rak', '').strip()
            stok_tersedia = request.form.get('stok_tersedia', 0)
            id_kategori = request.form.get('id_kategori')
            
            # Validasi field wajib
            if not all([judul, penulis]):
                flash('Judul dan Penulis harus diisi.', 'error')
                return redirect(url_for('staf.koleksi_buku'))
            
            # Cek duplikasi ISBN
            if isbn and Buku.query.filter_by(isbn=isbn).first():
                flash('ISBN sudah terdaftar. Gunakan yang lain.', 'error')
                return redirect(url_for('staf.koleksi_buku'))
            
            buku_baru = Buku(
                judul=judul,
                penulis=penulis,
                penerbit=penerbit,
                tahun_terbit=int(tahun_terbit) if tahun_terbit else None,
                isbn=isbn if isbn else None,
                bahasa=bahasa,
                jumlah_halaman=int(jumlah_halaman) if jumlah_halaman else None,
                sinopsis=sinopsis,
                lokasi_rak=lokasi_rak,
                stok_tersedia=int(stok_tersedia),
                id_kategori=int(id_kategori) if id_kategori else None
            )
            
            db.session.add(buku_baru)
            db.session.commit()
            
            flash(f'Buku "{judul}" berhasil ditambahkan!', 'success')
        
        elif action == 'edit':
            # Edit buku
            id_buku = request.form.get('id_buku')
            buku = Buku.query.get(id_buku)
            
            if buku:
                buku.judul = request.form.get('judul', '').strip()
                buku.penulis = request.form.get('penulis', '').strip()
                buku.penerbit = request.form.get('penerbit', '').strip()
                buku.tahun_terbit = int(request.form.get('tahun_terbit')) if request.form.get('tahun_terbit') else None
                buku.isbn = request.form.get('isbn', '').strip()
                buku.bahasa = request.form.get('bahasa')
                buku.jumlah_halaman = int(request.form.get('jumlah_halaman')) if request.form.get('jumlah_halaman') else None
                buku.sinopsis = request.form.get('sinopsis', '').strip()
                buku.lokasi_rak = request.form.get('lokasi_rak', '').strip()
                buku.stok_tersedia = int(request.form.get('stok_tersedia', 0))
                buku.id_kategori = int(request.form.get('id_kategori')) if request.form.get('id_kategori') else None
                
                db.session.commit()
                flash('Data buku berhasil diperbarui.', 'success')
        
        elif action == 'hapus':
            # Hapus buku (hard delete)
            id_buku = request.form.get('id_buku')
            buku = Buku.query.get(id_buku)
            
            if buku:
                judul = buku.judul
                db.session.delete(buku)
                db.session.commit()
                flash(f'Buku "{judul}" telah dihapus.', 'warning')
        
        return redirect(url_for('staf.koleksi_buku'))
    
    # GET - tampilkan semua buku
    search = request.args.get('search', '')
    
    if search:
        buku_list = Buku.query.filter(
            db.or_(
                Buku.judul.ilike(f'%{search}%'),
                Buku.penulis.ilike(f'%{search}%'),
                Buku.isbn.ilike(f'%{search}%')
            )
        ).order_by(Buku.judul).all()
    else:
        buku_list = Buku.query.order_by(Buku.judul).all()
    
    kategori_list = KategoriBuku.query.order_by(KategoriBuku.nama_kategori).all()
    
    return render_template('petugas/koleksi_buku.html',
                         buku_list=buku_list,
                         kategori_list=kategori_list)
