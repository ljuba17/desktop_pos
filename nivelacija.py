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

        # Prva kolona id je skrivena
        # Postavljanje širine kolona u tableStavke
        self.tableStavke.setColumnWidth(0, 60)  # Prva kolona širine 60 id iz karticaart
        self.tableStavke.setColumnWidth(1, 70)  # Druga kolona širine 70 sifra
        self.tableStavke.setColumnWidth(2, 220)  # Treća kolona širine 220 Naziv artikla
        self.tableStavke.setColumnWidth(3, 80)  # Četvrta kolona širine 80 kolicina
        self.tableStavke.setColumnWidth(4, 90)  # Peta kolona širine 90 stara cena
        self.tableStavke.setColumnWidth(5, 90)  # Peta kolona širine 90 nova cena
        self.tableStavke.setColumnWidth(6, 90)  # Peta kolona širine 90 razlika
        self.tableStavke.setColumnWidth(7, 70)  # Peta kolona širine 70 % nivelacije
        self.tableStavke.setColumnWidth(8, 70)  # Peta kolona širine 70 broj nivelacije
        self.tableStavke.setColumnHidden(0, True)
        self.tableStavke.setColumnHidden(8, True)

        # Povezivanje dugmeta sa funkcijom za učitavanje izveštaja
        self.btnObradi.clicked.connect(self.pokreni_nivelaciju)
        self.btnCancel.clicked.connect(self.reject)


    def proveri_postojecu_nivelaciju(self):
        datum_qdate = self.datumEdit.date()
        datum_str = datum_qdate.toString("yyyy-MM-dd")

        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cur = conn.cursor()

            sql = """
                SELECT broj FROM kasa.robnadok
                WHERE god = %s
                  AND sifobj = %s
                  AND vrsta = 4
                  AND datdok = %s
                  AND opis LIKE 'Auto niv. br%%'
            """
            cur.execute(sql, (GODINA, SIFOBJEKTA, datum_str))
            rezultat = cur.fetchone()

            cur.close()
            conn.close()

            return rezultat is not None

        except Exception as e:
            QMessageBox.critical(None, "Greška", f"Greška prilikom provere nivelacije:\n{e}")
            return False

    def postoji_popust_za_datum(self):
        datum_qdate = self.datumEdit.date()
        datum_str = datum_qdate.toString("yyyy-MM-dd")

        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cur = conn.cursor()

            sql = """
                SELECT 1 FROM kasa.karticaart ka
                JOIN kasa.artikli a ON a.id = ka.artikliid
                WHERE ka.god = %s
                  AND ka.sifobj = %s
                  AND ka.datum = %s
                  AND ka.vrsta IN (3, 8, 9)
                  AND ka.cena <> ka.cenanabavna
                  AND a.tip = 1
                LIMIT 1
            """
            cur.execute(sql, (GODINA, SIFOBJEKTA, datum_str))
            postoji = cur.fetchone() is not None

            cur.close()
            conn.close()

            return postoji

        except Exception as e:
            QMessageBox.critical(None, "Greška", f"Greška prilikom provere stavki sa popustom:\n{e}")
            return False

    def generisi_broj_dokumenta(self):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cur = conn.cursor()

            cur.execute("""
                SELECT broj FROM kasa.robnadok
                WHERE god = %s AND sifobj = %s AND vrsta = %s
                ORDER BY broj DESC LIMIT 1
            """, (GODINA, SIFOBJEKTA, 4))

            row = cur.fetchone()
            novi_broj = row[0] + 1 if row else 1

            cur.close()
            conn.close()
            return novi_broj

        except Exception as e:
            raise Exception(f"Greška pri generisanju broja dokumenta: {e}")

    def kreiraj_zaglavlje_nivelacije(self, datum_qdate, novi_broj):
        datum_str = datum_qdate.toString("yyyy-MM-dd")

        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cur = conn.cursor()

            sql = """
                INSERT INTO kasa.robnadok (
                    god, kar, vrsta, sifobj,
                    datdok, datdospeca, kreirao,
                    broj, opis, vrednost
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            cur.execute(sql, (
                GODINA,
                1,                      # kar = 1
                4,                      # vrsta = 4 (nivelacija)
                SIFOBJEKTA,
                datum_str,
                datum_str,
                os.getenv("APP_USER") or "auto_nivelacija",
                novi_broj,
                f"Auto niv. br: {novi_broj}",
                0                      # vrednost se kasnije ažurira
            ))

            conn.commit()
            cur.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(None, "Greška", f"Greška prilikom kreiranja zaglavlja nivelacije:\n{e}")

    def dohvati_agregirane_stavke_nivelacije(self, datum, sifobj):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cur = conn.cursor()

            sql = """
                SELECT
                    a.sifra,
                    a.id,
                    k.tarifa,
                    k.porezproc,
                    k.grupa,
                    k.porezid,
                    k.cena AS nova_cena,
                    k.cenanabavna,
                    SUM(k.kolicina) AS ukupna_kolicina
                FROM
                    kasa.karticaart k
                    JOIN kasa.artikli a ON k.sifra = a.sifra
                WHERE
                    k.datum = %s
                    AND k.sifobj = %s
                    AND k.vrsta IN (8, 9, 3)
                    AND k.cena <> k.cenanabavna
                    AND a.tip = 1
                GROUP BY
                    a.sifra, a.id, k.tarifa, k.porezproc,
                    k.grupa, k.porezid, k.cena, k.cenanabavna
                ORDER BY
                    a.sifra, k.cena
            """

            cur.execute(sql, (datum, sifobj))
            result = cur.fetchall()

            stavke = []
            for row in result:
                sifra, artikliid, tarifa, porezproc, grupa, porezid, nova_cena, cenanabavna, ukupna_kolicina = row
                stavke.append({
                    "sifra": sifra,
                    "artikliid": artikliid,
                    "tarifa": tarifa,
                    "porezproc": porezproc,
                    "grupa": grupa,
                    "porezid": porezid,
                    "nova_cena": float(nova_cena),
                    "cenanabavna": float(cenanabavna),
                    "kolicina": float(ukupna_kolicina)
                })

                print(f"➡ Šifra: {sifra}, Nova cena: {nova_cena}, Nabavna: {cenanabavna}, Količina: {ukupna_kolicina}")

            cur.close()
            conn.close()

            return stavke

        except Exception as e:
            raise Exception(f"Greška pri dohvatanju agregiranih stavki nivelacije: {e}")


    def dodaj_stavku_nivelacije(self, broj_dokumenta, datum_qdate, sifobj, korisnik, stavka):
        """
        Dodaje jednu stavku nivelacije u karticaart koristeći podatke iz agregatne funkcije.
        """
        sifra = stavka["sifra"]
        artikliid = stavka["artikliid"]
        tarifa = stavka["tarifa"]
        porezproc = stavka["porezproc"]
        grupa = stavka["grupa"]
        porezid = stavka["porezid"]
        nova_cena = stavka["nova_cena"]
        staracena = stavka["cenanabavna"]
        kolicina = stavka["kolicina"]

        if not sifra or artikliid is None or nova_cena is None or kolicina is None:
            raise ValueError("Nedostaju potrebni parametri.")

        if kolicina <= 0:
            raise ValueError("Količina mora biti veća od nule.")

        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cur = conn.cursor()

            # Računanje poreza
            stopa_poreza = porezproc or 0
            if stopa_poreza > 0:
                nprer1 = (stopa_poreza * 100) / (stopa_poreza + 100)
            else:
                nprer1 = 0

            razlika_cene = nova_cena - staracena
            porez = round(razlika_cene * (nprer1 / 100) * kolicina, 2)

            datum_str = datum_qdate.toString("yyyy-MM-dd")

            #print(f"✅ Dodavanje stavke: Šifra={sifra}, Količina={kolicina}, Cena={nova_cena}, Nabavna={staracena}")

            cur.execute("""
                INSERT INTO kasa.karticaart (
                    god, kar, broj, sifobj, vrsta,
                    artikliid, sifra, kolicina, cena, staracena,
                    porez, porezproc, tarifa, porezid, grupa,
                    opis, datum, kreirao, idpartneri
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
            """, (
                GODINA,
                1,  # kar
                broj_dokumenta,
                sifobj,
                4,  # vrsta = 4 (nivelacija)
                artikliid,
                sifra,
                kolicina,
                nova_cena,
                staracena,
                porez,
                stopa_poreza,
                tarifa or '',
                porezid,
                grupa,
                f"Auto niv. br: {broj_dokumenta}",
                datum_str,
                korisnik,
                None
            ))

            conn.commit()
            cur.close()
            conn.close()

        except Exception as e:
            raise Exception(f"Greška pri dodavanju stavke nivelacije: {e}")
        
    def azuriraj_vrednost_nivelacije(self, broj, sifobj):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cur = conn.cursor()

            # Saberemo vrednost razlike cena * količina za taj dokument
            cur.execute("""
                SELECT SUM((cena - staracena) * kolicina)
                FROM kasa.karticaart
                WHERE god = %s AND sifobj = %s AND vrsta = 4 AND broj = %s
            """, (GODINA, sifobj, broj))
            ukupna_vrednost = cur.fetchone()[0] or 0

            # Ažuriramo vrednost u zaglavlju
            cur.execute("""
                UPDATE kasa.robnadok
                SET vrednost = %s
                WHERE god = %s AND sifobj = %s AND vrsta = 4 AND broj = %s
            """, (ukupna_vrednost, GODINA, sifobj, broj))

            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška prilikom ažuriranja vrednosti nivelacije:\n{e}")

    def dohvati_broj_nivelacije_za_datum(self, godina, sifobj, datum_str):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT broj FROM kasa.robnadok
                WHERE god = %s
                AND sifobj = %s
                AND vrsta = 4
                AND datdok = %s
                AND opis LIKE 'Auto niv. br%%'
                LIMIT 1
            """, (godina, sifobj, datum_str))
            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                return result[0]
            return None

        except Exception as e:
            QMessageBox.critical(None, "Greška", f"Greška prilikom dohvata broja nivelacije:\n{e}")
            return None


    def proveri_i_prikazi_nivelaciju(self):
        datum_qdate = self.datumEdit.date()
        datum_str = datum_qdate.toString("yyyy-MM-dd")

        if self.proveri_postojecu_nivelaciju():
            broj_nivelacije = self.dohvati_broj_nivelacije_za_datum(GODINA, SIFOBJEKTA, datum_str)
            if broj_nivelacije:
                self.prikazi_stavke_nivelacije(broj_nivelacije, SIFOBJEKTA)
            QMessageBox.information(None, "Informacija", "Nivelacija za izabrani datum već postoji i prikazane su njene stavke.")
            return True
        return False


    def pokreni_nivelaciju(self):
        if self.proveri_i_prikazi_nivelaciju():
            return

        if not self.postoji_popust_za_datum():
            QMessageBox.information(None, "Informacija", "Za izabrani datum nema prodaje sa popustom. Nivelacija neće biti kreirana.")
            return

        try:
            broj = self.generisi_broj_dokumenta()
        except Exception as e:
            QMessageBox.critical(None, "Greška", f"Nije moguće generisati broj dokumenta:\n{e}")
            return

        datum_qdate = self.datumEdit.date()
        self.kreiraj_zaglavlje_nivelacije(datum_qdate, broj)

        datum_str = datum_qdate.toString("yyyy-MM-dd")
        try:
            stavke = self.dohvati_agregirane_stavke_nivelacije(datum_str, SIFOBJEKTA)
        except Exception as e:
            QMessageBox.critical(None, "Greška", f"Greška prilikom dohvata stavki za nivelaciju:\n{e}")
            return

        if not stavke:
            QMessageBox.information(None, "Informacija", "Nema stavki koje ispunjavaju uslove za nivelaciju.")
            return

        korisnik = os.getenv("APP_USER") or "auto_nivelacija"

        broj_uspesnih = 0
        for stavka in stavke:
            try:
                self.dodaj_stavku_nivelacije(
                    broj_dokumenta=broj,
                    datum_qdate=datum_qdate,
                    sifobj=SIFOBJEKTA,
                    korisnik=korisnik,
                    stavka=stavka
                )
                broj_uspesnih += 1
            except Exception as e:
                print(f"Greška za šifru {stavka['sifra']}: {e}")

        self.azuriraj_vrednost_nivelacije(broj, SIFOBJEKTA)
        self.prikazi_stavke_nivelacije(broj, SIFOBJEKTA)
        QMessageBox.information(
            None,
            "Uspeh",
            f"Nivelacija za datum {datum_qdate.toString('yyyy-MM-dd')} je uspešno kreirana.\nDodato stavki: {broj_uspesnih}"
        )

    
    def prikazi_stavke_nivelacije(self, broj_nivelacije, sifobj):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cur = conn.cursor()

            # Dohvati sve stavke za dokument
            cur.execute("""
                SELECT 
                    ka.id,            -- 0 (skriveno)
                    ka.sifra,         -- 1
                    a.naziv,          -- 2
                    ka.kolicina,      -- 3
                    ka.staracena,     -- 4
                    ka.cena,          -- 5
                    ka.cena - ka.staracena AS razlika, -- 6
                    ROUND(((ka.cena - ka.staracena) / NULLIF(ka.staracena, 0))::numeric * 100, 2) AS procenat, -- 7
                    ka.broj           -- 8 (skriveno)
                FROM kasa.karticaart ka
                JOIN kasa.artikli a ON a.sifra = ka.sifra
                WHERE ka.god = %s AND ka.sifobj = %s AND ka.vrsta = 4 AND ka.broj = %s
                ORDER BY ka.id
            """, (GODINA, sifobj, broj_nivelacije))

            rezultati = cur.fetchall()
            self.tableStavke.setRowCount(len(rezultati))
            self.tableStavke.setColumnCount(9)

            for red, stavka in enumerate(rezultati):
                for kolona, vrednost in enumerate(stavka):
                    item = QTableWidgetItem(str(vrednost))
                    if kolona in [0, 8]:
                        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                    self.tableStavke.setItem(red, kolona, item)

            # Podesi širine kolona i sakrij one koje ne treba prikazivati
            self.tableStavke.setColumnWidth(0, 60)
            self.tableStavke.setColumnWidth(1, 70)
            self.tableStavke.setColumnWidth(2, 220)
            self.tableStavke.setColumnWidth(3, 80)
            self.tableStavke.setColumnWidth(4, 90)
            self.tableStavke.setColumnWidth(5, 90)
            self.tableStavke.setColumnWidth(6, 90)
            self.tableStavke.setColumnWidth(7, 70)

            self.tableStavke.setColumnHidden(0, True)  # ID stavke
            self.tableStavke.setColumnHidden(8, True)  # broj nivelacije

            cur.close()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Greška prilikom prikaza stavki:\n{e}")


