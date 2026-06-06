from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Pengguna, Buku, Peminjaman, Reservasi, KategoriBuku
from datetime import datetime, timedelta, date
from sqlalchemy import func

staf_bp = Blueprint('staf', __name__)


@staf_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard petugas - ringkasan tugas harian"""
    if current_user.peran != 'petugas':
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    # Statistik hari ini
    today = date.today()
    peminjaman_hari_ini = Peminjaman.query.filter(
        Peminjaman.tgl_pinjam == today
    ).count()
    
    pengembalian_hari_ini = Peminjaman.query.filter(
        Peminjaman.tgl_kembali_realisasi == today
    ).count()
    
    # Jatuh tempo hari ini
    jatuh_tempo_hari_ini = Peminjaman.query.filter(
        Peminjaman.tgl_jatuh_tempo == today,
        Peminjaman.tgl_kembali_realisasi == None
    ).count()
    
    # Denda belum lunas
    denda_belum_lunas = Peminjaman.query.filter(
        Peminjaman.status_pembayaran_denda == 'belum_bayar',
        Peminjaman.nominal_denda > 0
    ).count()
    
    # Reservasi yang siap diambil
    reservasi_siap = Reservasi.query.filter_by(status_antrian='siap_diambil').count()
    
    return render_template('petugas/dashboard.html',
                         peminjaman_hari_ini=peminjaman_hari_ini,
                         pengembalian_hari_ini=pengembalian_hari_ini,
                         jatuh_tempo_hari_ini=jatuh_tempo_hari_ini,
                         denda_belum_lunas=denda_belum_lunas,
                         reservasi_siap=reservasi_siap)


@staf_bp.route('/manajemen-peminjaman', methods=['GET', 'POST'])
@login_required
def manajemen_peminjaman():
    """Halaman utama proses pinjam & kembali buku"""
    if current_user.peran != 'petugas':
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    anggota = None
    buku = None
    error_message = None
    success_message = None
    
    # Konstanta kuota
    KUOTA_MAHASISWA = 2
    KUOTA_DOSEN = 10
    DURASI_MAHASISWA = 14
    DURASI_DOSEN = 30
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'cek_anggota':
            # Cari anggota berdasarkan Nomor Induk (NIM/NIP)
            nomor_induk = request.form.get('nomor_induk')
            anggota = Pengguna.query.filter_by(nomor_induk=nomor_induk).first()
            
            if not anggota:
                error_message = 'Nomor Induk tidak ditemukan.'
            elif not anggota.status_aktif:
                error_message = 'Akun anggota ini telah dinonaktifkan.'
                anggota = None
            elif anggota.peran not in ['mahasiswa', 'dosen']:
                error_message = 'Akun ini bukan akun mahasiswa atau dosen.'
                anggota = None
        
        elif action == 'cek_buku':
            # Cari buku berdasarkan ISBN atau ID
            isbn_or_id = request.form.get('isbn_or_id')
            # Coba cari berdasarkan ID dulu, baru ISBN
            try:
                buku_id = int(isbn_or_id)
                buku = Buku.query.get(buku_id)
            except (ValueError, TypeError):
                buku = Buku.query.filter_by(isbn=isbn_or_id).first()
            
            if not buku:
                error_message = 'Buku tidak ditemukan.'
        
        elif action == 'pinjam':
            # Proses peminjaman
            pengguna_id = request.form.get('pengguna_id')
            buku_id = request.form.get('buku_id')
            
            pengguna = Pengguna.query.get(pengguna_id)
            buku_item = Buku.query.get(buku_id)
            
            if not pengguna or not buku_item:
                error_message = 'Data tidak valid.'
            elif buku_item.stok_tersedia <= 0:
                error_message = 'Stok buku tidak tersedia.'
            else:
                # Cek kuota
                peminjaman_aktif_count = Peminjaman.query.filter_by(
                    id_peminjam=pengguna_id,
                    tgl_kembali_realisasi=None
                ).count()
                
                kuota = KUOTA_DOSEN if pengguna.peran == 'dosen' else KUOTA_MAHASISWA
                
                if peminjaman_aktif_count >= kuota:
                    error_message = f'Kuota peminjaman penuh. {pengguna.get_nama_peran()} hanya boleh meminjam {kuota} buku.'
                else:
                    # Hitung tanggal jatuh tempo
                    durasi = DURASI_DOSEN if pengguna.peran == 'dosen' else DURASI_MAHASISWA
                    tgl_jatuh_tempo = date.today() + timedelta(days=durasi)
                    
                    # Buat peminjaman baru
                    peminjaman_baru = Peminjaman(
                        id_peminjam=pengguna_id,
                        id_buku=buku_id,
                        tgl_pinjam=date.today(),
                        tgl_jatuh_tempo=tgl_jatuh_tempo,
                        status_transaksi='dipinjam',
                        nominal_denda=0.00,
                        status_pembayaran_denda='bebas_denda',
                        sudah_diperpanjang=False,
                        id_petugas_pelayan=current_user.id
                    )
                    
                    # Kurangi stok
                    buku_item.stok_tersedia -= 1
                    
                    db.session.add(peminjaman_baru)
                    db.session.commit()
                    
                    success_message = f'Berhasil meminjamkan "{buku_item.judul}" kepada {pengguna.nama_lengkap}. Jatuh tempo: {tgl_jatuh_tempo.strftime("%d %B %Y")}'
                    
                    # Refresh data
                    anggota = pengguna
                    buku = buku_item
        
        elif action == 'kembali':
            # Proses pengembalian
            peminjaman_id = request.form.get('peminjaman_id')
            peminjaman = Peminjaman.query.get(peminjaman_id)
            
            if not peminjaman:
                error_message = 'Peminjaman tidak ditemukan.'
            else:
                # Hitung denda
                tgl_kembali = date.today()
                peminjaman.tgl_kembali_realisasi = tgl_kembali
                
                if tgl_kembali > peminjaman.tgl_jatuh_tempo:
                    hari_terlambat = (tgl_kembali - peminjaman.tgl_jatuh_tempo).days
                    denda = hari_terlambat * 500
                    peminjaman.nominal_denda = denda
                    peminjaman.status_pembayaran_denda = 'belum_bayar'
                else:
                    peminjaman.nominal_denda = 0.00
                    peminjaman.status_pembayaran_denda = 'bebas_denda'
                
                peminjaman.status_transaksi = 'kembali'
                
                # Tambah stok kembali
                buku_item = Buku.query.get(peminjaman.id_buku)
                if buku_item:
                    buku_item.stok_tersedia += 1
                
                db.session.commit()
                
                if peminjaman.nominal_denda > 0:
                    success_message = f'Buku berhasil dikembalikan. Ada denda Rp{int(peminjaman.nominal_denda):,} yang harus dibayar.'
                else:
                    success_message = 'Buku berhasil dikembalikan. Tidak ada denda.'
                
                # Refresh data
                anggota = peminjaman.peminjam
    
    # Ambil peminjaman aktif untuk anggota jika ada
    peminjaman_aktif_list = []
    if anggota:
        peminjaman_aktif_list = Peminjaman.query.filter_by(
            id_peminjam=anggota.id,
            tgl_kembali_realisasi=None
        ).all()
    
    return render_template('petugas/manajemen_peminjaman.html',
                         anggota=anggota,
                         buku=buku,
                         peminjaman_aktif_list=peminjaman_aktif_list,
                         error_message=error_message,
                         success_message=success_message,
                         KUOTA_MAHASISWA=KUOTA_MAHASISWA,
                         KUOTA_DOSEN=KUOTA_DOSEN)


@staf_bp.route('/tagihan-denda')
@login_required
def tagihan_denda():
    """Daftar tunggakan denda"""
    if current_user.peran != 'petugas':
        flash('Anda tidak memiliki akses ke halaman ini.', 'error')
        return redirect(url_for('auth.login'))
    
    # Ambil semua peminjaman dengan denda belum lunas
    denda_list = Peminjaman.query.join(Pengguna).filter(
        Peminjaman.status_pembayaran_denda == 'belum_bayar',
        Peminjaman.nominal_denda > 0
    ).order_by(Peminjaman.tgl_kembali_realisasi.desc()).all()
    
    return render_template('petugas/tagihan_denda.html', denda_list=denda_list)


@staf_bp.route('/tagihan-denda/lunasi/<int:id>', methods=['POST'])
@login_required
def lunasi_denda(id):
    """Konfirmasi pembayaran denda"""
    if current_user.peran != 'petugas':
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('staf.tagihan_denda'))
    
    peminjaman = Peminjaman.query.get_or_404(id)
    peminjaman.status_pembayaran_denda = 'lunas'
    peminjaman.tgl_bayar_denda = datetime.now()
    
    db.session.commit()
    
    flash(f'Denda atas nama {peminjaman.peminjam.nama_lengkap} sebesar Rp{int(peminjaman.nominal_denda):,} telah dilunasi.', 'success')
    return redirect(url_for('staf.tagihan_denda'))


@staf_bp.route('/koleksi-buku', methods=['GET', 'POST'])
@login_required
def koleksi_buku():
    """Kelola koleksi buku"""
    if current_user.peran != 'petugas':
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
    
    return render_template('petugas/koleksi_buku.html',
                         buku_list=buku_list,
                         categories=categories,
                         search_query=search_query,
                         kategori_filter=kategori_filter)


@staf_bp.route('/koleksi-buku/tambah', methods=['POST'])
@login_required
def tambah_buku():
    """Tambah buku baru"""
    if current_user.peran != 'petugas':
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('staf.koleksi_buku'))
    
    try:
        new_buku = Buku(
            judul=request.form.get('judul'),
            penulis=request.form.get('penulis'),
            penerbit=request.form.get('penerbit'),
            tahun_terbit=int(request.form.get('tahun_terbit') or 0),
            isbn=request.form.get('isbn'),
            bahasa=request.form.get('bahasa', 'Indonesia'),
            jumlah_halaman=int(request.form.get('jumlah_halaman') or 0),
            sinopsis=request.form.get('sinopsis'),
            url_cover=request.form.get('url_cover'),
            id_kategori=int(request.form.get('id_kategori') or None),
            stok_tersedia=int(request.form.get('stok_tersedia') or 0),
            lokasi_rak=request.form.get('lokasi_rak')
        )
        
        db.session.add(new_buku)
        db.session.commit()
        
        flash(f'Buku "{new_buku.judul}" berhasil ditambahkan.', 'success')
    except Exception as e:
        flash(f'Gagal menambahkan buku: {str(e)}', 'error')
    
    return redirect(url_for('staf.koleksi_buku'))


@staf_bp.route('/koleksi-buku/edit/<int:id>', methods=['POST'])
@login_required
def edit_buku(id):
    """Edit data buku"""
    if current_user.peran != 'petugas':
        flash('Anda tidak memiliki akses.', 'error')
        return redirect(url_for('staf.koleksi_buku'))
    
    buku = Buku.query.get_or_404(id)
    
    try:
        buku.judul = request.form.get('judul', buku.judul)
        buku.penulis = request.form.get('penulis', buku.penulis)
        buku.penerbit = request.form.get('penerbit', buku.penerbit)
        buku.tahun_terbit = int(request.form.get('tahun_terbit') or buku.tahun_terbit)
        buku.isbn = request.form.get('isbn', buku.isbn)
        buku.bahasa = request.form.get('bahasa', buku.bahasa)
        buku.jumlah_halaman = int(request.form.get('jumlah_halaman') or buku.jumlah_halaman)
        buku.sinopsis = request.form.get('sinopsis', buku.sinopsis)
        buku.url_cover = request.form.get('url_cover', buku.url_cover)
        buku.id_kategori = int(request.form.get('id_kategori') or buku.id_kategori) if request.form.get('id_kategori') else buku.id_kategori
        buku.stok_tersedia = int(request.form.get('stok_tersedia') or buku.stok_tersedia)
        buku.lokasi_rak = request.form.get('lokasi_rak', buku.lokasi_rak)
        
        db.session.commit()
        
        flash(f'Data buku "{buku.judul}" berhasil diperbarui.', 'success')
    except Exception as e:
        flash(f'Gagal memperbarui buku: {str(e)}', 'error')
    
    return redirect(url_for('staf.koleksi_buku'))
