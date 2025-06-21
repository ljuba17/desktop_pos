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
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics


# Učitavanje konfiguracije iz kasa.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')


class PazarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "pazar.ui")
        uic.loadUi(ui_path, self)
        
        
        self.tablePazar.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  
        self.tablePazar.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)      
        self.tablePazar.horizontalHeader().setStretchLastSection(False)

        # Postavljanje današnjeg datuma
        today = QDate.currentDate()
        self.oddatEdit.setDate(today)
        self.dodatEdit.setDate(today)

        # Povezivanje oddatEdit sa dodatEdit
        self.oddatEdit.dateChanged.connect(self.sync_dates)

        # Povezivanje dugmeta sa funkcijom za učitavanje izveštaja
        self.btnObradi.clicked.connect(self.ucitaj_izvestaj)
        self.btnCancel.clicked.connect(self.reject)
        self.btnStampa.clicked.connect(self.stampaj_izvestaj)

    def sync_dates(self, date):
        """Kada korisnik promeni oddatEdit, ažurira se dodatEdit na istu vrednost."""
        self.dodatEdit.setDate(date)

    def ucitaj_izvestaj(self):
        """Učitava podatke iz baze i prikazuje ih u tabeli."""
        odd_date = self.oddatEdit.date().toString("yyyy-MM-dd")
        dodat_date = self.dodatEdit.date().toString("yyyy-MM-dd")

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

            # SQL upit za zbir po korisnicima
            query = f"""
            SELECT kreirao, 
                SUM(vrgotovina) AS gotovina, 
                SUM(vrkartica) AS kartica, 
                SUM(vrcek) AS cek, 
                SUM(vrfaktura) AS faktura, 
                SUM(vrinstant) AS instant, 
                SUM(vauvcer) AS vaucer
            FROM kasa.kasasum
            WHERE kreirano BETWEEN '{odd_date} 00:00:00' AND '{dodat_date} 23:59:59'
            AND tipracuna IN ('0','4')
            AND tiptransakcije = '0'
            GROUP BY kreirao
            ORDER BY kreirao;
            """
            cur.execute(query)
            rezultati = cur.fetchall()

            # Brisanje starih podataka iz tabele
            self.tablePazar.setRowCount(0)

            ukupno = [0] * 6  # Za zbirne vrednosti

            # Popunjavanje podataka u tabeli po korisnicima
            for row_idx, row in enumerate(rezultati):
                self.tablePazar.insertRow(row_idx)
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Onemogućavanje editovanja
                    self.tablePazar.setItem(row_idx, col_idx, item)
                    if col_idx > 0:  # Preskačemo prvi stupac (kreirao)
                        ukupno[col_idx - 1] += value

            # Dodavanje reda "UKUPNO"
            row_idx = self.tablePazar.rowCount()
            self.tablePazar.insertRow(row_idx)
            self.tablePazar.setItem(row_idx, 0, QTableWidgetItem("UKUPNO"))
            for col_idx, value in enumerate(ukupno, start=1):
                item = QTableWidgetItem(str(value))
                item.setForeground(QBrush(QColor("darkblue")))  # Tamnoplavi font
                item.setBackground(QBrush(QColor("lightyellow")))
                item.setFont(QFont("Arial", weight=QFont.Weight.Bold))  # Bold font
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tablePazar.setItem(row_idx, col_idx, item)

            # SQL upit za refundaciju (samo zbir)
            query_refundacija = f"""
            SELECT 
                -SUM(vrgotovina) AS gotovina, 
                -SUM(vrkartica) AS kartica, 
                -SUM(vrcek) AS cek, 
                -SUM(vrfaktura) AS faktura, 
                -SUM(vrinstant) AS instant, 
                -SUM(vauvcer) AS vaucer
            FROM kasa.kasasum
            WHERE kreirano BETWEEN '{odd_date} 00:00:00' AND '{dodat_date} 23:59:59'
            AND tipracuna IN ('0','4')
            AND tiptransakcije = '1';
            """
            cur.execute(query_refundacija)
            refundacija_rezultat = cur.fetchone()

            if refundacija_rezultat and any(refundacija_rezultat):  # Proveravamo da li ima refundacije
                row_idx = self.tablePazar.rowCount()
                self.tablePazar.insertRow(row_idx)
                self.tablePazar.setItem(row_idx, 0, QTableWidgetItem("REFUNDACIJA"))
                ukupno_refundacija = [0] * 6  # Za refundacije

                for col_idx, value in enumerate(refundacija_rezultat, start=1):
                    item = QTableWidgetItem(str(value))
                    item.setForeground(QBrush(QColor("darkred")))  # Crveni font
                    item.setBackground(QBrush(QColor("lightyellow")))  # Svetlosiva pozadina
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.tablePazar.setItem(row_idx, col_idx, item)
                    ukupno_refundacija[col_idx - 1] = value
                    
                # Ažuriranje ukupnih vrednosti posle refundacije
                row_idx = self.tablePazar.rowCount()
                self.tablePazar.insertRow(row_idx)
                ukupna_posle_refundacije = QTableWidgetItem("UKUPNO POSLE REFUNDACIJE")
                ukupna_posle_refundacije.setForeground(QBrush(QColor("darkgreen")))  # Tamnozeleni font
                ukupna_posle_refundacije.setFont(QFont("Arial", weight=QFont.Weight.Bold))  # Bold font
                ukupna_posle_refundacije.setBackground(QBrush(QColor("lightyellow")))  # Svetlosiva pozadina
                self.tablePazar.setItem(row_idx, 0, ukupna_posle_refundacije)
                
                for col_idx in range(1, 7):
                    ukupna_vrednost = ukupno[col_idx - 1] + ukupno_refundacija[col_idx - 1]
                    item = QTableWidgetItem(str(ukupna_vrednost))
                    item.setForeground(QBrush(QColor("darkgreen")))  # Tamnozeleni font
                    item.setFont(QFont("Arial", weight=QFont.Weight.Bold))  # Bold font
                    item.setBackground(QBrush(QColor("lightyellow")))  # Svetlosiva pozadina
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.tablePazar.setItem(row_idx, col_idx, item)

            cur.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Došlo je do greške prilikom učitavanja podataka: {e}")
            

    # Funkcija za generisanje PDF izveštaja
    def stampaj_izvestaj(self):
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

        # **Putanja do foldera izveštaja**
        #folder_izvestaja = r"D:\pos_desktop\desktop_pos\izvestaji"
        #os.makedirs(folder_izvestaja, exist_ok=True)  # Kreira folder ako ne postoji

        # **Putanja do fonta**
        #font_path = r"D:\pos_desktop\desktop_pos\fonts\DejaVuSans.ttf"
        #pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))

        odd_date = self.oddatEdit.date().toString("dd-MM-yyyy")
        dodat_date = self.dodatEdit.date().toString("dd-MM-yyyy")

        # **Povezivanje sa bazom**
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        cur = conn.cursor()

        # **Podaci o firmi i objektu**
        cur.execute("SELECT naziv, adresa, mesto FROM kasa.fvr LIMIT 1")
        naziv_firme, adresa_firme, mesto_firme = cur.fetchone()

        cur.execute("SELECT objekat, adresa, mesto FROM kasa.objekti WHERE sifobj = %s", (SIFOBJEKTA,))
        objekat, adresa_objekta, mesto_objekta = cur.fetchone()

        # **Podaci o pazaru**
        cur.execute("""
            SELECT kreirao, 
                SUM(vrgotovina), SUM(vrkartica), SUM(vrcek),
                SUM(vrfaktura), SUM(vrinstant), SUM(vauvcer), SUM(vrbezgotovinsko)
            FROM kasa.kasasum
            WHERE kreirano BETWEEN %s AND %s
            AND tipracuna IN ('0','4') 
            AND tiptransakcije = '0'
            GROUP BY kreirao
            ORDER BY kreirao
        """, (f"{odd_date} 00:00:00", f"{dodat_date} 23:59:59"))
        rezultati = cur.fetchall()

        # **Podaci o refundaciji**
        cur.execute("""
            SELECT 
                COALESCE(-SUM(vrgotovina), 0), COALESCE(-SUM(vrkartica), 0), COALESCE(-SUM(vrcek), 0),
                COALESCE(-SUM(vrfaktura), 0), COALESCE(-SUM(vrinstant), 0), COALESCE(-SUM(vauvcer), 0), COALESCE(-SUM(vrbezgotovinsko), 0)
            FROM kasa.kasasum
            WHERE kreirano BETWEEN %s AND %s
            AND tipracuna IN ('0','4') 
            AND tiptransakcije = '1'
        """, (f"{odd_date} 00:00:00", f"{dodat_date} 23:59:59"))
        refundacija = cur.fetchone()

        cur.close()
        conn.close()

        # **Generisanje naziva PDF-a**
        fajl_izvestaja = os.path.join(folder_izvestaja, f"Pregled_pazara_{odd_date}_do_{dodat_date}.pdf")

        # **Kreiranje PDF-a**
        c = canvas.Canvas(fajl_izvestaja, pagesize=landscape(A4))
        c.setFont("EncodeSans-Medium", 8)

        # **Zaglavlje**
        c.drawString(30, 550, naziv_firme)
        c.drawString(30, 535, f"{adresa_firme}, {mesto_firme}")
        c.drawString(30, 520, f"Objekat: {objekat}")
        c.drawString(30, 505, f"{adresa_objekta}, {mesto_objekta}")

        c.setFont("EncodeSans-Medium", 11)
        c.drawCentredString(420, 550, "Pregled pazara")

        c.setFont("EncodeSans-Medium", 8)
        c.drawCentredString(420, 535, f"Za period {odd_date} do {dodat_date}")

        # **Širina kolona (duplirana širina za "Korisnik")**
        sirina_korisnik = 195  # Dupla širina
        sirina_ostale = 85  # Ostale kolone ravnomerno
        col_widths = [sirina_korisnik] + [sirina_ostale] * 6

        # **Tabelarni podaci**
        zaglavlje = ["Korisnik", "Gotovina", "Kartica", "Ček", "Faktura", "Instant", "Vaučer", "Bezgotovinsko"]
        tabela_podaci = [zaglavlje]

        ukupno = [0] * 7  # Inicijalizacija ukupnih vrednosti

        for red in rezultati:
            korisnik = red[0]
            vrednosti = [float(v) if v is not None else 0 for v in red[1:]]
            tabela_podaci.append([korisnik] + vrednosti)

            for i in range(7):
                ukupno[i] += vrednosti[i]

        # **Dodavanje ukupnog reda**
        tabela_podaci.append(["UKUPNO"] + ukupno)

        # **Dodavanje refundacije ako postoji**
        if refundacija and any(refundacija):
            tabela_podaci.append(["REFUNDACIJA"] + list(refundacija))
            ukupno_posle_refundacije = [ukupno[i] + refundacija[i] for i in range(7)]
            tabela_podaci.append(["UKUPNO POSLE REFUNDACIJE"] + ukupno_posle_refundacije)

        # **Kreiranje tabele**
        tabela = Table(tabela_podaci, colWidths=col_widths)

        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), "EncodeSans-Medium"),

            # Poravnanja
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),      # Zaglavlja svih kolona
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),        # Podaci u prvoj koloni
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),      # Podaci u ostalim kolonama

            # Ostalo
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.whitesmoke),
            ('FONTNAME', (0, -1), (-1, -1), "EncodeSans-Medium"),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.darkblue),
        ]))

        # **Pozicija tabele**
        tabela_y = 380  # Probna vrednost, možeš fino podešavati
        tabela.wrapOn(c, 800, tabela_y)
        tabela.drawOn(c, 30, tabela_y)

        # **Zatvaranje PDF-a**
        c.save()

        #print(f"Izveštaj generisan: {fajl_izvestaja}")

        # **Otvaranje PDF-a za pregled**
        webbrowser.open(fajl_izvestaja)
    