from django.urls import path
from . import views
from django.views.generic.base import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="login", permanent=False)),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_admin_view, name="dashboard_admin"),
    path("karyawan/", views.karyawan_list_view, name="karyawan_list"),
    path(
        "karyawan/edit/<int:id_pegawai>/",
        views.karyawan_edit_view,
        name="karyawan_edit",
    ),
    path(
        "karyawan/hapus/<int:id_pegawai>/",
        views.karyawan_hapus_view,
        name="karyawan_hapus",
    ),
    # Path karyawan
    path("pegawai/dashboard/", views.dashboard_pegawai_view, name="dashboard_pegawai"),
    path("pegawai/absensi/", views.absensi_view, name="absensi"),
    path("pegawai/riwayat/", views.riwayat_absensi_view, name="riwayat_absensi"),
    path("pegawai/izin/", views.ajukan_izin_view, name="ajukan_izin"),
    path("pegawai/izin/riwayat/", views.riwayat_izin_view, name="riwayat_izin"),
    path("data-lokasi/", views.data_lokasi_view, name="data_lokasi"),
    path("data-absensi/", views.data_absensi_view, name="data_absensi"),
    path(
        "laporan/absensi/cetak/<str:tanggal>/",
        views.cetak_laporan_absensi,
        name="cetak_laporan_absensi",
    ),
    path("data-wajah/", views.data_wajah_view, name="data_wajah"),
    path(
        "api/get-wajah/<int:id_pegawai>/",
        views.get_data_wajah_api,
        name="api_get_data_wajah",
    ),
    path("tambah-wajah/", views.tambah_data_wajah_view, name="tambah_data_wajah"),
    path(
        "api/hapus-wajah/<int:id_wajah>/",
        views.hapus_data_wajah_api,
        name="api_hapus_wajah",
    ),
    path(
        "proses-absensi-manual/",
        views.proses_absensi_manual_view,
        name="proses_absensi_manual",
    ),
    path(
        "laporan/absensi/rentang/<str:tanggal_awal>/<str:tanggal_akhir>/",
        views.cetak_laporan_rentang,
        name="cetak_laporan_rentang",
    ),
    path("admin/perizinan/", views.kelola_perizinan_view, name="kelola_perizinan"),
    path(
        "admin/perizinan/update/<int:id_izin>/",
        views.update_status_izin_view,
        name="update_status_izin",
    ),
    path("pengajuan-izin/", views.daftar_pengajuan_izin, name="daftar_pengajuan_izin"),
    path(
        "verifikasi-izin/<int:id_izin>/<str:aksi>/",
        views.verifikasi_izin,
        name="verifikasi_izin",
    ),
    path(
        "perizinan/detail/<int:id_izin>/",
        views.detail_perizinan,
        name="detail_perizinan",
    ),path('absensi/hadir-hari-ini/', views.absensi_hari_ini_view, name='absensi_hari_ini'),
    path("perizinan/kelola/", views.kelola_perizinan_view, name="kelola_perizinan"),path('absensi/hadir-hari-ini/', views.absensi_hari_ini_view, name='absensi_hari_ini'),path('absensi/hadir-hari-ini/', views.absensi_hari_ini_view, name='absensi_hari_ini'),
    path('absensi/belum-absen-hari-ini/', views.belum_absen_hari_ini_view, name='belum_absen_hari_ini'),
    # path('data-master/pegawai/', views.tampil_semua_pegawai, name='daftar_pegawai_view'),
]
