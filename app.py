# Aplikasi POS (Point of Sale) Toko
# Dibangun dengan Flask dan MongoDB
# Mengelola login, penjualan, master data (karyawan, produk, kategori, shift), 
# serta kontrol akses berbasis peran (admin dan kasir)
# Semua operasi waktu menggunakan zona WIB (Waktu Indonesia Barat)

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, abort
from pymongo import MongoClient
from bson import ObjectId
from functools import wraps
from datetime import datetime, timedelta
import pytz
import bcrypt

# --- Konfigurasi Timezone WIB ---
# WIB digunakan sebagai acuan utama untuk semua operasi waktu
WIB = pytz.timezone('Asia/Jakarta')

# Fungsi bantu: mengembalikan waktu saat ini dalam format naive (tanpa timezone info)
# Digunakan untuk penyimpanan konsisten di MongoDB
def now_wib_naive():
    return datetime.now(WIB).replace(tzinfo=None)

# --- Inisialisasi Flask ---
app = Flask(__name__)
app.secret_key = 'pos_system_secret_key_raihan_agil'

# --- Koneksi MongoDB ---
# Menghubungkan ke database MongoDB Atlas
MONGO_URI = "mongodb+srv://agil:agil@agil.v9koihu.mongodb.net/?appName=agil"
client = MongoClient(MONGO_URI)
db = client['POS_TOKO']

# Collections (tabel data) yang digunakan
karyawan_col = db['master_karyawan']
product_col = db['master_product']
kategori_col = db['master_kategori']
shift_col = db['master_shift']
sales_col = db['Sales']

# --- Mapping nama hari dari bahasa Inggris ke Indonesia ---
DAY_MAP = {
    "Monday": "Senin",
    "Tuesday": "Selasa",
    "Wednesday": "Rabu",
    "Thursday": "Kamis",
    "Friday": "Jumat",
    "Saturday": "Sabtu",
    "Sunday": "Minggu"
}

# Urutan hari untuk keperluan sorting (misal: tampilan jadwal)
HARI_URUT = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

# --- Fungsi bantu untuk keamanan password ---
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    if isinstance(hashed, str):
        hashed = hashed.encode('utf-8')
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

# --- Validasi shift kasir ---
# Memeriksa apakah karyawan (kasir) sedang dalam jam kerja yang sah
def validate_kasir_shift(user_id):
    now = now_wib_naive()
    hari_ini = DAY_MAP.get(now.strftime("%A"), now.strftime("%A"))
    current_time = now.time()

    # Cari shift aktif untuk karyawan pada hari ini
    shift = shift_col.find_one({
        'karyawanId': ObjectId(user_id),
        'hari': {'$in': [hari_ini]},
        'isActive': True
    })

    if not shift:
        return False, "Anda tidak memiliki jadwal shift hari ini. Silakan hubungi admin."

    # Parsing jam masuk dan keluar dari string "HH:MM"
    try:
        jam_masuk = datetime.strptime(shift['jamMasuk'], "%H:%M").time()
        jam_keluar = datetime.strptime(shift['jamKeluar'], "%H:%M").time()
    except Exception:
        return False, "Konfigurasi jam shift tidak valid. Silakan hubungi admin."

    # Periksa apakah waktu sekarang berada dalam rentang shift
    dalam_shift = False
    # Handle kasus shift malam (misal: 22.00 – 06.00)
    if jam_masuk > jam_keluar:
        if current_time >= jam_masuk or current_time <= jam_keluar:
            dalam_shift = True
    else:
        if jam_masuk <= current_time <= jam_keluar:
            dalam_shift = True

    if not dalam_shift:
        jam_masuk_str = jam_masuk.strftime("%H:%M")
        jam_keluar_str = jam_keluar.strftime("%H:%M")
        return False, f"Di luar jam shift Anda ({jam_masuk_str}–{jam_keluar_str}). Silakan hubungi admin."

    return True, ""

# --- Cari shift berdasarkan karyawan dan template ---
# Digunakan saat menyimpan shift baru untuk mencegah duplikasi
def find_relevant_shift(karyawan_id_obj, shift_template_id):
    return shift_col.find_one({
        "karyawanId": karyawan_id_obj,
        "shiftTemplateId": shift_template_id
    })

# --- Fungsi bantu: konversi dokumen MongoDB agar bisa dikirim via JSON ---
def serialize_doc(doc):
    if doc:
        doc['_id'] = str(doc['_id'])
        if 'karyawanId' in doc and isinstance(doc['karyawanId'], ObjectId):
            doc['karyawanId'] = str(doc['karyawanId'])
        if 'kasirId' in doc and isinstance(doc['kasirId'], ObjectId):
            doc['kasirId'] = str(doc['kasirId'])
    return doc

def serialize_list(docs):
    return [serialize_doc(doc) for doc in docs]

# --- Decorator untuk membatasi akses berdasarkan peran ---
def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Untuk permintaan API (JSON)
            if request.headers.get('Accept', '').startswith('application/json') or request.path.startswith('/api/'):
                if 'role' not in session:
                    return jsonify({'error': 'Unauthorized'}), 401
                if session['role'] not in allowed_roles:
                    return jsonify({'error': 'Forbidden'}), 403
            # Untuk halaman web biasa
            else:
                if 'role' not in session:
                    return redirect(url_for('login'))
                if session['role'] not in allowed_roles:
                    abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Middleware: validasi shift untuk kasir sebelum setiap request ---
# Dicek sebelum setiap halaman dibuka (kecuali halaman yang diizinkan)
@app.before_request
def check_shift_validity():
    # Daftar endpoint yang boleh diakses meskipun shift tidak valid
    allowed_endpoints = [
        'login', 'static', 'logout',
        'api_active_products',
        'api_sales_years', 'api_sales_months_for_year',
        'api_sales_daily', 'api_sales_history', 'api_shifts',
        'api_employees', 'api_employee_detail',
        'api_categories', 'api_products',
        'master_shift', 'print_shift',
        'master_kategori', 'master_product',
        'master_karyawan',
        'sales_page',
        'record_sale',
        'api_shift_valid',
        'receipt_page',
    ]
    
    if request.endpoint in allowed_endpoints:
        return

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'kasir':
        return

    is_valid, _ = validate_kasir_shift(session['user_id'])
    if not is_valid:
        session.clear()
        return redirect(url_for('login'))

# --- Inisialisasi kategori default jika belum ada ---
def init_default_categories():
    if kategori_col.count_documents({}) == 0:
        kategori_col.insert_many([
            {'nama': 'Makanan', 'createdAt': now_wib_naive()},
            {'nama': 'Minuman', 'createdAt': now_wib_naive()}
        ])

# === Routes Utama ===

@app.route('/', methods=['GET', 'POST'])
def login():
    # Tampilkan form login atau proses data login
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('index.html', error='Username dan password harus diisi.')

        user = karyawan_col.find_one({'nama': username})
        if user:
            if not user.get('isActive', False):
                return render_template('index.html', error='Akun tidak aktif. Silakan hubungi admin.')
            
            if not verify_password(password, user['password']):
                return render_template('index.html', error='Username atau password salah.')
            
            # Jika pengguna adalah kasir, validasi shift-nya
            if user.get('role') == 'kasir':
                is_valid, error_msg = validate_kasir_shift(str(user['_id']))
                if not is_valid:
                    return render_template('index.html', error=error_msg)
            
            # Simpan data sesi
            session['user_id'] = str(user['_id'])
            session['username'] = user['nama']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            return render_template('index.html', error='Username atau password salah.')

    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    # Halaman utama setelah login
    if 'username' not in session:
        return redirect(url_for('login'))

    now = now_wib_naive()
    today = now.date()
    yesterday = today - timedelta(days=1)

    active_products = list(product_col.find({'isActive': True}))
    employees = list(karyawan_col.find())
    sales = list(sales_col.find())

    # Pisahkan penjualan hari ini dan kemarin
    today_sales = []
    yesterday_sales = []
    for s in sales:
        if isinstance(s['tanggal'], datetime):
            # Konversi ke WIB untuk perbandingan
            sale_wib = s['tanggal'].astimezone(WIB) if s['tanggal'].tzinfo else s['tanggal'].replace(tzinfo=pytz.UTC).astimezone(WIB)
            sale_date = sale_wib.date()
            if sale_date == today:
                today_sales.append(s)
            elif sale_date == yesterday:
                yesterday_sales.append(s)

    low_stock = len([p for p in active_products if p.get('stok', 0) < 10])
    total_products = len(active_products)

    total_revenue = sum(s['total'] for s in today_sales)
    total_transactions = len(today_sales)
    total_revenue_yesterday = sum(s['total'] for s in yesterday_sales)

    return render_template(
        'dashboard.html',
        username=session['username'],
        role=session['role'],
        total_products=total_products,
        low_stock=low_stock,
        total_revenue=total_revenue,
        total_transactions=total_transactions,
        total_employees=len(employees),
        total_revenue_yesterday=total_revenue_yesterday,
        now=now
    )

# === API untuk laporan penjualan ===

@app.route('/api/sales/years')
def api_sales_years():
    # Ambil semua tahun yang memiliki data penjualan
    years = set()
    for doc in sales_col.find({'tanggal': {'$exists': True}}):
        if isinstance(doc['tanggal'], datetime):
            dt_wib = doc['tanggal'].astimezone(WIB) if doc['tanggal'].tzinfo else doc['tanggal'].replace(tzinfo=pytz.UTC).astimezone(WIB)
            years.add(dt_wib.year)
    return jsonify(sorted(years, reverse=True))

@app.route('/api/sales/months-for-year')
def api_sales_months_for_year():
    # Ambil bulan yang memiliki data penjualan pada tahun tertentu
    try:
        year = int(request.args.get('year', 0))
        if year <= 0:
            return jsonify([])
    except:
        return jsonify([])

    now = now_wib_naive()
    current_year = now.year
    current_month = now.month

    months = set()
    for doc in sales_col.find({'tanggal': {'$exists': True}}):
        if isinstance(doc['tanggal'], datetime):
            dt_wib = doc['tanggal'].astimezone(WIB) if doc['tanggal'].tzinfo else doc['tanggal'].replace(tzinfo=pytz.UTC).astimezone(WIB)
            if dt_wib.year == year:
                if year == current_year and dt_wib.month > current_month:
                    continue
                months.add(dt_wib.month)
    return jsonify(sorted(months))

@app.route('/api/sales/daily')
def api_sales_daily():
    # Ambil data penjualan harian untuk grafik
    try:
        year = int(request.args.get('year'))
        month = int(request.args.get('month'))
        if not (1 <= month <= 12):
            return jsonify({"labels": [], "sales": []})
    except:
        return jsonify({"labels": [], "sales": []})

    from calendar import monthrange
    days_in_month = monthrange(year, month)[1]
    daily_sales = [0] * days_in_month

    for doc in sales_col.find():
        try:
            if 'tanggal' not in doc or 'total' not in doc:
                continue
            dt = doc['tanggal']
            total_val = doc['total']
            if not isinstance(dt, datetime) or not isinstance(total_val, (int, float)) or isinstance(total_val, bool):
                continue
            
            # Konversi ke WIB
            dt_wib = dt.astimezone(WIB) if dt.tzinfo else dt.replace(tzinfo=pytz.UTC).astimezone(WIB)
            
            if dt_wib.year == year and dt_wib.month == month:
                day = dt_wib.day
                if 1 <= day <= days_in_month:
                    daily_sales[day - 1] += int(float(total_val))
        except:
            continue

    labels = [str(d) for d in range(1, days_in_month + 1)]
    return {
        "labels": labels,
        "sales": [int(x) for x in daily_sales]
    }

@app.route('/api/sales/history')
def api_sales_history():
    # Ambil riwayat penjualan (kasir hanya lihat miliknya sendiri)
    now = now_wib_naive()
    try:
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
    except:
        year = now.year
        month = now.month

    # Buat rentang waktu dalam WIB
    start_wib = WIB.localize(datetime(year, month, 1))
    if month == 12:
        end_wib = WIB.localize(datetime(year + 1, 1, 1))
    else:
        end_wib = WIB.localize(datetime(year, month + 1, 1))

    # Konversi ke UTC untuk query MongoDB
    start_utc = start_wib.astimezone(pytz.UTC)
    end_utc = end_wib.astimezone(pytz.UTC)

    query = {
        'tanggal': {
            '$gte': start_utc,
            '$lt': end_utc
        }
    }

    # Jika pengguna adalah kasir, batasi hanya transaksinya sendiri
    if 'role' in session and session['role'] == 'kasir':
        query['kasirId'] = ObjectId(session['user_id'])

    sales = list(sales_col.find(query).sort('tanggal', -1))

    # Siapkan data untuk respons JSON
    for s in sales:
        s['_id'] = str(s['_id'])
        if 'kasirId' in s:
            s['kasirId'] = str(s['kasirId'])
        if isinstance(s['tanggal'], datetime):
            s['tanggal_formatted'] = s['tanggal'].astimezone(WIB).strftime('%d %B %Y, %H.%M.%S')
        else:
            s['tanggal_formatted'] = str(s['tanggal'])

    return jsonify(sales)

@app.route('/api/shift/valid')
def api_shift_valid():
    # API untuk cek real-time apakah shift kasir masih valid
    if session.get('role') != 'kasir' or 'user_id' not in session:
        return jsonify({'valid': False, 'message': 'Unauthorized'}), 401

    is_valid, error_msg = validate_kasir_shift(session['user_id'])
    return jsonify({'valid': is_valid, 'message': error_msg if not is_valid else ''})

# === API untuk manajemen master data ===

@app.route('/api/products/active')
def api_active_products():
    # Digunakan di halaman kasir untuk menampilkan produk yang bisa dijual
    products = serialize_list(product_col.find({'stok': {'$gt': 0}, 'isActive': True}))
    return jsonify(products)

@app.route('/api/products/<product_id>', methods=['PUT'])
@role_required(['admin'])
def update_product(product_id):
    # Update data produk (hanya admin)
    try:
        prod_id = ObjectId(product_id)
    except:
        return jsonify({'error': 'ID Produk tidak valid'}), 400

    if not product_col.find_one({'_id': prod_id}):
        return jsonify({'error': 'Produk tidak ditemukan'}), 404

    data = request.json
    nama = data.get('nama', '').strip()
    harga = data.get('harga')
    stok = data.get('stok')
    kategori = data.get('kategori', '').strip()
    is_active = data.get('isActive', True)

    if not nama:
        return jsonify({'error': 'Nama produk wajib diisi'}), 400
    if harga is None or stok is None:
        return jsonify({'error': 'Harga dan stok wajib diisi'}), 400
    if not kategori:
        return jsonify({'error': 'Kategori wajib diisi'}), 400

    # Cek duplikasi nama produk
    if product_col.find_one({
        '_id': {'$ne': prod_id},
        'nama': {'$regex': f'^{nama}$', '$options': 'i'}
    }):
        return jsonify({'error': 'Nama produk sudah digunakan'}), 400

    # Pastikan kategori ada
    if not kategori_col.find_one({'nama': {'$regex': f'^{kategori}$', '$options': 'i'}}):
        return jsonify({'error': 'Kategori tidak ditemukan'}), 400

    product_col.update_one(
        {'_id': prod_id},
        {'$set': {
            'nama': nama,
            'harga': int(harga),
            'stok': int(stok),
            'kategori': kategori,
            'isActive': is_active,
            'updatedAt': now_wib_naive()
        }}
    )
    return jsonify({'status': 'success'})

# === Halaman Penjualan dan Struk ===

@app.route('/sales')
def sales_page():
    # Halaman untuk mencatat transaksi (bisa diakses admin dan kasir)
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('sales.html', username=session['username'])

@app.route('/receipt/<sale_id>')
def receipt_page(sale_id):
    # Tampilkan struk penjualan tertentu
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            obj_id = ObjectId(sale_id)
        except InvalidId:
            abort(404)

        sale = sales_col.find_one({'_id': obj_id})
        if not sale:
            abort(404)

        # Pastikan kasir hanya bisa lihat struk miliknya
        if session['role'] == 'kasir' and str(sale.get('kasirId')) != session['user_id']:
            abort(403)

        if isinstance(sale['tanggal'], datetime):
            sale['tanggal_formatted'] = sale['tanggal'].astimezone(WIB).strftime('%d %B %Y, %H.%M.%S')
        else:
            sale['tanggal_formatted'] = str(sale['tanggal'])

        return render_template('receipt.html', sale=sale)

    except Exception:
        abort(404)

@app.route('/api/sales', methods=['POST'])
@role_required(['kasir', 'admin'])
def record_sale():
    # Simpan transaksi penjualan dan kurangi stok
    data = request.json

    raw_items = data.get('items', [])
    if not isinstance(raw_items, list):
        return jsonify({'error': 'Invalid items format'}), 400

    safe_items = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        safe_items.append({
            'productId': str(item.get('productId', '')),
            'nama': str(item.get('nama', '')),
            'harga': int(item.get('harga', 0)),
            'quantity': int(item.get('quantity', 0)),
            'subtotal': int(item.get('subtotal', 0))
        })

    if not safe_items:
        return jsonify({'error': 'No valid items'}), 400

    total = int(data.get('total', 0))
    dibayar = int(data.get('dibayar', 0))
    kembalian = int(data.get('kembalian', 0))

    # Simpan transaksi
    result = sales_col.insert_one({
        'tanggal': now_wib_naive(),
        'kasirId': ObjectId(session['user_id']),
        'kasirNama': session['username'],
        'items': safe_items,
        'total': total,
        'dibayar': dibayar,
        'kembalian': kembalian,
        'createdAt': now_wib_naive()
    })

    # Kurangi stok setiap produk yang terjual
    for item in safe_items:
        product_col.update_one(
            {'_id': ObjectId(item['productId'])},
            {'$inc': {'stok': -item['quantity']}},
            upsert=False
        )

    return jsonify({'status': 'success', 'saleId': str(result.inserted_id)})

# === Halaman Master (Admin Only) ===

@app.route('/master_karyawan')
@role_required(['admin'])
def master_karyawan():
    employees = serialize_list(karyawan_col.find())
    return render_template('master_karyawan.html', employees=employees)

@app.route('/master_product')
@role_required(['admin'])
def master_product():
    total_categories = kategori_col.count_documents({})
    return render_template('master_product.html', total_categories=total_categories)

@app.route('/master_kategori')
@role_required(['admin'])
def master_kategori():
    categories = list(kategori_col.find({}))
    return render_template('master_kategori.html', categories=categories)

@app.route('/master_shift')
@role_required(['admin'])
def master_shift():
    return render_template('master_shift.html')

# === API: Kategori Produk ===
@app.route('/api/categories', methods=['GET', 'POST', 'PUT'])
@role_required(['admin'])
def api_categories():
    if request.method == 'POST':
        data = request.json
        nama = data.get('nama', '').strip()
        if not nama:
            return jsonify({'error': 'Nama kategori wajib diisi'}), 400
        if kategori_col.find_one({'nama': {'$regex': f'^{nama}$', '$options': 'i'}}):
            return jsonify({'error': 'Kategori sudah ada'}), 400
        kategori_col.insert_one({'nama': nama, 'createdAt': now_wib_naive()})
        return jsonify({'status': 'success'}), 201
    
    elif request.method == 'PUT':
        data = request.json
        category_id = data.get('id')
        nama = data.get('nama', '').strip()
        if not category_id or not nama:
            return jsonify({'error': 'ID dan nama wajib diisi'}), 400
        try:
            cat_id_obj = ObjectId(category_id)
        except:
            return jsonify({'error': 'ID tidak valid'}), 400
        if kategori_col.find_one({'_id': {'$ne': cat_id_obj}, 'nama': {'$regex': f'^{nama}$', '$options': 'i'}}):
            return jsonify({'error': 'Nama sudah digunakan'}), 400
        kategori_col.update_one({'_id': cat_id_obj}, {'$set': {'nama': nama, 'updatedAt': now_wib_naive()}})
        return jsonify({'status': 'success'})
    
    else:
        categories = list(kategori_col.find({}))
        return jsonify(serialize_list(categories))

# === API: Karyawan ===
@app.route('/api/employees', methods=['GET', 'POST'])
@role_required(['admin'])
def api_employees():
    if request.method == 'POST':
        data = request.json
        nama = data['nama'].strip()
        email = data['email'].strip()
        password = data['password']
        if not nama or not email:
            return jsonify({'status': 'error', 'message': 'Nama dan email wajib diisi.'}), 400
        if karyawan_col.find_one({'nama': {'$regex': f'^{nama}$', '$options': 'i'}}):
            return jsonify({'status': 'error', 'message': 'Nama sudah digunakan.'}), 400
        if karyawan_col.find_one({'email': {'$regex': f'^{email}$', '$options': 'i'}}):
            return jsonify({'status': 'error', 'message': 'Email sudah digunakan.'}), 400
        if len(password) < 6 or len(password) > 10:
            return jsonify({'status': 'error', 'message': 'Password harus 6-10 karakter.'}), 400

        total = karyawan_col.count_documents({})
        next_no = total + 1
        id_karyawan = f"K{next_no:04d}"

        karyawan_col.insert_one({
            'id_karyawan': id_karyawan,
            'nama': nama,
            'email': email,
            'password': hash_password(password),
            'role': data['role'],
            'isActive': bool(data.get('isActive', True)),
            'createdAt': now_wib_naive()
        })
        return jsonify({'status': 'success'})
    else:
        employees = serialize_list(karyawan_col.find())
        return jsonify(employees)

@app.route('/api/employees/<id>', methods=['PUT'])
@role_required(['admin'])
def api_employee_detail(id):
    data = request.json
    nama = data['nama'].strip()
    email = data['email'].strip()
    if not nama or not email:
        return jsonify({'status': 'error', 'message': 'Nama dan email wajib diisi.'}), 400

    existing_nama = karyawan_col.find_one({
        '_id': {'$ne': ObjectId(id)},
        'nama': {'$regex': f'^{nama}$', '$options': 'i'}
    })
    if existing_nama:
        return jsonify({'status': 'error', 'message': 'Nama sudah digunakan.'}), 400

    existing_email = karyawan_col.find_one({
        '_id': {'$ne': ObjectId(id)},
        'email': {'$regex': f'^{email}$', '$options': 'i'}
    })
    if existing_email:
        return jsonify({'status': 'error', 'message': 'Email sudah digunakan.'}), 400

    update_data = {
        'nama': nama,
        'email': email,
        'role': data['role'],
        'isActive': bool(data.get('isActive', True)),
        'updatedAt': now_wib_naive()
    }
    if data.get('password'):
        if 6 <= len(data['password']) <= 10:
            update_data['password'] = hash_password(data['password'])
        else:
            return jsonify({'status': 'error', 'message': 'Password harus 6-10 karakter.'}), 400

    karyawan_col.update_one({'_id': ObjectId(id)}, {'$set': update_data})

    # Jika karyawan dinonaktifkan, nonaktifkan juga semua shift-nya
    if not data.get('isActive', True):
        shift_col.update_many({'karyawanId': ObjectId(id)}, {'$set': {'isActive': False}})

    return jsonify({'status': 'success'})

# === API: Produk ===
@app.route('/api/products', methods=['GET', 'POST'])
@role_required(['admin'])
def api_products():
    if request.method == 'POST':
        data = request.json
        nama = data['nama'].strip()
        if not nama:
            return jsonify({'error': 'Nama produk wajib diisi'}), 400
        if product_col.find_one({'nama': {'$regex': f'^{nama}$', '$options': 'i'}}):
            return jsonify({'error': 'Nama produk sudah digunakan'}), 400

        kategori_input = data.get('kategori', '').strip()
        if not kategori_input:
            return jsonify({'error': 'Kategori tidak boleh kosong'}), 400
        if not kategori_col.find_one({'nama': {'$regex': f'^{kategori_input}$', '$options': 'i'}}):
            return jsonify({'error': 'Kategori tidak ditemukan.'}), 400

        total = product_col.count_documents({})
        next_no = total + 1
        id_produk = f"P{next_no:04d}"

        product_col.insert_one({
            'id_produk': id_produk,
            'nama': nama,
            'harga': int(data['harga']),
            'stok': int(data['stok']),
            'kategori': kategori_input,
            'isActive': data.get('isActive', True),
            'createdAt': now_wib_naive()
        })
        return jsonify({'status': 'success'})
    else:
        products = serialize_list(product_col.find())
        return jsonify(products)

# === API: Shift Karyawan ===
@app.route('/api/shifts', methods=['GET', 'POST'])
@role_required(['admin'])
def api_shifts():
    if request.method == 'POST':
        data = request.json
        required = ['shiftTemplateId', 'karyawanId', 'hari', 'status', 'jamMasuk', 'jamKeluar']
        if not all(k in data for k in required):
            return jsonify({"error": "Data tidak lengkap"}), 400

        try:
            karyawan_id_obj = ObjectId(data['karyawanId'])
        except:
            return jsonify({"error": "ID Karyawan tidak valid"}), 400

        if not karyawan_col.find_one({'_id': karyawan_id_obj}):
            return jsonify({"error": "Karyawan tidak ditemukan"}), 400

        hari = data.get('hari')
        if not isinstance(hari, list) or not hari:
            return jsonify({"error": "Hari kerja tidak valid"}), 400

        shift_template_id = str(data['shiftTemplateId'])
        if shift_template_id not in ['1', '2', '3']:
            return jsonify({"error": "Template shift tidak valid"}), 400

        jam_masuk = data.get('jamMasuk', '').strip()
        jam_keluar = data.get('jamKeluar', '').strip()
        try:
            datetime.strptime(jam_masuk, "%H:%M")
            datetime.strptime(jam_keluar, "%H:%M")
        except ValueError:
            return jsonify({"error": "Format jam tidak valid (HH:MM)"}), 400

        if jam_masuk == jam_keluar:
            return jsonify({"error": "Jam masuk dan keluar tidak boleh sama"}), 400

        is_active = data['status'] == 'aktif'

        # Cari apakah shift untuk karyawan + template ini sudah ada (upsert)
        existing_shift = find_relevant_shift(karyawan_id_obj, shift_template_id)

        update_data = {
            "karyawanId": karyawan_id_obj,
            "shiftTemplateId": shift_template_id,
            "hari": hari,
            "isActive": is_active,
            "jamMasuk": jam_masuk,
            "jamKeluar": jam_keluar,
        }

        if existing_shift:
            update_data["updatedAt"] = now_wib_naive()
            shift_col.update_one({"_id": existing_shift['_id']}, {"$set": update_data})
            updated = shift_col.find_one({"_id": existing_shift['_id']})
        else:
            update_data["createdAt"] = now_wib_naive()
            result = shift_col.insert_one(update_data)
            updated = shift_col.find_one({"_id": result.inserted_id})

        updated['_id'] = str(updated['_id'])
        updated['karyawanId'] = str(updated['karyawanId'])
        updated['shiftTemplateId'] = str(updated['shiftTemplateId'])
        return jsonify(updated), 201 if not existing_shift else 200

    else:
        shifts = list(shift_col.find())
        for shift in shifts:
            shift['_id'] = str(shift['_id'])
            shift['karyawanId'] = str(shift['karyawanId'])
            shift['shiftTemplateId'] = str(shift['shiftTemplateId'])
        return jsonify(shifts)

@app.route('/api/shifts/<shift_id>', methods=['PUT'])
@role_required(['admin'])
def api_update_shift(shift_id):
    # Mirip dengan POST, tapi untuk update spesifik berdasarkan ID
    try:
        shift_obj_id = ObjectId(shift_id)
    except:
        return jsonify({"error": "ID Shift tidak valid"}), 400

    if not shift_col.find_one({'_id': shift_obj_id}):
        return jsonify({"error": "Shift tidak ditemukan"}), 404

    data = request.json
    required = ['shiftTemplateId', 'karyawanId', 'hari', 'status', 'jamMasuk', 'jamKeluar']
    if not all(k in data for k in required):
        return jsonify({"error": "Data tidak lengkap"}), 400

    try:
        karyawan_id_obj = ObjectId(data['karyawanId'])
    except:
        return jsonify({"error": "ID Karyawan tidak valid"}), 400

    if not karyawan_col.find_one({'_id': karyawan_id_obj}):
        return jsonify({"error": "Karyawan tidak ditemukan"}), 400

    hari = data.get('hari')
    if not isinstance(hari, list) or not hari:
        return jsonify({"error": "Hari kerja tidak valid"}), 400

    shift_template_id = str(data['shiftTemplateId'])
    if shift_template_id not in ['1', '2', '3']:
        return jsonify({"error": "Template shift tidak valid"}), 400

    jam_masuk = data.get('jamMasuk', '').strip()
    jam_keluar = data.get('jamKeluar', '').strip()
    try:
        datetime.strptime(jam_masuk, "%H:%M")
        datetime.strptime(jam_keluar, "%H:%M")
    except ValueError:
        return jsonify({"error": "Format jam tidak valid (HH:MM)"}), 400

    if jam_masuk == jam_keluar:
        return jsonify({"error": "Jam masuk dan keluar tidak boleh sama"}), 400

    is_active = data['status'] == 'aktif'

    update_data = {
        "karyawanId": karyawan_id_obj,
        "shiftTemplateId": shift_template_id,
        "hari": hari,
        "isActive": is_active,
        "jamMasuk": jam_masuk,
        "jamKeluar": jam_keluar,
        "updatedAt": now_wib_naive()
    }

    shift_col.update_one({"_id": shift_obj_id}, {"$set": update_data})
    updated = shift_col.find_one({"_id": shift_obj_id})
    updated['_id'] = str(updated['_id'])
    updated['karyawanId'] = str(updated['karyawanId'])
    updated['shiftTemplateId'] = str(updated['shiftTemplateId'])
    return jsonify(updated)

# === Logout ===
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# === Penanganan Error ===
@app.errorhandler(403)
def forbidden(e):
    if request.headers.get('Accept', '').startswith('application/json'):
        return jsonify({'error': 'Forbidden'}), 403
    return render_template('error.html', error_code=403, message="Akses ditolak."), 403

@app.errorhandler(404)
def page_not_found(e):
    if request.headers.get('Accept', '').startswith('application/json'):
        return jsonify({'error': 'Not Found'}), 404
    return render_template('error.html', error_code=404, message="Halaman tidak ditemukan."), 404


if __name__ == '__main__':
    app.run(debug=True)