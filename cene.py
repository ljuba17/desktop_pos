import os
import platform
import subprocess
import sys
import psycopg2
import webbrowser
from PyQt6.QtWidgets import QDialog, QMessageBox, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import QDate
from PyQt6 import uic, QtGui
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtCore import Qt
import configparser
from datetime import datetime


# Učitavanje konfiguracije iz kasa.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)
GODINA = config.get('POS_Settings', 'god')
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')

class CeneDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "cene.ui")
        uic.loadUi(ui_path, self)
        
        # Postavljanje današnjeg datuma
        today = QDate.currentDate()
        # Pokretanje funkcije za popunjavanje tabele
        #self.ucitaj_zalihe()

        # Tabela u zalihe dijalog
        self.tableCene.setColumnWidth(0, 100)  # Prva kolona širine 100 - datum
        self.tableCene.setColumnWidth(1, 80)  # Druga kolona širine 80 - sifra
        self.tableCene.setColumnWidth(2, 290)  # Treca kolona širine 290 - naziv
        self.tableCene.setColumnWidth(3, 80)  # Cetvrta kolona širine 80 - stara cena
        self.tableCene.setColumnWidth(4, 80)  # Peta kolona širine 80 - nova cena

        # Povezivanje dugmeta sa funkcijom za učitavanje izveštaja
        self.btnCancel.clicked.connect(self.reject)