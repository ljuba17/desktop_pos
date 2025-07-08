import os
import psycopg2
from PyQt6.QtWidgets import QDialog, QMessageBox
from PyQt6 import uic
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (QDialog, QMessageBox, QLineEdit)
import configparser

# Učitavanje konfiguracije iz kasa.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)
GODINA = config.get('POS_Settings', 'god')
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')

class ArtiklibuDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(BASE_DIR, "ui", "artiklibu.ui")
        uic.loadUi(ui_path, self)

        self.sifraEdit.installEventFilter(self)
        self.btnObradi.setAutoDefault(False)
        self.btnObradi.setDefault(False)
        self.infolabel.setWordWrap(True)
        self.cenaEdit.focusInEvent = self.selektuj_tekst_u_fokusu(self.cenaEdit)
        self.btnObradi.clicked.connect(self.snimi_artikal)
        self.btnCancel.clicked.connect(self.reject)
        #self.sifraEdit.returnPressed.connect(self.proveri_sifru)
        #self.sifraEdit.editingFinished.connect(self.proveri_sifru)

        self.artikli_id = None
        self.samo_izmena_cene = False

        self.popuni_comboboxove()

    def eventFilter(self, obj, event):
        if obj == self.sifraEdit and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.proveri_sifru()
                return True
        return super().eventFilter(obj, event)
    
    def selektuj_tekst_u_fokusu(self, line_edit):
        def event_handler(event):
            QLineEdit.focusInEvent(line_edit, event)
            QTimer.singleShot(0, line_edit.selectAll)
        return event_handler

    def konekcija(self):
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )

    def koristi_counter_artikli(self):
        try:
            with self.konekcija() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT use_counter_artikli FROM kasa.core_appconfig LIMIT 1")
                    return cur.fetchone()[0]
        except:
            return False

    def generisi_novu_sifru(self):
        with self.konekcija() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(sifra) FROM kasa.artikli")
                poslednja = cur.fetchone()[0]
                if poslednja:
                    nova = str(int(poslednja) + 1).zfill(5)
                else:
                    nova = '00001'

                if nova in ('999995', '999996', '999997', '999998'):
                    nova = str(int(nova) + 1).zfill(5)
                return nova

    def popuni_comboboxove(self):
        try:
            with self.konekcija() as conn:
                with conn.cursor() as cur:
                    self.jmcombo.clear()
                    cur.execute("SELECT id, jm FROM kasa.jedmere ORDER BY jm")
                    for id, jm in cur.fetchall():
                        self.jmcombo.addItem(str(jm), id)

                    self.pdvcombo.clear()
                    cur.execute("SELECT id, stopa FROM kasa.porezi ORDER BY stopa")
                    for id, stopa in cur.fetchall():
                        self.pdvcombo.addItem(str(stopa), id)

                    self.rgcombo.clear()
                    cur.execute("SELECT id, naziv FROM kasa.robnegrupe ORDER BY naziv")
                    for id, naziv in cur.fetchall():
                        self.rgcombo.addItem(naziv, id)
        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška pri učitavanju combo box vrednosti:\n{e}")

    def crveni_Info(self):
        crveni_stil = """
            QLabel {
                border-style:outset;
                border-width:2px;
                border-radius:10px;
                border-color:#4c6084;
                color: red; 
            }
        """

    def proveri_sifru(self):
        sifra = self.sifraEdit.text().strip()
        if not sifra:
            return

        try:
            with self.konekcija() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, naziv, tip, jedinica_mere_id, porez_id, robna_grupa_id FROM kasa.artikli WHERE sifra = %s", (sifra,))
                    rezultat = cur.fetchone()
                    if rezultat:
                        self.artikli_id = rezultat[0]
                        self.nazivEdit.setText(rezultat[1])
                        tip = rezultat[2]
                        self.radioRoba.setChecked(tip == 1)
                        self.radioUsluga.setChecked(tip == 2)
                        self.radioSet.setChecked(tip == 3)
                        self.jmcombo.setCurrentIndex(self.jmcombo.findData(rezultat[3]))
                        self.pdvcombo.setCurrentIndex(self.pdvcombo.findData(rezultat[4]))
                        self.rgcombo.setCurrentIndex(self.rgcombo.findData(rezultat[5]))

                        # Dohvati cenu iz zaliheart
                        cur.execute("""
                            SELECT cena FROM kasa.zaliheart
                            WHERE sifra = %s AND god = %s AND sifobj = %s
                        """, (sifra, GODINA, SIFOBJEKTA))
                        cenarez = cur.fetchone()
                        if cenarez:
                            self.cenaEdit.setText(str(cenarez[0]))

                        # Proveri promet u kartici
                        cur.execute("""
                            SELECT 1 FROM kasa.karticaart
                            WHERE god = %s AND sifra = %s AND vrsta != 6
                            LIMIT 1
                        """, (GODINA, sifra))
                        if cur.fetchone():
                            self.infolabel.setStyleSheet("""
                            QLabel {
                                border-style:outset;
                                border-width:2px;
                                border-radius:10px;
                                border-color:#4c6084;
                                color: red; 
                                font-style: italic;                         
                            }
                            """)
                            self.infolabel.setText(f"Izabrani artikal je imao promet u poslovnoj {GODINA} godini.\nDozvoljena je samo izmena cene.")
                            self.samo_izmena_cene = True
                            self.cenaEdit.setFocus()
                        else:
                            self.infolabel.setStyleSheet("""
                            QLabel {
                                border-style:outset;
                                border-width:2px;
                                border-radius:10px;
                                border-color:#4c6084;
                                color: green;
                                font-style: italic;                         
                            }
                            """)
                            self.infolabel.setText(f"Artikal sa izabranom šifrom nije imao promet u poslovnoj {GODINA} godini. Možete izmeniti sve podatke osim šifre.")
                            self.samo_izmena_cene = False
                            self.nazivEdit.setFocus()
                    else:
                        self.infolabel.setText("")
                        self.artikli_id = None
                        self.samo_izmena_cene = False
                        self.nazivEdit.setFocus()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška pri proveri šifre:\n{e}")

    def snimi_artikal(self):
        sifra = self.sifraEdit.text().strip()
        naziv = self.nazivEdit.text().strip()
        cena = self.cenaEdit.text().strip()
        tip = 1 if self.radioRoba.isChecked() else 2 if self.radioUsluga.isChecked() else 3

        try:
            cena = float(cena)
        except ValueError:
            QMessageBox.warning(self, "Upozorenje", "Cena mora biti broj.")
            return

        if self.koristi_counter_artikli() and not self.artikli_id:
            sifra = self.generisi_novu_sifru()
            self.sifraEdit.setText(sifra)
        elif not sifra:
            QMessageBox.warning(self, "Upozorenje", "Šifra mora biti uneta.")
            return

        try:
            with self.konekcija() as conn:
                with conn.cursor() as cur:
                    jedmere_id = self.jmcombo.currentData()
                    porez_id = self.pdvcombo.currentData()
                    robnagru_id = self.rgcombo.currentData()
                    korisnik = os.getenv("APP_USER") or "auto"

                    if self.artikli_id:
                        if self.samo_izmena_cene:
                            cur.execute("""
                                UPDATE kasa.zaliheart
                                SET cena = %s, kreirao = %s
                                WHERE sifra = %s AND god = %s AND sifobj = %s
                            """, (cena, korisnik, sifra, GODINA, SIFOBJEKTA))
                        else:
                            cur.execute("""
                                UPDATE kasa.artikli
                                SET naziv = %s, tip = %s, jedinica_mere_id = %s,
                                    porez_id = %s, robna_grupa_id = %s, kreirao = %s
                                WHERE id = %s
                            """, (naziv, tip, jedmere_id, porez_id, robnagru_id, korisnik, self.artikli_id))
                            cur.execute("""
                                UPDATE kasa.zaliheart
                                SET cena = %s, kreirao = %s
                                WHERE sifra = %s AND god = %s AND sifobj = %s
                            """, (cena, korisnik, sifra, GODINA, SIFOBJEKTA))
                    else:
                        cur.execute("""
                            INSERT INTO kasa.artikli (
                                sifra, naziv, tip, jedinica_mere_id, porez_id, robna_grupa_id,
                                zaliheminus, kreirano, active, kreirao
                            ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, now(), TRUE, %s)
                            RETURNING id
                        """, (sifra, naziv, tip, jedmere_id, porez_id, robnagru_id, korisnik))
                        self.artikli_id = cur.fetchone()[0]

                        if tip == 1:
                            cur.execute("""
                                INSERT INTO kasa.zaliheart (
                                    sifra, god, sifobj, zaliha, kar, cena,
                                    cenanabavna, artikliid, netofcena, kreirao
                                ) VALUES (%s, %s, %s, 0, 1, %s, 0, %s, 0, %s)
                            """, (sifra, GODINA, SIFOBJEKTA, cena, self.artikli_id, korisnik))

                conn.commit()
                QMessageBox.information(self, "Uspeh", f"Artikal '{naziv}' uspešno sačuvan.")
                self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška pri unosu artikla:\n{e}")
