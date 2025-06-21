import os
import psycopg2
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QTableWidgetItem, QPushButton, QMessageBox
from PyQt6.QtGui import QColor, QBrush
from PyQt6 import uic
import configparser
import random
from functools import partial
import json
from datetime import datetime

# Učitavanje konfiguracije iz kasa.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)
GODINA = config.get('POS_Settings', 'god')
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')
KASA = config.get('POS_Settings', 'kasa')

class TraziAvansDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "trazi_avans.ui")
        uic.loadUi(ui_path, self)

        # Povezivanje pretrage sa funkcijom filtriranja
        self.traziEdit.textChanged.connect(self.filtriraj_racune)

        # Popunjavanje podataka iz baze
        self.ucitaj_racune()

        self.racuniTable.setColumnWidth(0, 90)  # Prva kolona širine 90 -datum
        self.racuniTable.setColumnWidth(1, 80)  # kolona širine 80 - vrednost
        self.racuniTable.setColumnWidth(2, 180)  # kolona širine 180 - PFR broj
        self.racuniTable.setColumnWidth(3, 130)  # kolona širine 130 - vreme transakcije
        self.racuniTable.setColumnWidth(4, 180)  # kolona širine 180 - referentni
        self.racuniTable.setColumnWidth(5, 60)  # kolona širine 60 - tip kupca
        self.racuniTable.setColumnWidth(6, 120)  # kolona širine 100 - oznaka kupca
        self.racuniTable.setColumnWidth(7, 80)  # kolona širine 80 - dugme izaberi
        self.racuniTable.setColumnWidth(8, 60)  # kolona širine 60 - kasa
        self.racuniTable.setColumnHidden(8, True)

    def ucitaj_racune(self):
        """Punjenje tabele racuniTable podacima iz kasasum."""
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            cursor.execute("""
                SELECT datum, ukiznos, brracpu, vremetransakcije, refbrracpu, 
                       kodkupca, oznakakupca, kasa
                FROM "kasa"."kasasum"
                WHERE sifobj = %s 
                    AND tipracuna = '4'  -- Dodato '' da bude string
                    AND tiptransakcije = '0'  -- Dodato '' da bude string
                ORDER BY datum DESC
            """, (SIFOBJEKTA,))
            
            podaci = cursor.fetchall()

            # Čišćenje tabele pre unosa novih podataka
            self.racuniTable.setRowCount(0)

            for row_idx, row_data in enumerate(podaci):
                self.racuniTable.insertRow(row_idx)
                for col_idx, value in enumerate(row_data):
                    self.racuniTable.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

                # Dugme "Izaberi" (kolona 7)
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
                btn_izaberi.clicked.connect(lambda _, r=row_idx: self.prebaci_podatke(r))
                self.racuniTable.setCellWidget(row_idx, 7, btn_izaberi)
                # Poslednja kolona: 'kasa' (kolona 8)
                self.racuniTable.setItem(row_idx, 8, QTableWidgetItem(str(row_data[-1])))

            cursor.close()
            conn.close()
        except Exception as e:
            print(f"❌ Greška pri učitavanju avansnih računa: {e}")

    def filtriraj_racune(self):
        """Filtriranje podataka u racuniTable na osnovu pretrage."""
        filter_text = self.traziEdit.text().lower()

        for row in range(self.racuniTable.rowCount()):
            brracpu = self.racuniTable.item(row, 2).text().lower()
            oznakakupca = self.racuniTable.item(row, 6).text().lower()

            # Prikazujemo samo redove koji sadrže tekst iz pretrage
            should_show = filter_text in brracpu or filter_text in oznakakupca
            self.racuniTable.setRowHidden(row, not should_show)

    def prebaci_podatke(self, row):
        """Prenosi podatke iz izabranog reda u AvansniDialog."""
        self.main_window.brrapuEdit.setText(self.racuniTable.item(row, 2).text())
        self.main_window.vremeTranEdit.setText(self.racuniTable.item(row, 3).text())
        self.main_window.tipEdit_2.setText(self.racuniTable.item(row, 5).text())
        self.main_window.oznakaEdit_2.setText(self.racuniTable.item(row, 6).text())

        self.close()