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

class TraziPartneraDialog(QDialog):
    def __init__(self, fakture_dialog, parent=None):  # bez tipa
        super().__init__(parent)
        self.fakture_dialog = fakture_dialog
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "traziPartnera.ui")
        uic.loadUi(ui_path, self)

        self.odustaniBtn.clicked.connect(self.reject)

        self.popuni_partnere()

        # Povezivanje pretrage sa funkcijom filtriranja
        self.pretragaEdit.textChanged.connect(self.filtriraj_partnere)

        self.partneriTable.horizontalHeader().setStyleSheet("QHeaderView::section { color: rgb(0, 0, 0); }")
        self.partneriTable.setStyleSheet("QTableWidget { background-color: rgb(240, 255, 255); }")

        # Postavljanje širine kolona u partneriTable
        self.partneriTable.setColumnWidth(0, 50)  # Prva kolona širine 50
        self.partneriTable.setColumnWidth(1, 280)  # Druga kolona širine 270
        self.partneriTable.setColumnWidth(2, 80)  # Treća kolona širine 80
        self.partneriTable.setColumnWidth(3, 80)  # Četvrta kolona širine 80
        self.partneriTable.setColumnWidth(4, 100)  # Peta kolona širine 100 (dugme Izaberi)
        self.partneriTable.setColumnHidden(0, True)  # sakrivam kolonu u kojoj je id partnera

    def popuni_partnere(self):
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
                SELECT id, naziv, pib, jbkjs
                FROM kasa.partneri
                ORDER BY (id) DESC
            """)

            rezultati = cursor.fetchall()
            self.partneriTable.setRowCount(0)  # Čisti tabelu

            for red_index, red in enumerate(rezultati):
                self.partneriTable.insertRow(red_index)

                # Unos podataka u ćelije
                self.partneriTable.setItem(red_index, 0, QTableWidgetItem(str(red[0])))  # id
                self.partneriTable.setItem(red_index, 1, QTableWidgetItem(str(red[1])))  # naziv
                self.partneriTable.setItem(red_index, 2, QTableWidgetItem(str(red[2])))  # pib
                self.partneriTable.setItem(red_index, 3, QTableWidgetItem(str(red[3])))  # jbkjs

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
                self.partneriTable.setCellWidget(red_index, 4, dugme)
                for row in range(self.partneriTable.rowCount()):
                    for col in range(self.partneriTable.columnCount()):
                        item = self.partneriTable.item(row, col)
                        if item is not None:
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            cursor.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška pri učitavanju partnera:\n{str(e)}")

    def filtriraj_partnere(self):
        """Filtriranje podataka u partneriTable na osnovu pretrage."""
        filter_text = self.pretragaEdit.text().lower()

        for row in range(self.partneriTable.rowCount()):
            naziv = self.partneriTable.item(row, 1).text().lower()
            pib = self.partneriTable.item(row, 2).text().lower()

            # Prikazujemo samo redove koji sadrže tekst iz pretrage
            should_show = filter_text in naziv or filter_text in pib
            self.partneriTable.setRowHidden(row, not should_show)

    def prebaci_podatke(self, row):
        """Prenosi podatke iz izabranog reda u FaktureDialog."""
        id_partner = self.partneriTable.item(row, 0).text()
        naziv = self.partneriTable.item(row, 1).text()
        jbkjs = self.partneriTable.item(row, 3).text()

        self.fakture_dialog.idkupcaEdit.setText(id_partner)
        self.fakture_dialog.kupacEdit.setText(naziv)
        self.fakture_dialog.jbkjsjnEdit.setText(jbkjs)

        self.accept()  # Zatvori dijalog