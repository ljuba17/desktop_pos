import os
import psycopg2
import webbrowser
from PyQt6.QtWidgets import QDialog, QMessageBox, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import QDate
from PyQt6 import uic, QtGui
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtCore import Qt
import configparser
from datetime import datetime
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Table, TableStyle
import json
from utils.nbs_api import vrati_proveri_pib_nbs, vrati_pib_tekrac_nbs

# Učitavanje konfiguracije iz kasa.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)
GODINA = config.get('POS_Settings', 'god')
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')

class PartneriDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "noviPartner.ui")
        uic.loadUi(ui_path, self)

        self.racuniText.hide()

        self.odustaniBtn.clicked.connect(self.reject)
        self.pibBtn.clicked.connect(self.popuni_podatke_po_pibu)
        self.snimiBtn.clicked.connect(self.sacuvaj_partnera)
    
    def generisi_novu_sifru(self):
        try:
            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT MAX(sifra) FROM kasa.partneri")
                    rezultat = cursor.fetchone()
                    if rezultat[0] is None:
                        nova_sifra = "0001"
                    else:
                        nova_sifra = str(int(rezultat[0]) + 1).zfill(4)
            return nova_sifra
        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Ne mogu da generišem novu šifru:\n{e}")
            return None
        
    def popuni_podatke_po_pibu(self):
        pib = self.pibEdit.text().strip()

        if not pib.isdigit() or len(pib) < 9:
            QMessageBox.warning(self, "Neispravan PIB", "Unesite ispravan PIB (min 9 cifara).")
            return

        podaci = vrati_proveri_pib_nbs(pib)

        if podaci:
            naziv, mesto, pobro, adresa, matbr, naziv1 = podaci
            self.nazivEdit.setText(naziv)
            self.mestoEdit.setText(mesto)
            self.pobroEdit.setText(pobro)
            self.adresaEdit.setText(adresa)
            self.matbrEdit.setText(matbr)
            self.naziv1Edit.setText(naziv1)
        else:
            QMessageBox.warning(self, "Nema podataka", "Nije moguće pronaći podatke za uneti PIB.")

        try:
            racuni_data = vrati_pib_tekrac_nbs(pib)
            if racuni_data:
                self.tekuci_racuni_json = json.dumps(racuni_data, ensure_ascii=False)
                self.racuniText.setPlainText(self.tekuci_racuni_json)  # prikaz u QTextEdit
            else:
                self.tekuci_racuni_json = "{}"
                self.racuniText.setPlainText("Računi nisu dostupni.")
        except Exception as e:
            self.tekuci_racuni_json = "{}"
            self.racuniText.setPlainText("Greška prilikom preuzimanja računa.")
            print(f"Greška pri dohvatanju računa: {e}")

    def sacuvaj_partnera(self):
        tippdv_tekst = self.tippdvCombo.currentText().strip()

        mapa_tippdv = {
            "U sistemu PDV-a": 1,
            "Van sistema PDV-a": 2,
            "Registrovan poljoprivrednik": 3,
            "Neregistrovan poljoprivrednik": 4
        }

        tip_pdv = mapa_tippdv.get(tippdv_tekst)

        if not tip_pdv:
            QMessageBox.warning(self, "Greška", "Morate izabrati tip PDV-a.")
            return

        if not self.nazivEdit.text().strip():
            QMessageBox.warning(self, "Greška", "Morate uneti naziv partnera.")
            return

        sifra = self.generisi_novu_sifru()
        if not sifra:
            return

        ziro_json = self.tekuci_racuni_json if hasattr(self, 'tekuci_racuni_json') and self.tekuci_racuni_json else "{}"

        try:
            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    # Provera da li PIB već postoji
                    cursor.execute("SELECT 1 FROM kasa.partneri WHERE pib = %s", (self.pibEdit.text().strip(),))
                    if cursor.fetchone():
                        QMessageBox.warning(self, "Duplikat", "Partner sa unetim PIB-om već postoji u bazi.")
                        return
                    query = """
                        INSERT INTO kasa.partneri (
                            tippdv, pib, naziv, pobro, mesto, matbr, jbkjs, jib,
                            adresa, naziv1, email, kar, telefon, kontaktosb, sifra, ziro, kreirao
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    vrednosti = (
                        tip_pdv,
                        self.pibEdit.text(),
                        self.nazivEdit.text(),
                        self.pobroEdit.text(),
                        self.mestoEdit.text(),
                        self.matbrEdit.text(),
                        self.jbkjsEdit.text(),
                        self.jibEdit.text(),
                        self.adresaEdit.text(),
                        self.naziv1Edit.toPlainText(),
                        self.emailEdit.text(),
                        1,
                        self.telefonEdit.text(),
                        self.kontaktosbEdit.text(),
                        sifra,
                        ziro_json,
                        "sistem"
                    )
                    cursor.execute(query, vrednosti)
                    conn.commit()

            QMessageBox.information(self, "Uspeh", "Partner je uspešno unet.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Došlo je do greške prilikom upisa:\n{e}")