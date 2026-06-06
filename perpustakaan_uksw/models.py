from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Pengguna(UserMixin, db.Model):
    """Model untuk pengguna sistem (mahasiswa, dosen, petugas, admin)"""
    __tablename__ = 'pengguna'
    
    id = db.Column(db.Integer, primary_key=True)
    nim_nip = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nama = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    peran = db.Column(db.String(20), nullable=False)  # 'mahasiswa', 'dosen', 'petugas', 'admin'
    prodi = db.Column(db.String(100))  # Program studi (untuk mahasiswa/dosen)
    is_aktif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relasi ke peminjaman
    peminjaman_aktif = db.relationship('Peminjaman', backref='peminjam', 
                                        lazy='dynamic', 
                                        primaryjoin='and_(Pengguna.id==Peminjaman.pengguna_id, Peminjaman.tgl_kembali==None)')
    semua_peminjaman = db.relationship('Peminjaman', backref='semua_peminjam', lazy='dynamic')
    reservasi = db.relationship('Reservasi', backref='pemesan', lazy='dynamic')
    
    def set_password(self, password):
        """Hash password sebelum disimpan"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Cek apakah password cocok dengan hash"""
        return check_password_hash(self.password_hash, password)
    
    def get_nama_peran(self):
        """Mengembalikan nama peran dalam bahasa Indonesia"""
        role_map = {
            'mahasiswa': 'Mahasiswa',
            'dosen': 'Dosen',
            'petugas': 'Petugas Perpustakaan',
            'admin': 'Admin/Super Petugas'
        }
        return role_map.get(self.peran, self.peran)
    
    def __repr__(self):
        return f'<Pengguna {self.nama} ({self.nim_nip})>'


class Buku(db.Model):
    """Model untuk koleksi buku perpustakaan"""
    __tablename__ = 'buku'
    
    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(20), unique=True, nullable=False, index=True)
    judul = db.Column(db.String(200), nullable=False)
    pengarang = db.Column(db.String(100), nullable=False)
    penerbit = db.Column(db.String(100))
    tahun_terbit = db.Column(db.Integer)
    kategori = db.Column(db.String(50))  # Misalnya: 'Teknologi', 'Sastra', 'Sains'
    stok_total = db.Column(db.Integer, default=1)
    stok_tersedia = db.Column(db.Integer, default=1)
    deskripsi = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relasi ke peminjaman dan reservasi
    peminjaman_aktif = db.relationship('Peminjaman', backref='buku_dipinjam',
                                        lazy='dynamic',
                                        primaryjoin='and_(Buku.id==Peminjaman.buku_id, Peminjaman.tgl_kembali==None)')
    reservasi_aktif = db.relationship('Reservasi', backref='buku_dipesan', lazy='dynamic',
                                       primaryjoin='and_(Buku.id==Reservasi.buku_id, Reservasi.status=="menunggu")')
    
    def __repr__(self):
        return f'<Buku {self.judul}>'


class Peminjaman(db.Model):
    """Model untuk transaksi peminjaman buku"""
    __tablename__ = 'peminjaman'
    
    id = db.Column(db.Integer, primary_key=True)
    pengguna_id = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    buku_id = db.Column(db.Integer, db.ForeignKey('buku.id'), nullable=False)
    tgl_pinjam = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    tgl_jatuh_tempo = db.Column(db.DateTime, nullable=False)
    tgl_kembali = db.Column(db.DateTime)  # NULL jika belum dikembalikan
    denda = db.Column(db.Integer, default=0)  # Dalam rupiah
    status_denda = db.Column(db.String(20), default='belum_lunas')  # 'belum_lunas', 'lunas'
    diperpanjang = db.Column(db.Boolean, default=False)  # Apakah sudah pernah diperpanjang
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def hitung_denda(self):
        """Hitung denda jika terlambat mengembalikan"""
        if self.tgl_kembali and self.tgl_kembali > self.tgl_jatuh_tempo:
            hari_terlambat = (self.tgl_kembali - self.tgl_jatuh_tempo).days
            return hari_terlambat * 500
        return 0
    
    def __repr__(self):
        return f'<Peminjaman ID:{self.id} - {self.peminjam.nama}>'


class Reservasi(db.Model):
    """Model untuk reservasi/pesanan buku yang sedang dipinjam"""
    __tablename__ = 'reservasi'
    
    id = db.Column(db.Integer, primary_key=True)
    pengguna_id = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    buku_id = db.Column(db.Integer, db.ForeignKey('buku.id'), nullable=False)
    tgl_reservasi = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(20), default='menunggu')  # 'menunggu', 'siap_diambil', 'selesai', 'dibatalkan'
    antrian_ke = db.Column(db.Integer)  # Posisi antrian
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Reservasi ID:{self.id} - {self.pemesan.nama}>'
