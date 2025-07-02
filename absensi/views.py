from django.shortcuts import render, redirect
from .models import (
    User,
    Pegawai,
    Absensi,
    DataWajah,
    Lokasi,
    Perizinan as AbsensiPerizinan,
)
from django.utils import timezone
import bcrypt
from django.db import transaction  # Impor transaction
from django.contrib import messages  # Impor messages framework
from django.core.files.storage import default_storage  # Impor storage
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import base64
from django.core.files.base import ContentFile
import json
from datetime import datetime
from .face_recognition_utils import train_model, recognize_face, is_model_trained
import numpy as np
import cv2
import math

from datetime import datetime, time, timedelta

from .forms import KaryawanForm, IzinForm, AbsensiManualForm, Perizinan
from .models import Pegawai, Absensi
from .face_recognition_utils import train_model, recognize_face
from django.urls import reverse

from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from collections import defaultdict


def login_view(request):
    request.session.flush()

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        error_message = None

        try:
            user = User.objects.get(username=username, status_akun="Aktif")

            if bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8")):
                # === PERBAIKAN UTAMA DI SINI ===

                # Normalisasi role: hapus spasi dan ubah ke huruf kecil
                role = user.role.strip().lower()

                if role == "admin":
                    request.session["admin_logged_in"] = True
                    request.session["admin_id_user"] = user.id_user
                    request.session["admin_username"] = user.username
                    request.session["admin_nama_lengkap"] = user.nama_lengkap
                    request.session["admin_role"] = user.role
                    return redirect("dashboard_admin")

                elif role == "pegawai":
                    try:
                        pegawai = Pegawai.objects.get(id_user=user)
                        request.session["pegawai_logged_in"] = True
                        request.session["pegawai_id_user"] = user.id_user
                        request.session["pegawai_id_pegawai"] = pegawai.id_pegawai
                        request.session["pegawai_username"] = user.username
                        request.session["pegawai_nama_lengkap"] = user.nama_lengkap
                        request.session["pegawai_role"] = user.role
                        return redirect("dashboard_pegawai")
                    except Pegawai.DoesNotExist:
                        error_message = (
                            "Data profil pegawai untuk user ini tidak ditemukan."
                        )

                else:
                    # Jika rolenya bukan admin atau pegawai
                    error_message = f"Role '{user.role}' tidak dikenali oleh sistem."
                # === AKHIR PERBAIKAN ===
            else:
                error_message = "Username atau password salah!"

        except User.DoesNotExist:
            error_message = "Username atau password salah!"

        context = {"error_message": error_message}
        return render(request, "absensi/login.html", context)

    return render(request, "absensi/login.html")


def logout_view(request):
    request.session.flush()
    return redirect("login")


def dashboard_admin_view(request):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    # Ambil tanggal hari ini sesuai timezone di settings.py
    today = timezone.localdate()

    # --- [LOGIKA QUERY BARU YANG LEBIH KUAT] ---
    # 1. Tentukan rentang waktu 24 jam untuk hari ini
    start_of_day = timezone.make_aware(datetime.combine(today, time.min))
    end_of_day = timezone.make_aware(datetime.combine(today, time.max))

    # 2. Hitung pegawai yang "Sudah Absen" menggunakan rentang waktu
    # Ini jauh lebih akurat daripada filter __date
    pegawai_sudah_absen_ids = set(
        Absensi.objects.filter(waktu_absensi__range=(start_of_day, end_of_day))
        .values_list('id_pegawai_id', flat=True)
        .distinct()
    )
    total_sudah_absen_hari_ini = len(pegawai_sudah_absen_ids)

    # 3. Hitung total pegawai aktif
    total_pegawai_aktif = Pegawai.objects.filter(status_pegawai='Aktif').count()

    # 4. Hitung yang belum absen
    total_belum_absen_hari_ini = total_pegawai_aktif - total_sudah_absen_hari_ini
    
    context = {
        "total_pegawai_aktif": total_pegawai_aktif,
        "total_hadir_hari_ini": total_sudah_absen_hari_ini,
        "total_belum_absen_hari_ini": max(0, total_belum_absen_hari_ini),
    }

    return render(request, "absensi/dashboard_admin.html", context)

def karyawan_list_view(request):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    if request.method == "POST":
        # if not request.FILES.getlist("data_wajah"):
        #     messages.error(request, "Anda harus mengunggah setidaknya satu foto wajah.")
        #     # Redirect kembali dengan form yang kosong (atau bisa diisi data sebelumnya)
        #     # Kode di bawah ini menangani kasus tersebut
        form = KaryawanForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    nip = form.cleaned_data["nip"]
                    nama_lengkap = form.cleaned_data["nama_lengkap"]
                    jabatan = form.cleaned_data["jabatan"]
                    username = form.cleaned_data["username"]
                    password = form.cleaned_data["password"]
                    status_pegawai = form.cleaned_data["status_pegawai"]

                    hashed_password = bcrypt.hashpw(
                        password.encode("utf-8"), bcrypt.gensalt()
                    )

                    user_baru = User.objects.create(
                        username=username,
                        password=hashed_password.decode("utf-8"),
                        role="Pegawai",
                        nama_lengkap=nama_lengkap,
                        status_akun=status_pegawai,
                    )

                    pegawai_baru = Pegawai.objects.create(
                        id_user=user_baru,
                        nip=nip,
                        nama_lengkap=nama_lengkap,
                        jabatan=jabatan,
                        status_pegawai=status_pegawai,
                    )

                    wajah_files = request.FILES.getlist("data_wajah")
                    for file in wajah_files:
                        # Cukup berikan objek file langsung ke field FileField
                        # Django akan otomatis menangani penyimpanan dan path.
                        DataWajah.objects.create(id_user=user_baru, data_embedding=file)
                    # ==================================

                messages.success(
                    request, f'Karyawan "{nama_lengkap}" berhasil ditambahkan.'
                )

            except Exception as e:
                messages.error(request, f"Gagal menambah karyawan: {e}")

            return redirect("karyawan_list")
        else:
            messages.error(
                request, "Form tidak valid. Silakan periksa kembali data yang diinput."
            )

    form = KaryawanForm()
    semua_karyawan_qs = Pegawai.objects.select_related("id_user").order_by(
        "nama_lengkap"
    )

    semua_karyawan_json = list(
        semua_karyawan_qs.values(
            "id_pegawai",
            "nip",
            "nama_lengkap",
            "jabatan",
            "status_pegawai",
            "id_user__username",  # Ambil username dari relasi
        )
    )

    context = {
        "semua_karyawan": semua_karyawan_qs,  # Untuk perulangan di tabel
        "semua_karyawan_json": semua_karyawan_json,  # Untuk Javascript/Alpine.js
        "form": form,
    }

    return render(request, "absensi/karyawan_list.html", context)


@transaction.atomic
def karyawan_edit_view(request, id_pegawai):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    try:
        pegawai = Pegawai.objects.select_related("id_user").get(id_pegawai=id_pegawai)
        user = pegawai.id_user
    except Pegawai.DoesNotExist:
        messages.error(request, "Pegawai tidak ditemukan.")
        return redirect("karyawan_list")

    if request.method == "POST":
        form = KaryawanForm(request.POST, request.FILES)
        if form.is_valid():
            # Update data User
            user.username = form.cleaned_data["username"]
            user.nama_lengkap = form.cleaned_data["nama_lengkap"]
            user.status_akun = form.cleaned_data["status_pegawai"]
            password = form.cleaned_data.get("password")
            if password:  # Hanya update password jika diisi
                hashed_password = bcrypt.hashpw(
                    password.encode("utf-8"), bcrypt.gensalt()
                )
                user.password = hashed_password.decode("utf-8")
            user.save()

            # Update data Pegawai
            pegawai.nip = form.cleaned_data["nip"]
            pegawai.nama_lengkap = form.cleaned_data["nama_lengkap"]
            pegawai.jabatan = form.cleaned_data["jabatan"]
            pegawai.status_pegawai = form.cleaned_data["status_pegawai"]
            pegawai.save()

            # Proses upload foto wajah baru jika ada
            wajah_files = request.FILES.getlist("data_wajah")
            if wajah_files:
                # Hapus data wajah lama (opsional, tapi disarankan)
                DataWajah.objects.filter(id_user=user).delete()
                # Hapus file lama dari storage (lebih advance, bisa ditambahkan nanti)

                user_dataset_path = f"face_datasets/{user.id_user}"
                for index, file in enumerate(wajah_files):
                    file_name = f"User.{user.id_user}.{index + 1}.jpg"
                    saved_path = default_storage.save(
                        os.path.join(user_dataset_path, file_name), file
                    )
                    DataWajah.objects.create(id_user=user, data_embedding=saved_path)

            messages.success(
                request, f'Data karyawan "{pegawai.nama_lengkap}" berhasil diperbarui.'
            )
            return redirect("karyawan_list")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect("karyawan_list")
    messages.error(request, "Metode tidak valid.")
    return redirect("karyawan_list")


def karyawan_hapus_view(request, id_pegawai):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    try:
        pegawai = Pegawai.objects.get(id_pegawai=id_pegawai)
        user = pegawai.id_user
        nama_pegawai = pegawai.nama_lengkap

        user.delete()

        messages.success(
            request,
            f'Karyawan "{nama_pegawai}" dan semua data terkait berhasil dihapus.',
        )
    except Pegawai.DoesNotExist:
        messages.error(request, "Pegawai tidak ditemukan.")
    except Exception as e:
        messages.error(request, f"Gagal menghapus karyawan: {e}")

    return redirect("karyawan_list")


def dashboard_pegawai_view(request):
    if not request.session.get("pegawai_logged_in"):
        return redirect("login")

    pegawai_id = request.session["pegawai_id_pegawai"]

    # Menggunakan query __range yang akurat timezone
    today = timezone.localdate()
    today_start = timezone.make_aware(datetime.combine(today, time.min))
    today_end = timezone.make_aware(datetime.combine(today, time.max))

    absen_masuk = Absensi.objects.filter(
        id_pegawai_id=pegawai_id,
        waktu_absensi__range=(today_start, today_end),
        tipe_absensi="Masuk",
    ).first()

    absen_pulang = Absensi.objects.filter(
        id_pegawai_id=pegawai_id,
        waktu_absensi__range=(today_start, today_end),
        tipe_absensi="Pulang",
    ).first()

    context = {
        # Mengambil nama lengkap dari session
        "nama_lengkap": request.session.get("pegawai_nama_lengkap", "Pegawai"),
        "absen_masuk": absen_masuk,
        "absen_pulang": absen_pulang,
    }

    return render(request, "absensi/dashboard_pegawai.html", context)


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Radius bumi dalam meter
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@csrf_exempt
@transaction.atomic
def absensi_view(request):
    if not request.session.get("pegawai_logged_in"):
        return redirect("login")

    if request.method == "POST":
        data = json.loads(request.body)
        tipe_absensi = data.get("tipe")

        try:
            pegawai = Pegawai.objects.get(
                id_pegawai=request.session["pegawai_id_pegawai"]
            )

            today = timezone.localdate()
            today_start = timezone.make_aware(datetime.combine(today, time.min))
            today_end = timezone.make_aware(datetime.combine(today, time.max))

            if tipe_absensi == "Masuk":
                sudah_absen_masuk = Absensi.objects.filter(
                    id_pegawai=pegawai,
                    waktu_absensi__range=(today_start, today_end),
                    tipe_absensi="Masuk",
                ).exists()

                if sudah_absen_masuk:
                    # =======================================================
                    # === PERUBAHAN UTAMA UNTUK TES ADA DI SINI ===
                    # =======================================================
                    # Kita sengaja membuat aplikasi error untuk membuktikan
                    # bahwa blok validasi ini berjalan.
                    raise Exception(
                        "VALIDASI BERHASIL DIJALANKAN! Absen masuk kedua seharusnya tidak terjadi."
                    )
                    # =======================================================

            # (Sisa kode tidak relevan untuk tes ini, tetapi dibiarkan apa adanya)
            id_user_login = request.session["pegawai_id_user"]
            image_data_url = data.get("image")
            lat_user = data.get("latitude")
            lon_user = data.get("longitude")
            format, imgstr = image_data_url.split(";base64,")
            image_data = ContentFile(base64.b64decode(imgstr))
            image_array = np.frombuffer(image_data.read(), np.uint8)
            img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            recognized_user_id, confidence, error_msg = recognize_face(img)

            if error_msg:
                return JsonResponse(
                    {"status": "error", "message": error_msg}, status=400
                )

            is_match = recognized_user_id == id_user_login and (
                confidence is not None and confidence > 50
            )

            if is_match:
                jenis_kerja_final = "WFH"
                koordinat_str = f"{lat_user},{lon_user}"
                lokasi_kantor = Lokasi.objects.first()

                if lokasi_kantor:
                    jarak = haversine_distance(
                        lat_user,
                        lon_user,
                        lokasi_kantor.latitude,
                        lokasi_kantor.longitude,
                    )
                    if jarak <= 100:
                        jenis_kerja_final = "WFO"

                Absensi.objects.create(
                    id_pegawai=pegawai,
                    waktu_absensi=timezone.now(),
                    tipe_absensi=tipe_absensi,
                    status_verifikasi="Berhasil",
                    foto_bukti=image_data,
                    koordinat_lokasi=koordinat_str,
                    jenis_kerja=jenis_kerja_final,
                )
                pesan = f"Absen {tipe_absensi} sebagai {jenis_kerja_final} berhasil! Terima kasih."
                return JsonResponse({"status": "success", "message": pesan})
            else:
                pesan = "Wajah tidak cocok. Silakan coba lagi."
                return JsonResponse({"status": "error", "message": pesan})

        except Exception as e:
            # Jika crash terjadi karena Exception yang kita buat, tampilkan pesannya
            if "VALIDASI BERHASIL DIJALANKAN" in str(e):
                raise e  # Lanjutkan untuk menampilkan halaman error kuning
            return JsonResponse(
                {"status": "error", "message": f"Terjadi error: {str(e)}"}
            )

    else:
        sistem_siap = is_model_trained()
        pegawai_id = request.session.get("pegawai_id_pegawai")
        if not pegawai_id:
            return redirect("login")

        today = timezone.localdate()
        today_start = timezone.make_aware(datetime.combine(today, time.min))
        today_end = timezone.make_aware(datetime.combine(today, time.max))

        sudah_absen_masuk = Absensi.objects.filter(
            id_pegawai_id=pegawai_id,
            tipe_absensi="Masuk",
            waktu_absensi__range=(today_start, today_end),
        ).exists()
        sudah_absen_pulang = Absensi.objects.filter(
            id_pegawai_id=pegawai_id,
            tipe_absensi="Pulang",
            waktu_absensi__range=(today_start, today_end),
        ).exists()

        context = {
            "sistem_siap": sistem_siap,
            "sudah_absen_masuk": sudah_absen_masuk,
            "sudah_absen_pulang": sudah_absen_pulang,
        }
        return render(request, "absensi/absensi_page.html", context)


def ajukan_izin_view(request):
    if not request.session.get("pegawai_logged_in"):
        return redirect("login")

    pegawai = Pegawai.objects.get(id_pegawai=request.session["pegawai_id_pegawai"])

    if request.method == "POST":

        # =======================================================
        # === BLOK PENGECEKAN FINAL YANG SUDAH DIPERBAIKI TOTAL ===
        # =======================================================

        tanggal_awal_str = request.POST.get("tanggal_awal")
        today = timezone.localdate()

        # Pengecekan hanya berjalan jika pegawai mengajukan izin yang dimulai HARI INI
        if (
            tanggal_awal_str
            and datetime.strptime(tanggal_awal_str, "%Y-%m-%d").date() == today
        ):

            # Definisikan rentang waktu yang akurat untuk "hari ini"
            today_start = timezone.make_aware(datetime.combine(today, time.min))
            today_end = timezone.make_aware(datetime.combine(today, time.max))

            # Gunakan query __range yang aman timezone
            sudah_absen_masuk = Absensi.objects.filter(
                id_pegawai=pegawai,
                tipe_absensi="Masuk",
                waktu_absensi__range=(today_start, today_end),  # <-- PERBAIKAN UTAMA
            ).exists()

            # Jika record ditemukan, hentikan proses dan beri pesan error
            if sudah_absen_masuk:
                messages.error(
                    request,
                    "Gagal. Anda tidak bisa mengajukan izin untuk hari ini karena sudah melakukan absen masuk.",
                )
                # Redirect kembali ke form, error akan ditampilkan dari messages
                return redirect("ajukan_izin")

        # === AKHIR BLOK PENGECEKAN ===

        # Jika lolos pengecekan di atas, lanjutkan ke validasi form
        # (Sisa kode tidak diubah, sudah benar)
        form = IzinForm(request.POST, request.FILES, pegawai=pegawai)

        if form.is_valid():
            izin = form.save(commit=False)
            izin.id_pegawai = pegawai
            izin.save()
            messages.success(request, "Pengajuan izin Anda telah berhasil dikirim.")
            return redirect("riwayat_izin")

    else:  # Jika method GET
        form = IzinForm(pegawai=pegawai)

    return render(request, "absensi/ajukan_izin.html", {"form": form})


from .models import Lokasi
from .forms import LokasiForm


def data_lokasi_view(request):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    lokasi, created = Lokasi.objects.get_or_create(
        pk=1, defaults={"nama": "Lokasi Kantor Utama", "latitude": 0, "longitude": 0}
    )

    if request.method == "POST":
        form = LokasiForm(request.POST, instance=lokasi)
        if form.is_valid():
            form.save()
            messages.success(request, "Data lokasi berhasil diperbarui.")
            return redirect("data_lokasi")
    else:
        form = LokasiForm(instance=lokasi)

    context = {"form": form}
    return render(request, "absensi/data_lokasi.html", context)


def data_wajah_view(request):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    semua_pegawai = Pegawai.objects.all().order_by("nama_lengkap")
    context = {"semua_pegawai": semua_pegawai}
    return render(request, "absensi/data_wajah.html", context)


def get_data_wajah_api(request, id_pegawai):
    """
    API untuk mengambil semua data wajah milik seorang pegawai.
    """
    data_wajah_list = DataWajah.objects.filter(id_user__pegawai__id_pegawai=id_pegawai)

    data = []
    for wajah in data_wajah_list:
        data.append(
            {
                "id": wajah.id_wajah,
                "url": wajah.data_embedding.url,  # .url akan membuat link ke file di folder media
            }
        )

    return JsonResponse({"data_wajah": data})


def hapus_data_wajah_api(request, id_wajah):
    """
    API untuk menghapus satu data wajah.
    """
    if request.method == "POST":  # Hanya izinkan penghapusan via POST untuk keamanan
        try:
            wajah = DataWajah.objects.get(pk=id_wajah)

            if wajah.data_embedding:
                wajah.data_embedding.delete(save=False)

            wajah.delete()

            train_model()

            return JsonResponse(
                {"status": "success", "message": "Data wajah berhasil dihapus."}
            )
        except DataWajah.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Data wajah tidak ditemukan."},
                status=404,
            )
        except Exception as e:
            return JsonResponse(
                {"status": "error", "message": f"Error: {e}"}, status=500
            )

    return JsonResponse(
        {"status": "error", "message": "Metode tidak diizinkan."}, status=405
    )


def tambah_data_wajah_view(request):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    if request.method == "POST":
        try:
            id_pegawai = request.POST.get("id_pegawai")
            wajah_files = request.FILES.getlist("wajah_baru")

            if not id_pegawai or not wajah_files:
                messages.error(
                    request,
                    "Pegawai harus dipilih dan minimal satu foto harus diunggah.",
                )
                return redirect("data_wajah")

            pegawai = Pegawai.objects.get(id_pegawai=id_pegawai)
            user = pegawai.id_user

            for file in wajah_files:
                DataWajah.objects.create(id_user=user, data_embedding=file)

            messages.success(
                request,
                f"Berhasil menambahkan {len(wajah_files)} foto wajah baru untuk {pegawai.nama_lengkap}.",
            )

            # PENTING: Lakukan training ulang setelah data baru ditambahkan
            train_model()

        except Pegawai.DoesNotExist:
            messages.error(request, "Pegawai tidak ditemukan.")
        except Exception as e:
            messages.error(request, f"Terjadi error: {e}")

        # Redirect kembali ke halaman data wajah dengan pegawai yang sudah terpilih
        return redirect(f"{reverse('data_wajah')}?pegawai={id_pegawai}")

    return redirect("data_wajah")


@transaction.atomic
def proses_absensi_manual_view(request):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    if request.method == "POST":
        form = AbsensiManualForm(request.POST)
        if form.is_valid():
            pegawai = form.cleaned_data["pegawai"]
            tanggal = form.cleaned_data["tanggal"]
            jam_masuk = form.cleaned_data.get("jam_masuk")
            jam_pulang = form.cleaned_data.get("jam_pulang")

            # Buat datetime aware dari tanggal dan jam yang diinput
            tz = timezone.get_current_timezone()

            # Proses JAM MASUK
            if jam_masuk:
                dt_masuk = timezone.make_aware(datetime.combine(tanggal, jam_masuk), tz)
                # Update atau buat baru record absen masuk
                Absensi.objects.update_or_create(
                    id_pegawai=pegawai,
                    waktu_absensi__date=tanggal,
                    tipe_absensi="Masuk",
                    defaults={
                        "waktu_absensi": dt_masuk,
                        "status_verifikasi": "Berhasil",
                    },
                )

            # Proses JAM PULANG
            if jam_pulang:
                dt_pulang = timezone.make_aware(
                    datetime.combine(tanggal, jam_pulang), tz
                )
                # Update atau buat baru record absen pulang
                Absensi.objects.update_or_create(
                    id_pegawai=pegawai,
                    waktu_absensi__date=tanggal,
                    tipe_absensi="Pulang",
                    defaults={
                        "waktu_absensi": dt_pulang,
                        "status_verifikasi": "Berhasil",
                    },
                )

            messages.success(
                request,
                f"Absensi untuk {pegawai.nama_lengkap} pada tanggal {tanggal.strftime('%d-%m-%Y')} berhasil diproses.",
            )
        else:
            messages.error(request, f"Form tidak valid: {form.errors.as_text()}")

    return redirect(
        f"{reverse('data_absensi')}?tanggal={request.POST.get('tanggal', '')}"
    )


def _get_daily_attendance_data(tanggal):
    tz = timezone.get_current_timezone()
    today_start = timezone.make_aware(datetime.combine(tanggal, time.min), tz)
    today_end = timezone.make_aware(datetime.combine(tanggal, time.max), tz)

    absensi_hari_ini = Absensi.objects.filter(
        waktu_absensi__range=(today_start, today_end)
    ).order_by("waktu_absensi")

    # --- PERUBAHAN 1: Ambil SEMUA status perizinan pada tanggal ini ---
    perizinan_hari_ini = Perizinan.objects.select_related("id_pegawai").filter(
        tanggal_awal__lte=tanggal,
        tanggal_akhir__gte=tanggal,
        # Hapus filter status di sini agar semua jenis izin (Diajukan, Disetujui) terambil
    )
    # Ubah menjadi dictionary yang menyimpan SELURUH objek perizinan
    izin_per_pegawai = {izin.id_pegawai.id_pegawai: izin for izin in perizinan_hari_ini}
    # ----------------------------------------------------------------------

    data_terolah = {}
    for absen in absensi_hari_ini:
        id_pegawai = absen.id_pegawai.id_pegawai
        if id_pegawai not in data_terolah:
            data_terolah[id_pegawai] = {"jam_masuk_obj": None, "jam_pulang_obj": None}

        if absen.tipe_absensi == "Masuk":
            if data_terolah[id_pegawai]["jam_masuk_obj"] is None:
                data_terolah[id_pegawai]["jam_masuk_obj"] = absen
        elif absen.tipe_absensi == "Pulang":
            data_terolah[id_pegawai]["jam_pulang_obj"] = absen

    hasil_akhir = []
    semua_pegawai = (
        Pegawai.objects.select_related("id_user")
        .filter(status_pegawai="Aktif")
        .order_by("nama_lengkap")
    )

    for pegawai in semua_pegawai:
        data = data_terolah.get(pegawai.id_pegawai, {})
        jam_masuk_obj = data.get("jam_masuk_obj")
        jam_pulang_obj = data.get("jam_pulang_obj")
        jam_kerja_str = "-"

        # --- PERUBAHAN 2: Logika status dan penambahan objek izin ---
        status = ""
        perizinan_obj = izin_per_pegawai.get(pegawai.id_pegawai)

        if not perizinan_obj:  # Jika tidak ada catatan izin sama sekali
            if jam_masuk_obj:
                waktu_masuk_lokal = jam_masuk_obj.waktu_absensi.astimezone(tz)
                if waktu_masuk_lokal.time() > time(8, 0, 0):
                    status = "Terlambat"
                else:
                    status = "Tepat Waktu"
            else:
                status = "Tidak Hadir"
        # Jika ada catatan izin, kita tidak perlu mengisi status 'Tepat Waktu', dll.
        # Status akan ditentukan di template berdasarkan status_pengajuan dari perizinan_obj.

        if jam_masuk_obj and jam_pulang_obj:
            durasi = jam_pulang_obj.waktu_absensi - jam_masuk_obj.waktu_absensi
            if durasi.total_seconds() < 0:
                durasi += timedelta(days=1)
            jam, sisa = divmod(int(durasi.total_seconds()), 3600)
            menit, _ = divmod(sisa, 60)
            jam_kerja_str = f"{jam} jam {menit} menit"

        hasil_akhir.append(
            {
                "pegawai": pegawai,
                "jam_masuk": jam_masuk_obj.waktu_absensi if jam_masuk_obj else None,
                "jam_pulang": jam_pulang_obj.waktu_absensi if jam_pulang_obj else None,
                "jam_kerja": jam_kerja_str,
                "status": status,
                "perizinan_obj": perizinan_obj,  # <-- KIRIM OBJEK IZIN KE TEMPLATE
            }
        )
    return hasil_akhir


def cetak_laporan_absensi(request, tanggal):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    try:
        tanggal_laporan = datetime.strptime(tanggal, "%Y-%m-%d").date()
    except ValueError:
        return HttpResponse("Format tanggal tidak valid.")

    absensi_list = _get_daily_attendance_data(tanggal_laporan)

    template = get_template("absensi/laporan_pdf_template.html")

    # === MULAI PERBAIKAN DI SINI ===
    context = {
        "absensi_list": absensi_list,
        "tanggal_laporan": tanggal_laporan,
        # Ganti 'today' dengan 'waktu_cetak' yang berisi informasi waktu lengkap
        "waktu_cetak": timezone.localtime(),
    }
    # === AKHIR PERBAIKAN ===

    html = template.render(context)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="laporan_absensi_{tanggal}.pdf"'
    )

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("Terjadi error saat membuat PDF <pre>" + html + "</pre>")

    return response


def data_absensi_view(request):
    """
    Menampilkan halaman Monitor Absensi untuk admin.
    """
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    # Mengambil tanggal dari parameter URL, default ke hari ini
    tanggal_str = request.GET.get("tanggal", timezone.localdate().strftime("%Y-%m-%d"))
    try:
        tanggal_terpilih = datetime.strptime(tanggal_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        tanggal_terpilih = timezone.localdate()

    # Panggil helper untuk mendapatkan data yang sudah diolah
    absensi_list = _get_daily_attendance_data(tanggal_terpilih)

    # Siapkan form untuk modal Tambah/Edit
    form_manual = AbsensiManualForm(initial={"tanggal": tanggal_terpilih})

    # --- TAMBAHKAN BARIS INI UNTUK DEBUG ---
    print("--- DEBUG DATA UNTUK TEMPLATE ---")
    for item in absensi_list:
        print(item)
    print("-----------------------------------")
    # ----------------------------------------

    context = {
        "absensi_list": absensi_list,
        "tanggal_terpilih": tanggal_terpilih,
        "form_manual": form_manual,
    }
    return render(request, "absensi/data_absensi.html", context)


# Di dalam absensi/views.py


def cetak_laporan_rentang(request, tanggal_awal, tanggal_akhir):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    try:
        tgl_awal_obj = datetime.strptime(tanggal_awal, "%Y-%m-%d").date()
        tgl_akhir_obj = datetime.strptime(tanggal_akhir, "%Y-%m-%d").date()
    except ValueError:
        return HttpResponse("Format tanggal tidak valid. Gunakan format YYYY-MM-DD.")

    # --- PERUBAHAN LOGIKA UTAMA: Siapkan struktur data per pegawai ---
    laporan_per_pegawai = {}
    semua_pegawai = Pegawai.objects.filter(status_pegawai='Aktif').order_by('nama_lengkap')

    for pegawai in semua_pegawai:
        laporan_per_pegawai[pegawai.id_pegawai] = {
            "pegawai": pegawai,
            "rincian_harian": [],
            "total_detik_kerja": 0
        }

    # Loop setiap hari dalam rentang tanggal
    delta = tgl_akhir_obj - tgl_awal_obj
    for i in range(delta.days + 1):
        hari = tgl_awal_obj + timedelta(days=i)
        
        # Ambil data harian yang sudah diproses (sudah lengkap dengan 'perizinan_obj')
        data_harian = _get_daily_attendance_data(hari)

        # Masukkan data harian ke dalam struktur per pegawai
        for item in data_harian:
            pegawai_id = item["pegawai"].id_pegawai
            if pegawai_id in laporan_per_pegawai:
                
                # Tambahkan rincian hari itu ke daftar absensi pegawai
                # Hanya tambahkan jika ada aktivitas (hadir atau ada izin)
                if item["jam_masuk"] or item["perizinan_obj"]:
                    rincian = {
                        "tanggal": hari,
                        "jam_masuk": item["jam_masuk"],
                        "jam_pulang": item["jam_pulang"],
                        "jam_kerja": item["jam_kerja"],
                        "status": item["status"],
                        "perizinan_obj": item["perizinan_obj"],
                        "jenis_kerja": item["jenis_kerja"]
                    }
                    laporan_per_pegawai[pegawai_id]["rincian_harian"].append(rincian)

                # Akumulasi total jam kerja
                if item["jam_masuk"] and item["jam_pulang"]:
                    durasi = item["jam_pulang"] - item["jam_masuk"]
                    if durasi.total_seconds() > 0:
                        laporan_per_pegawai[pegawai_id]["total_detik_kerja"] += durasi.total_seconds()

    # Format total detik menjadi string "X jam Y menit"
    for id_peg, data in laporan_per_pegawai.items():
        total_seconds = data["total_detik_kerja"]
        jam, sisa = divmod(int(total_seconds), 3600)
        menit, _ = divmod(sisa, 60)
        data["total_jam_kerja_str"] = f"{jam} jam {menit} menit"

    template = get_template("absensi/laporan_rentang_pdf.html") 
    context = {
        # Kirim struktur data yang baru ke template
        "laporan_per_pegawai": laporan_per_pegawai,
        "tanggal_awal": tgl_awal_obj,
        "tanggal_akhir": tgl_akhir_obj,
    }
    html = template.render(context)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="laporan_rekap_pegawai_{tanggal_awal}_sd_{tanggal_akhir}.pdf"'
    )

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("Terjadi error saat membuat PDF.")
    
    return response

def kelola_perizinan_view(request):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    # Ambil semua data perizinan, urutkan dari yang terbaru dan status 'Menunggu'
    list_perizinan = Perizinan.objects.select_related("id_pegawai").order_by(
        "status_izin", "-tanggal_pengajuan"
    )

    context = {"list_perizinan": list_perizinan}
    return render(request, "absensi/kelola_perizinan.html", context)


def update_status_izin_view(request, id_izin):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    if request.method == "POST":
        try:
            izin = Perizinan.objects.get(id_izin=id_izin)
            status_baru = request.POST.get("status")

            if status_baru in ["Disetujui", "Ditolak"]:
                izin.status_izin = status_baru
                izin.save()
                messages.success(
                    request,
                    f"Status izin untuk {izin.id_pegawai.nama_lengkap} berhasil diperbarui menjadi {status_baru}.",
                )
            else:
                messages.error(request, "Status yang dikirim tidak valid.")
        except Perizinan.DoesNotExist:
            messages.error(request, "Data perizinan tidak ditemukan.")

    return redirect("kelola_perizinan")


def riwayat_izin_view(request):
    if not request.session.get("pegawai_logged_in"):
        return redirect("login")

    pegawai_id = request.session["pegawai_id_pegawai"]
    riwayat_list = Perizinan.objects.filter(id_pegawai_id=pegawai_id).order_by(
        "-tanggal_pengajuan"
    )

    context = {"riwayat_list": riwayat_list}
    return render(request, "absensi/riwayat_izin.html", context)


def _get_daily_attendance_data(tanggal):
    tz = timezone.get_current_timezone()
    today_start = timezone.make_aware(datetime.combine(tanggal, time.min), tz)
    today_end = timezone.make_aware(datetime.combine(tanggal, time.max), tz)

    absensi_hari_ini = Absensi.objects.filter(
        waktu_absensi__range=(today_start, today_end)
    ).order_by("waktu_absensi")

    # Bagian ini sudah benar: mengambil semua perizinan pada hari itu
    perizinan_hari_ini = Perizinan.objects.select_related("id_pegawai").filter(
        tanggal_awal__lte=tanggal, tanggal_akhir__gte=tanggal
    )
    izin_per_pegawai = {izin.id_pegawai.id_pegawai: izin for izin in perizinan_hari_ini}

    data_terolah = {}
    for absen in absensi_hari_ini:
        id_pegawai = absen.id_pegawai.id_pegawai
        if id_pegawai not in data_terolah:
            data_terolah[id_pegawai] = {"jam_masuk_obj": None, "jam_pulang_obj": None}

        if absen.tipe_absensi == "Masuk":
            if data_terolah[id_pegawai]["jam_masuk_obj"] is None:
                data_terolah[id_pegawai]["jam_masuk_obj"] = absen
        elif absen.tipe_absensi == "Pulang":
            data_terolah[id_pegawai]["jam_pulang_obj"] = absen

    hasil_akhir = []
    semua_pegawai = (
        Pegawai.objects.select_related("id_user")
        .filter(status_pegawai="Aktif")
        .order_by("nama_lengkap")
    )

    for pegawai in semua_pegawai:
        data = data_terolah.get(pegawai.id_pegawai, {})
        jam_masuk_obj = data.get("jam_masuk_obj")
        jam_pulang_obj = data.get("jam_pulang_obj")
        jam_kerja_str = "-"
        status = ""

        # Bagian ini sudah benar: mengambil objek izin jika ada
        perizinan_obj = izin_per_pegawai.get(pegawai.id_pegawai)
        
        jenis_kerja_str = jam_masuk_obj.get_jenis_kerja_display() if jam_masuk_obj else ""

        if not perizinan_obj:
            if jam_masuk_obj:
                waktu_masuk_lokal = jam_masuk_obj.waktu_absensi.astimezone(tz)
                if waktu_masuk_lokal.time() > time(8, 0, 0):
                    status = "Terlambat"
                else:
                    status = "Tepat Waktu"
            else:
                status = "Tidak Hadir"

        if jam_masuk_obj and jam_pulang_obj:
            durasi = jam_pulang_obj.waktu_absensi - jam_masuk_obj.waktu_absensi
            if durasi.total_seconds() < 0:
                durasi += timedelta(days=1)
            jam, sisa = divmod(int(durasi.total_seconds()), 3600)
            menit, _ = divmod(sisa, 60)
            jam_kerja_str = f"{jam} jam {menit} menit"

        # --- INI ADALAH BAGIAN YANG DIPERBAIKI ---
        # Pastikan 'perizinan_obj' selalu dimasukkan ke dalam dictionary
        hasil_akhir.append(
            {
                "pegawai": pegawai,
                "jam_masuk": jam_masuk_obj.waktu_absensi if jam_masuk_obj else None,
                "jam_pulang": jam_pulang_obj.waktu_absensi if jam_pulang_obj else None,
                "jam_kerja": jam_kerja_str,
                "status": status,
                "perizinan_obj": perizinan_obj,  
                "jenis_kerja": jenis_kerja_str,
            }
        )
        # ----------------------------------------

    return hasil_akhir


# Di dalam absensi/views.py

def riwayat_absensi_view(request):
    if not request.session.get("pegawai_logged_in"):
        return redirect("login")

    pegawai_id = request.session["pegawai_id_pegawai"]
    semua_riwayat = Absensi.objects.filter(id_pegawai_id=pegawai_id).order_by(
        "waktu_absensi"
    )

    absensi_harian = defaultdict(lambda: {"masuk": None, "pulang": None})
    tz = timezone.get_current_timezone()

    for absen in semua_riwayat:
        tanggal_lokal = absen.waktu_absensi.astimezone(tz).date()
        if absen.tipe_absensi == "Masuk" and not absensi_harian[tanggal_lokal]["masuk"]:
            absensi_harian[tanggal_lokal]["masuk"] = absen
        elif absen.tipe_absensi == "Pulang":
            absensi_harian[tanggal_lokal]["pulang"] = absen

    riwayat_final = []
    total_detik_kerja = 0  # [BARU] Inisialisasi total detik kerja

    for tanggal, data in sorted(absensi_harian.items(), reverse=True):
        jam_masuk = data["masuk"]
        jam_pulang = data["pulang"]
        jam_kerja_str = "-"
        status = "Tidak Lengkap"

        if jam_masuk and jam_pulang:
            durasi = jam_pulang.waktu_absensi - jam_masuk.waktu_absensi
            # Pastikan durasi positif untuk menghindari error
            if durasi.total_seconds() > 0:
                total_detik_kerja += durasi.total_seconds()  # [BARU] Akumulasi total detik
            
            jam, sisa = divmod(int(durasi.total_seconds()), 3600)
            menit, _ = divmod(sisa, 60)
            jam_kerja_str = f"{jam} jam {menit} menit"

        if jam_masuk:
            waktu_masuk_lokal = jam_masuk.waktu_absensi.astimezone(tz)
            if waktu_masuk_lokal.time() <= time(8, 0, 0):
                status = "Tepat Waktu"
            else:
                status = "Terlambat"

        riwayat_final.append(
            {
                "tanggal": tanggal,
                "jam_masuk": jam_masuk.waktu_absensi if jam_masuk else None,
                "jam_pulang": jam_pulang.waktu_absensi if jam_pulang else None,
                "status": status,
                "jenis_kerja": (
                    jam_masuk.get_jenis_kerja_display() if jam_masuk else "-"
                ),
                "jam_kerja": jam_kerja_str,
            }
        )
    
    total_jam, sisa_detik = divmod(int(total_detik_kerja), 3600)
    total_menit, _ = divmod(sisa_detik, 60)
    total_jam_kerja_str = f"{total_jam} jam {total_menit} menit"

    context = {
        "riwayat_list_final": riwayat_final,
        "total_jam_kerja": total_jam_kerja_str,
    }
    return render(request, "absensi/riwayat_absensi.html", context)

def daftar_pengajuan_izin(request):
    """
    Menampilkan halaman daftar pengajuan izin yang perlu diverifikasi admin.
    """
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    # Ambil semua pengajuan yang statusnya masih 'Diajukan'
    pengajuan_list = AbsensiPerizinan.objects.filter(
        status_pengajuan="Diajukan"
    ).order_by("tanggal_pengajuan")

    context = {"pengajuan_list": pengajuan_list}
    return render(request, "absensi/daftar_pengajuan_izin.html", context)


@require_POST
def verifikasi_izin(request, id_izin, aksi):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    pengajuan = get_object_or_404(Perizinan, id_izin=id_izin)

    # --- PERUBAHAN: Simpan tanggal untuk redirect ---
    tanggal_redirect = pengajuan.tanggal_awal.strftime("%Y-%m-%d")

    if aksi == "setujui":
        pengajuan.status_pengajuan = "Disetujui"
        messages.success(
            request,
            f"Pengajuan izin untuk {pengajuan.id_pegawai.nama_lengkap} telah disetujui.",
        )
    elif aksi == "tolak":
        pengajuan.status_pengajuan = "Ditolak"
        messages.warning(
            request,
            f"Pengajuan izin untuk {pengajuan.id_pegawai.nama_lengkap} telah ditolak.",
        )

    pengajuan.save()

    # Redirect kembali ke halaman data_absensi dengan parameter tanggal yang sesuai
    redirect_url = f"{reverse('data_absensi')}?tanggal={tanggal_redirect}"
    return redirect(redirect_url)


def detail_perizinan(request, id_izin):
    """
    Menampilkan halaman detail untuk satu objek perizinan.
    """
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    # Ambil objek perizinan atau tampilkan halaman 404 jika tidak ditemukan
    pengajuan = get_object_or_404(Perizinan, id_izin=id_izin)

    context = {"pengajuan": pengajuan}
    return render(request, "absensi/detail_perizinan.html", context)


def kelola_perizinan_view(request):
    """
    Menampilkan halaman untuk mengelola semua perizinan.
    """
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    # --- PERBAIKAN: Ambil SEMUA data perizinan dan kelompokkan di template ---
    semua_pengajuan = Perizinan.objects.select_related("id_pegawai").order_by(
        "-tanggal_pengajuan"
    )

    context = {
        # Kita kirim semua data, nanti template yang akan memisahkan
        "semua_pengajuan": semua_pengajuan,
    }
    return render(request, "absensi/kelola_perizinan.html", context)
# Di dalam absensi/views.py

def absensi_hari_ini_view(request):
    """
    Menampilkan halaman monitor absensi yang terkunci untuk hari ini.
    Mirip data_absensi_view tapi tanpa filter tanggal.
    """
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    # Langsung lock tanggal ke hari ini
    tanggal_terpilih = timezone.localdate()

    # Panggil helper yang sudah ada untuk mendapatkan data lengkap
    absensi_list = _get_daily_attendance_data(tanggal_terpilih)
    
    # Form ini tetap diperlukan oleh template, meskipun tidak kita gunakan di sini
    form_manual = AbsensiManualForm(initial={"tanggal": tanggal_terpilih})

    context = {
        "absensi_list": absensi_list,
        "tanggal_terpilih": tanggal_terpilih,
        "form_manual": form_manual,
        "halaman_khusus": True, # Flag untuk menyembunyikan filter tanggal di template (opsional)
    }
    # Menggunakan kembali template monitor absensi yang sudah ada!
    return render(request, "absensi/data_absensi.html", context)# Di dalam absensi/views.py


def belum_absen_hari_ini_view(request):
    """ Halaman untuk menampilkan daftar yang BELUM absen hari ini """
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    today = timezone.localdate()

    # --- [LOGIKA QUERY FINAL YANG SINKRON DENGAN DASHBOARD] ---
    # 1. Tentukan rentang waktu 24 jam untuk hari ini
    start_of_day = timezone.make_aware(datetime.combine(today, time.min))
    end_of_day = timezone.make_aware(datetime.combine(today, time.max))

    # 2. Ambil ID semua pegawai aktif
    pegawai_aktif_ids = set(
        Pegawai.objects.filter(status_pegawai='Aktif').values_list('id_pegawai', flat=True)
    )

    # 3. Ambil ID pegawai yang punya catatan absensi hari ini menggunakan rentang waktu
    pegawai_sudah_absen_ids = set(
        Absensi.objects.filter(waktu_absensi__range=(start_of_day, end_of_day))
        .values_list('id_pegawai_id', flat=True)
        .distinct()
    )

    # 4. Cari selisihnya: Pegawai yang belum absen adalah (semua pegawai aktif) - (yang sudah absen)
    pegawai_belum_absen_ids = pegawai_aktif_ids - pegawai_sudah_absen_ids

    # 5. Ambil objek Pegawai dari ID yang tersisa
    pegawai_list = Pegawai.objects.filter(id_pegawai__in=pegawai_belum_absen_ids).order_by('nama_lengkap')

    context = {
        'pegawai_list': pegawai_list,
        'tanggal_hari_ini': today,
    }
    return render(request, 'absensi/belum_absen.html', context)


def manajemen_pegawai_view(request):
    """
    Menampilkan halaman daftar semua pegawai untuk dikelola oleh admin.
    """
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    # Ambil semua objek pegawai, urutkan berdasarkan nama
    semua_pegawai = Pegawai.objects.select_related('id_user').all().order_by('nama_lengkap')

    context = {
        'semua_pegawai': semua_pegawai
    }
    # Pastikan me-render ke template yang benar
    return render(request, 'absensi/manajemen_pegawai.html', context)

# Di dalam absensi/views.py

def absensi_hari_ini_view(request):
    if not request.session.get("admin_logged_in"):
        return redirect("login")

    tanggal_terpilih = timezone.localdate()
    
    # Ambil semua data absensi hari ini seperti biasa
    absensi_list_lengkap = _get_daily_attendance_data(tanggal_terpilih)

    # [LOGIKA BARU] Saring daftar untuk hanya menampilkan yang jam masuknya TIDAK NULL
    absensi_list_final = [
        item for item in absensi_list_lengkap if item.get("jam_masuk") is not None
    ]
    
    form_manual = AbsensiManualForm(initial={"tanggal": tanggal_terpilih})
    context = {
        "absensi_list": absensi_list_final, # Kirim daftar yang sudah disaring
        "tanggal_terpilih": tanggal_terpilih,
        "form_manual": form_manual,
        "halaman_khusus": True,
        "judul_halaman": "Daftar Pegawai Sudah Absen Hari Ini" # Judul baru untuk kejelasan
    }
    return render(request, "absensi/data_absensi.html", context)