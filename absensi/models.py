from django.db import models


class User(models.Model):
    # Field ini akan menjadi primary key yang auto-increment
    id_user = models.AutoField(primary_key=True)
    username = models.CharField(max_length=255, unique=True)
    # Django akan menangani hashing secara otomatis, kita hanya simpan hasilnya.
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=50)
    nama_lengkap = models.CharField(max_length=255, blank=True, null=True)

    # Opsi 'choices' adalah cara Django untuk menangani ENUM
    STATUS_AKUN_CHOICES = [
        ("Aktif", "Aktif"),
        ("Tidak Aktif", "Tidak Aktif"),
    ]
    status_akun = models.CharField(
        max_length=15, choices=STATUS_AKUN_CHOICES, default="Aktif"
    )

    class Meta:
        # Memberi tahu Django untuk menggunakan tabel 'users' yang sudah ada
        db_table = "users"

    def __str__(self):
        return self.nama_lengkap or self.username


class Pegawai(models.Model):
    id_pegawai = models.AutoField(primary_key=True)
    # OneToOneField digunakan karena id_user di tabel pegawai bersifat UNIQUE.
    # Ini menandakan hubungan satu-ke-satu dengan tabel User.
    id_user = models.OneToOneField(User, on_delete=models.CASCADE, db_column="id_user")
    nip = models.CharField(max_length=50, unique=True, blank=True, null=True)
    nama_lengkap = models.CharField(max_length=255, blank=True, null=True)
    jabatan = models.CharField(max_length=100, blank=True, null=True)

    STATUS_PEGAWAI_CHOICES = [
        ("Aktif", "Aktif"),
        ("Tidak Aktif", "Tidak Aktif"),
    ]
    status_pegawai = models.CharField(
        max_length=15, choices=STATUS_PEGAWAI_CHOICES, default="Aktif"
    )

    class Meta:
        db_table = "pegawai"

    def __str__(self):
        return self.nama_lengkap


class DataWajah(models.Model):
    id_wajah = models.AutoField(primary_key=True)
    id_user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="id_user")
    data_embedding = models.FileField(upload_to="face_datasets/")
    tanggal_enroll = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "data_wajah"


class Absensi(models.Model):
    id_absensi = models.AutoField(primary_key=True)
    id_pegawai = models.ForeignKey(
        Pegawai, on_delete=models.CASCADE, db_column="id_pegawai"
    )
    waktu_absensi = models.DateTimeField()

    TIPE_ABSENSI_CHOICES = [
        ("Masuk", "Masuk"),
        ("Pulang", "Pulang"),
    ]
    tipe_absensi = models.CharField(max_length=10, choices=TIPE_ABSENSI_CHOICES)

    STATUS_VERIFIKASI_CHOICES = [
        ("Berhasil", "Berhasil"),
        ("Gagal", "Gagal"),
    ]
    status_verifikasi = models.CharField(
        max_length=10, choices=STATUS_VERIFIKASI_CHOICES
    )

    foto_bukti = models.FileField(upload_to="absensi_bukti/", blank=True, null=True)
    koordinat_lokasi = models.CharField(max_length=255, blank=True, null=True)

    JENIS_KERJA_CHOICES = [
        ("WFO", "Work From Office"),
        ("WFH", "Work From Home"),
    ]
    jenis_kerja = models.CharField(
        max_length=3, choices=JENIS_KERJA_CHOICES, default="WFO"
    )

    class Meta:
        db_table = "absensi"

    def __str__(self):
        return f"{self.id_pegawai.nama_lengkap} - {self.tipe_absensi} pada {self.waktu_absensi}"


class Lokasi(models.Model):
    nama = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        db_table = "lokasi"

    def __str__(self):
        return self.nama


# Di dalam absensi/models.py
# HAPUS SEMUA DEFINISI 'Perizinan' YANG LAMA, DAN GANTI DENGAN YANG SATU INI.


class Perizinan(models.Model):
    DIAJUKAN = "Diajukan"
    DISETUJUI = "Disetujui"
    DITOLAK = "Ditolak"
    STATUS_PENGAJUAN_CHOICES = [
        (DIAJUKAN, "Diajukan"),
        (DISETUJUI, "Disetujui"),
        (DITOLAK, "Ditolak"),
    ]
    # Field ini disamakan persis dengan kolom di database Anda
    id_izin = models.AutoField(primary_key=True)

    # Kunci perbaikan untuk error awal: db_column='id_pegawai'
    id_pegawai = models.ForeignKey(
        Pegawai, on_delete=models.CASCADE, db_column="id_pegawai"
    )

    tanggal_awal = models.DateField()
    tanggal_akhir = models.DateField()

    # Sesuaikan CHOICES dengan ENUM di database
    JENIS_IZIN_CHOICES = [
        ("Sakit", "Sakit"),
        ("Izin", "Izin"),
        ("Cuti", "Cuti"),  # Di DB hanya 'Cuti'
    ]
    jenis_izin = models.CharField(max_length=15, choices=JENIS_IZIN_CHOICES)

    keterangan = models.TextField()
    file_lampiran = models.FileField(upload_to="lampiran_izin/", blank=True, null=True)

    STATUS_PENGAJUAN_CHOICES = [
        ("Diajukan", "Diajukan"),
        ("Disetujui", "Disetujui"),
        ("Ditolak", "Ditolak"),
    ]
    status_pengajuan = models.CharField(
        max_length=15, choices=STATUS_PENGAJUAN_CHOICES, default="Diajukan"
    )

    # Biarkan Django mengatur ini secara otomatis saat pembuatan
    tanggal_pengajuan = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Beri tahu Django nama tabel yang benar
        db_table = "absensi_perizinan"

    def __str__(self):
        # Gunakan nama field yang benar
        return f"Izin {self.jenis_izin} oleh {self.id_pegawai.nama_lengkap}"
