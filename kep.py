import os
import sys
import psycopg2
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import QDialog, QTableWidgetItem, QPushButton, QMessageBox, QVBoxLayout
from trazi_avans import TraziAvansDialog
from PyQt6.QtGui import QFont, QColor, QBrush, QIcon
from PyQt6 import uic
from PyQt6.QtWidgets import QTreeWidgetItem
import configparser
import random
from functools import partial
import json
import math
from datetime import datetime,date
from collections import defaultdict
from kep_stampa_dijalog import KepStampaDijalog
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.platypus.flowables import PageBreak
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import webbrowser


# Učitavanje konfiguracije iz kasa.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)
GODINA = config.get('POS_Settings', 'god')
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')
KASA = config.get('POS_Settings', 'kasa')

class KepDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "kep.ui")
        uic.loadUi(ui_path, self)

        self.GODINA = GODINA
        self.SIFOBJEKTA = SIFOBJEKTA
        self.KASA = KASA

        self.btnStampa.clicked.connect(self.otvori_dijalog_za_stampu)
        self.btnObrisi.clicked.connect(self.obrisi_stavke_za_datum)

        self.kepTable.setColumnWidth(0, 70)  # Prva kolona širine 70 -id
        self.kepTable.setColumnWidth(1, 90)  # kolona širine 90 - datum
        self.kepTable.setColumnWidth(2, 100)  # kolona širine 180 - zaduzenje
        self.kepTable.setColumnWidth(3, 100)  # kolona širine 100 - razduzenje
        self.kepTable.setColumnWidth(4, 225)  # kolona širine 220 - opis
        self.kepTable.setColumnHidden(0, True)  # sakrivam kolonu u kojoj je id tk tabele u bazi

        today = QDate.currentDate()
        self.datumEdit.setDate(today)
        self.osvezi_tabelu()
        self.datumEdit.dateChanged.connect(self.datumEdit_changed)
        self.autoCheck.stateChanged.connect(self.autoCheck_changed)

    def datumEdit_changed(self):
        self.osvezi_tabelu()

    def osvezi_tabelu(self):
        try:
            datum = self.datumEdit.date().toString("yyyy-MM-dd")

            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    query = """
                        SELECT id, datum, zaduzenje, razduzenje, opis
                        FROM kasa.tk
                        WHERE datum = %s AND god = %s AND sifobj = %s
                        ORDER BY id
                    """
                    cursor.execute(query, (datum, self.GODINA, self.SIFOBJEKTA))
                    rezultati = cursor.fetchall()

                    self.kepTable.setRowCount(0)  # Čistimo tabelu pre punjenja

                    for row in rezultati:
                        row_position = self.kepTable.rowCount()
                        self.kepTable.insertRow(row_position)

                        # ID (skriven)
                        self.kepTable.setItem(row_position, 0, QTableWidgetItem(str(row[0])))

                        # Datum u formatu dd-mm-yyyy
                        if isinstance(row[1], (datetime, date)):
                            formatted_date = row[1].strftime('%d-%m-%Y')
                        else:
                            formatted_date = str(row[1])
                        self.kepTable.setItem(row_position, 1, QTableWidgetItem(formatted_date))

                        # Zaduženje, Razduženje, Opis
                        self.kepTable.setItem(row_position, 2, QTableWidgetItem(str(row[2])))
                        self.kepTable.setItem(row_position, 3, QTableWidgetItem(str(row[3])))
                        self.kepTable.setItem(row_position, 4, QTableWidgetItem(str(row[4])))

            # Postavljanje autoCheck dugmeta
            if self.kepTable.rowCount() > 0:
                self.autoCheck.setEnabled(False)
                self.autoCheck.setChecked(True)
            else:
                self.autoCheck.setEnabled(True)
                self.autoCheck.setChecked(False)

            # Omogućava prelamanje linija u tekstu u ćelijama
            self.kepTable.setWordWrap(True)

            # Automatski prilagođava visinu redova tako da se sadržaj prikazuje
            self.kepTable.resizeRowsToContents()

            # Ako želiš da širina kolone bude automatski prilagođena sadržaju
            #self.kepTable.resizeColumnsToContents()
        except Exception as e:
            print(f"[ERROR] Greška u osvežavanju tabele: {e}")

    def postoji_zapis_za_datum(self, datum_str):
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
                        SELECT COUNT(*) FROM kasa.tk
                        WHERE datum = %s AND god = %s AND sifobj = %s
                    """
                    cursor.execute(query, (datum_str, self.GODINA, self.SIFOBJEKTA))
                    count = cursor.fetchone()[0]
                    return count > 0
        except Exception as e:
            print(f"[ERROR] Greška u postoji_zapis_za_datum: {e}")
            return False

    def autoCheck_changed(self, state):
        if state == 2:  # Checked
            datum_qdate = self.datumEdit.date()
            datum_str = datum_qdate.toString("yyyy-MM-dd")

            # Ako je izabrani datum 01.01.
            if datum_str.endswith("-01-01"):
                self.obradi_pocetno_stanje()

            # 🔒 Provera da li već postoje zapisi
            if self.postoji_zapis_za_datum(datum_str):
                print("[INFO] Zapisi za ovaj datum već postoje – preskačem zaduženja i razduženja.")
                return

            self.obradi_dnevni_pazar()
            # Zaduzenja
            self.obradi_kalkulacije()
            self.obradi_nivelacije()
            self.obradi_povratnicu()
            self.obradi_interni_ulaz()
            self.obradi_prenosVP()
            # Razduzenja
            self.obradi_otpis()
            self.obradi_interni_izlaz()
            # Prikazi u dijalogu
            self.osvezi_tabelu()

    def obradi_dnevni_pazar(self):
        try:
            datum_qdate = self.datumEdit.date()
            datum_str = datum_qdate.toString("yyyy-MM-dd")  # Za SQL
            datum_za_opis = datum_qdate.toString("d.M.yyyy")  # Za opis
            now = datetime.now()

            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    # Provera da li postoji unos za taj datum
                    provera_query = """
                        SELECT COUNT(*) FROM kasa.tk
                        WHERE god = %s AND sifobj = %s AND datum = %s
                    """
                    cursor.execute(provera_query, (self.GODINA, self.SIFOBJEKTA, datum_str))
                    if cursor.fetchone()[0] > 0:
                        print("[INFO] Pazar za ovaj dan je već unet, nema potrebe za ponovnim unosom.")
                        return

                    # Dohvatanje suma po načinu plaćanja
                    query = """
                        SELECT
                            SUM(CASE WHEN tipracuna::integer IN (0,4) AND tiptransakcije::integer = 0 THEN vrgotovina ELSE 0 END),
                            SUM(CASE WHEN tipracuna::integer IN (0,4) AND tiptransakcije::integer = 0 THEN vrkartica ELSE 0 END),
                            SUM(CASE WHEN tipracuna::integer IN (0,4) AND tiptransakcije::integer = 0 THEN vrcek ELSE 0 END),
                            SUM(CASE WHEN tipracuna::integer IN (0,4) AND tiptransakcije::integer = 0 THEN vrfaktura ELSE 0 END)
                        FROM kasa.kasasum
                        WHERE god = %s AND sifobj = %s AND datum = %s
                    """
                    cursor.execute(query, (self.GODINA, self.SIFOBJEKTA, datum_str))
                    gotovina, kartica, cek, faktura = [x or 0 for x in cursor.fetchone()]

                    print(f"[INFO] Gotovina: {gotovina}, Kartica: {kartica}, Ček: {cek}, Faktura: {faktura}")

                    # Upis u TK tabelu
                    def upisi_red(opis, iznos, vrstaplacanja):
                        if iznos == 0:
                            return
                        cursor.execute("""
                            INSERT INTO kasa.tk 
                            (datum, opis, zaduzenje, razduzenje, datupl, iznos, vrstaplacanja, sifobj, god, kar, xopunos, xdatunosa)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            datum_str,
                            opis,
                            0,
                            round(iznos, 2),
                            datum_str,
                            0,
                            vrstaplacanja,
                            self.SIFOBJEKTA,
                            self.GODINA,
                            1,
                            "sistem",
                            now
                        ))
                        print(f"[INFO] Upisan red: {opis} | {iznos} RSD")

                    upisi_red(f"Dnevni pazar gotovina za dan {datum_za_opis}", gotovina, 1)
                    upisi_red(f"Dnevni pazar kartica za dan {datum_za_opis}", kartica, 2)
                    upisi_red(f"Dnevni pazar ček za dan {datum_za_opis}", cek, 3)
                    upisi_red(f"Dnevni pazar prenos na račun za dan {datum_za_opis}", faktura, 4)

                    # Refundacije
                    cursor.execute("""
                        SELECT brracpu, ukiznos FROM kasa.kasasum
                        WHERE god = %s AND sifobj = %s AND datum = %s
                        AND tiptransakcije = '1' AND tipracuna IN ('0','4')
                    """, (self.GODINA, self.SIFOBJEKTA, datum_str))
                    for brracpu, ukiznos in cursor.fetchall():
                        if ukiznos and ukiznos != 0:
                            opis = f"Refundacija po računu {brracpu} za datum {datum_za_opis}"
                            vrednost = -abs(round(ukiznos, 2))
                            upisi_red(opis, vrednost, 4)

                    conn.commit()
                    print("[INFO] Obrada dnevnog pazara sa refundacijama uspešno završena!")

            #self.osvezi_tabelu()

        except Exception as e:
            print(f"[ERROR] Greška u obradi dnevnog pazara: {e}")


    def obradi_pocetno_stanje(self):
        try:
            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    # Koristimo fiksni datum 01.01.GODINA
                    #datum_str = f"{self.GODINA}-01-01"
                    datum_qdate = self.datumEdit.date()
                    datum_str = datum_qdate.toString("yyyy-MM-dd")  # Za SQL

                    # Provera da li već postoji upis za početno stanje za tu godinu
                    provera_query = """
                        SELECT COUNT(*) FROM kasa.tk
                        WHERE god = %s AND sifobj = %s AND datum = %s AND opis ILIKE '%%Početno stanje%%'
                    """
                    cursor.execute(provera_query, (self.GODINA, self.SIFOBJEKTA, datum_str))
                    if cursor.fetchone()[0] > 0:
                        print("[INFO] Početno stanje za ovu godinu već postoji u KEP knjizi.")
                        return

                    # Suma vrednosti iz karticaart za vrstu 5 (početno stanje)
                    upit = """
                        SELECT COALESCE(SUM(kolicina * cena), 0)
                        FROM kasa.karticaart
                        WHERE god = %s AND sifobj = %s AND vrsta = 5
                    """
                    cursor.execute(upit, (self.GODINA, self.SIFOBJEKTA))
                    ukupno_zaduzenje = cursor.fetchone()[0]

                    ukupno_zaduzenje = round(ukupno_zaduzenje, 2)

                    if ukupno_zaduzenje == 0:
                        print("[INFO] Nema stavki za početno stanje – preskačemo unos.")
                        return

                    # Unos u KEP knjigu
                    insert_query = """
                        INSERT INTO kasa.tk
                        (datum, opis, zaduzenje, razduzenje, datupl, iznos, sifobj, god, kar, xopunos, xdatunosa)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    opis = f"Početno stanje zaliha za godinu {self.GODINA}"
                    vrednosti = (
                        datum_str, opis, ukupno_zaduzenje, 0, datum_str, 0,
                        self.SIFOBJEKTA, self.GODINA, 1, "sistem", datetime.now()
                    )
                    cursor.execute(insert_query, vrednosti)
                    conn.commit()

                    print(f"[INFO] Početno stanje uspešno upisano u KEP knjigu: {ukupno_zaduzenje:.2f} RSD")

                #self.osvezi_tabelu()

        except Exception as e:
            print(f"[ERROR] Greška pri upisu početnog stanja: {e}")

############################## Pocetak dokumenata zaduzenja ######################################
    def obradi_kalkulacije(self):
        try:
            # Dobijanje datuma iz kontrole
            datum_qdate = self.datumEdit.date()
            datum_str = datum_qdate.toString("yyyy-MM-dd")  # Za SQL

            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    # Dohvatanje dokumenta tipa kalkulacija
                    query_robnadok = """
                        SELECT d.broj, d.brojuidok, d.idpartneri, p.naziv
                        FROM kasa.robnadok d
                        LEFT JOIN kasa.partneri p ON d.idpartneri = p.id
                        WHERE d.god = %s AND d.sifobj = %s AND d.vrsta = 1 AND d.datdok = %s
                    """
                    cursor.execute(query_robnadok, (self.GODINA, self.SIFOBJEKTA, datum_str))
                    dokumenti = cursor.fetchall()

                    for dok in dokumenti:
                        broj, brojuidok, idpartneri, naziv_partnera = dok
                        naziv_partnera = naziv_partnera or ""
                        opis = f"Kalkulacija broj {broj} od {naziv_partnera} br. ulaznog dok. {brojuidok}"

                        # Dohvatanje stavki za tu kalkulaciju
                        query_stavke = """
                            SELECT kolicina, cena
                            FROM kasa.karticaart
                            WHERE god = %s AND sifobj = %s AND vrsta = 1 AND broj = %s
                        """
                        cursor.execute(query_stavke, (self.GODINA, self.SIFOBJEKTA, broj))
                        stavke = cursor.fetchall()

                        ukupno_zaduzenje = sum(kolicina * cena for kolicina, cena in stavke)
                        ukupno_zaduzenje = round(ukupno_zaduzenje, 2)

                        # Direktan upis u TK
                        try:
                            now = datetime.now()

                            insert_query = """
                                INSERT INTO kasa.tk 
                                (datum, opis, zaduzenje, razduzenje, datupl, iznos, vrstaplacanja, sifobj, god, kar, xopunos, xdatunosa)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """

                            values = (
                                datum_str,          # datum
                                opis,               # opis
                                ukupno_zaduzenje,   # zaduzenje
                                0,                  # razduzenje
                                datum_str,          # datupl
                                0,                  # iznos
                                0,                  # vrstaplacanja
                                self.SIFOBJEKTA,    # sifobj
                                self.GODINA,        # god
                                1,                  # kar
                                "sistem",           # xopunos
                                now                 # xdatunosa
                            )

                            cursor.execute(insert_query, values)
                            print(f"[INFO] Unos kalkulacije u TK: {opis}")
                        except Exception as e:
                            print(f"[ERROR] Greška prilikom unosa kalkulacije u TK: {e}")

                    conn.commit()

                #self.osvezi_tabelu()

        except Exception as e:
            print(f"[ERROR] Greška u obradi kalkulacija: {e}")
            QMessageBox.critical(None, "Greška", f"Greška u obradi kalkulacija:\n{e}")

    def obradi_nivelacije(self):
        try:
            datum_qdate = self.datumEdit.date()
            datum_str = datum_qdate.toString("yyyy-MM-dd")  # Za SQL

            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    # Dohvati dokumenta tipa nivelacija
                    query_robnadok = """
                        SELECT broj
                        FROM kasa.robnadok
                        WHERE god = %s AND sifobj = %s AND vrsta = 4 AND datdok = %s
                    """
                    cursor.execute(query_robnadok, (self.GODINA, self.SIFOBJEKTA, datum_str))
                    dokumenti = cursor.fetchall()

                    for (broj,) in dokumenti:
                        opis = f"Nivelacija broj {broj}"

                        query_stavke = """
                            SELECT kolicina, cena, staracena
                            FROM kasa.karticaart
                            WHERE god = %s AND sifobj = %s AND vrsta = 4 AND broj = %s
                        """
                        cursor.execute(query_stavke, (self.GODINA, self.SIFOBJEKTA, broj))
                        stavke = cursor.fetchall()

                        ukupna_nivelacija = sum((cena - staracena) * kolicina for kolicina, cena, staracena in stavke)
                        ukupna_nivelacija = round(ukupna_nivelacija, 2)

                        now = datetime.now()

                        # Direktan INSERT u TK
                        insert_query = """
                            INSERT INTO kasa.tk (datum, opis, razduzenje, zaduzenje, vrstaplacanja, sifobj, god, kar, xopunos, xdatunosa)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(insert_query, (
                            datum_str,
                            opis,
                            0,                    # razduženje
                            ukupna_nivelacija,    # zaduženje može biti negativno
                            0,                     # vrstaplacanja
                            self.SIFOBJEKTA,    # sifobj
                            self.GODINA,        # god
                            1,                  # kar
                            "sistem",           # xopunos
                            now                 # xdatunosa
                        ))

                    conn.commit()
                    
                #self.osvezi_tabelu()

        except Exception as e:
            print(f"[ERROR] Greška u obradi nivelacija: {e}")
            QMessageBox.critical(None, "Greška", f"Greška u obradi nivelacija:\n{e}")

    def obradi_povratnicu(self):
        try:
            # Dobijanje datuma iz kontrole
            datum_qdate = self.datumEdit.date()
            datum_str = datum_qdate.toString("yyyy-MM-dd")  # Za SQL

            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    # Dohvatanje dokumenta tipa kalkulacija
                    query_robnadok = """
                        SELECT d.broj, d.brojuidok, d.idpartneri, p.naziv
                        FROM kasa.robnadok d
                        LEFT JOIN kasa.partneri p ON d.idpartneri = p.id
                        WHERE d.god = %s AND d.sifobj = %s AND d.vrsta = 16 AND d.datdok = %s
                    """
                    cursor.execute(query_robnadok, (self.GODINA, self.SIFOBJEKTA, datum_str))
                    dokumenti = cursor.fetchall()

                    for dok in dokumenti:
                        broj, brojuidok, idpartneri, naziv_partnera = dok
                        naziv_partnera = naziv_partnera or ""
                        opis = f"Povratnica dobavljaču broj {broj} za {naziv_partnera}"

                        # Dohvatanje stavki za tu kalkulaciju
                        query_stavke = """
                            SELECT kolicina, cena
                            FROM kasa.karticaart
                            WHERE god = %s AND sifobj = %s AND vrsta = 16 AND broj = %s
                        """
                        cursor.execute(query_stavke, (self.GODINA, self.SIFOBJEKTA, broj))
                        stavke = cursor.fetchall()

                        ukupno_zaduzenje = -abs(sum(kolicina * cena for kolicina, cena in stavke))
                        ukupno_zaduzenje = round(ukupno_zaduzenje, 2)

                        # Direktan upis u TK
                        try:
                            now = datetime.now()

                            insert_query = """
                                INSERT INTO kasa.tk 
                                (datum, opis, zaduzenje, razduzenje, datupl, iznos, vrstaplacanja, sifobj, god, kar, xopunos, xdatunosa)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """

                            values = (
                                datum_str,          # datum
                                opis,               # opis
                                ukupno_zaduzenje,   # zaduzenje
                                0,                  # razduzenje
                                datum_str,          # datupl
                                0,                  # iznos
                                0,                  # vrstaplacanja
                                self.SIFOBJEKTA,    # sifobj
                                self.GODINA,        # god
                                1,                  # kar
                                "sistem",           # xopunos
                                now                 # xdatunosa
                            )

                            cursor.execute(insert_query, values)
                            print(f"[INFO] Unos povratnice dobavljaču u TK: {opis}")
                        except Exception as e:
                            print(f"[ERROR] Greška prilikom unosa povratnice dobavljaču u TK: {e}")

                    conn.commit()

                #self.osvezi_tabelu()

        except Exception as e:
            print(f"[ERROR] Greška u obradi povratnice dobavljaču: {e}")
            QMessageBox.critical(None, "Greška", f"Greška u obradi povratnice dobavljaču:\n{e}")

    def obradi_interni_ulaz(self):
        try:
            # Dobijanje datuma iz kontrole
            datum_qdate = self.datumEdit.date()
            datum_str = datum_qdate.toString("yyyy-MM-dd")  # Za SQL

            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    # Dohvatanje dokumenta tipa kalkulacija
                    query_robnadok = """
                        SELECT d.broj, d.brojuidok, d.opis, d.idpartneri, p.naziv
                        FROM kasa.robnadok d
                        LEFT JOIN kasa.partneri p ON d.idpartneri = p.id
                        WHERE d.god = %s AND d.sifobj = %s AND d.vrsta = 40 AND d.datdok = %s
                    """
                    cursor.execute(query_robnadok, (self.GODINA, self.SIFOBJEKTA, datum_str))
                    dokumenti = cursor.fetchall()

                    for dok in dokumenti:
                        broj, brojuidok, opis, idpartneri, naziv_partnera = dok
                        naziv_partnera = naziv_partnera or ""
                        opistk = f"{opis} br. ulaznog dok. {brojuidok}"

                        # Dohvatanje stavki za tu kalkulaciju
                        query_stavke = """
                            SELECT kolicina, cena
                            FROM kasa.karticaart
                            WHERE god = %s AND sifobj = %s AND vrsta = 40 AND broj = %s
                        """
                        cursor.execute(query_stavke, (self.GODINA, self.SIFOBJEKTA, broj))
                        stavke = cursor.fetchall()

                        ukupno_zaduzenje = sum(kolicina * cena for kolicina, cena in stavke)
                        ukupno_zaduzenje = round(ukupno_zaduzenje, 2)

                        # Direktan upis u TK
                        try:
                            now = datetime.now()

                            insert_query = """
                                INSERT INTO kasa.tk 
                                (datum, opis, zaduzenje, razduzenje, datupl, iznos, vrstaplacanja, sifobj, god, kar, xopunos, xdatunosa)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """

                            values = (
                                datum_str,          # datum
                                opistk,             # opis
                                ukupno_zaduzenje,   # zaduzenje
                                0,                  # razduzenje
                                datum_str,          # datupl
                                0,                  # iznos
                                0,                  # vrstaplacanja
                                self.SIFOBJEKTA,    # sifobj
                                self.GODINA,        # god
                                1,                  # kar
                                "sistem",           # xopunos
                                now                 # xdatunosa
                            )

                            cursor.execute(insert_query, values)
                            print(f"[INFO] Unos internog prenosa - ulaz u TK: {opistk}")
                        except Exception as e:
                            print(f"[ERROR] Greška prilikom unosa internog prenosa - ulaz u TK: {e}")

                    conn.commit()

                #self.osvezi_tabelu()

        except Exception as e:
            print(f"[ERROR] Greška u obradi internog prenosa - ulaz: {e}")
            QMessageBox.critical(None, "Greška", f"Greška u obradi internog prenosa - ulaz:\n{e}")

    def obradi_prenosVP(self):
        try:
            # Dobijanje datuma iz kontrole
            datum_qdate = self.datumEdit.date()
            datum_str = datum_qdate.toString("yyyy-MM-dd")  # Za SQL

            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    # Dohvatanje dokumenta tipa kalkulacija
                    query_robnadok = """
                        SELECT d.broj, d.brojuidok, d.opis, d.idpartneri, p.naziv
                        FROM kasa.robnadok d
                        LEFT JOIN kasa.partneri p ON d.idpartneri = p.id
                        WHERE d.god = %s AND d.sifobj = %s AND d.vrsta = 42 AND d.datdok = %s
                    """
                    cursor.execute(query_robnadok, (self.GODINA, self.SIFOBJEKTA, datum_str))
                    dokumenti = cursor.fetchall()

                    for dok in dokumenti:
                        broj, brojuidok, opis, idpartneri, naziv_partnera = dok
                        naziv_partnera = naziv_partnera or ""
                        opis = f"Prenos iz veleprodaje broj {broj} br. ulaznog dok. {brojuidok}"

                        # Dohvatanje stavki za tu kalkulaciju
                        query_stavke = """
                            SELECT kolicina, cena
                            FROM kasa.karticaart
                            WHERE god = %s AND sifobj = %s AND vrsta = 42 AND broj = %s
                        """
                        cursor.execute(query_stavke, (self.GODINA, self.SIFOBJEKTA, broj))
                        stavke = cursor.fetchall()

                        ukupno_zaduzenje = sum(kolicina * cena for kolicina, cena in stavke)
                        ukupno_zaduzenje = round(ukupno_zaduzenje, 2)

                        # Direktan upis u TK
                        try:
                            now = datetime.now()

                            insert_query = """
                                INSERT INTO kasa.tk 
                                (datum, opis, zaduzenje, razduzenje, datupl, iznos, vrstaplacanja, sifobj, god, kar, xopunos, xdatunosa)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """

                            values = (
                                datum_str,          # datum
                                opis,             # opis
                                ukupno_zaduzenje,   # zaduzenje
                                0,                  # razduzenje
                                datum_str,          # datupl
                                0,                  # iznos
                                0,                  # vrstaplacanja
                                self.SIFOBJEKTA,    # sifobj
                                self.GODINA,        # god
                                1,                  # kar
                                "sistem",           # xopunos
                                now                 # xdatunosa
                            )

                            cursor.execute(insert_query, values)
                            print(f"[INFO] Unos prenosa iz VP u TK: {opis}")
                        except Exception as e:
                            print(f"[ERROR] Greška prilikom unosa prenosa iz VP u TK: {e}")

                    conn.commit()

                #self.osvezi_tabelu()

        except Exception as e:
            print(f"[ERROR] Greška u obradi internog prenosa - ulaz: {e}")
            QMessageBox.critical(None, "Greška", f"Greška u obradi prenosa iz VP:\n{e}")

############################## Kraj dokumenata zaduzenja ######################################

############################## Pocetak dokumenata razduzenja ######################################
    def obradi_otpis(self):
        try:
            # Dobijanje datuma iz kontrole
            datum_qdate = self.datumEdit.date()
            datum_str = datum_qdate.toString("yyyy-MM-dd")  # Za SQL

            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    # Dohvatanje dokumenta tipa kalkulacija
                    query_robnadok = """
                        SELECT d.broj, d.brojuidok, d.opis, d.idpartneri, p.naziv
                        FROM kasa.robnadok d
                        LEFT JOIN kasa.partneri p ON d.idpartneri = p.id
                        WHERE d.god = %s AND d.sifobj = %s AND d.vrsta = 15 AND d.datdok = %s
                    """
                    cursor.execute(query_robnadok, (self.GODINA, self.SIFOBJEKTA, datum_str))
                    dokumenti = cursor.fetchall()

                    for dok in dokumenti:
                        broj, brojuidok, opis, idpartneri, naziv_partnera = dok
                        naziv_partnera = naziv_partnera or ""
                        opis = f"Otpis robe {broj}"

                        # Dohvatanje stavki za tu kalkulaciju
                        query_stavke = """
                            SELECT kolicina, cena
                            FROM kasa.karticaart
                            WHERE god = %s AND sifobj = %s AND vrsta = 15 AND broj = %s
                        """
                        cursor.execute(query_stavke, (self.GODINA, self.SIFOBJEKTA, broj))
                        stavke = cursor.fetchall()

                        ukupno_razduzenje = sum(kolicina * cena for kolicina, cena in stavke)
                        ukupno_razduzenje = round(ukupno_razduzenje, 2)

                        # Direktan upis u TK
                        try:
                            now = datetime.now()

                            insert_query = """
                                INSERT INTO kasa.tk 
                                (datum, opis, zaduzenje, razduzenje, datupl, iznos, vrstaplacanja, sifobj, god, kar, xopunos, xdatunosa)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """

                            values = (
                                datum_str,          # datum
                                opis,               # opis
                                0,                  # zaduzenje
                                ukupno_razduzenje,  # razduzenje
                                datum_str,          # datupl
                                0,                  # iznos
                                0,                  # vrstaplacanja
                                self.SIFOBJEKTA,    # sifobj
                                self.GODINA,        # god
                                1,                  # kar
                                "sistem",           # xopunos
                                now                 # xdatunosa
                            )

                            cursor.execute(insert_query, values)
                            print(f"[INFO] Unos otpisa u TK: {opis}")
                        except Exception as e:
                            print(f"[ERROR] Greška prilikom unosa otpisa u TK: {e}")

                    conn.commit()

                #self.osvezi_tabelu()

        except Exception as e:
            print(f"[ERROR] Greška u obradi internog prenosa - ulaz: {e}")
            QMessageBox.critical(None, "Greška", f"Greška u obradi otpisa:\n{e}")

    def obradi_interni_izlaz(self):
        try:
            # Dobijanje datuma iz kontrole
            datum_qdate = self.datumEdit.date()
            datum_str = datum_qdate.toString("yyyy-MM-dd")  # Za SQL

            with psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            ) as conn:
                with conn.cursor() as cursor:
                    # Dohvatanje dokumenta tipa kalkulacija
                    query_robnadok = """
                        SELECT d.broj, d.brojuidok, d.opis, d.idpartneri, p.naziv
                        FROM kasa.robnadok d
                        LEFT JOIN kasa.partneri p ON d.idpartneri = p.id
                        WHERE d.god = %s AND d.sifobj = %s AND d.vrsta = 39 AND d.datdok = %s
                    """
                    cursor.execute(query_robnadok, (self.GODINA, self.SIFOBJEKTA, datum_str))
                    dokumenti = cursor.fetchall()

                    for dok in dokumenti:
                        broj, brojuidok, opis, idpartneri, naziv_partnera = dok
                        naziv_partnera = naziv_partnera or ""
                        opistk = f"{opis}"

                        # Dohvatanje stavki za tu kalkulaciju
                        query_stavke = """
                            SELECT kolicina, cena
                            FROM kasa.karticaart
                            WHERE god = %s AND sifobj = %s AND vrsta = 39 AND broj = %s
                        """
                        cursor.execute(query_stavke, (self.GODINA, self.SIFOBJEKTA, broj))
                        stavke = cursor.fetchall()

                        ukupno_razduzenje = sum(kolicina * cena for kolicina, cena in stavke)
                        ukupno_razduzenje = round(ukupno_razduzenje, 2)

                        # Direktan upis u TK
                        try:
                            now = datetime.now()

                            insert_query = """
                                INSERT INTO kasa.tk 
                                (datum, opis, zaduzenje, razduzenje, datupl, iznos, vrstaplacanja, sifobj, god, kar, xopunos, xdatunosa)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """

                            values = (
                                datum_str,          # datum
                                opistk,             # opis
                                0,                  # zaduzenje
                                ukupno_razduzenje,  # razduzenje
                                datum_str,          # datupl
                                0,                  # iznos
                                0,                  # vrstaplacanja
                                self.SIFOBJEKTA,    # sifobj
                                self.GODINA,        # god
                                1,                  # kar
                                "sistem",           # xopunos
                                now                 # xdatunosa
                            )

                            cursor.execute(insert_query, values)
                            print(f"[INFO] Unos internog prenosa - izlaz u TK: {opistk}")
                        except Exception as e:
                            print(f"[ERROR] Greška prilikom unosa internog prenosa - izlaz u TK: {e}")

                    conn.commit()

                #self.osvezi_tabelu()

        except Exception as e:
            print(f"[ERROR] Greška u obradi internog prenosa - izlaz: {e}")
            QMessageBox.critical(None, "Greška", f"Greška u obradi internog prenosa - izlaz:\n{e}")

############################## Kraj dokumenata razduzenja ######################################
################# Brisanje stavki TK za izabrani datum i sifru objekta #########################
    def obrisi_stavke_za_datum(self):
        datum = self.datumEdit.date().toString("yyyy-MM-dd")
        datumsrp = self.datumEdit.date().toString("dd-MM-yyyy")
        potvrda = QMessageBox.question(
            self,
            "Potvrda brisanja",
            f"Da li ste sigurni da želite da obrišete sve stavke za datum {datumsrp}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if potvrda != QMessageBox.StandardButton.Yes:
            return

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
                        DELETE FROM kasa.tk
                        WHERE god = %s AND sifobj = %s AND datum = %s
                    """
                    cursor.execute(query, (self.GODINA, self.SIFOBJEKTA, datum))
                    conn.commit()

            QMessageBox.information(self, "Brisanje", "Stavke su uspešno obrisane.")
            self.osvezi_tabelu()

        except Exception as e:
            print(f"[ERROR] Greška pri brisanju stavki: {e}")
            QMessageBox.critical(self, "Greška", f"Greška pri brisanju stavki:\n{e}")

####### Stampa KEP knjige za izabrani satumski opseg i sifru objekta ########
    def stampa_kep_izvestaja(self, od_datum, do_datum):
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
        # Putanje i font
        #folder_izvestaja = r"D:\\pos_desktop\\desktop_pos\\izvestaji"
        #os.makedirs(folder_izvestaja, exist_ok=True)
        #font_path = r"D:\\pos_desktop\\desktop_pos\\fonts\\EncodeSans-Medium.ttf"
        #pdfmetrics.registerFont(TTFont("EncodeSans-Medium", font_path))

        od_datum_str = od_datum.strftime("%Y-%m-%d")
        do_datum_str = do_datum.strftime("%Y-%m-%d")
        od_datum_ispis = od_datum.strftime("%d.%m.%Y")
        do_datum_ispis = do_datum.strftime("%d.%m.%Y")
        godina = self.GODINA
        sifobjekta = self.SIFOBJEKTA

        # Konekcija
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        cur = conn.cursor()

        cur.execute("SELECT naziv FROM kasa.fvr LIMIT 1")
        naziv_firme = cur.fetchone()[0]

        cur.execute("SELECT objekat, adresa, mesto FROM kasa.objekti WHERE sifobj = %s", (sifobjekta,))
        objekat_podaci = cur.fetchone()
        naziv_objekta, adresa_objekta, mesto_objekta = objekat_podaci if objekat_podaci else ("", "", "")

        cur.execute("""
            SELECT datum, opis, zaduzenje, razduzenje
            FROM kasa.tk
            WHERE datum BETWEEN %s AND %s
            ORDER BY datum ASC
        """, (od_datum_str, do_datum_str))
        podaci = cur.fetchall()

        cur.execute("""
            SELECT COUNT(*) FROM kasa.tk
            WHERE datum < %s AND EXTRACT(YEAR FROM datum) = %s
        """, (od_datum_str, godina))
        redni_pocetni = cur.fetchone()[0] + 1

        cur.close()
        conn.close()

        # PDF fajl
        fajl_izvestaja = os.path.join(folder_izvestaja, f"KEP_knjiga_{od_datum_str}_do_{do_datum_str}.pdf")

        # Stilovi
        stil_opisa = ParagraphStyle(name='OpisStil', fontName='EncodeSans-Medium', fontSize=9, leading=11, alignment=TA_LEFT)
        stil_naslova = ParagraphStyle(name='Naslov', fontName='EncodeSans-Medium', fontSize=14, alignment=1)
        stil_podnaslova = ParagraphStyle(name='Podnaslov', fontName='EncodeSans-Medium', fontSize=11, alignment=1)

        # Priprema podataka za tabelu
        redni_broj = redni_pocetni
        ukupno_zaduzenje = 0
        ukupno_razduzenje = 0
        tabela_podaci = [["R.br", "Datum", "Opis", "Zaduženje", "Razduženje"]]

        for datum, opis, zaduzenje, razduzenje in podaci:
            zaduzenje = zaduzenje or 0
            razduzenje = razduzenje or 0
            ukupno_zaduzenje += zaduzenje
            ukupno_razduzenje += razduzenje
            tabela_podaci.append([
                str(redni_broj),
                datum.strftime("%d.%m.%Y"),
                Paragraph(opis, stil_opisa),
                f"{zaduzenje:.2f}" if zaduzenje else "",
                f"{razduzenje:.2f}" if razduzenje else ""
            ])
            redni_broj += 1

        saldo = ukupno_zaduzenje - ukupno_razduzenje
        tabela_podaci.append(["", "", "UKUPNO:", f"{ukupno_zaduzenje:.2f}", f"{ukupno_razduzenje:.2f}"])
        tabela_podaci.append(["", "", "SALDO:", f"{saldo:.2f}", ""])

        # Tabela
        col_widths = [15 * mm, 25 * mm, 75 * mm, 30 * mm, 30 * mm]
        tabela = Table(tabela_podaci, colWidths=col_widths, repeatRows=1)
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgray),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -3), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, -1), "EncodeSans-Medium"),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('SPAN', (-2, -1), (-1, -1)),
            ('ALIGN', (-2, -1), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, -2), (-1, -2), colors.lightgrey),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ]))

        # Funkcija za paginaciju
        def on_each_page(canvas, doc):
            canvas.setFont("EncodeSans-Medium", 8)
            canvas.drawRightString(200 * mm, 10 * mm, f"Strana {doc.page}")

            canvas.setFont("EncodeSans-Medium", 10)
            canvas.drawString(20 * mm, 280 * mm, naziv_firme)
            canvas.drawString(20 * mm, 275 * mm, naziv_objekta)
            canvas.drawString(20 * mm, 270 * mm, adresa_objekta)
            canvas.drawString(20 * mm, 265 * mm, mesto_objekta)

            canvas.setFont("EncodeSans-Medium", 14)
            canvas.drawCentredString(105 * mm, 255 * mm, f"Knjiga evidencije prometa za poslovnu {godina} godinu")
            canvas.setFont("EncodeSans-Medium", 11)
            canvas.drawCentredString(105 * mm, 245 * mm, f"Period: {od_datum_ispis} do {do_datum_ispis}")

        # PDF dokument sa zaglavljem i paginacijom
        doc = SimpleDocTemplate(
            fajl_izvestaja,
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=60 * mm,
            bottomMargin=20 * mm
        )
        doc.build([tabela], onFirstPage=on_each_page, onLaterPages=on_each_page)

        webbrowser.open(fajl_izvestaja)

    def on_stampa_clicked(self):
        od_datum = self.oddatuEdit.date()
        do_datum = self.dodatumEdit.date()
        self.parent().stampa_kep_izvestaja(od_datum, do_datum)
        self.accept()


    def otvori_dijalog_za_stampu(self):
        dijalog = KepStampaDijalog(self)
        if dijalog.exec():  # Ako korisnik klikne na "Štampa"
            od_datum, do_datum = dijalog.get_datumi()
            self.stampa_kep_izvestaja(od_datum, do_datum)

    