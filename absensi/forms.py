from django import forms
from django.utils import timezone
from .models import Perizinan, Lokasi, Pegawai  # Tambahkan Lokasi


class KaryawanForm(forms.Form):
    nip = forms.CharField(
        label="NIP",
        max_length=50,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm"
            }
        ),
    )
    nama_lengkap = forms.CharField(
        label="Nama Lengkap",
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm"
            }
        ),
    )
    jabatan = forms.CharField(
        label="Jabatan",
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm"
            }
        ),
    )
    username = forms.CharField(
        label="Username",
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm"
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm"
            }
        ),
        required=False,
    )

    STATUS_CHOICES = [
        ("Aktif", "Aktif"),
        ("Tidak Aktif", "Tidak Aktif"),
    ]
    status_pegawai = forms.ChoiceField(
        label="Status Pegawai",
        choices=STATUS_CHOICES,
        required=True,
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm"
            }
        ),
    )

    # data_wajah = forms.ImageField(
    #     label="Data Wajah",
    #     required=False,  # Dibuat tidak wajib di form, tapi divalidasi di view.
    #     help_text="Unggah minimal 1 foto wajah. Untuk hasil terbaik, unggah 10-20 foto.",
    # )


from .models import Perizinan


class IzinForm(forms.ModelForm):
    
    # Kita butuh object pegawai untuk validasi tumpang tindih,
    # jadi kita siapkan di constructor form.
    def __init__(self, *args, **kwargs):
        self.pegawai = kwargs.pop('pegawai', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = Perizinan
        fields = [
            'tanggal_awal', 
            'tanggal_akhir', 
            'jenis_izin', 
            'keterangan', 
            'file_lampiran'
        ]
        widgets = {
            'tanggal_awal': forms.DateInput(attrs={'type': 'date', 'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500'}),
            'tanggal_akhir': forms.DateInput(attrs={'type': 'date', 'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500'}),
            'jenis_izin': forms.Select(attrs={'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500'}),
            'keterangan': forms.Textarea(attrs={'rows': 4, 'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500', 'placeholder': 'Contoh: Perlu istirahat karena demam tinggi.'}),
            'file_lampiran': forms.FileInput(attrs={'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-red-100 file:text-red-700 hover:file:bg-red-200 cursor-pointer'}),
        }
        labels = {
            'tanggal_awal': 'Dari Tanggal',
            'tanggal_akhir': 'Sampai Tanggal',
            'jenis_izin': 'Jenis Izin',
            'keterangan': 'Keterangan',
            'file_lampiran': 'File Lampiran (Opsional)',
        }

    # --- BLOK VALIDASI BARU ---
    def clean(self):
        cleaned_data = super().clean()
        tanggal_awal = cleaned_data.get('tanggal_awal')
        tanggal_akhir = cleaned_data.get('tanggal_akhir')
        
        # Pengecekan 1: Tanggal mulai tidak boleh di masa lalu
        if tanggal_awal and tanggal_awal < timezone.localdate():
            raise forms.ValidationError("Tanggal mulai izin tidak boleh kurang dari tanggal hari ini.")
            
        # Pengecekan 2: Tanggal akhir tidak boleh sebelum tanggal mulai
        if tanggal_awal and tanggal_akhir and tanggal_akhir < tanggal_awal:
            raise forms.ValidationError("Tanggal selesai tidak boleh lebih awal dari tanggal mulai.")

        # Pengecekan 3: Rentang tanggal tidak boleh tumpang tindih dengan izin yang sudah ada
        if tanggal_awal and tanggal_akhir and self.pegawai:
            overlapping_requests = Perizinan.objects.filter(
                id_pegawai=self.pegawai,
                tanggal_akhir__gte=tanggal_awal,
                tanggal_awal__lte=tanggal_akhir
            ).exists()
            
            if overlapping_requests:
                raise forms.ValidationError("Anda sudah memiliki pengajuan izin yang tumpang tindih dengan rentang tanggal ini.")
                
        return cleaned_data
    
class LokasiForm(forms.ModelForm):
    class Meta:
        model = Lokasi
        fields = ["latitude", "longitude"]
        labels = {"latitude": "Latitude Kantor", "longitude": "Longitude Kantor"}
        widgets = {
            "latitude": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm",
                    "step": "any",
                }
            ),
            "longitude": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm",
                    "step": "any",
                }
            ),
        }

class AbsensiManualForm(forms.Form):
    # Dropdown untuk memilih pegawai
    pegawai = forms.ModelChoiceField(
        queryset=Pegawai.objects.all().order_by("nama_lengkap"),
        label="Pilih Pegawai",
        widget=forms.Select(attrs={"class": "mt-1 block w-full ..."}),
    )
    # Input untuk tanggal absensi
    tanggal = forms.DateField(
        label="Tanggal Absensi",
        widget=forms.DateInput(
            attrs={"type": "date", "class": "mt-1 block w-full ..."}
        ),
    )
    # Input untuk jam, tidak wajib diisi keduanya
    jam_masuk = forms.TimeField(
        label="Jam Masuk (Contoh: 07:30)",
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "mt-1 block w-full ..."}
        ),
        required=False,
    )
    jam_pulang = forms.TimeField(
        label="Jam Pulang (Contoh: 16:05)",
        widget=forms.TimeInput(
            attrs={"type": "time", "class": "mt-1 block w-full ..."}
        ),
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        jam_masuk = cleaned_data.get("jam_masuk")
        jam_pulang = cleaned_data.get("jam_pulang")

        if jam_pulang and not jam_masuk:
            raise forms.ValidationError(
                "Jam masuk harus diisi jika ingin mengisi jam pulang."
            )

        return cleaned_data  
