import sys
import os

# Dodaj apsolutnu putanju do Django projekta u sys.path
sys.path.insert(0, r"D:\mrkapp")

# Postavi env varijablu za settings modul
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import django
django.setup()

from PyQt6.QtWidgets import QDialog, QMessageBox
from login_dijalog import Ui_login
import psycopg2
from dotenv import load_dotenv
from django.contrib.auth.hashers import check_password

# Učitavanje .env fajla
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path)

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.ui = Ui_login()
        self.ui.setupUi(self)
        self.setWindowTitle("Prijava korisnika")
        self.setFixedSize(self.size())

        self.ui.pushButton.clicked.connect(self.proveri_korisnika)
        self.ui.passEdit.returnPressed.connect(self.proveri_korisnika)
        self.ui.unEdit.setFocus()

    def proveri_korisnika(self):
        korisnicko_ime = self.ui.unEdit.text()
        lozinka = self.ui.passEdit.text()

        print(f"Provera korisnika: {korisnicko_ime}")

        if not korisnicko_ime or not lozinka:
            QMessageBox.warning(self, "Greška", "Unesite korisničko ime i lozinku.")
            return

        try:
            print("Pokušavam da se povežem na bazu...")
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            print("Uspostavljena konekcija sa bazom.")

            cursor = conn.cursor()
            # Imaj u vidu da je šema 'kasa' i moraš precizirati u upitu
            cursor.execute("SELECT password, is_active FROM kasa.auth_user WHERE username = %s", (korisnicko_ime,))
            korisnik = cursor.fetchone()

            print(f"Rezultat upita: {korisnik}")

            if korisnik and korisnik[1]:
                sifrovana_lozinka = korisnik[0]
                print(f"Provera lozinke za korisnika: {korisnicko_ime}")

                if check_password(lozinka, sifrovana_lozinka):
                    QMessageBox.information(self, "Uspeh", f"Prijavljeni ste kao {korisnicko_ime}")
                    print("Lozinka je tačna.")
                    self.accept()
                else:
                    QMessageBox.critical(self, "Greška", "Pogrešna lozinka.")
                    print("Pogrešna lozinka.")
            else:
                QMessageBox.critical(self, "Greška", "Neispravno korisničko ime ili korisnik nije aktivan.")
                print("Korisnik ne postoji ili nije aktivan.")

            cursor.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Greška pri povezivanju", str(e))
            print(f"Greška pri povezivanju: {e}")
