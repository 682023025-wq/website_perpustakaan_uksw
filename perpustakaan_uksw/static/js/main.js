/**
 * JavaScript utama untuk Perpustakaan UKSW
 * Menangani toggle hamburger menu dan interaksi UI lainnya
 */

document.addEventListener('DOMContentLoaded', function() {
    // Toggle Hamburger Menu untuk Mobile
    const hamburgerBtn = document.getElementById('hamburger-btn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    
    if (hamburgerBtn && sidebar) {
        // Fungsi untuk membuka sidebar
        function openSidebar() {
            sidebar.classList.add('active');
            if (sidebarOverlay) {
                sidebarOverlay.classList.remove('hidden');
            }
            document.body.style.overflow = 'hidden'; // Prevent scroll saat menu terbuka
        }
        
        // Fungsi untuk menutup sidebar
        function closeSidebar() {
            sidebar.classList.remove('active');
            if (sidebarOverlay) {
                sidebarOverlay.classList.add('hidden');
            }
            document.body.style.overflow = ''; // Restore scroll
        }
        
        // Event listener untuk tombol hamburger
        hamburgerBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (sidebar.classList.contains('active')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
        
        // Event listener untuk overlay (klik di luar sidebar)
        if (sidebarOverlay) {
            sidebarOverlay.addEventListener('click', function() {
                closeSidebar();
            });
        }
        
        // Tutup sidebar saat menekan tombol Escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && sidebar.classList.contains('active')) {
                closeSidebar();
            }
        });
    }
    
    // Auto-hide flash messages setelah 5 detik
    const flashMessages = document.querySelectorAll('[role="alert"]');
    flashMessages.forEach(function(message) {
        setTimeout(function() {
            message.style.opacity = '0';
            message.style.transition = 'opacity 0.5s ease';
            setTimeout(function() {
                message.style.display = 'none';
            }, 500);
        }, 5000);
    });
    
    // Konfirmasi sebelum menghapus data
    const deleteButtons = document.querySelectorAll('[data-confirm-delete]');
    deleteButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm-delete') || 'Apakah Anda yakin ingin menghapus data ini?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
    
    // Format angka ke format Rupiah
    window.formatRupiah = function(angka) {
        return new Intl.NumberFormat('id-ID', {
            style: 'currency',
            currency: 'IDR',
            minimumFractionDigits: 0
        }).format(angka);
    };
    
    // Format tanggal ke format Indonesia
    window.formatTanggalIndonesia = function(tanggal) {
        if (!tanggal) return '-';
        const date = new Date(tanggal);
        return date.toLocaleDateString('id-ID', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    };
    
    // Search box auto-submit saat enter ditekan
    const searchInputs = document.querySelectorAll('[data-search-auto-submit]');
    searchInputs.forEach(function(input) {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const form = this.closest('form');
                if (form) {
                    form.submit();
                }
            }
        });
    });
    
    // Modal/Dialog sederhana
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            document.body.style.overflow = 'hidden';
        }
    };
    
    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
            document.body.style.overflow = '';
        }
    };
    
    // Inisialisasi tooltips (jika ada)
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    tooltipElements.forEach(function(el) {
        el.addEventListener('mouseenter', function() {
            const tooltipText = this.getAttribute('data-tooltip');
            // Implementasi tooltip bisa ditambahkan di sini
        });
    });
    
    console.log('✅ JavaScript Perpustakaan UKSW telah dimuat');
});
