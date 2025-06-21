import os
import psycopg2
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QTableWidgetItem, QPushButton, QMessageBox, QVBoxLayout, QMessageBox
from trazi_avans import TraziAvansDialog
from PyQt6.QtGui import QFont, QColor, QBrush, QIcon
from PyQt6 import uic
from PyQt6.QtWidgets import QTreeWidgetItem
import configparser
import random
import webbrowser  # Za otvaranje slike u podrazumevanoj aplikaciji
from functools import partial
import json
from datetime import datetime
from collections import defaultdict


# Učitavanje konfiguracije iz kasa.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)
GODINA = config.get('POS_Settings', 'god')
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')
KASA = config.get('POS_Settings', 'kasa')

LATIN_TO_CYRILLIC_MAP = {
        "A": "А", #"\u0410",  # А - Nije u PDV
        "G": "Г", #"\u0413",  # Г - Bez PDV
        "Đ": "Ђ", #"\u0402",  # Ђ - Opšta stopa (20%)
        "E": "Е" #"\u0415",  # Е - Posebna stopa (10%)
    }

class RefundiraniAvansDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "refundiraniAvansi.ui")
        uic.loadUi(ui_path, self)

        self.ip_stampe, self.lservis = self.main_window.ucitaj_konfiguraciju_kase()

        self.pretrazifrEdit.textChanged.connect(self.filter_refundiraniTable)
        self.refundiraniTable.cellClicked.connect(self.oznaci_red)

    # ✅ Sakrivanje kolone slovo u refundiraniTable iz dijaloga
        self.refundiraniTable.setColumnWidth(0, 220)  # Prva kolona širine 220 brracpu
        self.refundiraniTable.setColumnWidth(1, 180)  # kolona širine 180 - vreme transakcije
        self.refundiraniTable.setColumnWidth(2, 60)  # kolona širine 60 - kod kupca
        self.refundiraniTable.setColumnWidth(3, 140)  # kolona širine 140 - oznaka kupca
        self.refundiraniTable.setColumnWidth(4, 100)  # kolona širine 100 - vrednost
        self.refundiraniTable.setColumnWidth(5, 100)  # kolona širine 100 - dugme slika racuna
        self.refundiraniTable.setColumnWidth(6, 100)  # kolona širine 100 - dugme izaberi
        self.refundiraniTable.setColumnWidth(7, 100)  # kolona širine 100 - Broj
        self.refundiraniTable.setColumnWidth(8, 100)  # kolona širine 100 - Godina
        self.refundiraniTable.setColumnWidth(9, 220)  # kolona širine 100 - Poslednji avans (referentni racun)
        self.refundiraniTable.setColumnHidden(2, True)  # sakrivam kolonu u kojoj je kod kupca
        self.refundiraniTable.setColumnHidden(7, True)  # sakrivam kolonu u kojoj je broj
        self.refundiraniTable.setColumnHidden(8, True)  # sakrivam kolonu u kojoj je godina
        self.refundiraniTable.setColumnHidden(9, True)  # sakrivam kolonu u kojoj je Poslednji avans (referentni racun)

        self.popuni_refundiraniTable()  # ← Poziv funkcije za punjenje tabele

    def popuni_refundiraniTable(self):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # 🔍 Čitanje našeg PIB-a iz fvr
            cursor.execute("SELECT pib FROM \"kasa\".\"fvr\" LIMIT 1")
            pib_red = cursor.fetchone()
            if not pib_red:
                QMessageBox.warning(self, "Upozorenje", "Nije pronađen PIB iz tabele fvr.")
                return
            nas_pib = pib_red[0]

            # 🔍 Čitanje refundiranih avansnih računa koji nisu naši
            cursor.execute("""
                SELECT brracpu, vremetransakcije, ukiznos, kodkupca, oznakakupca, broj, god, refbrracpu
                FROM kasa.kasasum
                WHERE sifobj = %s 
                AND brracpu IS NOT NULL
                AND tipracuna = '4'
                AND tiptransakcije = '1'
                AND oznakakupca IS DISTINCT FROM %s
                ORDER BY vremetransakcije DESC
            """, (SIFOBJEKTA, nas_pib))

            podaci = cursor.fetchall()
            self.refundiraniTable.setRowCount(0)  # Očistimo prethodni sadržaj

            for row_idx, (brracpu, vreme, iznos, kodkupca, oznakakupca, broj, god, refbrracpu) in enumerate(podaci):
                self.refundiraniTable.insertRow(row_idx)

                # Dodavanje običnih ćelija
                self.refundiraniTable.setItem(row_idx, 0, QTableWidgetItem(brracpu))
                self.refundiraniTable.setItem(row_idx, 1, QTableWidgetItem(str(vreme)))
                self.refundiraniTable.setItem(row_idx, 2, QTableWidgetItem(str(kodkupca)))
                self.refundiraniTable.setItem(row_idx, 3, QTableWidgetItem(oznakakupca))
                self.refundiraniTable.setItem(row_idx, 4, QTableWidgetItem(f"{iznos:.2f}"))
                self.refundiraniTable.setItem(row_idx, 7, QTableWidgetItem(f"{broj}"))
                self.refundiraniTable.setItem(row_idx, 8, QTableWidgetItem(f"{god}"))
                self.refundiraniTable.setItem(row_idx, 9, QTableWidgetItem(f"{refbrracpu}"))

                # 🔘 Dugme "Prikaži sliku"
                btn_slikaracuna = QPushButton("Prikaži sliku")
                btn_slikaracuna.setStyleSheet("""
                    QPushButton {
                        background-color: lightblue;
                        color: black;
                        border: 2px solid gray;
                        border-radius: 5px;
                        padding: 5px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #87cefa;
                    }
                    QPushButton:pressed {
                        background-color: #4682b4;
                    }
                """)
                btn_slikaracuna.clicked.connect(partial(self.prikazi_sliku, row_idx))
                self.refundiraniTable.setCellWidget(row_idx, 5, btn_slikaracuna)
                btn_slikaracuna.clicked.connect(lambda _, r=row_idx: self.oznaci_red(r))

                # 🔘 Dugme "Izaberi"
                btn_izaberi = QPushButton("Izaberi")
                btn_izaberi.setStyleSheet("""
                    QPushButton {
                        background-color: orange;
                        color: black;
                        border: 2px solid gray;
                        border-radius: 5px;
                        padding: 5px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: darkorange;
                    }
                    QPushButton:pressed {
                        background-color: #ff8c00;
                    }
                """)
                btn_izaberi.clicked.connect(partial(self.izaberi_racun, row_idx))
                self.refundiraniTable.setCellWidget(row_idx, 6, btn_izaberi)

            cursor.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška pri popunjavanju refundiranih avansa:\n{str(e)}")

    def prikazi_sliku(self, row):
        """
        Prikazuje sliku računa u podrazumevanoj aplikaciji.
        """
        try:
            broj = self.refundiraniTable.item(row, 7).text()  # Dohvatamo broj iz skrivene kolone
            trenutna_godina = self.refundiraniTable.item(row, 8).text() #datetime.now().year
            godina = str(trenutna_godina)[-2:]  # Poslednje dve cifre godine, kao string

            # Provera IP adrese za lokalnu putanju
            if self.ip_stampe == "127.0.0.1":
                slika_putanja = f"C:\\myLPFR\\exchange\\from-sdc\\Receipt-{broj}-{godina}.png"
            else:
                slika_putanja = f"\\\\{self.ip_stampe}\\MyLPFR\\exchange\\from-sdc\\Receipt-{broj}-{godina}.png"

            # Debug ispis za putanju slike
            #print(f"🛠️ Debug: Proveravam putanju slike: {slika_putanja}")

            # Provera postojanja slike
            if os.path.exists(slika_putanja):
            #    print(f"✅ Slika pronađena: {slika_putanja}")  # Debug poruka za terminal
                webbrowser.open(slika_putanja)  # Otvaranje slike u podrazumevanoj aplikaciji
            else:
            #    print(f"❌ Slika nije pronađena na putanji: {slika_putanja}")  # Debug poruka za terminal
                QMessageBox.warning(self, "Greška", f"Slika računa nije pronađena na putanji:\n{slika_putanja}")

        except Exception as e:
            print(f"❌ Greška u prikazi_sliku: {e}")  # Debug poruka za terminal

    def filter_refundiraniTable(self):
        """
        Filtrira refundiraniTable na osnovu unosa u pretrazifrEdit.
        Ako je polje prazno, prikazuje sve redove.
        """
        search_term = self.pretrazifrEdit.text().lower()

        for row in range(self.refundiraniTable.rowCount()):
            item = self.refundiraniTable.item(row, 0)  # Broj računa PU
            if item:
                if search_term in item.text().lower():
                    self.refundiraniTable.setRowHidden(row, False)
                else:
                    self.refundiraniTable.setRowHidden(row, True)
            else:
                self.refundiraniTable.setRowHidden(row, True)

    def oznaci_red(self, red):
        """
        Obeležava izabrani red u refundiraniTable tako što menja njegov stil.
        """
        # Resetujemo sve redove na podrazumevani stil
        for r in range(self.refundiraniTable.rowCount()):
            for c in range(self.refundiraniTable.columnCount()):
                item = self.refundiraniTable.item(r, c)
                if item:
                    font = item.font()
                    font.setBold(False)
                    font.setPointSize(9)
                    item.setFont(font)

        # Stilizujemo samo izabrani red
        for c in range(self.refundiraniTable.columnCount()):
            item = self.refundiraniTable.item(red, c)
            if item:
                font = item.font()
                font.setBold(True)
                font.setPointSize(10)  # Veći font za istaknuti red
                item.setFont(font)

    def izaberi_racun(self, row, *args):
        """
        Prenosi izabrani red iz refundiraniTable u glavni prozor.
        """
        brrnpu = self.refundiraniTable.item(row, 0).text()
        vremetrans = self.refundiraniTable.item(row, 1).text()
        kodkupca = self.refundiraniTable.item(row, 2).text()
        oznakakupca = self.refundiraniTable.item(row, 3).text()
        iznos = self.refundiraniTable.item(row, 4).text()
        refbrracpu = self.refundiraniTable.item(row, 9).text()

        self.main_window.brrnpuEdit.setText(brrnpu)
        self.main_window.vremeTransEdit.setText(vremetrans)
        self.main_window.tipEdit.setText(kodkupca)
        self.main_window.kupacEdit.setText(oznakakupca)
        self.main_window.iznosRefundacijeEdit.setText(iznos)
        self.main_window.poslednjiAvansEdit.setText(refbrracpu)

        self.close()  # Zatvori dijalog nakon izbora


        
