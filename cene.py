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
        # Pokretanje funkcije za primenu nivelacije
        self.primeni_nivelacije()
        self.ucitaj_cene(dana=10)

        # Tabela u zalihe dijalog
        self.tableCene.setColumnWidth(0, 100)  # Prva kolona širine 100 - datum
        self.tableCene.setColumnWidth(1, 80)  # Druga kolona širine 80 - sifra
        self.tableCene.setColumnWidth(2, 290)  # Treca kolona širine 290 - naziv
        self.tableCene.setColumnWidth(3, 80)  # Cetvrta kolona širine 80 - stara cena
        self.tableCene.setColumnWidth(4, 80)  # Peta kolona širine 80 - nova cena

        # Povezivanje dugmeta sa funkcijom za učitavanje izveštaja
        self.btnCancel.clicked.connect(self.reject)

    def primeni_nivelacije(self):
        """
        Automatska primena nivelacija za dokumente čiji datum važenja (`datdospeca`) je prošao,
        osim za 'Auto niv.' (nivelacije popusta).
        """
        today = datetime.now().date()

        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        cursor = conn.cursor()

        # Dohvati sve dokumente za nivelacije za dati objekat iz kasa.ini
        cursor.execute("""
            SELECT broj, god, sifobj, datdospeca
            FROM kasa.robnadok
            WHERE vrsta = 4
            AND god = %s
            AND sifobj = %s
            AND datdospeca <= %s
            AND opis NOT LIKE 'Auto niv. br:%%'
            ORDER BY datdospeca
        """, (GODINA, SIFOBJEKTA, today))
        nivelacije = cursor.fetchall()

        for broj, god, sifobj, datdospeca in nivelacije:
            # Dohvati sve stavke za dokument
            cursor.execute("""
                SELECT artikliid, cena
                FROM kasa.karticaart
                WHERE god = %s
                AND sifobj = %s
                AND broj = %s
                AND vrsta = 4
                AND opis NOT LIKE 'Auto niv. br:%%'
            """, (god, sifobj, broj))
            stavke = cursor.fetchall()

            for artikliid, nova_cena in stavke:
                # Provera za novije nivelacije istog artikla
                cursor.execute("""
                    SELECT 1
                    FROM kasa.karticaart
                    WHERE god = %s
                    AND sifobj = %s
                    AND artikliid = %s
                    AND vrsta = 4
                    AND datum > %s
                    AND opis NOT LIKE 'Auto niv. br:%%'
                    LIMIT 1
                """, (god, sifobj, artikliid, datdospeca))
                if cursor.fetchone():
                    continue  # postoji novija nivelacija → preskoči

                # Ažuriraj cenu u zalihama
                cursor.execute("""
                    UPDATE kasa.zaliheart
                    SET cena = %s
                    WHERE god = %s
                    AND sifobj = %s
                    AND artikliid = %s
                """, (nova_cena, god, sifobj, artikliid))

        conn.commit()
        cursor.close()
        conn.close()

    def ucitaj_cene(self, dana=10):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            query = """
                SELECT k.datum, a.sifra, a.naziv, k.staracena AS stara_cena, k.cena AS nova_cena
                FROM kasa.karticaart k
                JOIN kasa.artikli a ON k.artikliid = a.id
                JOIN kasa.zaliheart z ON z.artikliid = k.artikliid 
                                AND z.god = k.god 
                                AND z.sifobj = k.sifobj
                WHERE k.god = %s
                AND k.sifobj = %s
                AND k.kar = 1
                AND k.vrsta = 4
                AND k.datum >= CURRENT_DATE - interval '%s day'
                AND k.opis NOT LIKE 'Auto niv. br:%%'
                ORDER BY k.datum DESC;
            """

            cursor.execute(query, (GODINA, SIFOBJEKTA, dana))
            rezultati = cursor.fetchall()

            self.tableCene.setRowCount(len(rezultati))

            for row_idx, (datum, sifra, naziv, stara_cena, nova_cena) in enumerate(rezultati):
                # Datum
                self.tableCene.setItem(row_idx, 0, QTableWidgetItem(datum.strftime("%d.%m.%Y")))

                # Šifra
                self.tableCene.setItem(row_idx, 1, QTableWidgetItem(str(sifra)))

                # Naziv artikla
                self.tableCene.setItem(row_idx, 2, QTableWidgetItem(naziv))

                # Stara cena (crvena)
                item_stara = QTableWidgetItem(f"{stara_cena:.2f}")
                item_stara.setForeground(QBrush(QColor("red")))
                self.tableCene.setItem(row_idx, 3, item_stara)

                # Nova cena (zelena)
                item_nova = QTableWidgetItem(f"{nova_cena:.2f}")
                item_nova.setForeground(QBrush(QColor("green")))
                font = item_nova.font()
                font.setBold(True)
                item_nova.setFont(font)
                self.tableCene.setItem(row_idx, 4, item_nova)

            cursor.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Ne mogu da učitam izmene cena:\n{e}")

