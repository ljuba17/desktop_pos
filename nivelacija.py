import os
import sys
import psycopg2
import webbrowser
from PyQt6.QtWidgets import QDialog, QMessageBox, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import QDate
from PyQt6 import uic, QtGui
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtCore import Qt
import configparser
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, PageBreak, Paragraph, Spacer


# Učitavanje konfiguracije iz kasa.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)
GODINA = config.get('POS_Settings', 'god')
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')

class NivelacijaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "nivelacija.ui")
        uic.loadUi(ui_path, self)
        
        # Postavljanje današnjeg datuma
        today = QDate.currentDate()
        self.datumEdit.setDate(today)

        # Poslednja kolona id je skrivena
        # Postavljanje širine kolona u tableStavke
        self.tableStavke.setColumnWidth(0, 60)  # Prva kolona širine 80
        self.tableStavke.setColumnWidth(1, 70)  # Druga kolona širine 70
        self.tableStavke.setColumnWidth(2, 220)  # Treća kolona širine 140
        self.tableStavke.setColumnWidth(3, 80)  # Četvrta kolona širine 80
        self.tableStavke.setColumnWidth(4, 90)  # Peta kolona širine 90
        self.tableStavke.setColumnWidth(5, 90)  # Peta kolona širine 90
        self.tableStavke.setColumnWidth(6, 90)  # Peta kolona širine 90
        self.tableStavke.setColumnWidth(7, 90)  # Peta kolona širine 90
        self.tableStavke.setColumnHidden(0, True)

        # Povezivanje dugmeta sa funkcijom za učitavanje izveštaja
        #self.btnObradi.clicked.connect()
        self.btnCancel.clicked.connect(self.reject)
        