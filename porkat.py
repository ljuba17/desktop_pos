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

class PorkatDialog(QDialog):
    def __init__(self, fakture_dialog, parent=None):  # bez tipa
        super().__init__(parent)
        self.fakture_dialog = fakture_dialog
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "porkat.ui")
        uic.loadUi(ui_path, self)

        self.odustaniBtn.clicked.connect(self.reject)

        self.popuni_porkat()

        # Povezivanje pretrage sa funkcijom filtriranja
        self.pretragaEdit.textChanged.connect(self.filtriraj_porkat)

        # Postavljanje širine kolona u porkatTable
        self.porkatTable.setColumnWidth(0, 60)  # Prva kolona širine 80
        self.porkatTable.setColumnWidth(1, 120)  # Druga kolona širine 120
        self.porkatTable.setColumnWidth(2, 80)  # Treća kolona širine 80
        self.porkatTable.setColumnWidth(3, 300)  # Četvrta kolona širine 300
        self.porkatTable.setColumnWidth(4, 160)  # peta kolona širine 160
        self.porkatTable.setColumnWidth(5, 100)  # Šesta kolona širine 100 dugme Izaberi

        self.porkatTable.setColumnHidden(0, True)  # sakrivam prvu kolonu

    def popuni_porkat(self):
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
                SELECT reasonid, keykat, category, text, law
                FROM kasa.porkat
                ORDER BY (reasonid) ASC
            """)

            rezultati = cursor.fetchall()
            self.porkatTable.setRowCount(0)  # Čisti tabelu

            for red_index, red in enumerate(rezultati):
                self.porkatTable.insertRow(red_index)

                # Unos podataka u ćelije
                self.porkatTable.setItem(red_index, 0, QTableWidgetItem(str(red[0])))  
                self.porkatTable.setItem(red_index, 1, QTableWidgetItem(str(red[1])))  
                self.porkatTable.setItem(red_index, 2, QTableWidgetItem(str(red[2])))  
                self.porkatTable.setItem(red_index, 3, QTableWidgetItem(str(red[3])))  
                self.porkatTable.setItem(red_index, 4, QTableWidgetItem(str(red[4]))) 

                # Omogućava prelamanje linija u tekstu u ćelijama
                #self.porkatTable.setWordWrap(True)
                # Automatski prilagođava visinu redova tako da se sadržaj prikazuje
                #self.porkatTable.resizeRowsToContents()

                # Onemogućavanje editovanja ćelija
                for col in range(4):
                    item = self.porkatTable.item(red_index, col)
                    if item:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                 

                # Dodavanje dugmeta "Izaberi"
                dugme = QPushButton("Izaberi")
                dugme.setStyleSheet("""
                    QPushButton {
                        background-color: #3498db;
                        color: white;
                        border: 2px solid navy;
                        border-radius: 6px;
                        padding: 6px 14px;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #2980b9;
                    }
                    QPushButton:pressed {
                        background-color: #2471a3;
                    }
                """)
                dugme.clicked.connect(partial(self.prebaci_podatke, red_index))
                self.porkatTable.setCellWidget(red_index, 5, dugme)
                for row in range(self.porkatTable.rowCount()):
                    for col in range(self.porkatTable.columnCount()):
                        item = self.porkatTable.item(row, col)
                        if item is not None:
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            cursor.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška pri učitavanju poreskih kategorija:\n{str(e)}")

    def filtriraj_porkat(self):
        """Filtriranje podataka u partneriTable na osnovu pretrage."""
        filter_text = self.pretragaEdit.text().lower()

        for row in range(self.porkatTable.rowCount()):
            kategorija = self.porkatTable.item(row, 2).text().lower()
            opis = self.porkatTable.item(row, 3).text().lower()

            # Prikazujemo samo redove koji sadrže tekst iz pretrage
            should_show = filter_text in kategorija or filter_text in opis
            self.porkatTable.setRowHidden(row, not should_show)

    def prebaci_podatke(self, row):
        """Prenosi podatke iz izabranog reda u FaktureDialog."""
        keykat = self.porkatTable.item(row, 1).text()
        category = self.porkatTable.item(row, 2).text()        

        self.fakture_dialog.keykatEdit.setText(category)
        self.fakture_dialog.categoryEdit.setText(keykat)

        self.accept()  # Zatvori dijalog