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

class ZaliheDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "zalihe.ui")
        uic.loadUi(ui_path, self)
        
        # Postavljanje današnjeg datuma
        today = QDate.currentDate()
        # Pokretanje funkcije za popunjavanje tabele
        self.ucitaj_zalihe()

        # Tabela u zalihe dijalog
        self.tableZalihe.setColumnWidth(0, 70)  # Druga kolona širine 70 - sifra
        self.tableZalihe.setColumnWidth(1, 270)  # Treca kolona širine 270 - naziv 
        self.tableZalihe.setColumnWidth(2, 70)  # Cetvrta kolona širine 70 - jed. mere
        self.tableZalihe.setColumnWidth(3, 70)  # Peta kolona širine 70 - PDV stopa
        self.tableZalihe.setColumnWidth(4, 85)  # Sesta kolona širine 85 - kolicina
        self.tableZalihe.setColumnWidth(5, 85)  # Sedma kolona širine 85 - cena
        self.tableZalihe.setColumnWidth(6, 90)  # Osma kolona širine 90 - vrednost

        # Povezivanje dugmeta sa funkcijom za učitavanje izveštaja
        self.btnCancel.clicked.connect(self.reject)
        #self.btnStampa.clicked.connect(self.stampaj_artikle_prodati)


    def ucitaj_zalihe(self):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # Izvršavanje funkcije obradi – današnji datum
            cursor.execute("""
                SELECT * FROM kasa.obradi(%s, %s, %s, CURRENT_DATE)
            """, [GODINA, 1, SIFOBJEKTA])

            rezultati = cursor.fetchall()
            kolone = [desc[0] for desc in cursor.description]

            # Indeksi kolona koje nas zanimaju iz funkcije obradi
            idx_sifra   = kolone.index("sifra")
            idx_naziv   = kolone.index("naziv")
            idx_jm      = kolone.index("jedinica_mere")
            idx_pdv     = kolone.index("pdv_stopa")
            idx_kol     = kolone.index("kolicina")
            idx_cena    = kolone.index("maloprodajna_cena")
            idx_vred    = kolone.index("vrednost")

            # Podesimo broj redova i kolona (7 kolona)
            self.tableZalihe.setRowCount(len(rezultati))
            self.tableZalihe.setColumnCount(7)
            self.tableZalihe.setHorizontalHeaderLabels([
                "Šifra", "Naziv", "JM", "PDV %", "Količina", "Cena", "Vrednost"
            ])

            # Popunjavanje podacima
            for i, red in enumerate(rezultati):
                # 0 Šifra
                self.tableZalihe.setItem(i, 0, QTableWidgetItem(str(red[idx_sifra])))

                # 1 Naziv
                self.tableZalihe.setItem(i, 1, QTableWidgetItem(str(red[idx_naziv])))

                # 2 JM
                self.tableZalihe.setItem(i, 2, QTableWidgetItem(str(red[idx_jm])))

                # 3 PDV stopa
                item = QTableWidgetItem(f"{red[idx_pdv]:.0f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tableZalihe.setItem(i, 3, item)

                # 4 Kolicina
                item = QTableWidgetItem(f"{red[idx_kol]:,.2f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tableZalihe.setItem(i, 4, item)

                # 5 Cena
                item = QTableWidgetItem(f"{red[idx_cena]:,.2f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tableZalihe.setItem(i, 5, item)

                # 6 Vrednost
                item = QTableWidgetItem(f"{red[idx_vred]:,.2f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tableZalihe.setItem(i, 6, item)

            # 🔄 Ažuriranje zaliheart sa stanjem za danas
            for red in rezultati:
                sifra = red[idx_sifra]
                zaliha = red[idx_kol]

                cursor.execute("""
                    SELECT 1 FROM kasa.zaliheart 
                    WHERE god = %s AND sifobj = %s AND sifra = %s
                """, [GODINA, SIFOBJEKTA, sifra])
                exists = cursor.fetchone()

                if exists:
                    cursor.execute("""
                        UPDATE kasa.zaliheart
                        SET zaliha = %s
                        WHERE god = %s AND sifobj = %s AND sifra = %s
                    """, [zaliha, GODINA, SIFOBJEKTA, sifra])

            conn.commit()

            cursor.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Ne mogu da učitam zalihe:\n{e}")

