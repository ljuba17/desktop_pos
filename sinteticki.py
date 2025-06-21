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
from datetime import datetime
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame

# Učitavanje konfiguracije iz kasa.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)
GODINA = config.get('POS_Settings', 'god')
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')

class SintetickiDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "sintetika.ui")
        uic.loadUi(ui_path, self)
        
        # Postavljanje današnjeg datuma
        today = QDate.currentDate()
        self.oddatEdit.setDate(today)
        self.dodatEdit.setDate(today)

        # Povezivanje oddatEdit sa dodatEdit
        self.oddatEdit.dateChanged.connect(self.sync_dates)

        # Poslednja kolona dokstatus je skrivena
        self.tableStavke.setColumnHidden(10, True)

        # Povezivanje dugmeta sa funkcijom za učitavanje izveštaja
        self.btnObradi.clicked.connect(self.ucitaj_izvestaj)
        self.btnCancel.clicked.connect(self.reject)
        self.btnStampa.clicked.connect(self.stampa_izvestaja)

    def sync_dates(self, date):
        """Kada korisnik promeni oddatEdit, ažurira se dodatEdit na istu vrednost."""
        self.dodatEdit.setDate(date)

    def ucitaj_izvestaj(self):
        # Konvertovanje datuma u format YYYY-MM-DD
        oddat = self.oddatEdit.date().toString("yyyy-MM-dd")
        dodat = self.dodatEdit.date().toString("yyyy-MM-dd")

        # Filtriranje tipa artikala
        filter_tip = "1" if not self.checkSvi else "1,2,3"
        
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cur = conn.cursor()

            query = f"""
                SELECT 
                    k.sifra AS sifra,               
                    a.naziv AS naziv,              
                    j.jm AS jm,
                    CASE 
                        WHEN k.dokstatus IN ('PR', 'AR') THEN SUM(-k.kolic)  -- Refundacija ima negativnu količinu  WHEN k.dokstatus = 'PR' THEN -k.kolic
                        ELSE SUM(k.kolic)
                    END AS kolic,                           
                    k.cena2 AS cena,                
                    k.popproc1 AS popproc1,        
                    SUM(k.popsum) AS popsum,       
                    k.cena AS cena_sa_popustom,
                    (CASE 
                        WHEN k.dokstatus IN ('PR', 'AR') THEN SUM(-k.kolic * k.cena)   --WHEN k.dokstatus = 'PR' THEN -k.kolic * k.cena
                        ELSE SUM(k.kolic * k.cena)
                    END) AS vrednost,  -- Vrednost takođe negativna za refundaciju
                    k.dokstatus AS dokstatus       
                FROM 
                    "kasa"."kasa" k
                JOIN "kasa"."artikli" a ON a.sifra = k.sifra
                JOIN "kasa"."jedmere" j ON j.id = a.jedinica_mere_id
                WHERE 
                    k.god = '{GODINA}'
                    AND k.sifobj = '{SIFOBJEKTA}'
                    AND k.datum BETWEEN '{oddat}' AND '{dodat}'
                    AND a.tip IN ({filter_tip})
                    AND k.dokstatus IN ('PP', 'PR', 'AP', 'AR')
                GROUP BY k.sifra, a.naziv, j.jm, k.cena, k.popproc1, k.cena2, k.dokstatus
                ORDER BY k.sifra, k.cena;
            """
            cur.execute(query)
            rezultati = cur.fetchall()

            # Brisanje starih podataka iz tabele
            self.tableStavke.setRowCount(0)

            ukupna_vrednost = 0  # Inicijalizacija sume

            # Popunjavanje podataka u tabeli
            for row_idx, row in enumerate(rezultati):
                self.tableStavke.insertRow(row_idx)
                vrednost = row[8]  # Kolona 8 je 'vrednost'

                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.tableStavke.setItem(row_idx, col_idx, item)
                
                # Stilizacija refundiranih stavki
                dokstatus_item = self.tableStavke.item(row_idx, 9)  # Kolona 9 je 'dokstatus'
                if dokstatus_item and dokstatus_item.text() == 'PR' or dokstatus_item.text() == 'AR':
                    for col in range(self.tableStavke.columnCount()):
                        item = self.tableStavke.item(row_idx, col)
                        if item:
                            item.setBackground(QBrush(QColor(211, 211, 211)))  # Svetlo siva pozadina
                            item.setForeground(QBrush(QColor(255, 0, 0)))  # Crveni font
                    # Postavi količinu na negativnu vrednost
                    kolicina_item = self.tableStavke.item(row_idx, 3)  # Kolona 3 je 'kolic'
                    if kolicina_item:
                        kolicina_item.setText(f"-{abs(float(kolicina_item.text()))}")
                    # Postavi vrednost na negativnu vrednost
                    vrednost = -abs(vrednost)
                    self.tableStavke.setItem(row_idx, 8, QTableWidgetItem(str(vrednost)))
                
                ukupna_vrednost += vrednost

            cur.close()
            conn.close()

            # Dodavanje reda sa ukupnom vrednošću
            total_row = self.tableStavke.rowCount()
            self.tableStavke.insertRow(total_row)
            total_item = QTableWidgetItem("UKUPNO")
            total_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.tableStavke.setItem(total_row, 7, total_item)  # Postavljamo "UKUPNO" u pretposlednju kolonu
            total_value_item = QTableWidgetItem(str(round(ukupna_vrednost, 2)))
            total_value_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.tableStavke.setItem(total_row, 8, total_value_item)  # Postavljamo zbir u poslednju kolonu

            # Podesi širinu kolona
            self.tableStavke.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            
            # Sakrivanje kolone 'dokstatus'
            self.tableStavke.setColumnHidden(9, True)
            
            # Proširivanje kolone 'naziv'
            self.tableStavke.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

            # Isključujemo automatsko širenje poslednje kolone
            self.tableStavke.horizontalHeader().setStretchLastSection(False)

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Došlo je do greške prilikom učitavanja podataka: {e}")

    
    def stampa_izvestaja(self):
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

        odd_date = self.oddatEdit.date().toString("dd-MM-yyyy")
        dodat_date = self.dodatEdit.date().toString("dd-MM-yyyy")

        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        cur = conn.cursor()

        cur.execute("SELECT naziv, adresa, mesto FROM kasa.fvr LIMIT 1")
        naziv_firme, adresa_firme, mesto_firme = cur.fetchone()

        cur.execute("SELECT objekat, adresa FROM kasa.objekti WHERE sifobj = %s", (SIFOBJEKTA,))
        objekat, adresa_objekta = cur.fetchone()

        filter_tip = "1" if not self.checkSvi else "1,2,3"

        query = f"""
            SELECT 
                k.sifra AS sifra,               
                a.naziv AS naziv,              
                j.jm AS jm,                    
                SUM(CASE WHEN k.dokstatus IN ('PR', 'AR') THEN -k.kolic ELSE k.kolic END) AS kolic,         
                k.cena2 AS cena,                
                k.popproc1 AS popproc1,        
                SUM(k.popsum) AS popsum,       
                k.cena AS cena_sa_popustom,
                SUM(CASE WHEN k.dokstatus IN ('PR', 'AR') THEN -k.kolic * k.cena ELSE k.kolic * k.cena END) AS vrednost,
                k.dokstatus AS hidden
            FROM 
                kasa.kasa k
            JOIN kasa.artikli a ON a.sifra = k.sifra
            JOIN kasa.jedmere j ON j.id = a.jedinica_mere_id
            WHERE 
                k.god = '{GODINA}'
                AND k.sifobj = '{SIFOBJEKTA}'
                AND k.datum BETWEEN '{odd_date}' AND '{dodat_date}'
                AND a.tip IN ({filter_tip})
                AND k.dokstatus IN ('PP', 'PR', 'AP', 'AR')
            GROUP BY k.sifra, a.naziv, j.jm, k.cena, k.popproc1, k.cena2, k.dokstatus
            ORDER BY k.sifra, k.cena;
        """
        cur.execute(query)
        podaci = cur.fetchall()
        cur.close()
        conn.close()

        prikaz_podataka = [row[:-1] for row in podaci]  # bez hidden kolone

        ukupna_vrednost = sum(row[8] for row in prikaz_podataka)
        red_ukupno = ["", "UKUPNO ZA PERIOD", "", "", "", "", "", "", f"{ukupna_vrednost:.2f}"]

        zaglavlje = ["Šifra", "Naziv", "Jed. mere", "Količina", "MP cena", "Popust %", "Popust", "Prod. cena", "Vrednost"]
        tabela_podaci = [zaglavlje] + prikaz_podataka + [red_ukupno]
        sirina_kolona = [20 * mm, 90 * mm, 20 * mm, 25 * mm, 20 * mm, 20 * mm, 25 * mm, 25 * mm, 25 * mm]

        fajl_izvestaja = os.path.join(folder_izvestaja, f"Izvestaj_prodaje_{odd_date}_do_{dodat_date}.pdf")

        class BrojanjeStranaDoc(BaseDocTemplate):
            def __init__(self, filename, **kw):
                super().__init__(filename, **kw)
                frame = Frame(
                    10 * mm,        # leftMargin
                    20 * mm,        # bottomMargin
                    self.width,     # full width
                    150 * mm,       # height of printable area (210mm - 170mm)
                    id='normal'
                )
                self.addPageTemplates([PageTemplate(id='All', frames=frame, onPage=self.header_footer)])

            def header_footer(self, canvas, doc):
                canvas.saveState()
                canvas.setFont("EncodeSans-Medium", 10)
                canvas.drawString(10 * mm, 200 * mm, naziv_firme)
                canvas.drawString(10 * mm, 195 * mm, f"{adresa_firme}, {mesto_firme}")
                canvas.drawString(10 * mm, 185 * mm, f"Objekat: {objekat}")
                canvas.drawString(10 * mm, 180 * mm, adresa_objekta)

                canvas.setFont("EncodeSans-Medium", 14)
                canvas.drawCentredString(148 * mm, 200 * mm, f"Pregled prodaje")
                canvas.setFont("EncodeSans-Medium", 12)
                canvas.drawCentredString(148 * mm, 190 * mm, f"od {odd_date} do {dodat_date}")

                canvas.setFont("EncodeSans-Medium", 8)
                canvas.drawRightString(285 * mm, 10 * mm, f"Strana {doc.page}")
                canvas.restoreState()

        tabela = Table(tabela_podaci, colWidths=sirina_kolona, repeatRows=1)
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 1), (-1, -2), 'CENTER'),
            ('ALIGN', (1, 1), (1, -2), 'LEFT'),     # Naziv artikla
            ('ALIGN', (1, -1), (1, -1), 'LEFT'),    # UKUPNO ZA PERIOD tekst
            ('ALIGN', (8, -1), (8, -1), 'RIGHT'),   # ukupna vrednost
            ('FONTNAME', (0, 0), (-1, -1), "EncodeSans-Medium"),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
            ('BOX', (0, -1), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.whitesmoke),
        ]))

        doc = BrojanjeStranaDoc(fajl_izvestaja, pagesize=landscape(A4),
                                leftMargin=10 * mm, rightMargin=10 * mm,
                                topMargin=40 * mm, bottomMargin=20 * mm)

        doc.build([tabela])
        webbrowser.open(fajl_izvestaja)

        