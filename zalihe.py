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
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime


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
        self.traziEdit.textChanged.connect(self.filtriraj_zalihe)
        self.btnCancel.clicked.connect(self.reject)
        self.btnStampa.clicked.connect(self.stampaj_zalihe)


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

            cursor.execute("""
                SELECT * FROM kasa.obradi(%s, %s, %s, CURRENT_DATE)
            """, [GODINA, 1, SIFOBJEKTA])

            rezultati = cursor.fetchall()
            kolone = [desc[0] for desc in cursor.description]

            # Sačuvamo podatke i indekse kolona
            self.svi_podaci = rezultati
            self.kolone = {
                "sifra": kolone.index("sifra"),
                "naziv": kolone.index("naziv"),
                "jm": kolone.index("jedinica_mere"),
                "pdv": kolone.index("pdv_stopa"),
                "kol": kolone.index("kolicina"),
                "cena": kolone.index("maloprodajna_cena"),
                "vred": kolone.index("vrednost"),
            }

            # Popuni tabelu svim podacima
            self.popuni_tabelu(rezultati)

            # 🔄 Ažuriranje zaliheart
            for red in rezultati:
                sifra = red[self.kolone["sifra"]]
                zaliha = red[self.kolone["kol"]]

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

    
    def popuni_tabelu(self, podaci):
        self.tableZalihe.setRowCount(len(podaci))
        self.tableZalihe.setColumnCount(7)
        self.tableZalihe.setHorizontalHeaderLabels([
            "Šifra", "Naziv", "JM", "PDV %", "Količina", "Cena", "Vrednost"
        ])

        for i, red in enumerate(podaci):
            # Šifra
            self.tableZalihe.setItem(i, 0, QTableWidgetItem(str(red[self.kolone["sifra"]])))

            # Naziv
            self.tableZalihe.setItem(i, 1, QTableWidgetItem(str(red[self.kolone["naziv"]])))

            # JM
            self.tableZalihe.setItem(i, 2, QTableWidgetItem(str(red[self.kolone["jm"]])))

            # PDV %
            item = QTableWidgetItem(f"{red[self.kolone['pdv']]:.0f}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tableZalihe.setItem(i, 3, item)

            # Količina
            item = QTableWidgetItem(f"{red[self.kolone['kol']]:,.2f}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tableZalihe.setItem(i, 4, item)

            # Cena
            item = QTableWidgetItem(f"{red[self.kolone['cena']]:,.2f}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tableZalihe.setItem(i, 5, item)

            # Vrednost
            item = QTableWidgetItem(f"{red[self.kolone['vred']]:,.2f}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tableZalihe.setItem(i, 6, item)

    def filtriraj_zalihe(self):
        tekst = self.traziEdit.text().lower()
        if not tekst:  # Ako je polje prazno → svi podaci
            self.popuni_tabelu(self.svi_podaci)
            return

        filtrirani = []
        for red in self.svi_podaci:
            sifra = str(red[self.kolone["sifra"]]).lower()
            naziv = str(red[self.kolone["naziv"]]).lower()
            if tekst in sifra or tekst in naziv:
                filtrirani.append(red)

        self.popuni_tabelu(filtrirani)

    # Stampa zaliha
    def stampaj_zalihe(self):
        """
        Generiše PDF izveštaj o zalihama (osnovni, A4 portret).
        Datum je uvek današnji, poslovna godina i sifobj iz kasa.ini.
        PDF se automatski otvara nakon generisanja.
        """
        # Putanja ka folderu za izveštaje
        folder_izvestaja = os.path.join(BASE_DIR, "izvestaji")
        os.makedirs(folder_izvestaja, exist_ok=True)

        datum = datetime.today().strftime("%Y-%m-%d")
        datum_fmt = datetime.today().strftime("%d.%m.%Y")
        datum_file = datetime.today().strftime("%d%m%Y")
        output_file = os.path.join(folder_izvestaja, f"zalihe_{datum_file}.pdf")

        # Konekcija na bazu
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )

        # Registracija fonta
        font_path = os.path.join("fonts", "EncodeSans-Medium.ttf")
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont("EncodeSans-Medium", font_path))
            font_name = "EncodeSans-Medium"
        else:
            font_name = "Helvetica"

        doc = SimpleDocTemplate(
            output_file,
            pagesize=A4,
            topMargin=15, bottomMargin=15, leftMargin=10, rightMargin=10
        )
        story = []

        # --- Heder ---
        cur = conn.cursor()
        cur.execute("SELECT sifobj, objekat, adresa, mesto FROM kasa.objekti WHERE sifobj=%s", [SIFOBJEKTA])
        objekat = cur.fetchone()
        cur.close()

        if objekat:
            objekat_podaci = f"{objekat[0]} {objekat[1]}"
            adresa = objekat[2] or "Nepoznata adresa"
            mesto = objekat[3] or "Nepoznato mesto"
        else:
            objekat_podaci = "Nepoznat objekat"
            adresa = "Nepoznata adresa"
            mesto = "Nepoznato mesto"

        story.extend([
            Paragraph(f"<b>{objekat_podaci}</b>", ParagraphStyle("Objekat", fontName=font_name, fontSize=10)),
            Paragraph(f"{adresa}", ParagraphStyle("Adresa", fontName=font_name, fontSize=10)),
            Paragraph(f"{mesto}", ParagraphStyle("Mesto", fontName=font_name, fontSize=10)),
            Paragraph("Stanje artikala - skraćeni izveštaj", ParagraphStyle("Naslov", fontName=font_name, fontSize=14, alignment=1)),
            Spacer(1, 14),
            Paragraph(f"Na dan: {datum_fmt}", ParagraphStyle("Datum", fontName=font_name, fontSize=10, alignment=1)),
            Spacer(1, 12),
        ])

        # --- Podaci ---
        cur = conn.cursor()
        cur.execute("""SELECT * FROM kasa.obradi(%s, %s, %s, %s)""", [GODINA, 1, SIFOBJEKTA, datum])
        rezultati = cur.fetchall()
        cur.close()

        tabela_podaci = []
        ukupna_vrednost = 0

        kolone = [
            "R. b.", "Šifra", "Naziv", "Jedinica mere", "PDV",
            "Zaliha", "Maloprod. cena", "Vrednost"
        ]

        for idx, red in enumerate(rezultati, start=1):
            vrednost = float(red[12])
            ukupna_vrednost += vrednost
            tabela_podaci.append([
                idx,
                red[0],
                red[1],
                red[2],
                f"{red[3]:.0f}%",
                f"{red[9]:.3f}",
                f"{red[5]:.2f}",
                f"{vrednost:.2f}",
            ])

        if tabela_podaci:
            tabela_podaci.append([""]*5 + ["Ukupna vrednost zaliha", "", f"{ukupna_vrednost:,.2f}"])
            col_widths = [25, 45, 150, 60, 50, 60, 70, 80]

            tabela = Table([kolone] + tabela_podaci, colWidths=col_widths, repeatRows=1)
            tabela.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONT", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "LEFT"),
                ("SPAN", (0, -1), (-2, -1)),
                ("ALIGN", (-1, -1), (-1, -1), "RIGHT"),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.darkblue),
                ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
            ]))
            story.append(tabela)
        else:
            story.append(Paragraph("Nema podataka za prikaz.", ParagraphStyle("Warning", fontName=font_name, fontSize=10, textColor=colors.red)))

        # --- Generisanje PDF-a ---
        doc.build(story)
        conn.close()

        # --- Otvori PDF automatski ---
        if platform.system() == "Windows":
            os.startfile(output_file)
        elif platform.system() == "Darwin":
            subprocess.run(["open", output_file])
        else:
            subprocess.run(["xdg-open", output_file])

        print(f"Izveštaj generisan: {output_file}")

