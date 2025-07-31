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

class AnalitickaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "analitika.ui")
        uic.loadUi(ui_path, self)
        
        # Postavljanje današnjeg datuma
        today = QDate.currentDate()
        self.datumEdit.setDate(today)

        # Poslednja kolona dokstatus je skrivena
        self.tableStavke.setColumnHidden(10, True)

        # Povezivanje dugmeta sa funkcijom za učitavanje izveštaja
        self.btnObradi.clicked.connect(self.ucitaj_izvestaj)
        self.btnCancel.clicked.connect(self.reject)
        self.btnStampa.clicked.connect(self.stampaj_artikle_prodati)

    def ucitaj_izvestaj(self):
        # Konvertovanje datuma u format YYYY-MM-DD
        datum = self.datumEdit.date().toString("yyyy-MM-dd")

        # Filtriranje tipa artikala
        filter_tip = "1" if not self.checkSvi else "1,2,3"

        # Konekcija sa bazom
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
                        WHEN k.dokstatus IN ('PR', 'AR') THEN -k.kolic  -- Refundacija ima negativnu količinu  WHEN k.dokstatus = 'PR' THEN -k.kolic
                        ELSE k.kolic 
                    END AS kolic,                  
                    k.cena2 AS cena2,              
                    k.popproc1 AS popproc1,        
                    k.popsum AS popsum,            
                    k.cena AS cena,                
                    (CASE 
                        WHEN k.dokstatus IN ('PR', 'AR') THEN -k.kolic * k.cena   --WHEN k.dokstatus = 'PR' THEN -k.kolic * k.cena
                        ELSE k.kolic * k.cena 
                    END) AS vrednost,  -- Vrednost takođe negativna za refundaciju
                    ks.brracpu AS pfr_broj,        
                    k.dokstatus AS dokstatus       -- Dodato da aplikacija zna koji je status
                FROM 
                    "kasa"."kasa" k
                JOIN "kasa"."artikli" a ON a.sifra = k.sifra
                JOIN "kasa"."jedmere" j ON j.id = a.jedinica_mere_id
                JOIN "kasa"."kasasum" ks 
                    ON ks.god = k.god 
                AND ks.sifobj = k.sifobj 
                AND ks.broj = k.broj
                WHERE 
                    k.god = '{GODINA}'
                    AND k.sifobj = '{SIFOBJEKTA}'
                    AND k.datum = '{datum}'
                    AND a.tip IN ({filter_tip})
                    AND k.dokstatus NOT IN ('RP', 'RR', 'OP', 'OR')
            """
            cur.execute(query)
            rezultati = cur.fetchall()

            # Brisanje starih podataka iz tabele
            self.tableStavke.setRowCount(0)


            # Popunjavanje podataka u tabeli po korisnicima
            for row_idx, row in enumerate(rezultati):
                self.tableStavke.insertRow(row_idx)
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Onemogućavanje editovanja
                    self.tableStavke.setItem(row_idx, col_idx, item)
                    

            cur.close()
            conn.close()

            # Primena stilizacije za refundirane stavke (dokstatus == 'PR')
            for row in range(self.tableStavke.rowCount()):
                dokstatus_item = self.tableStavke.item(row, 10)  # Kolona 9 je 'dokstatus'
                if dokstatus_item and dokstatus_item.text() == 'PR' or dokstatus_item.text() == 'AR':
                    # Postavi količinu na negativnu vrednost
                    kolicina_item = self.tableStavke.item(row, 3)  # Kolona 3 je 'kolic'
                    if kolicina_item:
                        kolicina_item.setText(f"{kolicina_item.text()}")

                    # Postavi stilizaciju (svetlo siva pozadina i crveni tekst)
                    for col in range(self.tableStavke.columnCount()):
                        item = self.tableStavke.item(row, col)
                        if item:
                            item.setBackground(QBrush(QColor(211, 211, 211)))  # Svetlo siva pozadina
                            item.setForeground(QBrush(QColor(255, 0, 0)))  # Crveni font

            # Podesi širinu kolona
            self.tableStavke.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

            # Fiksne širine za ostale kolone
            for col in range(self.tableStavke.columnCount()):
                if col not in (1, 9):  # Sve osim 'Naziv' (1) i 'PFR broj' (9)
                    self.tableStavke.setColumnWidth(col, 80)

            # 'Naziv' i 'PFR broj' zauzimaju sav prostor
            self.tableStavke.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self.tableStavke.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)

            # Isključujemo automatsko širenje poslednje kolone (da ne bi narušilo izgled)
            self.tableStavke.horizontalHeader().setStretchLastSection(False)

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Došlo je do greške prilikom učitavanja podataka: {e}")


    def stampaj_artikle_prodati(self):
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

        izabrani_datum = self.datumEdit.date().toString("dd-MM-yyyy")
        filter_tip = "1,2,3" if self.checkSvi.isChecked() else "1"

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

        cur.execute(f"""
            SELECT 
                k.sifra, a.naziv, j.jm,
                CASE WHEN k.dokstatus IN ('PR', 'AR') THEN -k.kolic ELSE k.kolic END,
                k.cena2, k.popproc1, k.popsum, k.cena,
                CASE WHEN k.dokstatus IN ('PR', 'AR') THEN -k.kolic * k.cena ELSE k.kolic * k.cena END,
                ks.brracpu
            FROM kasa.kasa k
            JOIN kasa.artikli a ON a.sifra = k.sifra
            JOIN kasa.jedmere j ON j.id = a.jedinica_mere_id
            JOIN kasa.kasasum ks ON ks.god = k.god AND ks.sifobj = k.sifobj AND ks.broj = k.broj
            WHERE 
                k.god = '{GODINA}'
                AND k.sifobj = '{SIFOBJEKTA}'
                AND k.datum = '{izabrani_datum}'
                AND a.tip IN ({filter_tip})
                AND k.dokstatus NOT IN ('RP', 'RR', 'OP', 'OR')
        """)
        podaci = cur.fetchall()

        cur.close()
        conn.close()

        # Saberi ukupnu vrednost
        ukupna_vrednost = sum(red[8] for red in podaci)
        red_ukupno = ["", "UKUPNO ZA DAN"] + [""] * 6 + [f"{ukupna_vrednost:.2f}", ""]

        zaglavlje = ["Šifra", "Naziv", "Jed. mere", "Količina", "MP cena", "Popust %", "Popust", "Prod. cena", "Vrednost", "PFR broj"]
        tabela_podaci = [zaglavlje] + podaci + [red_ukupno]

        sirina_kolona = [15 * mm, 65 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm, 25 * mm, 25 * mm, 45 * mm]

        # Kreiranje PDF-a
        fajl_izvestaja = os.path.join(folder_izvestaja, f"Artikli_prodati{izabrani_datum}.pdf")

        elementi = []

        def header_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont("EncodeSans-Medium", 10)
            canvas.drawString(10 * mm, 200 * mm, naziv_firme)
            canvas.drawString(10 * mm, 195 * mm, f"{adresa_firme}, {mesto_firme}")
            canvas.drawString(10 * mm, 185 * mm, f"Objekat: {objekat}")
            canvas.drawString(10 * mm, 180 * mm, adresa_objekta)

            canvas.setFont("EncodeSans-Medium", 14)
            canvas.drawCentredString(148 * mm, 200 * mm, f"Artikli prodati dana {izabrani_datum}")

            # Broj strane
            broj_strane = f"Strana {canvas.getPageNumber()}"
            canvas.setFont("EncodeSans-Medium", 8)
            canvas.drawRightString(285 * mm, 10 * mm, broj_strane)
            canvas.restoreState()

        # Napravi tabelu
        tabela = Table(tabela_podaci, colWidths=sirina_kolona, repeatRows=1)
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-2, -2), 'CENTER'),
            ('ALIGN', (-2, 1), (-2, -2), 'RIGHT'),  # Vrednost desno poravnanje
            ('FONTNAME', (0, 0), (-1, -2), "EncodeSans-Medium"),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.black),

            # Stil za poslednji red ("UKUPNO ZA DAN")
            ('BACKGROUND', (0, -1), (-1, -1), colors.whitesmoke),
            ('FONTNAME', (0, -1), (-1, -1), "EncodeSans-Medium"),
            ('ALIGN', (1, -1), (1, -1), 'LEFT'),
            ('ALIGN', (-2, -1), (-2, -1), 'RIGHT'),
            ("BOX", (0,0), (-1,-1), 0.25, colors.black),
        ]))

        elementi.append(tabela)

        from reportlab.platypus import PageTemplate, BaseDocTemplate, Frame

        class BrojanjeStranaDoc(BaseDocTemplate):
            def __init__(self, filename, **kw):
                BaseDocTemplate.__init__(self, filename, **kw)
                frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='normal')
                self.addPageTemplates([PageTemplate(id='All', frames=frame, onPage=header_footer)])

        doc = BrojanjeStranaDoc(fajl_izvestaja, pagesize=landscape(A4),
                                leftMargin=10 * mm, rightMargin=10 * mm,
                                topMargin=40 * mm, bottomMargin=20 * mm)
        doc.build(elementi)

        # Otvori PDF
        webbrowser.open(fajl_izvestaja)
