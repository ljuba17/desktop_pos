import os
import psycopg2
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QTableWidgetItem, QPushButton, QMessageBox
from PyQt6.QtGui import QColor, QBrush
from PyQt6 import uic
import configparser
from functools import partial
import json
from datetime import datetime

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

class NeobradjeniDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "neobradjeni.ui")
        uic.loadUi(ui_path, self)

        # Proširujemo kolonu "kreirano"
        # Postavljanje širine kolona u tableHDR
        self.tableHDR.setColumnWidth(0, 100)  # Prva kolona širine 100
        self.tableHDR.setColumnWidth(1, 100)  # Druga kolona širine 100
        self.tableHDR.setColumnWidth(2, 250)  # Treća kolona širine 250 (vreme transakcije)
        self.tableHDR.setColumnWidth(3, 100)  # Četvrta kolona širine 100
        self.tableHDR.setColumnWidth(4, 100)  # Peta kolona širine 100
        self.tableHDR.setColumnWidth(5, 100)  # Šesta kolona širine 100 (dugme Obriši)

        # Postavljanje širine kolona u stavkeTable
        self.stavkeTable.setColumnWidth(0, 100)  # Prva kolona širine 100
        self.stavkeTable.setColumnWidth(1, 350)  # Druga kolona širine 370 (Naziv)
        self.stavkeTable.setColumnWidth(2, 100)  # Treća kolona širine 100
        self.stavkeTable.setColumnWidth(3, 100)  # Četvrta kolona širine 100
        self.stavkeTable.setColumnWidth(4, 100)  # Peta kolona širine 100
        

        # Učitavanje neobrađenih računa u tableHDR
        self.ucitaj_neobradjene_racune()
        # Učitavanje stavki racuna u tabelu stavkeTable
        self.tableHDR.itemSelectionChanged.connect(self.prikazi_stavke_racuna)


    def ucitaj_neobradjene_racune(self):
        """Dohvata sve račune bez broja računa PU ili vremena transakcije i prikazuje ih u tableHDR."""
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # Dohvatamo neobrađene račune i njihove parametre iz confkasa
            cursor.execute("""
                SELECT ks.broj, ks.kasa, ks.kreirano, ks.ukiznos, ks.tiptransakcije, 
                    ks.vrgotovina, ks.vrkartica, ks.vrfaktura, ks.vrcek, ks.tipracuna, 
                    ks.kodkupca, ks.oznakakupca, ck.ipstampe, ck.lservis
                FROM "kasa"."kasasum" ks
                JOIN "kasa"."confkasa" ck ON ks.kasa = ck.kasa AND ks.sifobj = ck.sifobj
                WHERE (ks.brracpu IS NULL OR ks.vremetransakcije IS NULL)
                AND ks.god = %s AND ks.sifobj = %s
                ORDER BY ks.kreirano DESC
            """, (GODINA, SIFOBJEKTA))

            racuni = cursor.fetchall()
            self.tableHDR.setRowCount(len(racuni))
            self.tableHDR.setColumnCount(7 + 9)  # Dodajemo još 9 skrivenih kolona

            for row_idx, (broj, kasa, kreirano, ukiznos, tiptransakcije, vrgotovina, vrkartica, vrfaktura, vrcek, 
                        tipracuna, kodkupca, oznakakupca, ipstampe, lservis) in enumerate(racuni):
                self.tableHDR.setItem(row_idx, 0, QTableWidgetItem(str(broj)))
                self.tableHDR.setItem(row_idx, 1, QTableWidgetItem(str(kasa)))
                self.tableHDR.setItem(row_idx, 2, QTableWidgetItem(str(kreirano)))
                self.tableHDR.setItem(row_idx, 3, QTableWidgetItem(str(ukiznos)))

                # Postavljamo skrivene kolone
                hidden_data = [tiptransakcije, vrgotovina, vrkartica, vrfaktura, vrcek, tipracuna, kodkupca, oznakakupca, ipstampe, lservis]
                for col_offset, data in enumerate(hidden_data, start=6):
                    hidden_item = QTableWidgetItem(str(data))
                    hidden_item.setFlags(hidden_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Onemogućavamo menjanje
                    self.tableHDR.setItem(row_idx, col_offset, hidden_item)
                    self.tableHDR.setColumnHidden(col_offset, True)  # Sakrivamo kolonu

                # Dugme "Ponovi račun" - dodaje se SAMO ako tipracuna == 0 i tiptransakcije == 0
                if int(tipracuna) == 0 and int(tiptransakcije) == 0:
                    btn_ponovi = QPushButton("Ponovi račun")
                    btn_ponovi.setStyleSheet("""
                        QPushButton {
                            background-color: lightblue;
                            color: black;
                            border: 2px solid gray;
                            border-radius: 5px;
                            padding: 5px;
                            font-weight: bold;
                        }
                        QPushButton:hover {
                            background-color: #87cefa;
                        }
                        QPushButton:pressed {
                            background-color: #4682b4;
                        }
                    """)
                    btn_ponovi.clicked.connect(lambda _, r=row_idx: self.stampaj_neobradjeniPP(
                        self.ucitaj_tableHDR(r), self.ucitaj_stavkeTable(r)))
                    self.tableHDR.setCellWidget(row_idx, 4, btn_ponovi)
                else:
                    self.tableHDR.setCellWidget(row_idx, 4, None)  # Uklanjamo dugme!

                # Dugme "Obriši račun"
                btn_obrisi = QPushButton("Obriši")
                btn_obrisi.setStyleSheet("""
                    QPushButton {
                        background-color: orange;
                        color: black;
                        border: 2px solid gray;
                        border-radius: 5px;
                        padding: 5px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: darkorange;
                    }
                    QPushButton:pressed {
                        background-color: #cc0000;
                    }
                """)
                btn_obrisi.clicked.connect(self.obrisi_racun)
                self.tableHDR.setCellWidget(row_idx, 5, btn_obrisi)

                # Stilizacija reda ako je tipracuna ≠ 0 ili tiptransakcije ≠ 0
                if int(tipracuna) != 0 or int(tiptransakcije) != 0:
                    for col in range(self.tableHDR.columnCount()):
                        item = self.tableHDR.item(row_idx, col)
                        if item:
                            item.setForeground(QBrush(QColor("red")))  # Crveni font
                            item.setBackground(QBrush(QColor("lightgray")))  # Crna pozadina

            conn.close()
            #row_data = [self.tableHDR.item(row_idx, col).text() if self.tableHDR.item(row_idx, col) else "N/A" for col in range(self.tableHDR.columnCount())]
            #print(f"Red {row_idx}: {row_data}")

        except Exception as e:
            print(f"Greška pri učitavanju računa: {e}")

    def prikazi_stavke_racuna(self):
        #print("🔍 Pozvana funkcija prikazi_stavke_racuna")

        selected_row = self.tableHDR.currentRow()
        if selected_row == -1:
            #print("⚠️ Nema selektovanog reda!")
            return

        broj_racuna_item = self.tableHDR.item(selected_row, 0)
        if broj_racuna_item is None:
            #print(f"⚠️ Red {selected_row} nema podatak u koloni 0.")
            return

        broj_racuna = broj_racuna_item.text().strip()
        if not broj_racuna:
            #print(f"⚠️ Broj računa u redu {selected_row} je prazan!")
            return

        #print(f"✅ Učitavam stavke za račun: {broj_racuna}")

        god_racuna = GODINA
        sifobj_racuna = SIFOBJEKTA

        #print(f"📌 Parametri upita: sifobj_racuna={sifobj_racuna}, god_racuna={god_racuna}, broj_racuna={broj_racuna}")

        conn = None
        try:
            #print("🔗 Povezivanje na bazu podataka...")
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            #print("🔍 Izvršavam SQL upit za stavke računa...")
            query = """
                SELECT 
                    k.sifra, 
                    CONCAT(a.naziv, ' / ', jm.jm) AS naziv,
                    k.kolic, 
                    k.cena, 
                    (k.kolic * k.cena) AS vrednost,
                    COALESCE(k.popsum, 0) AS popustdin,
                    p.slovo AS slovo_poreza
                FROM kasa.kasa k
                LEFT JOIN kasa.artikli a ON a.sifra = k.sifra
                LEFT JOIN kasa.jedmere jm ON a.jedinica_mere_id = jm.id
                LEFT JOIN kasa.porezi p ON a.porez_id = p.id
                WHERE k.sifobj = %s AND k.god = %s AND k.broj = %s
            """
            cursor.execute(query, (sifobj_racuna, god_racuna, broj_racuna))

            rows = cursor.fetchall()
            #print(f"✅ Učitano {len(rows)} stavki iz baze.")

            self.stavkeTable.setRowCount(0)
            hidden_columns = {"popustdin": 5, "slovo_poreza": 6}
            
            for row_idx, row in enumerate(rows):
                #print(f"📝 Obrada reda {row_idx}: {row}")
                self.stavkeTable.insertRow(row_idx)
                for col_idx, value in enumerate(row[:5]):
                    self.stavkeTable.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
                
                # Dodavanje skrivenih podataka
                popustdin = row[5] if row[5] else 0
                slovo_poreza = row[6] if row[6] else ""
                hidden_values = [popustdin, slovo_poreza]

                for key, col_idx in hidden_columns.items():
                    self.stavkeTable.setItem(row_idx, col_idx, QTableWidgetItem(str(hidden_values[col_idx - 5])))
                    self.stavkeTable.setColumnHidden(col_idx, True)

            cursor.close()

        except Exception as e:
            print(f"❌ Greška pri dohvaćanju stavki računa: {e}")
        
        finally:
            if conn:
                conn.close()
                #print("🔌 Konekcija zatvorena.")

    def pripremi_stavke(self):
        row_count = self.stavkeTable.rowCount()
        stavke_lista = []

        for row_idx in range(row_count):
            sifra_item = self.stavkeTable.item(row_idx, 0)
            naziv_item = self.stavkeTable.item(row_idx, 1)
            kolicina_item = self.stavkeTable.item(row_idx, 2)
            cena_item = self.stavkeTable.item(row_idx, 3)
            vrednost_item = self.stavkeTable.item(row_idx, 4)
            popustdin_item = self.stavkeTable.item(row_idx, 5)
            slovo_poreza_item = self.stavkeTable.item(row_idx, 6)

            sifra = sifra_item.text().strip() if sifra_item else ""
            naziv = naziv_item.text().strip() if naziv_item else ""
            kolicina = float(kolicina_item.text().replace(",", ".")) if kolicina_item else 0
            cena = float(cena_item.text().replace(",", ".")) if cena_item else 0
            vrednost = float(vrednost_item.text().replace(",", ".")) if vrednost_item else 0
            popustdin = float(popustdin_item.text().replace(",", ".")) if popustdin_item else 0
            slovo_poreza = slovo_poreza_item.text().strip() if slovo_poreza_item else ""

            stavka = {
                "sifra": sifra,
                "naziv": naziv,
                "kolicina": kolicina,
                "cena": cena,
                "vrednost": vrednost,
                "popustdin": popustdin,
                "slovo_poreza": slovo_poreza
            }

            stavke_lista.append(stavka)

        return stavke_lista

    def pripremi_placanja(self, row_idx):
        """
        Priprema podataka o plaćanju za JSON iz selektovanog reda tableHDR.
        
        :param row_idx: Indeks reda iz kojeg se uzimaju podaci o plaćanju.
        :return: Lista sa podacima o plaćanju.
        """
        placanja = []

        # Indeksi skrivenih kolona u tableHDR
        COL_GOTOVINA = 7
        COL_KARTICA = 8
        COL_FAKTURA = 9
        COL_CEK = 10

        # Preuzimanje podataka iz tabele
        gotovina = float(self.tableHDR.item(row_idx, COL_GOTOVINA).text() or 0)
        kartica = float(self.tableHDR.item(row_idx, COL_KARTICA).text() or 0)
        faktura = float(self.tableHDR.item(row_idx, COL_FAKTURA).text() or 0)
        cek = float(self.tableHDR.item(row_idx, COL_CEK).text() or 0)

        # Dodavanje samo onih plaćanja koja postoje
        if gotovina > 0:
            placanja.append({"paymentType": "1", "amount": f"{gotovina:.2f}"})
        if kartica > 0:
            placanja.append({"paymentType": "2", "amount": f"{kartica:.2f}"})
        if faktura > 0:
            placanja.append({"paymentType": "4", "amount": f"{faktura:.2f}"})  # Pretpostavljam da je "račun" isto što i faktura
        if cek > 0:
            placanja.append({"paymentType": "3", "amount": f"{cek:.2f}"})

        return placanja

    def ucitaj_tableHDR(self, row):
        """Učitava podatke iz tableHDR za dati red."""
        tableHDR = []
        for col in range(self.tableHDR.columnCount()):
            item = self.tableHDR.item(row, col)
            tableHDR.append(item.text() if item else "")
        return tableHDR

    def ucitaj_stavkeTable(self, row):
        """Učitava sve stavke iz stavkeTable bez provere broja računa."""
        stavkeTable = []
        for r in range(self.stavkeTable.rowCount()):
            stavka = []
            for c in range(self.stavkeTable.columnCount()):
                item = self.stavkeTable.item(r, c)
                stavka.append(item.text() if item else "")
            stavkeTable.append(stavka)

        #print("Učitane stavke:", stavkeTable)  # Provera učitanih stavki
        return stavkeTable


    def stampaj_neobradjeniPP(self, tableHDR, stavkeTable):
        fiskalni_json = {
            "cashier": "Kasir 1",
            "invoiceNumber": "1161/1.0.128.0",
            "invoiceType": tableHDR[11],
            "transactionType": tableHDR[6],
            "items": [],
            "payment": [],
            "journalOptions": {
                "print": "true",
                "message": "HVALA NA POVERENJU"
            }
        }
        
        #print("🔍 Sadržaj stavkeTable:", stavkeTable)
        lservis = tableHDR[15].strip().lower() == "true"
        ukupni_popust = 0
        
        for stavka in stavkeTable:
            #print(f"➡ Obrada stavke: {stavka}")
            if len(stavka) < 7:
                print("❌ Greška: Stavka nema dovoljno polja!", stavka)
                continue
            try:
                popust = float(stavka[5]) if stavka[5] else 0
                ukupni_popust += popust
                #print(f"✔ Popust u stavci: {popust}, ukupno do sada: {ukupni_popust}")
                
                # Konverzija oznake poreza
                porez_slovo = "A" if lservis else LATIN_TO_CYRILLIC_MAP.get(stavka[6], stavka[6])
                
                fiskalni_json["items"].append({
                    "name": stavka[1],
                    "quantity": float(stavka[2]),
                    "unitPrice": float(stavka[3]),
                    "totalAmount": float(stavka[4]),
                    "labels": [porez_slovo]
                })
            except Exception as e:
                print("❌ Greška prilikom dodavanja stavke:", e)
        
        #print(f"🔍 Ukupni popust pre ažuriranja poruke: {ukupni_popust}")
        if ukupni_popust > 0:
            fiskalni_json["journalOptions"]["message"] = f"Ovom kupovinom ostvarili ste popust od: {ukupni_popust:.2f} dinara. HVALA NA POVERENJU"
        
        # Plaćanja
        for i, tip_placanja in enumerate(["1", "2", "3", "4"], start=6):
            if float(tableHDR[i]) > 0:
                fiskalni_json["payment"].append({"paymentType": tip_placanja, "amount": float(tableHDR[i])})
        
        # Dodavanje kupca
        if tableHDR[12] and tableHDR[13] and tableHDR[12] != "None" and tableHDR[13] != "None":
            fiskalni_json = {"buyerId": f"{tableHDR[12]}:{tableHDR[13]}", **fiskalni_json}
        
        #print("📄 Generisan JSON:")
        #print(json.dumps(fiskalni_json, indent=4, ensure_ascii=False))
        
        # Čuvanje JSON fajla
        try:
            ip_stampe = tableHDR[14]
            broj_racuna = tableHDR[0]
            godina = str(datetime.now().year)[-2:]
            direktorijum = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\to-sdc"
            json_fajl = os.path.join(direktorijum, f"CreateInvoice-{broj_racuna}-{godina}.json")
            os.makedirs(direktorijum, exist_ok=True)
            
            with open(json_fajl, "w", encoding="utf-8") as f:
                json.dump(fiskalni_json, f, indent=4, ensure_ascii=False)
            
            #print(f"💾 Fiskalni račun sačuvan u: {json_fajl}")
            # Poziv funkcije za obradu odgovora PU
            status, odgovor_fajl = self.main_window.obradi_odgovor(broj_racuna, ip_stampe)

            if status == "success":
                #print(f"✅ Račun uspešno fiskalizovan. Odgovor: {odgovor_fajl}")
                # Ako je odgovor uspešan, ažuriraj podatke u bazi
                self.main_window.azuriraj_kasasum(broj_racuna, ip_stampe)
            elif status == "error":
                print(f"❌ Greška pri fiskalizaciji. Detalji u: {odgovor_fajl}")
            elif status == "timeout":
                print("⏳ Fiskalizacija nije uspela - nema odgovora u zadatom vremenu.")
            # Osvezi dijalog
            self.ucitaj_neobradjene_racune()
        except Exception as e:
            print(f"❌ Greška prilikom čuvanja JSON fajla: {e}")

    def obrisi_racun(self):
        """Briše račun i sve njegove stavke iz baze podataka."""
        try:
            selected_row = self.tableHDR.currentRow()
            if selected_row == -1:
                QMessageBox.warning(self, "Upozorenje", "Morate odabrati račun za brisanje.")
                return

            broj_racuna = self.tableHDR.item(selected_row, 0).text()

            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # Potvrda brisanja
            reply = QMessageBox.question(self, "Brisanje računa",
                                        f"Da li ste sigurni da želite da obrišete račun broj {broj_racuna}?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                cursor.close()
                conn.close()
                return

            # Brisanje stavki iz kasa1
            cursor.execute("""
                DELETE FROM "kasa"."kasa1"
                WHERE god = %s AND sifobj = %s AND broj = %s
            """, (GODINA, SIFOBJEKTA, broj_racuna))
            #print("Obrisano iz kasa1:", cursor.rowcount)

            # Brisanje stavki iz kasa
            cursor.execute("""
                DELETE FROM "kasa"."kasa"
                WHERE god = %s AND sifobj = %s AND broj = %s
            """, (GODINA, SIFOBJEKTA, broj_racuna))
            #print("Obrisano iz kasa:", cursor.rowcount)

            # Brisanje stavki iz karticaart
            cursor.execute("""
                DELETE FROM "kasa"."karticaart"
                WHERE god = %s AND sifobj = %s AND (vrsta = 8 OR vrsta = 9) AND broj = %s 
            """, (GODINA, SIFOBJEKTA, broj_racuna))
            #print("Obrisano iz karticaart:", cursor.rowcount)

            # Brisanje zaglavlja računa iz kasasum (dodao god i sifobj)
            cursor.execute("""
                DELETE FROM "kasa"."kasasum"
                WHERE god = %s AND sifobj = %s AND broj = %s
            """, (GODINA, SIFOBJEKTA, broj_racuna))
            #print("Obrisano iz kasasum:", cursor.rowcount)

            conn.commit()
            cursor.close()
            conn.close()

            # Uklanjanje reda iz tabele
            self.tableHDR.removeRow(selected_row)

            # Osveži dijalog
            self.ucitaj_neobradjene_racune()
            self.prikazi_stavke_racuna()

            QMessageBox.information(self, "Obaveštenje", "Račun uspešno obrisan.")
        except Exception as e:
            QMessageBox.critical(self, "Greška", f"Došlo je do greške prilikom brisanja računa: {e}")
