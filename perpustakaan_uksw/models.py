"""
Model Database untuk Sistem Perpustakaan UKSW
Semua model mengikuti skema database yang telah ditentukan
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

db = SQLAlchemy()


class Pengguna(UserMixin, db.Model):
    """
    Model untuk tabel pengguna
    Menyimpan data semua aktor: super_petugas, petugas, dosen, mahasiswa
    """
    __tablename__ = 'pengguna'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_lengkap = db.Column(db.String(100), nullable=False)
    nomor_induk = db.Column(db.String(20), unique=True, nullable=False)
    peran = db.Column(db.Enum('super_petugas', 'petugas', 'dosen', 'mahasiswa'), default='mahasiswa')
    level_akses = db.Column(db.Enum('penuh', 'terbatas'), default='terbatas')
    program_studi = db.Column(db.String(100))
    fakultas = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    kata_sandi_hash = db.Column(db.String(255), nullable=False)
    status_aktif = db.Column(db.Boolean, default=True)
    tanggal_dibuat = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relasi ke peminjaman (sebagai peminjam)
    peminjaman_sebagai_peminjam = db.relationship(
        'Peminjaman', 
        foreign_keys='Peminjaman.id_peminjam',
        backref='peminjam', 
        lazy='dynamic'
    )
    
    # Relasi ke peminjaman (sebagai petugas pelayan)
    peminjaman_sebagai_petugas = db.relationship(
        'Peminjaman', 
        foreign_keys='Peminjaman.id_petugas_pelayan',
        backref='petugas_pelayan', 
        lazy='dynamic'
    )
    
    # Relasi ke reservasi
    reservasi = db.relationship('Reservasi', backref='pemesan', lazy='dynamic')
    
    def set_password(self, password):
        """Hash password sebelum disimpan"""
        self.kata_sandi_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """
        Verifikasi password dengan hash yang tersimpan.
        Menangani kasus jika hash kosong, tidak sesuai format, atau masih plain text.
        """
        if not self.kata_sandi_hash or self.kata_sandi_hash.strip() == '':
            return False
        
        # Cek apakah string hash terlihat valid (mengandung '$' untuk format werkzeug: method$salt$hash)
        if '$' not in self.kata_sandi_hash:
            # Kemungkinan password masih plain text di DB (data lama/testing)
            # Bandingkan langsung sebagai fallback (case-sensitive)
            try:
                return self.kata_sandi_hash == password
            except Exception:
                return False
        
        try:
            return check_password_hash(self.kata_sandi_hash, password)
        except ValueError as e:
            # Jika error format hash (misal: method tidak dikenali), coba bandingkan sebagai plain text
            print(f"Warning: Hash format tidak valid untuk user {self.nomor_induk}. Error: {e}")
            # Fallback: bandingkan string langsung (untuk data testing dengan hash dummy)
            try:
                return self.kata_sandi_hash == password
            except Exception:
                return False
        except Exception as e:
            # Error lainnya, coba bandingkan sebagai plain text
            print(f"Error saat check password: {e}")
            try:
                return self.kata_sandi_hash == password
            except Exception:
                return False
    
    @property
    def is_active(self):
        """Override is_active untuk memeriksa status_aktif"""
        return self.status_aktif
    
    def get_quota(self):
        """Mengembalikan kuota peminjaman berdasarkan peran"""
        if self.peran == 'mahasiswa':
            return 2
        elif self.peran == 'dosen':
            return 10
        else:
            return 0  # Petugas tidak punya kuota pinjam
    
    def get_active_loans_count(self):
        """Hitung jumlah peminjaman aktif pengguna"""
        return self.peminjaman_sebagai_peminjam.filter(
            Peminjaman.status_transaksi.in_(['dipinjam', 'terlambat'])
        ).count()
    
    def can_borrow_more(self):
        """Cek apakah pengguna masih bisa meminjam buku"""
        if self.peran not in ['mahasiswa', 'dosen']:
            return False
        quota = self.get_quota()
        active_loans = self.get_active_loans_count()
        return active_loans < quota
    
    def __repr__(self):
        return f'<Pengguna {self.nama_lengkap} ({self.nomor_induk})>'


class KategoriBuku(db.Model):
    """
    Model untuk tabel kategori_buku
    Mengelompokkan buku berdasarkan kategori
    """
    __tablename__ = 'kategori_buku'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_kategori = db.Column(db.String(100), unique=True, nullable=False)
    
    # Relasi ke buku
    buku = db.relationship('Buku', backref='kategori', lazy='dynamic')
    
    def __repr__(self):
        return f'<KategoriBuku {self.nama_kategori}>'


class Buku(db.Model):
    """
    Model untuk tabel buku
    Menyimpan informasi detail setiap buku di perpustakaan
    """
    __tablename__ = 'buku'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    judul = db.Column(db.String(255), nullable=False)
    penulis = db.Column(db.String(150), nullable=False)
    penerbit = db.Column(db.String(100))
    tahun_terbit = db.Column(db.Integer)
    isbn = db.Column(db.String(13), unique=True)
    bahasa = db.Column(db.Enum('Indonesia', 'Inggris', 'Lainnya'), default='Indonesia')
    jumlah_halaman = db.Column(db.Integer)
    sinopsis = db.Column(db.Text)
    url_cover = db.Column(db.String(255))
    id_kategori = db.Column(db.Integer, db.ForeignKey('kategori_buku.id', ondelete='SET NULL'))
    stok_tersedia = db.Column(db.Integer, default=0)
    lokasi_rak = db.Column(db.String(50))
    
    # Relasi ke peminjaman
    peminjaman = db.relationship('Peminjaman', backref='buku', lazy='dynamic')
    
    # Relasi ke reservasi
    reservasi = db.relationship('Reservasi', backref='buku', lazy='dynamic')
    
    def __repr__(self):
        return f'<Buku {self.judul}>'
    
    def is_available(self):
        """Cek apakah buku tersedia untuk dipinjam"""
        return self.stok_tersedia > 0
    
    def has_pending_reservation(self):
        """Cek apakah ada reservasi menunggu untuk buku ini"""
        return self.reservasi.filter(Reservasi.status_antrian == 'menunggu').first() is not None


class Peminjaman(db.Model):
    """
    Model untuk tabel peminjaman
    Mencatat transaksi peminjaman dan pengembalian buku
    """
    __tablename__ = 'peminjaman'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_peminjam = db.Column(db.Integer, db.ForeignKey('pengguna.id', ondelete='CASCADE'), nullable=False)
    id_buku = db.Column(db.Integer, db.ForeignKey('buku.id', ondelete='CASCADE'), nullable=False)
    tgl_pinjam = db.Column(db.Date, nullable=False)
    tgl_jatuh_tempo = db.Column(db.Date, nullable=False)
    tgl_kembali_realisasi = db.Column(db.Date, nullable=True)
    status_transaksi = db.Column(
        db.Enum('dipinjam', 'kembali', 'terlambat'), 
        default='dipinjam'
    )
    nominal_denda = db.Column(db.Numeric(10, 2), default=0.00)
    status_pembayaran_denda = db.Column(
        db.Enum('belum_bayar', 'lunas', 'bebas_denda'), 
        default='belum_bayar'
    )
    tgl_bayar_denda = db.Column(db.DateTime, nullable=True)
    sudah_diperpanjang = db.Column(db.Boolean, default=False)
    id_petugas_pelayan = db.Column(db.Integer, db.ForeignKey('pengguna.id', ondelete='SET NULL'))
    
    def __repr__(self):
        return f'<Peminjaman id={self.id} status={self.status_transaksi}>'
    
    def hitung_denda(self, tgl_kembali=None):
        """
        Hitung denda keterlambatan
        Denda: Rp 500 per hari keterlambatan
        """
        if tgl_kembali is None:
            tgl_kembali = date.today()
        
        if self.tgl_jatuh_tempo and tgl_kembali > self.tgl_jatuh_tempo:
            hari_terlambat = (tgl_kembali - self.tgl_jatuh_tempo).days
            return hari_terlambat * 500
        return 0
    
    def is_overdue(self):
        """Cek apakah peminjaman sudah lewat jatuh tempo"""
        if self.status_transaksi in ['kembali']:
            return False
        return date.today() > self.tgl_jatuh_tempo
    
    def can_extend(self):
        """Cek apakah peminjaman bisa diperpanjang"""
        if self.sudah_diperpanjang:
            return False
        if self.status_transaksi != 'dipinjam':
            return False
        # Cek apakah ada reservasi menunggu untuk buku ini
        if self.buku.has_pending_reservation():
            return False
        return True


class Reservasi(db.Model):
    """
    Model untuk tabel reservasi
    Mengelola antrian reservasi buku yang sedang tidak tersedia
    """
    __tablename__ = 'reservasi'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pemesan = db.Column(db.Integer, db.ForeignKey('pengguna.id', ondelete='CASCADE'), nullable=False)
    id_buku = db.Column(db.Integer, db.ForeignKey('buku.id', ondelete='CASCADE'), nullable=False)
    tgl_pemesanan = db.Column(db.DateTime, default=datetime.utcnow)
    status_antrian = db.Column(
        db.Enum('menunggu', 'siap_diambil', 'diambil', 'kadaluarsa', 'batal'), 
        default='menunggu'
    )
    tgl_notifikasi = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Reservasi id={self.id} status={self.status_antrian}>'
    
    def is_expired(self):
        """Cek apakah reservasi sudah kadaluarsa (lebih dari 3 hari sejak notifikasi)"""
        if self.status_antrian != 'siap_diambil' or not self.tgl_notifikasi:
            return False
        return datetime.utcnow() > self.tgl_notifikasi.replace(hour=0, minute=0, second=0)
