from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Pengguna(UserMixin, db.Model):
    """Model untuk pengguna sistem (mahasiswa, dosen, petugas, admin)"""
    __tablename__ = 'pengguna'
    
    id = db.Column(db.Integer, primary_key=True)
    nama_lengkap = db.Column(db.String(100), nullable=False)
    nomor_induk = db.Column(db.String(20), unique=True, nullable=False, index=True)
    peran = db.Column(db.Enum('super_petugas', 'petugas', 'dosen', 'mahasiswa'), default='mahasiswa')
    level_akses = db.Column(db.Enum('penuh', 'terbatas'), default='terbatas')
    program_studi = db.Column(db.String(100))
    fakultas = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    kata_sandi_hash = db.Column(db.String(255), nullable=False)
    status_aktif = db.Column(db.Boolean, default=True)
    tanggal_dibuat = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relasi ke peminjaman sebagai peminjam
    peminjaman_sebagai_peminjam = db.relationship('Peminjaman', 
                                                   backref='peminjam', 
                                                   lazy='dynamic',
                                                   foreign_keys='Peminjaman.id_peminjam')
    # Relasi ke peminjaman sebagai petugas pelayan
    peminjaman_sebagai_petugas = db.relationship('Peminjaman', 
                                                  backref='petugas_pelayan', 
                                                  lazy='dynamic',
                                                  foreign_keys='Peminjaman.id_petugas_pelayan')
    # Relasi ke reservasi
    reservasi = db.relationship('Reservasi', backref='pemesan', lazy='dynamic',
                                foreign_keys='Reservasi.id_pemesan')
    
    def set_password(self, password):
        """Hash password sebelum disimpan"""
        self.kata_sandi_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Cek apakah password cocok dengan hash"""
        return check_password_hash(self.kata_sandi_hash, password)
    
    @property
    def is_active(self):
        """Flask-Login butuh properti ini untuk cek apakah user aktif"""
        return self.status_aktif
    
    def get_nama_peran(self):
        """Mengembalikan nama peran dalam bahasa Indonesia"""
        role_map = {
            'mahasiswa': 'Mahasiswa',
            'dosen': 'Dosen',
            'petugas': 'Petugas Perpustakaan',
            'super_petugas': 'Admin/Super Petugas'
        }
        return role_map.get(self.peran, self.peran)
    
    def __repr__(self):
        return f'<Pengguna {self.nama_lengkap} ({self.nomor_induk})>'


class Buku(db.Model):
    """Model untuk koleksi buku perpustakaan"""
    __tablename__ = 'buku'
    
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(255), nullable=False)
    penulis = db.Column(db.String(150), nullable=False)
    penerbit = db.Column(db.String(100))
    tahun_terbit = db.Column(db.Integer)
    isbn = db.Column(db.String(13), unique=True)
    bahasa = db.Column(db.Enum('Indonesia', 'Inggris', 'Lainnya'), default='Indonesia')
    jumlah_halaman = db.Column(db.Integer)
    sinopsis = db.Column(db.Text)
    url_cover = db.Column(db.String(255))
    id_kategori = db.Column(db.Integer, db.ForeignKey('kategori_buku.id'))
    stok_tersedia = db.Column(db.Integer, default=0)
    lokasi_rak = db.Column(db.String(50))
    
    # Relasi ke kategori
    kategori = db.relationship('KategoriBuku', backref='buku', lazy='joined')
    # Relasi ke peminjaman
    peminjaman = db.relationship('Peminjaman', backref='buku', lazy='dynamic',
                                 foreign_keys='Peminjaman.id_buku')
    # Relasi ke reservasi
    reservasi = db.relationship('Reservasi', backref='buku', lazy='dynamic',
                                foreign_keys='Reservasi.id_buku')
    
    def __repr__(self):
        return f'<Buku {self.judul}>'


class Peminjaman(db.Model):
    """Model untuk transaksi peminjaman buku"""
    __tablename__ = 'peminjaman'
    
    id = db.Column(db.Integer, primary_key=True)
    id_peminjam = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    id_buku = db.Column(db.Integer, db.ForeignKey('buku.id'), nullable=False)
    tgl_pinjam = db.Column(db.Date, nullable=False)
    tgl_jatuh_tempo = db.Column(db.Date, nullable=False)
    tgl_kembali_realisasi = db.Column(db.Date)  # NULL jika belum dikembalikan
    status_transaksi = db.Column(db.Enum('dipinjam', 'kembali', 'terlambat'), default='dipinjam')
    nominal_denda = db.Column(db.Numeric(10, 2), default=0.00)
    status_pembayaran_denda = db.Column(db.Enum('belum_bayar', 'lunas', 'bebas_denda'), default='belum_bayar')
    tgl_bayar_denda = db.Column(db.DateTime)
    sudah_diperpanjang = db.Column(db.Boolean, default=False)
    id_petugas_pelayan = db.Column(db.Integer, db.ForeignKey('pengguna.id'))
    
    def hitung_denda(self):
        """Hitung denda jika terlambat mengembalikan"""
        if self.tgl_kembali_realisasi and self.tgl_kembali_realisasi > self.tgl_jatuh_tempo:
            hari_terlambat = (self.tgl_kembali_realisasi - self.tgl_jatuh_tempo).days
            return hari_terlambat * 500
        return 0
    
    def __repr__(self):
        return f'<Peminjaman ID:{self.id} - {self.peminjam.nama_lengkap}>'


class Reservasi(db.Model):
    """Model untuk reservasi/pesanan buku yang sedang dipinjam"""
    __tablename__ = 'reservasi'
    
    id = db.Column(db.Integer, primary_key=True)
    id_pemesan = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    id_buku = db.Column(db.Integer, db.ForeignKey('buku.id'), nullable=False)
    tgl_pemesanan = db.Column(db.DateTime, default=db.func.current_timestamp())
    status_antrian = db.Column(db.Enum('menunggu', 'siap_diambil', 'diambil', 'kadaluarsa', 'batal'), default='menunggu')
    tgl_notifikasi = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<Reservasi ID:{self.id} - {self.pemesan.nama_lengkap}>'


class KategoriBuku(db.Model):
    """Model untuk kategori buku"""
    __tablename__ = 'kategori_buku'
    
    id = db.Column(db.Integer, primary_key=True)
    nama_kategori = db.Column(db.String(100), unique=True, nullable=False)
    
    def __repr__(self):
        return f'<KategoriBuku {self.nama_kategori}>'
