import os
import sys
import psycopg2
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import QDialog, QTableWidgetItem, QPushButton, QMessageBox
from PyQt6.QtGui import QColor, QBrush, QIcon
from PyQt6 import uic
import configparser
import requests
from functools import partial
import json
from datetime import datetime
from decimal import Decimal
from trazi_partnera import TraziPartneraDialog
from porkat import PorkatDialog
from partneri import PartneriDialog
from efakture import eFaktureDialog
from reportlab.platypus import SimpleDocTemplate, BaseDocTemplate, Frame, PageTemplate, Table, TableStyle, Spacer, Paragraph, KeepTogether
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.styles import ParagraphStyle
from textwrap import wrap
import webbrowser

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

class FaktureDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "fakture.ui")
        uic.loadUi(ui_path, self)
        
        self.GODINA = GODINA
        self.SIFOBJEKTA = SIFOBJEKTA

        self.idkupcaEdit.hide()
        self.jbkjsjnEdit.hide()
        self.vrstaEdit.hide()

        self.odustaniBtn.clicked.connect(self.reject)
        self.zatvoriBtn.clicked.connect(self.reject)
        self.postavi_podatke_za_fakturu()
        self.sacuvajBtn.clicked.connect(self.pozovi_formiranje_fakture)
        self.faktureTab.currentChanged.connect(self.on_tab_changed)    # Pri promeni taba poziva funkciju za osvezavanje

        self.radioFaktura.toggled.connect(self.postavi_broj_fakture)
        self.radioGotovina.toggled.connect(self.postavi_broj_fakture)
        self.radioAvans.toggled.connect(self.postavi_broj_fakture)

        self.traziBtn.clicked.connect(self.otvori_trazi_partnera)
        self.noviBtn.clicked.connect(self.otvori_partnera)
        self.traziPKBtn.clicked.connect(self.otvori_trazi_porkat)

        self.popuni_neobradjene()
        self.neobradjeniTable.itemSelectionChanged.connect(self.prikazi_stavke_racuna)
        self.neobradjeniTable.cellClicked.connect(self.oznaci_red)

        self.datumdpdEdit.setDisplayFormat("dd-MM-yyyy")
        self.datumpredEdit.setDisplayFormat("dd-MM-yyyy")
        self.datumvazenjaEdit.setDisplayFormat("dd-MM-yyyy")
        datum_fakture = QDate.currentDate()
        self.datumpredEdit.setDate(datum_fakture)
        datum_valute = QDate.currentDate()
        self.datumvazenjaEdit.setDate(datum_valute)

        self.neobradjeniTable.setStyleSheet("QTableWidget { color: black; }")
        self.neobradjeniTable.horizontalHeader().setStyleSheet("QHeaderView::section { color: rgb(255, 255, 255); }")
        self.izabraniTable.setStyleSheet("QTableWidget { color: black; }")
        self.izabraniTable.horizontalHeader().setStyleSheet("QHeaderView::section { color: rgb(255, 255, 255); }")
        self.stavkeTable.setStyleSheet("QTableWidget { background-color: rgb(240, 255, 255); }")

        # Postavljanje širine kolona u neobradjeniTable
        self.neobradjeniTable.setColumnWidth(0, 80)  # Prva kolona širine 80
        self.neobradjeniTable.setColumnWidth(1, 50)  # Druga kolona širine 50
        self.neobradjeniTable.setColumnWidth(2, 110)  # Treća kolona širine 120
        self.neobradjeniTable.setColumnWidth(3, 100)  # Četvrta kolona širine 100
        self.neobradjeniTable.setColumnWidth(4, 100)  # Peta kolona širine 100
        self.neobradjeniTable.setColumnWidth(5, 100)  # Šesta kolona širine 100 (dugme Izaberi)
        self.neobradjeniTable.setColumnHidden(4, True)  # sakrivam kolonu u kojoj je brracpu u kasasum tabele u bazi
        # Postavljanje širine kolona u izabraniTable
        self.izabraniTable.setColumnWidth(0, 80)  # Prva kolona širine 80
        self.izabraniTable.setColumnWidth(1, 50)  # Druga kolona širine 50
        self.izabraniTable.setColumnWidth(2, 110)  # Treća kolona širine 110
        self.izabraniTable.setColumnWidth(3, 100)  # Četvrta kolona širine 100
        self.izabraniTable.setColumnWidth(4, 100)  # Peta kolona širine 100
        self.izabraniTable.setColumnWidth(5, 100)  # Šesta kolona širine 100 (dugme Ponisti)
        self.izabraniTable.setColumnHidden(4, True)  # sakrivam kolonu u kojoj je brracpu u kasasum tabele u bazi
        # Postavljanje širine kolona u stavkeTable
        self.stavkeTable.setColumnWidth(0, 80)  # Prva kolona širine 80
        self.stavkeTable.setColumnWidth(1, 190)  # Druga kolona širine 190
        self.stavkeTable.setColumnWidth(2, 90)  # Treća kolona širine 90
        self.stavkeTable.setColumnWidth(3, 100)  # Četvrta kolona širine 100
        self.stavkeTable.setColumnWidth(4, 100)  # Peta kolona širine 100

    ################ Drugi tab pregled faktura ################
        self.popuni_fakture()
        self.stampaBtn.clicked.connect(self.onStampaBtnClick)
        self.eFakturaBtn.clicked.connect(self.oneFakturaBtnClick)
        self.osveziBtn.clicked.connect(self.osvezi_status_e_faktura)
        self.faktureTable.cellClicked.connect(self.oznaci_fakturu)

        self.faktureTable.setStyleSheet("QTableWidget { color: black; }")
        self.faktureTable.setStyleSheet("QTableWidget { background-color: rgb(240, 255, 255); }")
        # Postavljanje širine kolona u faktureTable
        self.faktureTable.setColumnWidth(0, 50)  # Prva kolona širine 50  id iz faktura
        self.faktureTable.setColumnWidth(1, 50)  # Druga kolona širine 50 sifobj iz fakture
        self.faktureTable.setColumnWidth(2, 100)  # Treća kolona širine 100 brojfakture iz fakture
        self.faktureTable.setColumnWidth(3, 100)  # Četvrta kolona širine 100 datumpred iz fakture
        self.faktureTable.setColumnWidth(4, 40)  # Peta kolona širine 40 (dugme Izmeni)
        self.faktureTable.setColumnWidth(5, 200)  # Šesta kolona širine 200 naziv iz partneri
        self.faktureTable.setColumnWidth(6, 50)  # Sedma kolona širine 50 idpartneri iz fakture
        self.faktureTable.setColumnWidth(7, 100)  # osma kolona širine 100 datumdpd iz fakture
        self.faktureTable.setColumnWidth(8, 100)  # deveta kolona širine 100 datumvazenja iz fakture
        self.faktureTable.setColumnWidth(9, 100)  # deseta kolona širine 100 status_salinv iz fakture
        self.faktureTable.setColumnWidth(10, 100)  # jedanaesta kolona širine 100 invoiceid iz fakture
        self.faktureTable.setColumnWidth(11, 100)  # dvanaesta kolona širine 100 salesinvoiceid iz fakture
        self.faktureTable.setColumnWidth(12, 100)  # trinaesta kolona širine 100 vrsta iz fakture
        self.faktureTable.setColumnWidth(13, 60)  # trinaesta kolona širine 60 god iz fakture
        self.faktureTable.setColumnHidden(0, True)  # sakrivam kolonu u kojoj je id fakture u fakture tabele u bazi
        self.faktureTable.setColumnHidden(1, True)  # sakrivam kolonu u kojoj je sifobj fakture u fakture tabele u bazi
        self.faktureTable.setColumnHidden(6, True)  # sakrivam kolonu u kojoj je idpartneri fakture u fakture tabele u bazi
        # self.faktureTable.setColumnHidden(12, True)  # sakrivam kolonu u kojoj je vrsta fakture u fakture tabele u bazi
        self.faktureTable.setColumnHidden(13, True)  # sakrivam kolonu u kojoj je god fakture u fakture tabele u bazi

        self.stavkefaktTable.setStyleSheet("QTableWidget { color: black; }")
        self.stavkefaktTable.setStyleSheet("QTableWidget { background-color: rgb(240, 255, 255); }")
        # Postavljanje širine kolona u stavkefaktTable
        self.stavkefaktTable.setColumnWidth(0, 80)  # Prva kolona širine 80  sifra iz karticaart
        self.stavkefaktTable.setColumnWidth(1, 150)  # Druga kolona širine 150 naziv iz artikli
        self.stavkefaktTable.setColumnWidth(2, 80)  # Treća kolona širine 80 jm iz jedmere
        self.stavkefaktTable.setColumnWidth(3, 100)  # Četvrta kolona širine 100 kolicina iz karticaart
        self.stavkefaktTable.setColumnWidth(4, 90)  # Peta kolona širine 90 iz karticaart racuna se po formuli round(karticaart.cenanabavna *  ((1 - ((KARTICAART.POREZPROC*100) / (KARTICAART.POREZPROC +100)) /100)),2)
        self.stavkefaktTable.setColumnWidth(5, 90)  # Šesta kolona širine 90 rabatproc iz karticaart
        self.stavkefaktTable.setColumnWidth(6, 100)  # Sedma kolona širine 100 rabatdinarski iz karticaart
        self.stavkefaktTable.setColumnWidth(7, 100)  # osma kolona širine 100 kolona sa indeksom 4 * kolona sa indeksom 3
        self.stavkefaktTable.setColumnWidth(8, 90)  # deveta kolona širine 90 porezproc iz karticaart
        self.stavkefaktTable.setColumnWidth(9, 100)  # deseta kolona širine 100 porez iz karticaart
        self.stavkefaktTable.setColumnWidth(10, 100)  # jedanaesta kolona širine 100 cena * kolicina iz karticaart
        self.stavkefaktTable.setColumnWidth(11, 60)  # dvanaesta kolona širine 60 tarifa iz karticaart
        self.stavkefaktTable.setColumnWidth(12, 60)  # trinaesta kolona širine 60 id iz karticaart
        self.stavkefaktTable.setColumnHidden(11, True)  # sakrivam kolonu u kojoj je tarifa u karticaart tabele u bazi
        self.stavkefaktTable.setColumnHidden(12, True)  # sakrivam kolonu u kojoj je id karticaart tabele u bazi

    def on_tab_changed(self, index):
        if index == 1:  # drugi tab, jer se broji od 0
            self.popuni_fakture()

    def postavi_podatke_za_fakturu(self):
        try:
            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT obv FROM kasa.fvr LIMIT 1")
                    rezultat = cursor.fetchone()
                    if rezultat:
                        obv = rezultat[0]  # True ili False

                        if obv:  # Firma je obveznik
                            self.categoryEdit.setText("")
                            self.keykatEdit.setText("S")
                            self.napomenaEdit.setText("")
                        else:  # Firma nije obveznik
                            self.categoryEdit.setText("PDV-RS-33")
                            self.keykatEdit.setText("SS")
                            self.napomenaEdit.setText("član 33")

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška pri čitanju iz FVR tabele:\n{e}")

    def popuni_neobradjene(self):
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
                SELECT broj, kasa, datum, ukiznos, brracpu
                FROM kasa.kasasum
                WHERE god = %s
                AND sifobj = %s
                AND tipracuna IN ('0', '4')
                AND tiptransakcije = '0'
                AND brracpu IS NOT NULL
                AND brfakt IS NULL
                AND dokstatus IN ('PP', 'AP')
                ORDER BY (datum,broj) DESC
            """, (GODINA, SIFOBJEKTA))

            rezultati = cursor.fetchall()
            self.neobradjeniTable.setRowCount(0)  # Čisti tabelu

            for red_index, red in enumerate(rezultati):
                self.neobradjeniTable.insertRow(red_index)

                # Polja koja se upisuju u tabelu
                vrednosti = [
                    str(red[0]),                # broj
                    str(red[1]),                # kasa
                    str(red[2]),                # datum
                    f"{red[3]:.2f}",            # ukiznos
                    str(red[4])                 # brracpu (skriveno polje)
                ]

                for col_index, vrednost in enumerate(vrednosti):
                    item = QTableWidgetItem(vrednost)
                    # onemogućimo editovanje odmah
                    flags = item.flags()
                    flags &= ~Qt.ItemFlag.ItemIsEditable
                    item.setFlags(flags)
                    self.neobradjeniTable.setItem(red_index, col_index, item)

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
                dugme.clicked.connect(lambda _, r=red_index: self.izaberi_racun(r))
                self.neobradjeniTable.setCellWidget(red_index, 5, dugme)

            cursor.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška pri učitavanju računa:\n{str(e)}")

    def prikazi_stavke_racuna(self):
        selected_items = self.neobradjeniTable.selectedItems()
        if not selected_items:
            return

        # Uzimamo vrednosti iz prve dve kolone selektovanog reda
        red = selected_items[0].row()
        broj = self.neobradjeniTable.item(red, 0).text()
        kasa = self.neobradjeniTable.item(red, 1).text()

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
                SELECT k.sifra, a.naziv, k.kolic, k.cena, (k.kolic * k.cena) AS vrednost
                FROM kasa.kasa k
                LEFT JOIN kasa.artikli a ON a.sifra = k.sifra
                WHERE k.god = %s
                AND k.sifobj = %s
                AND k.broj = %s
                AND k.kasa = %s
            """, (GODINA, SIFOBJEKTA, broj, kasa))

            rezultati = cursor.fetchall()
            self.stavkeTable.setRowCount(0)

            for red_index, red in enumerate(rezultati):
                self.stavkeTable.insertRow(red_index)
                self.stavkeTable.setItem(red_index, 0, QTableWidgetItem(str(red[0])))  # sifra
                self.stavkeTable.setItem(red_index, 1, QTableWidgetItem(str(red[1])))  # naziv
                self.stavkeTable.setItem(red_index, 2, QTableWidgetItem(f"{red[2]:.3f}"))  # kolicina
                self.stavkeTable.setItem(red_index, 3, QTableWidgetItem(f"{red[3]:.2f}"))  # cena
                self.stavkeTable.setItem(red_index, 4, QTableWidgetItem(f"{red[4]:.2f}"))  # vrednost

                # Onemogućavanje editovanja ćelija
                for col in range(5):
                    item = self.stavkeTable.item(red_index, col)
                    if item:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            cursor.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška pri prikazu stavki:\n{str(e)}")

    def oznaci_red(self, red):
        """
        Obeležava izabrani red u neobradjeniTable tako što menja njegov stil.
        """
        # Resetujemo sve redove na podrazumevani stil
        for r in range(self.neobradjeniTable.rowCount()):
            for c in range(self.neobradjeniTable.columnCount()):
                item = self.neobradjeniTable.item(r, c)
                if item:
                    font = item.font()
                    font.setBold(False)
                    font.setPointSize(10)
                    item.setFont(font)

        # Stilizujemo samo izabrani red
        for c in range(self.neobradjeniTable.columnCount()):
            item = self.neobradjeniTable.item(red, c)
            if item:
                font = item.font()
                font.setBold(True)
                font.setPointSize(11)  # Veći font za istaknuti red
                item.setFont(font)

    def prikazi_stavke_racuna_za_racun(self, broj, kasa):
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
                SELECT k.sifra, a.naziv, k.kolic, k.cena, (k.kolic * k.cena) AS vrednost
                FROM kasa.kasa k
                LEFT JOIN kasa.artikli a ON a.sifra = k.sifra
                WHERE k.god = %s
                AND k.sifobj = %s
                AND k.broj = %s
                AND k.kasa = %s
            """, (GODINA, SIFOBJEKTA, broj, kasa))

            rezultati = cursor.fetchall()
            self.stavkeTable.setRowCount(0)

            for red_index, red in enumerate(rezultati):
                self.stavkeTable.insertRow(red_index)
                self.stavkeTable.setItem(red_index, 0, QTableWidgetItem(str(red[0])))  # sifra
                self.stavkeTable.setItem(red_index, 1, QTableWidgetItem(str(red[1])))  # naziv
                self.stavkeTable.setItem(red_index, 2, QTableWidgetItem(f"{red[2]:.3f}"))  # kolicina
                self.stavkeTable.setItem(red_index, 3, QTableWidgetItem(f"{red[3]:.2f}"))  # cena
                self.stavkeTable.setItem(red_index, 4, QTableWidgetItem(f"{red[4]:.2f}"))  # vrednost

                for col in range(5):
                    item = self.stavkeTable.item(red_index, col)
                    if item:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            cursor.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška pri prikazu stavki:\n{str(e)}")

    def izaberi_racun(self, red):
        # 1. Očisti prethodni izbor ako postoji
        self.izabraniTable.setRowCount(0)
        self.bracpuEdit.clear()
        self.datumdpdEdit.setDate(QDate.currentDate())  # reset na današnji datum

        # 2. Izvuci podatke iz selektovanog reda u neobradjeniTable
        broj_racuna = self.neobradjeniTable.item(red, 0).text()
        datum_str = self.neobradjeniTable.item(red, 2).text()
        kasa = self.neobradjeniTable.item(red, 1).text()
        ukupno = self.neobradjeniTable.item(red, 3).text()
        bracpu = self.neobradjeniTable.item(red, 4).text()

        # 3. Ubaci podatke u izabraniTable
        self.izabraniTable.setRowCount(1)
        self.izabraniTable.setItem(0, 0, QTableWidgetItem(broj_racuna))
        self.izabraniTable.selectRow(0)
        self.izabraniTable.setItem(0, 1, QTableWidgetItem(kasa))
        self.izabraniTable.setItem(0, 2, QTableWidgetItem(datum_str))
        self.izabraniTable.setItem(0, 3, QTableWidgetItem(ukupno))
        self.izabraniTable.setItem(0, 4, QTableWidgetItem(bracpu))

        # 4. Stilizovano dugme "Poništi"
        dugme_ponisti = QPushButton("Poništi")
        dugme_ponisti.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: 2px solid darkred;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #922b21;
            }
        """)
        dugme_ponisti.clicked.connect(self.ponisti_izbor)
        self.izabraniTable.setCellWidget(0, 5, dugme_ponisti)
        self.oznaci_red(red)

        # 5. Popuni kontrole izabranim vrednostima
        self.bracpuEdit.setText(bracpu)
        self.prikazi_stavke_racuna_za_racun(broj_racuna, kasa)

        try:
            datum_qdate = QDate.fromString(datum_str, "yyyy-MM-dd")
            if datum_qdate.isValid():
                self.datumdpdEdit.setDate(datum_qdate)
            else:
                # Ako format nije dd.MM.yyyy pokušaj drugi
                datum_qdate = QDate.fromString(datum_str, "dd-MM-yyyy")
                if datum_qdate.isValid():
                    self.datumdpdEdit.setDate(datum_qdate)
                    
            self.postavi_broj_fakture()

        except Exception as e:
            print("Greška u parsiranju datuma:", e)
        
    def ponisti_izbor(self):
        self.izabraniTable.setRowCount(0)
        self.bracpuEdit.clear()
        self.datumdpdEdit.setDate(QDate.currentDate())

    def otvori_trazi_partnera(self):
        """ Otvara dijalog za pretragu partnera """
        dialog = TraziPartneraDialog(self)  # Prosleđujemo `self` kao parent
        dialog.exec()  # Pokrećemo dijalog modalno

    def otvori_partnera(self):
        """ Otvara dijalog za unos partnera """
        dialog = PartneriDialog(self)  # Prosleđujemo `self` kao parent
        dialog.exec()  # Pokrećemo dijalog modalno
        
    def otvori_trazi_porkat(self):
        """ Otvara dijalog za pretragu poreskih kategorija """
        dialog = PorkatDialog(self)  # Prosleđujemo `self` kao parent
        dialog.exec()  # Pokrećemo dijalog modalno


    def generisi_broj_fakture(self, vrsta: int, izabrani_broj: str = None) -> str:
        broj_fakture = ""
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            if vrsta == 1:  # Klasična faktura
                cursor.execute("""
                    SELECT COUNT(*) FROM kasa.fakture 
                    WHERE vrsta = 1 AND god = %s AND sifobj = %s
                """, (self.GODINA, self.SIFOBJEKTA))
                rezultat = cursor.fetchone()
                sledeci_broj = (rezultat[0] or 0) + 1
                broj_fakture = f"{sledeci_broj}-{self.SIFOBJEKTA}-{self.GODINA}"
            elif vrsta == 2:  # Gotovina
                broj_fakture = izabrani_broj
            elif vrsta == 3:  # Avansna faktura
                cursor.execute("""
                    SELECT COUNT(*) FROM kasa.fakture 
                    WHERE vrsta = 3 AND god = %s AND sifobj = %s
                """, (self.GODINA, self.SIFOBJEKTA))
                rezultat = cursor.fetchone()
                sledeci_broj = (rezultat[0] or 0) + 1
                broj_fakture = f"A-{sledeci_broj}-{self.SIFOBJEKTA}-{self.GODINA}"
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[Greška] generisanje broja fakture: {e}")
            broj_fakture = ""

        return broj_fakture

    def postavi_broj_fakture(self):
        if self.radioFaktura.isChecked():
            broj_fakture = self.generisi_broj_fakture(1)
            #vrsta_fakture = 1
            self.vrstaEdit.setText("1")
        elif self.radioGotovina.isChecked():
            izabrani_red = self.izabraniTable.currentRow()
            if izabrani_red >= 0:
                celija = self.izabraniTable.item(izabrani_red, 0)
                if celija is not None:
                    broj_iz_kase = celija.text()
                    broj_fakture = self.generisi_broj_fakture(2, izabrani_broj=broj_iz_kase)
                    #vrsta_fakture = 2
                    self.vrstaEdit.setText("2")
                else:
                    print("[Upozorenje] Celija u koloni 0 je prazna.")
                    broj_fakture = ""
            else:
                print("[Upozorenje] Nije selektovan nijedan red.")
                broj_fakture = ""

        elif self.radioAvans.isChecked():
            broj_fakture = self.generisi_broj_fakture(3)
            #vrsta_fakture = 3
            self.vrstaEdit.setText("3")

        else:
            broj_fakture = ""

        self.brojrnEdit.setText(broj_fakture)  
        #self.vrstaEdit.setText(vrsta_fakture)  

    ################# Formiranje fakture #############
    def resetuj_polja(self):
        self.brojrnEdit.clear()
        datum_fakture = QDate.currentDate()
        self.datumpredEdit.setDate(datum_fakture)
        datum_valute = QDate.currentDate()
        self.datumvazenjaEdit.setDate(datum_valute)
        self.vrstaEdit.clear()
        self.idkupcaEdit.clear()
        self.keykatEdit.clear()
        self.categoryEdit.clear()
        self.napomenaEdit.clear()
        self.datumdpdEdit.clear()
        self.jbkjsjnEdit.clear()
        self.bracpuEdit.clear()
        self.ugovorEdit.clear()
        self.kupacEdit.clear()

    def formiraj_fakturu_iz_fiskalnog_racuna(
        self,
        brojrnEdit: str,
        datumpredEdit: str,
        datumvazenjaEdit: str,
        vrstaEdit: int,
        idkupcaEdit: int,
        keykatEdit: str,
        categoryEdit: str,
        napomenaEdit: str,
        datumdpdEdit: str,
        jbkjsjnEdit: str,
        bracpuEdit: str,
        ugovorEdit: str,
    ):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # === Pročitaj demoef iz tabele fvr ===
            cursor.execute("SELECT demoef FROM kasa.fvr LIMIT 1")
            rezultat = cursor.fetchone()
            demoef = rezultat[0] if rezultat else False  # fallback na False ako nema rezultata

            # ==== KORAK 1: Kreiraj zaglavlje fakture ako ne postoji ====
            cursor.execute("""
                SELECT 1 FROM kasa.fakture
                WHERE god = %s AND sifobj = %s AND brojfakture = %s
            """, (GODINA, SIFOBJEKTA, brojrnEdit))
            if not cursor.fetchone():
                brugov_final = ugovorEdit if ugovorEdit.strip() else str(brojrnEdit)
                cursor.execute("""
                    INSERT INTO kasa.fakture (
                        brojfakture, datumpred, datumvazenja, god, vrsta, idpartneri,
                        sifobj, kreirao, kar, keykat, category, pornapomena,
                        datumdpd, jbkjsnjn, brracpu, brugov,
                        osnovica, ukupnopdv, vrednost, demo
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, 'sistem', 1, %s, %s, %s,
                        %s, %s, %s, %s,
                        0, 0, 0, %s
                    )
                """, (
                    brojrnEdit, datumpredEdit, datumvazenjaEdit, GODINA, vrstaEdit,
                    idkupcaEdit, SIFOBJEKTA, keykatEdit, categoryEdit, napomenaEdit,
                    datumdpdEdit, jbkjsjnEdit, bracpuEdit, brugov_final, demoef
                ))

            # ==== KORAK 2: Pronađi fiskalni račun po brracpu ====
            cursor.execute("""
                SELECT god, sifobj, broj
                FROM kasa.kasasum
                WHERE brracpu = %s
            """, (bracpuEdit,))
            result = cursor.fetchone()

            if not result:
                print("Fiskalni račun nije pronađen.")
                return

            god_racuna, sifobj_racuna, broj_racuna = result

            # ==== KORAK 3: Učitaj stavke fiskalnog računa iz tabela 'kasa' ====
            cursor.execute("""
                SELECT sifra, kolic, cena
                FROM kasa.kasa
                WHERE god = %s AND sifobj = %s AND broj = %s
            """, (god_racuna, sifobj_racuna, broj_racuna))
            stavke = cursor.fetchall()

            # === KORAK 4 i 5: Kopiraj stavke fiskalnog računa (vrsta=8) u fakturu (vrsta=2) i ažuriraj zaglavlje fakture ===
            # 1. Preuzmi stavke iz karticaart za fiskalni račun
            cursor.execute("""
                SELECT sifra, sifobj, broj, datum, kolicina, cena, cenanabavna, tarifa,
                    opis, ui, porez, porezproc, grupa, valuta, rabatproc, rabatdinarski,
                    god, kar, kreirao, kreirano, izmenio, izmenjen, porezid, vm,
                    artikliid, netofcena, kasa, staracena, lokacija_id
                FROM kasa.karticaart
                WHERE god = %s AND sifobj = %s AND vrsta = 8 AND broj = %s
            """, (god_racuna, sifobj_racuna, broj_racuna))

            stavke = cursor.fetchall()
            if not stavke:
                print("Nema stavki za fiskalni račun.")
                return

            # 6. Priprema i izračun zbirnih vrednosti
            ukupna_vrednost = 0
            ukupan_pdv = 0

            for s in stavke:
                (sifra, sifobj, broj, datum, kolicina, cena, cenanabavna, tarifa,
                opis, ui, porez, porezproc, grupa, valuta, rabatproc, rabatdinarski,
                god, kar, kreirao, kreirano, izmenio, izmenjen, porezid, vm,
                artikliid, netofcena, kasa, staracena, lokacija_id) = s

                nova_vrsta = 2
                novi_opis = 'Faktura'

                # Dodavanje u zbir
                ukupna_vrednost += round((cena or 0) * (kolicina or 0),2)
                ukupan_pdv += round((porez or 0),2)

                # Insert nove stavke u karticaart (kao faktura)
                cursor.execute("""
                    INSERT INTO kasa.karticaart (
                        sifra, sifobj, lokacija_id, broj, datum, kolicina, cena, cenanabavna, tarifa,
                        vrsta, opis, ui, porez, porezproc, grupa, valuta, rabatproc,
                        rabatdinarski, god, kar, kreirao, kreirano, izmenio, izmenjen,
                        porezid, vm, idpartneri, marza, dobit, prenetpdv, zavtroskovi,
                        koltren, kolpop, dokstatus, brfakt, artikliid, netofcena, kasa, staracena
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, now(), %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    sifra, SIFOBJEKTA, lokacija_id, broj_racuna, datum, kolicina, cena, cenanabavna, tarifa,
                    nova_vrsta, novi_opis, ui, porez, porezproc, grupa, valuta, rabatproc,
                    rabatdinarski, GODINA, kar, kreirao, izmenio, izmenjen,
                    porezid, vm, idkupcaEdit, None, None, None, None,
                    None, None, None, brojrnEdit, artikliid, netofcena, kasa, staracena
                ))

            # 7. Izračun osnovice
            osnovica = round(ukupna_vrednost - ukupan_pdv,2)

            # 8. Ažuriraj zaglavlje fakture u tabeli fakture
            cursor.execute("""
                UPDATE kasa.fakture
                SET osnovica = %s, ukupnopdv = %s, vrednost = %s
                WHERE god = %s AND sifobj = %s AND brojfakture = %s
            """, (
                osnovica, ukupan_pdv, ukupna_vrednost,
                GODINA, SIFOBJEKTA, brojrnEdit
            ))

            print(f"Faktura ažurirana: osnovica={osnovica}, pdv={ukupan_pdv}, ukupno={ukupna_vrednost}")

            # ==== KORAK 9: Azuriranje kasasum ====
            cursor.execute("""
                UPDATE kasa.kasasum
                SET brfakt = %s, idpartneri = %s, izmenio = %s, izmenjen = now()
                WHERE brracpu = %s
            """, (brojrnEdit, idkupcaEdit, 'sistem', bracpuEdit))
            print(f"Kasasum ažurirana: broj fakture={brojrnEdit}, id kupca={idkupcaEdit}")

            conn.commit()
            print("Faktura uspešno formirana.")

        except Exception as e:
            print(f"Greška u formiranju fakture: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

    def pozovi_formiranje_fakture(self):
        try:
            self.formiraj_fakturu_iz_fiskalnog_racuna(
                self.brojrnEdit.text(),
                self.datumpredEdit.text(),
                self.datumvazenjaEdit.text(),
                int(self.vrstaEdit.text()),
                int(self.idkupcaEdit.text()),
                self.keykatEdit.text(),
                self.categoryEdit.text(),
                self.napomenaEdit.text(),
                self.datumdpdEdit.text(),
                self.jbkjsjnEdit.text(),
                self.bracpuEdit.text(),
                self.ugovorEdit.text()
            )
            self.resetuj_polja()
            self.popuni_neobradjene()
            self.ponisti_izbor()
        except Exception as e:
            print(f"Greška u formiranju fakture: {e}")


################# Pregled faktura, stampa, slanje #################

    def popuni_fakture(self):
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
                SELECT 
                    f.id, f.sifobj, f.brojfakture, f.datumpred, f.idpartneri,
                    f.datumdpd, f.datumvazenja, f.status_salinv, f.invoiceid,
                    f.salesinvoiceid, f.vrsta, p.naziv, f.god
                FROM kasa.fakture f
                LEFT JOIN kasa.partneri p ON f.idpartneri = p.id
                WHERE f.god = %s AND f.sifobj = %s
                ORDER BY f.id DESC
            """, (GODINA, SIFOBJEKTA))
            rezultati = cursor.fetchall()

            self.faktureTable.setRowCount(0)

            for red_idx, red in enumerate(rezultati):
                self.faktureTable.insertRow(red_idx)

                status = red[7] or ""
                boja = None
                if status == "Sent":
                    boja = QColor(70, 130, 180)  # plava
                elif status == "Approved":
                    boja = QColor(85, 170, 0)   # zelena
                elif status == "Rejected":
                    boja = QColor(255, 23, 38)  # crvena

                vrednosti = [
                    red[0], red[1], red[2], red[3], "",  # kolona 4 je dugme
                    red[11] or "",  # naziv partnera
                    red[4] or "",   # id partnera
                    red[5] or "",   # datumdpd
                    red[6] or "",   # datumvazenja
                    status,
                    red[8] or "",   # invoiceid
                    red[9] or "",   # salesinvoiceid
                    red[10] or "",  # vrsta
                    red[12]         # godina
                ]

                for col_idx, vrednost in enumerate(vrednosti):
                    if col_idx == 4:
                        dugme = QPushButton()
                        dugme.setToolTip("Izmeni partnera u fakturi.")
                        dugme.setIcon(QIcon("icons/edit.png"))

                        if boja:
                            dugme.setStyleSheet(f"color: rgb({boja.red()}, {boja.green()}, {boja.blue()});")

                        # Ako faktura ima InvoiceID ili status "Sent"/"Approved"/"Cancelled" — dugme je onemogućeno
                        #if red[8] is not None or status in ("Sent", "Approved", "Cancelled"):
                        if status in ("Sent", "Approved", "Cancelled", "Rejected"):
                            dugme.setEnabled(False)
                            dugme.setToolTip("Faktura je već poslata na SEF i ne može se menjati kupac.")

                        self.faktureTable.setCellWidget(red_idx, col_idx, dugme)
                    else:
                        item = QTableWidgetItem(str(vrednost))
                        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                        if boja:
                            item.setForeground(QBrush(boja))
                        self.faktureTable.setItem(red_idx, col_idx, item)

            cursor.close()
            conn.close()

        except Exception as e:
            print("Greška prilikom popunjavanja tabele faktura:", e)

    def prikazi_stavke_fakture(self, godina, sifobj, brojfakture):
        try:
            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    query = """
                    SELECT
                        ka.sifra,                               -- 0
                        a.naziv,                                -- 1
                        jm.jm,                                  -- 2
                        ka.kolicina,                            -- 3
                        ROUND(
                            (ka.cenanabavna * (1 - ((ka.porezproc * 100)::numeric / (ka.porezproc + 100)::numeric) / 100))::numeric, 
                            2
                        ) AS cena_bez_pdv,                      -- 4
                        ka.rabatproc,                           -- 5
                        ROUND((ka.cena * ka.kolicina)::numeric * (ka.rabatproc::numeric / 100), 2),                       -- 6
                        ROUND(ka.kolicina::numeric * ka.cena::numeric * ROUND(
                            (1 - ((ka.porezproc * 100)::numeric / (ka.porezproc + 100)::numeric) / 100)::numeric, 
                            4
                        ),2) AS iznos_bez_pdv,                     -- 7
                        ka.porezproc,                           -- 8
                        ka.porez,                               -- 9
                        ROUND((ka.cena * ka.kolicina)::numeric, 2),  -- 10
                        ka.tarifa,                              -- 11
                        ka.id                                   -- 12
                    FROM kasa.karticaart ka
                    LEFT JOIN kasa.artikli a ON a.sifra = ka.sifra
                    LEFT JOIN kasa.jedmere jm ON jm.id = a.jedinica_mere_id
                    WHERE ka.god = %s AND ka.sifobj = %s AND ka.brfakt = %s
                    ORDER BY ka.id
                    """
                    cursor.execute(query, (godina, sifobj, brojfakture))
                    stavke = cursor.fetchall()

            self.stavkefaktTable.setRowCount(0)
            for red_index, red in enumerate(stavke):
                self.stavkefaktTable.insertRow(red_index)
                for kol_index, vrednost in enumerate(red):
                    item = QTableWidgetItem(str(vrednost))
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)  # polje nije editabilno
                    self.stavkefaktTable.setItem(red_index, kol_index, item)

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška prilikom učitavanja stavki fakture:\n{e}")

    def oznaci_fakturu(self, red):
        """
        Obeležava izabrani red u faktureTable tako što menja njegov stil.
        """
        # Resetujemo sve redove na podrazumevani stil
        for r in range(self.faktureTable.rowCount()):
            for c in range(self.faktureTable.columnCount()):
                item = self.faktureTable.item(r, c)
                if item:
                    font = item.font()
                    font.setBold(False)
                    font.setPointSize(9)
                    item.setFont(font)

        # Stilizujemo samo izabrani red
        for c in range(self.faktureTable.columnCount()):
            item = self.faktureTable.item(red, c)
            if item:
                font = item.font()
                font.setBold(True)
                font.setPointSize(9)  # Veći font za istaknuti red
                item.setFont(font)

        # ➕ Ovde pozivamo prikaz stavki fakture
        try:
            god = self.faktureTable.item(red, 13).text()         # pretpostavka: GOD u koloni 13
            sifobj = self.faktureTable.item(red, 1).text()        # pretpostavka: SIFOBJEKAT u koloni 1
            brojfakture = self.faktureTable.item(red, 2).text()   # pretpostavka: BROJFAKTURE u koloni 2
            self.prikazi_stavke_fakture(god, sifobj, brojfakture)
        except Exception as e:
            print("Greška pri učitavanju stavki fakture:", e) 

    ################# Pregled faktura, stampa, slanje ################# 
    def broj_u_tekst(self, broj: float) -> str:
        jedinice = ["", "jedan", "dva", "tri", "četiri", "pet", "šest", "sedam", "osam", "devet"]
        desetice = ["", "deset", "dvadeset", "trideset", "četrdeset", "pedeset", "šezdeset", "sedamdeset", "osamdeset", "devedeset"]
        teen = {
            11: "jedanaest", 12: "dvanaest", 13: "trinaest", 14: "četrnaest",
            15: "petnaest", 16: "šesnaest", 17: "sedamnaest", 18: "osamnaest", 19: "devetnaest"
        }
        stotine = ["", "sto", "dvestotine", "tristotine", "četiristotine", "petstotina", "šeststotina", "sedamstotina", "osamstotina", "devetstotina"]
        grupa_jednina = ["", "hiljada", "milion", "milijarda"]
        grupa_mnozina = ["", "hiljade", "milioni", "milijarde"]
        grupa_genitiv = ["", "hiljada", "miliona", "milijardi"]

        def tri_cifre(n):
            s = ""
            n = int(n)
            c = n % 10
            b = (n // 10) % 10
            a = (n // 100) % 10
            if a:
                s += stotine[a]
            if b == 1 and c != 0:
                s += teen[10 + c]
            else:
                if b:
                    s += desetice[b]
                if c:
                    s += jedinice[c]
            return s

        def grupa_ime(n, stepen):
            if stepen == 0:
                return ""
            if n == 1:
                return grupa_jednina[stepen]
            elif 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
                return grupa_mnozina[stepen]
            else:
                return grupa_genitiv[stepen]

        # === Glavni deo
        broj = round(broj, 2)
        ceo = int(broj)
        pare = int(round((broj - ceo) * 100))

        if ceo == 0:
            tekst = "nula"
        else:
            tekst = ""
            grupe = []
            while ceo > 0:
                grupe.append(ceo % 1000)
                ceo //= 1000
            for i in reversed(range(len(grupe))):
                if grupe[i] == 0:
                    continue
                tekst += tri_cifre(grupe[i]) + grupa_ime(grupe[i], i)

        tekst += f"dinara i {pare:02d}/100 para"
        return tekst  
    
    def onStampaBtnClick(self):
            red = self.faktureTable.currentRow()

            if red < 0:
                print("Nijedna faktura nije selektovana.")
                return

            try:
                id_fakture = int(self.faktureTable.item(red, 0).text())
                self.stampa_faktura_pdf(id_fakture)  # poziv vaše funkcije za štampu
            except Exception as e:
                print("Greška pri čitanju ID-a fakture:", e)

    def stampa_faktura_pdf(self, faktura_id):
        # Osnovna putanja (gde se nalazi .py ili .exe fajl)
        if getattr(sys, 'frozen', False):  # ako je aplikacija pretvorena u .exe
            BASE_DIR = os.path.dirname(sys.executable)
        else:  # ako se pokreće kao .py fajl
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))

        # Putanja ka folderu za izveštaje
        folder_izvestaja = os.path.join(BASE_DIR, "izvestaji")
        os.makedirs(folder_izvestaja, exist_ok=True)

        # Putanja ka font fajlu
        font_path = os.path.join(BASE_DIR, "fonts", "EncodeSans-Medium.ttf")
        pdfmetrics.registerFont(TTFont("EncodeSans-Medium", font_path))

        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            cursor.execute("SELECT naziv, adresa, pobro, mesto, pib, banka, primarni_racun, tel, email, matbr, sifdel FROM kasa.fvr LIMIT 1")
            fvr_naziv, fvr_adresa, fvr_pobro, fvr_mesto, fvr_pib, fvr_banka, fvr_primarni_racun, fvr_tel, fvr_email, fvr_matbr, fvr_sifdel = cursor.fetchone()

            if isinstance(fvr_banka, str):
                fvr_banka = json.loads(fvr_banka)
            fvr_banka_naziv = fvr_banka.get("naziv", "")

            cursor.execute("SELECT sifobj, objekat, adresa, mesto, telefon, racunopolagac FROM kasa.objekti WHERE sifobj = %s", (SIFOBJEKTA,))
            sifobj, objekat_naziv, objekat_adresa, objekat_mesto, objekat_tel, racunopolagac = cursor.fetchone()

            cursor.execute("SELECT brojfakture, datumpred, datumdpd, datumvazenja, idpartneri, brracpu FROM kasa.fakture WHERE id = %s", (faktura_id,))
            brojfakture, datumpred, datumdpd, datumvazenja, idpartneri, brracpu = cursor.fetchone()

            cursor.execute("SELECT sifra, naziv, adresa, pobro, mesto, pib, matbr FROM kasa.partneri WHERE id = %s", (idpartneri,))
            p_sifra, p_naziv, p_adresa, p_pobro, p_mesto, p_pib, p_matbr = cursor.fetchone()

            cursor.execute("""
                SELECT
                    k.sifra,
                    a.naziv,
                    j.jm,
                    k.kolicina,
                    k.cenanabavna,
                    k.rabatdinarski
                FROM kasa.karticaart k
                JOIN kasa.artikli a ON a.sifra = k.sifra
                JOIN kasa.jedmere j ON j.id = a.jedinica_mere_id
                WHERE k.brfakt = %s
            """, (brojfakture,))
            stavke = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        naziv_pdf = f"Racun_{brojfakture}.pdf"
        putanja_pdf = os.path.join(folder_izvestaja, naziv_pdf)

        margin_left = 10 * mm
        margin_right = 10 * mm
        margin_top = 10 * mm
        margin_bottom = 8 * mm

        doc = BaseDocTemplate(
            putanja_pdf,
            pagesize=A4,
            leftMargin=margin_left,
            rightMargin=margin_right,
            topMargin=margin_top + 60 * mm,
            bottomMargin=margin_bottom + 30 * mm
        )

        frame = Frame(
            margin_left,
            margin_bottom + 30 * mm,
            A4[0] - margin_left - margin_right,
            A4[1] - margin_top - margin_bottom - 90 * mm,
            id='normal'
        )

        # === Stilovi za Paragraph ===
        style_kupac = ParagraphStyle(name='CustomNormal', fontName='EncodeSans-Medium', fontSize=10, leading=11)
        style_normal = ParagraphStyle(name='CustomNormal', fontName='EncodeSans-Medium', fontSize=8, leading=11)
        style_artikal = ParagraphStyle(name='ArtikalStyle', fontName='EncodeSans-Medium', fontSize=8, leading=9)

        def draw_page_decorator(canvas, doc):
            canvas.setFont("EncodeSans-Medium", 10)

            if doc.page == 1:
                y_top = A4[1] - 20 * mm
                x1 = 10 * mm
                y1 = y_top
                width1 = 90 * mm
                height1 = 35 * mm

                # Naša firma
                canvas.roundRect(x1, y1 - height1, width1, height1, radius=4, stroke=1, fill=0)
                text1 = [
                    fvr_naziv,
                    fvr_adresa,
                    f"{fvr_pobro} {fvr_mesto}",
                    f"PIB: {fvr_pib}",
                    "",
                    f"Prodavnica: {sifobj} {objekat_naziv}",
                    f"{objekat_adresa}, {objekat_mesto}",
                    f"Telefon: {objekat_tel}",
                ]
                t_y1 = y1 - 10
                for linija in text1:
                    canvas.drawString(x1 + 5, t_y1, linija)
                    t_y1 -= 12

                # Kupac (prelom teksta)
                x2 = A4[0] - 10 * mm - 90 * mm
                y2 = y_top
                width2 = 90 * mm
                height2 = 35 * mm
                canvas.roundRect(x2, y2 - height2, width2, height2, radius=4, stroke=1, fill=0)

                kupac_text = f"""
                <b>Kupac: {p_sifra}</b><br/>
                {p_naziv}<br/>
                {p_adresa}<br/>
                {p_pobro} {p_mesto}<br/>
                PIB: {p_pib} &nbsp;&nbsp; Mat. br: {p_matbr}
                """
                p_kupac = Paragraph(kupac_text, style_kupac)
                kupac_frame = Frame(x2 + 5, y2 - height2 + 5, width2 - 10, height2 - 10, showBoundary=0)
                kupac_frame.addFromList([p_kupac], canvas)

                # Naslov fakture
                canvas.setFont("EncodeSans-Medium", 12)
                canvas.drawString(x1, (y1 - height1) - 25, f"Račun br: {brojfakture}")

                canvas.setFont("EncodeSans-Medium", 10)
                dodatni_y = y2 - height2 - 10
                canvas.drawString(x2, dodatni_y, f"Datum računa:  {datumpred.strftime('%d.%m.%Y')}")
                canvas.drawString(x2, dodatni_y - 12, f"Datum prometa:   {datumdpd.strftime('%d.%m.%Y')}")
                canvas.drawString(x2, dodatni_y - 24, f"Valuta plaćanja: {datumvazenja.strftime('%d.%m.%Y')}")
                canvas.drawString(x2, dodatni_y - 36, f"Mesto izdavanja: {objekat_mesto}")

            # Footer
            canvas.setFont("EncodeSans-Medium", 8)
            y = 18 * mm
            center_x = A4[0] / 2
            banka_tekst = f"{fvr_banka_naziv} Tekući račun: {fvr_primarni_racun}"
            canvas.drawCentredString(center_x, y + 6, banka_tekst)
            canvas.line(margin_left, y + 4, A4[0] - margin_right, y + 4)
            kontakt = f"Tel: {fvr_tel}    eMail: {fvr_email}    Matični broj: {fvr_matbr}    Šifra delatnosti: {fvr_sifdel}"
            canvas.drawCentredString(center_x, y - 6, kontakt)
            canvas.drawRightString(A4[0] - 10 * mm, 10 * mm, f"Strana {doc.page}")

        doc.addPageTemplates([PageTemplate(id='Invoice', frames=frame, onPage=draw_page_decorator)])

        # === Tabela artikala ===
        data = [["R.br.", "Šifra", "Naziv artikla", "JM", "Količina", "Cena", "Popust", "Vrednost"]]
        ukupna_vrednost = 0
        ukupni_popust = 0

        for idx, (sifra, naziv, jm, kolicina, cena, rabat) in enumerate(stavke, start=1):
            vrednost = cena * kolicina - rabat
            ukupna_vrednost += cena * kolicina
            ukupni_popust += rabat

            # Naziv artikla kao Paragraph (automatski prelom)
            naziv_para = Paragraph(naziv, style_artikal)

            data.append([
                str(idx),
                sifra,
                naziv_para,  # koristi Paragraph
                jm,
                f"{kolicina:.3f}".replace(".", ","),
                f"{cena:.2f}".replace(".", ","),
                f"{rabat:.2f}".replace(".", ","),
                f"{vrednost:.2f}".replace(".", ",")
            ])

        col_widths = [13*mm, 16*mm, 55*mm, 18*mm, 18*mm, 25*mm, 18*mm, 27*mm]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.25, colors.black),
            ("ALIGN", (4,1), (-1,-1), "RIGHT"),
            ("ALIGN", (0,0), (-1,0), "CENTER"),
            ("FONTNAME", (0,0), (-1,-1), "EncodeSans-Medium"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("VALIGN", (0,0), (-1,-1), "TOP"),  # VAŽNO: da se paragraf drži gore
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ("TOPPADDING", (0,0), (-1,-1), 2),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ]))

        # Sumiranje
        za_uplatu = ukupna_vrednost - ukupni_popust
        iznos_tekst = self.broj_u_tekst(za_uplatu)

        levi_blok = [
            Paragraph(f"Iznos slovima: {iznos_tekst}", style_normal),
            Spacer(1, 2 * mm),
            Paragraph(f"Po fiskalnom računu: {brracpu}", style_normal),
            Spacer(1, 2 * mm),
            Paragraph("Račun je rađen na računaru i punovažan je bez pečata i potpisa", style_normal),
        ]

        sum_table = Table([
            ["Vrednost:", f"{ukupna_vrednost:.2f}".replace('.', ',')],
            ["Popust:", f"{ukupni_popust:.2f}".replace('.', ',')],
            ["Svega za uplatu:", f"{za_uplatu:.2f}".replace('.', ',')],
        ], colWidths=[43*mm, 27*mm])
        sum_table.setStyle(TableStyle([
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
            ("FONTNAME", (0,0), (-1,-1), "EncodeSans-Medium"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("BOTTOMPADDING", (0,0), (-1,-1), 1),
            ("TOPPADDING", (0,0), (-1,-1), 1),
            ("BOX", (0,0), (-1,-1), 0.25, colors.black),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.black),
        ]))

        offset_left = sum(col_widths[:-1]) + 4 * mm
        last_col_width = col_widths[-1]

        sum_and_iznos_row = Table([
            [levi_blok, sum_table]
        ], colWidths=[offset_left, last_col_width])
        sum_and_iznos_row.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("ALIGN", (1,0), (1,0), "RIGHT"),
        ]))

        elements = [table, Spacer(1, 1 * mm), sum_and_iznos_row]
        doc.build(elements)
        webbrowser.open(putanja_pdf)

    def stampa_faktura_prilog(self, faktura_id):
        # Osnovna putanja (gde se nalazi .py ili .exe fajl)
        if getattr(sys, 'frozen', False):  # ako je aplikacija pretvorena u .exe
            BASE_DIR = os.path.dirname(sys.executable)
        else:  # ako se pokreće kao .py fajl
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))

        # Putanja ka folderu za izveštaje
        folder_izvestaja = os.path.join(BASE_DIR, "izvestaji\\efakture")
        os.makedirs(folder_izvestaja, exist_ok=True)

        # Putanja ka font fajlu
        font_path = os.path.join(BASE_DIR, "fonts", "EncodeSans-Medium.ttf")
        pdfmetrics.registerFont(TTFont("EncodeSans-Medium", font_path))
        # ==== Stari deo koda za folder izvestaja i font koji se koristi ===#
        #folder_izvestaja = r"D:\\pos_desktop\\desktop_pos\\izvestaji\\efakture"
        #os.makedirs(folder_izvestaja, exist_ok=True)
        #font_path = r"D:\\pos_desktop\\desktop_pos\\fonts\\EncodeSans-Medium.ttf"
        #pdfmetrics.registerFont(TTFont("EncodeSans-Medium", font_path))
        # ==== Kraj Starog dela koda za folder izvestaja i font koji se koristi ===#
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            cursor.execute("SELECT naziv, adresa, pobro, mesto, pib, banka, primarni_racun, tel, email, matbr, sifdel FROM kasa.fvr LIMIT 1")
            fvr_naziv, fvr_adresa, fvr_pobro, fvr_mesto, fvr_pib, fvr_banka, fvr_primarni_racun, fvr_tel, fvr_email, fvr_matbr, fvr_sifdel = cursor.fetchone()

            # === RAZREŠAVANJE JSON POLJA ZA BANKU ===
            if isinstance(fvr_banka, str):
                fvr_banka = json.loads(fvr_banka)
            fvr_banka_naziv = fvr_banka.get("naziv", "")

            cursor.execute("SELECT sifobj, objekat, adresa, mesto, telefon, racunopolagac FROM kasa.objekti WHERE sifobj = %s", (SIFOBJEKTA,))
            sifobj, objekat_naziv, objekat_adresa, objekat_mesto, objekat_tel, racunopolagac = cursor.fetchone()

            cursor.execute("SELECT brojfakture, datumpred, datumdpd, datumvazenja, idpartneri, brracpu, vrsta FROM kasa.fakture WHERE id = %s", (faktura_id,))
            brojfakture, datumpred, datumdpd, datumvazenja, idpartneri, brracpu, vrsta = cursor.fetchone()

            cursor.execute("SELECT sifra, naziv, adresa, pobro, mesto, pib, matbr FROM kasa.partneri WHERE id = %s", (idpartneri,))
            p_sifra, p_naziv, p_adresa, p_pobro, p_mesto, p_pib, p_matbr = cursor.fetchone()

            query = """
            SELECT
                ka.sifra, a.naziv, jm.jm, ka.kolicina,
                ROUND((ka.cenanabavna * (1 - ((ka.porezproc * 100)::numeric / (ka.porezproc + 100)::numeric) / 100))::numeric, 2) AS cena_bez_pdv,
                ka.rabatproc,
                ROUND(((ka.cenanabavna * (1 - ((ka.porezproc * 100)::numeric / (ka.porezproc + 100)::numeric) / 100)) * ka.kolicina)::numeric * (ka.rabatproc::numeric / 100), 2),
                ROUND(ka.kolicina::numeric * ka.cena::numeric * ROUND((1 - ((ka.porezproc * 100)::numeric / (ka.porezproc + 100)::numeric) / 100)::numeric, 4),2),
                ka.porezproc, ka.porez,
                ROUND((ka.cena * ka.kolicina)::numeric, 2),
                ka.tarifa, ka.id
            FROM kasa.karticaart ka
            LEFT JOIN kasa.artikli a ON a.sifra = ka.sifra
            LEFT JOIN kasa.jedmere jm ON jm.id = a.jedinica_mere_id
            WHERE ka.god = %s AND ka.sifobj = %s AND ka.brfakt = %s
            ORDER BY ka.id
            """
            cursor.execute(query, (GODINA, SIFOBJEKTA, brojfakture))
            stavke = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        naziv_pdf = f"Racun_{brojfakture}.pdf"
        putanja_pdf = os.path.join(folder_izvestaja, naziv_pdf)

        margin_left = 10 * mm
        margin_right = 10 * mm
        margin_top = 15 * mm
        margin_bottom = 15 * mm

        doc = BaseDocTemplate(
            putanja_pdf,
            pagesize=A4,
            leftMargin=margin_left,
            rightMargin=margin_right,
            topMargin=margin_top + 60 * mm,
            bottomMargin=margin_bottom + 30 * mm
        )

        frame = Frame(
            margin_left,
            margin_bottom + 30 * mm,
            A4[0] - margin_left - margin_right,
            A4[1] - margin_top - margin_bottom - 90 * mm,
            id='normal'
        )

        def draw_page_decorator(canvas, doc):
            canvas.setFont("EncodeSans-Medium", 10)

            # === HEADER samo na prvoj stranici ===
            if doc.page == 1:
                y_top = A4[1] - 20 * mm
                x1 = 10 * mm
                y1 = y_top
                width1 = 90 * mm
                height1 = 35 * mm

                # Naša firma
                canvas.roundRect(x1, y1 - height1, width1, height1, radius=4, stroke=1, fill=0)
                text1 = [
                    fvr_naziv,
                    fvr_adresa,
                    f"{fvr_pobro} {fvr_mesto}",
                    f"PIB: {fvr_pib}",
                    "",
                    f"Prodavnica: {sifobj} {objekat_naziv}",
                    f"{objekat_adresa}, {objekat_mesto}",
                    f"Telefon: {objekat_tel}",
                ]
                t_y1 = y1 - 10
                for linija in text1:
                    canvas.drawString(x1 + 5, t_y1, linija)
                    t_y1 -= 12

                # Kupac
                # Kupac
                x2 = A4[0] - 10 * mm - 90 * mm
                y2 = y_top
                canvas.roundRect(x2, y2 - height1, 90 * mm, height1, radius=4, stroke=1, fill=0)

                text2 = [
                    f"Kupac: {p_sifra}",
                    p_naziv,
                    p_adresa,
                    f"{p_pobro} {p_mesto}",
                    f"PIB: {p_pib}  Mat. br: {p_matbr}"
                ]

                t_y2 = y2 - 10
                for linija in text2:
                    # Ako linija može biti preduga (npr. naziv kupca), prelomimo je
                    for podlinija in wrap(linija, 40):  # 40 karaktera = gruba širina
                        canvas.drawString(x2 + 5, t_y2, podlinija)
                        t_y2 -= 12

                if vrsta != 3:
                    canvas.setFont("EncodeSans-Medium", 12)
                    canvas.drawString(x1, (y1 - height1) - 25, f"Račun br: {brojfakture}")
                else:
                    canvas.setFont("EncodeSans-Medium", 12)
                    canvas.drawString(x1, (y1 - height1) - 25, f"Avansni račun br: {brojfakture}")

                canvas.setFont("EncodeSans-Medium", 10)
                dodatni_y = y2 - height1 - 10
                canvas.drawString(x2, dodatni_y, f"Datum računa:  {datumpred.strftime('%d.%m.%Y')}")
                canvas.drawString(x2, dodatni_y - 12, f"Datum prometa:   {datumdpd.strftime('%d.%m.%Y')}")
                canvas.drawString(x2, dodatni_y - 24, f"Valuta plaćanja: {datumvazenja.strftime('%d.%m.%Y')}")
                canvas.drawString(x2, dodatni_y - 36, f"Mesto izdavanja: {objekat_mesto}")

            # === FOOTER na SVAKOJ stranici ===
            canvas.setFont("EncodeSans-Medium", 8)
            y = 18 * mm
            center_x = A4[0] / 2

            banka_tekst = f"{fvr_banka_naziv} Tekući račun: {fvr_primarni_racun}"
            canvas.drawCentredString(center_x, y + 6, banka_tekst)

            canvas.line(margin_left, y + 4, A4[0] - margin_right, y + 4)

            kontakt = f"Tel: {fvr_tel}    eMail: {fvr_email}    Matični broj: {fvr_matbr}    Šifra delatnosti: {fvr_sifdel}"
            canvas.drawCentredString(center_x, y - 6, kontakt)

            canvas.drawRightString(A4[0] - 10 * mm, 10 * mm, f"Strana {doc.page}")

        doc.addPageTemplates([PageTemplate(id='Invoice', frames=frame, onPage=draw_page_decorator)])

        styles = getSampleStyleSheet()
        style_normal = ParagraphStyle(name='CustomNormal', fontName='EncodeSans-Medium', fontSize=9, leading=12)
        style_iznos = ParagraphStyle(name='CustomNormal', fontName='EncodeSans-Medium', fontSize=7, leading=8)

        # === TABELA STAVKI ===
        data = [["R.Br", "Šifra", "Naziv", "JM", "Količina", "Cena\nbez PDV", "Pop.\n%", "Popust", "Osnovica", "Stopa\nPDV", "PDV", "Vrednost"]]
        suma_osnovica = suma_popust = suma_pdv = suma_vrednost = suma_za_uplatu = suma_bez_popusta = 0
        visoka_osn = visoka_pdv = niza_osn = niza_pdv = 0

        style_naziv = ParagraphStyle(
            name='NazivArtikla',
            fontName='EncodeSans-Medium',
            fontSize=6,
            leading=7,
        )

        for idx, stavka in enumerate(stavke, start=1):
            sifra, naziv, jm, kolicina, cena_bez_pdv, rabatproc, popust, osnovica, stopa_pdv, pdv_iznos, ukupno, tarifa, _ = stavka

            kolicina = float(kolicina)
            cena_bez_pdv = float(cena_bez_pdv)
            rabatproc = float(rabatproc)
            popust = float(popust)
            osnovica = float(osnovica)
            stopa_pdv = float(stopa_pdv)
            pdv_iznos = float(pdv_iznos)
            ukupno = float(ukupno)

            suma_bez_popusta += cena_bez_pdv * kolicina
            suma_popust += popust
            suma_osnovica += osnovica
            suma_pdv += pdv_iznos
            suma_za_uplatu += ukupno

            if tarifa == 3:
                visoka_osn += osnovica
                visoka_pdv += pdv_iznos
            elif tarifa == 4:
                niza_osn += osnovica
                niza_pdv += pdv_iznos

            data.append([
                str(idx), sifra, 
                Paragraph(naziv, style_naziv), 
                jm,
                f"{kolicina:.3f}".replace(".", ","),
                f"{cena_bez_pdv:.2f}".replace(".", ","),
                f"{rabatproc:.2f}".replace(".", ","),
                f"{popust:.2f}".replace(".", ","),
                f"{osnovica:.2f}".replace(".", ","),
                f"{stopa_pdv:.2f}".replace(".", ","),
                f"{pdv_iznos:.2f}".replace(".", ","),
                f"{ukupno:.2f}".replace(".", ",")
            ])

        col_widths = [9*mm, 11*mm, 42*mm, 14*mm, 15*mm, 17*mm, 10*mm, 12*mm, 17*mm, 12*mm, 16*mm, 18*mm]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.25, colors.black),
            ("FONTNAME", (0,0), (-1,-1), "EncodeSans-Medium"),
            ("FONTSIZE", (0,0), (-1,-1), 6),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 1),  # Smanjena visina reda
            ("TOPPADDING", (0,0), (-1,-1), 1),     # Smanjena visina reda
            ("ALIGN", (4,1), (-1,-1), "RIGHT"),
            ("ALIGN", (0,0), (-1,0), "CENTER"),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ]))

        
        iznos_tekst = self.broj_u_tekst(suma_za_uplatu)

        # Formatiramo sve vrednosti za prikaz
        v_osn = f"{visoka_osn:.2f}".replace(".", ",")
        v_pdv = f"{visoka_pdv:.2f}".replace(".", ",")
        n_osn = f"{niza_osn:.2f}".replace(".", ",")
        n_pdv = f"{niza_pdv:.2f}".replace(".", ",")

        levi_blok = [
            Paragraph(f"Iznos slovima: {iznos_tekst}", style_iznos),
            Spacer(1, 2 * mm),
            Paragraph(f"Po fiskalnom računu: {brracpu}", style_iznos),
            Spacer(1, 2 * mm),
            Paragraph("Specifikacija poreza:", style_iznos),
            Spacer(1, 2 * mm),
            Paragraph(f"Osnovica po opštoj stopi: {v_osn}, Porez po opštoj stopi: {v_pdv}", style_iznos),
            Spacer(1, 2 * mm),
            Paragraph(f"Osnovica po posebnoj stopi: {n_osn}, Porez po posebnoj stopi: {n_pdv}", style_iznos),
            Spacer(1, 2 * mm),
            Paragraph("Račun je rađen na računaru i punovažan je bez pečata i potpisa", style_iznos),
        ]               

        # === SUMARNI DEO ===
        suma_table = Table([
            ["Cena bez popusta:", f"{suma_bez_popusta:.2f}".replace(".", ",")],
            ["Popust:", f"{suma_popust:.2f}".replace(".", ",")],
            ["Poreska osnovica:", f"{suma_osnovica:.2f}".replace(".", ",")],
            ["Ukupan PDV:", f"{suma_pdv:.2f}".replace(".", ",")],
            ["Svega za uplatu:", f"{suma_za_uplatu:.2f}".replace(".", ",")],
        ], colWidths=[30*mm, 25*mm])
        suma_table.setStyle(TableStyle([
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
            ("FONTNAME", (0,0), (-1,-1), "EncodeSans-Medium"),
            ("FONTSIZE", (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 1),  # Smanjena visina reda
            ("TOPPADDING", (0,0), (-1,-1), 1),     # Smanjena visina reda
            ("BOX", (0,0), (-1,-1), 0.25, colors.black),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.black),
            ("BACKGROUND", (1, -5), (-1, -2), colors.whitesmoke),
            ("BACKGROUND", (1, -4), (-1, -2), colors.whitesmoke),
            ("BACKGROUND", (1, -3), (-1, -2), colors.whitesmoke),
            ("BACKGROUND", (1, -2), (-1, -2), colors.whitesmoke),
            ("BACKGROUND", (1, -1), (-1, -1), colors.whitesmoke),
        ]))

        offset_left = sum(col_widths[:-1]) + 4 * mm
        last_col_width = col_widths[-1]

        sum_and_iznos_row = Table([
            [levi_blok, suma_table]
        ], colWidths=[offset_left, last_col_width])
        sum_and_iznos_row.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("ALIGN", (1,0), (1,0), "RIGHT"),
        ]))

        # === NIZ ELEMENATA ZA PRIKAZ ===
        elements = [
            table,
            Spacer(1, 1 * mm),
            sum_and_iznos_row
        ]

        # === AVANSNI DEO AKO JE VRSTA == 1 ===
        avansni_blok = []
        if vrsta == 1:
            #print("=== AVANSNA FAKTURA ===")
            #print("Brojfakture:", brojfakture)
            #print("Brracpu:", brracpu)
            #print("Vrsta iz baze:", vrsta)
            #print("Faktura je avansna, proveravam prethodne avanse...")

            detaljni_avanse = self.izvuci_detaljne_avanse(brracpu)
            if detaljni_avanse:
                #print("✅ Pronađeni avansi:", detaljni_avanse)

                tabela_avansa_data = [[
                    "Po računu", "Datum računa",
                    "Osnovica posebna", "PDV posebna",
                    "Osnovica opšta", "PDV opšta",
                    "Ukupno"
                ]]

                ukupno_avansi = 0

                for avans in detaljni_avanse:
                    ukupno_red = (
                        avans['osn_posebna'] + avans['pdv_posebna'] +
                        avans['osn_opsta'] + avans['pdv_opsta']
                    )
                    ukupno_avansi += ukupno_red

                    tabela_avansa_data.append([
                        avans["brfakt"],
                        avans["datum"],
                        f"{avans['osn_posebna']:.2f}".replace(".", ","),
                        f"{avans['pdv_posebna']:.2f}".replace(".", ","),
                        f"{avans['osn_opsta']:.2f}".replace(".", ","),
                        f"{avans['pdv_opsta']:.2f}".replace(".", ","),
                        f"{ukupno_red:.2f}".replace(".", ",")
                    ])

                ostatak = suma_za_uplatu - ukupno_avansi

                # Dodajemo red sa ukupnim sumama
                tabela_avansa_data.append([
                    "Ukupno plaćeno avansima", "", "", "", "", "",
                    f"{ukupno_avansi:.2f}".replace(".", ",")
                ])
                tabela_avansa_data.append([
                    "Ostatak za uplatu", "", "", "", "", "",
                    f"{ostatak:.2f}".replace(".", ",")
                ])

                tabela_avansa = Table(
                    tabela_avansa_data,
                    colWidths=[40*mm, 20*mm, 25*mm, 25*mm, 25*mm, 25*mm, 25*mm]
                )
                tabela_avansa.setStyle(TableStyle([
                    ("GRID", (0,0), (-1,-1), 0.25, colors.black),
                    ("FONTNAME", (0,0), (-1,-1), "EncodeSans-Medium"),
                    ("FONTSIZE", (0,0), (-1,-1), 7),
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 1),  # Smanjena visina reda
                    ("TOPPADDING", (0,0), (-1,-1), 1),     # Smanjena visina reda
                    ("ALIGN", (2,1), (-1,-1), "RIGHT"),
                    ("ALIGN", (0,0), (-1,0), "CENTER"),
                    ("SPAN", (0, -2), (-2, -2)),  # Spoji prva 6 polja za red "Ukupno"
                    ("SPAN", (0, -1), (-2, -1)),  # Spoji prva 6 polja za red "Ostatak"
                    ("BACKGROUND", (0, -2), (-1, -2), colors.whitesmoke),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
                ]))

                avansni_blok.extend([
                    Spacer(1, 4 * mm),
                    Paragraph("Avansne uplate:", style_iznos),
                    Spacer(1, 2 * mm),
                    tabela_avansa,
                ])
            else:
                print("❌ Nema prethodnih avansa za prikaz.")
        else:
            print("Faktura nije avansna (vrsta != 3), avansi se ne prikazuju.")

        elements = [
            table,
            Spacer(1, 1 * mm),
            sum_and_iznos_row,
            *avansni_blok
        ]

        doc.build(elements)
        #webbrowser.open(putanja_pdf)    #ukoliko hoćemo da nam prikaže pdf priloga

    def izvuci_detaljne_avanse(self, brracpu_konacnog):
        """
        Rekurzivno izvlači sve prethodne avansne račune povezane sa konačnim računom
        i vraća ih kao listu sa detaljima po stopama poreza i podacima za SEF referenciranje.
        """
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            def nadji_sve_avanse(brracpu):
                """Rekurzivno pronalazi sve prethodne avanse do prvog."""
                avansi = []
                trenutni = brracpu
                while trenutni:
                    cursor.execute("""
                        SELECT refbrracpu, tipracuna, tiptransakcije, datum
                        FROM kasa.kasasum
                        WHERE brracpu = %s
                    """, (trenutni,))
                    rezultat = cursor.fetchone()
                    if not rezultat:
                        break
                    refbrracpu, tipracuna, tiptransakcije, datum = rezultat

                    if tipracuna == '4' and tiptransakcije == '0':
                        avansi.append((trenutni, datum))

                    if not refbrracpu:
                        break
                    trenutni = refbrracpu
                return list(reversed(avansi))

            # Nađi refundaciju
            cursor.execute("""
                SELECT refbrracpu
                FROM kasa.kasasum
                WHERE brracpu = %s
            """, (brracpu_konacnog,))
            red = cursor.fetchone()
            if not red or not red[0]:
                return []

            brracpu_refundacije = red[0]
            avansi = nadji_sve_avanse(brracpu_refundacije)

            detalji = []
            for brracpu_avans, datum in avansi:
                cursor.execute("""
                    SELECT god, sifobj, broj, brfakt, datum
                    FROM kasa.kasasum
                    WHERE brracpu = %s
                """, (brracpu_avans,))
                podaci = cursor.fetchone()
                if not podaci:
                    continue

                god, sifobj, broj, brfakt, datum_izdavanja = podaci
                cursor.execute("""
                    SELECT tarifa,
                        ROUND((kolicina * cena - porez)::numeric, 2) AS osnovica,
                        ROUND(porez::numeric, 2) AS pdv
                    FROM kasa.karticaart
                    WHERE god = %s AND sifobj = %s AND broj = %s AND vrsta = 8
                """, (god, sifobj, broj))

                osn_opsta = pdv_opsta = osn_posebna = pdv_posebna = osn_0 = pdv_0 = 0
                for tarifa, osnovica, pdv in cursor.fetchall():
                    if tarifa == 3:
                        osn_opsta += float(osnovica)
                        pdv_opsta += float(pdv)
                    elif tarifa == 4:
                        osn_posebna += float(osnovica)
                        pdv_posebna += float(pdv)
                    elif tarifa in (0, 1):
                        osn_0 += float(osnovica)
                        pdv_0 += float(pdv)

                detalji.append({
                    "brracpu": brracpu_avans,
                    "brfakt": brfakt,
                    "faktura_broj": brfakt,
                    "datum": datum.strftime("%d.%m.%Y"),
                    "datum_izdavanja": datum_izdavanja.strftime("%Y-%m-%d"),
                    "osn_opsta": osn_opsta,
                    "pdv_opsta": pdv_opsta,
                    "osn_posebna": osn_posebna,
                    "pdv_posebna": pdv_posebna,
                    "osn_0": osn_0,
                    "pdv_0": pdv_0
                })

            return detalji

        except Exception as e:
            print(f"❌ Greška u izvuci_detaljne_avanse: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def sef_izvuci_parametre(self):
        try:
            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT demoef, kljuc_api, kljuc_demo_api FROM kasa.fvr LIMIT 1")
                    fvr_demo, fvr_api, fvr_api_demo = cursor.fetchone()

            if fvr_demo:
                url_base = "https://demoefaktura.mfin.gov.rs/api/publicApi/sales-invoice"
                apikey = fvr_api_demo
            else:
                url_base = "https://efaktura.mfin.gov.rs/api/publicApi/sales-invoice"
                apikey = fvr_api

            return url_base, apikey, fvr_demo

        except Exception as e:
            print("❌ Greška pri čitanju SEF parametara:", e)
            return None, None, None
        
    def osvezi_status_e_faktura(self):
        try:
            url_base, apikey, _ = self.sef_izvuci_parametre()
            if not url_base or not apikey:
                QMessageBox.warning(self, "Greška", "Nisu postavljeni SEF parametri.")
                return

            brojac = 0

            for row in range(self.faktureTable.rowCount()):
                sales_id_item = self.faktureTable.item(row, 11)  # kolona 11 = salesinvoiceid
                if not sales_id_item:
                    continue

                salesinvoiceid = sales_id_item.text().strip()
                if not salesinvoiceid:
                    continue

                sef_url = f"{url_base}?invoiceId={salesinvoiceid}"
                headers = {
                    "Accept": "application/json",
                    "apikey": apikey
                }

                response = requests.get(sef_url, headers=headers)
                if response.status_code != 200:
                    #print(f"❌ Status {response.status_code} za SalesInvoiceId {salesinvoiceid}: {response.text}")
                    continue

                podaci = response.json()
                status = podaci.get("Status", "").strip()
                cir_id = podaci.get("CirInvoiceId", "")
                last_mod = podaci.get("LastModifiedUtc", None)

                if not status:
                    continue

                with psycopg2.connect(
                    dbname=os.getenv("DB_NAME"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT")
                ) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            UPDATE kasa.fakture
                            SET status_salinv = %s,
                                datum_stat_salinv = %s,
                                cirinvoiceid = %s
                            WHERE salesinvoiceid = %s
                        """, (
                            status,
                            last_mod,
                            cir_id,
                            salesinvoiceid
                        ))
                        conn.commit()
                        brojac += 1

            QMessageBox.information(self, "Status ažuriran", f"Ažurirano {brojac} faktura.")
            self.popuni_fakture()

        except Exception as e:
            print("❌ Greška u osvežavanju statusa faktura:", e)
            QMessageBox.critical(self, "Greška", f"Došlo je do greške:\n{e}")


    #====== FUNKCIJE ZA SLANJE eFAKTURA ========#
    def oneFakturaBtnClick(self):
        red = self.faktureTable.currentRow()

        if red < 0:
            print("Nijedna faktura nije selektovana.")
            return

        try:
            invoiceid_item = self.faktureTable.item(red, 10)  # indeks 10 za kolonu invoiceid
            invoiceid_text = invoiceid_item.text().strip() if invoiceid_item else ""

            #print(f"DEBUG: invoiceid_text = '{invoiceid_text}'")

            #if invoiceid_text and invoiceid_text.lower() != "none" and invoiceid_text != "0":
            #    QMessageBox.information(self, "Informacija", "Ova faktura je već poslata na SEF i ne može se ponovo slati.")
            #    return

            id_fakture = int(self.faktureTable.item(red, 0).text())
            self.stampa_faktura_prilog(id_fakture)

            dialog = eFaktureDialog(self, id_fakture)
            dialog.exec()

        except Exception as e:
            print("Greška pri čitanju ID-a fakture:", e)