from PyQt6 import uic
from PyQt6.QtWidgets import QDialog
import json
import os
from datetime import datetime

class PeriodicniDialog(QDialog):
    def __init__(self, parent=None, ip_stampe=""):
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "periodicni.ui")
        uic.loadUi(ui_path, self)

        self.ip_stampe = ip_stampe  # IP adresa štampača

        # Povezivanje dugmadi OK i Cancel
        self.buttonBox.accepted.connect(self.stampaj_periodicni_izvestaj)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def stampaj_periodicni_izvestaj(self):
        # Čitanje unetih datuma
        pocetni_datum = self.oddatEdit.date().toString("yyyy-MM-dd")
        krajnji_datum = self.dodatEdit.date().toString("yyyy-MM-dd")

        # Generisanje vremenskog pečata za naziv fajla
        sada = datetime.now().strftime("%Y-%m-%d-%H-%M")
        naziv_fajla = f"GetReport-Period-{sada}.json"

        # Kreiranje JSON zahteva
        zahtev = {
            "reportType": "Periodic",
            "startDate": pocetni_datum,
            "endDate": krajnji_datum
        }

        # Putanja do direktorijuma
        direktorijum = f"\\\\{self.ip_stampe}\\MyLPFR\\exchange\\to-sdc"
        putanja_fajla = os.path.join(direktorijum, naziv_fajla)

        try:
            # Upisivanje JSON fajla
            with open(putanja_fajla, "w", encoding="utf-8") as f:
                json.dump(zahtev, f, indent=4)
            #print(f"✅ Uspešno sačuvan: {putanja_fajla}")
        except Exception as e:
            print(f"❌ Greška pri upisu fajla: {e}")
