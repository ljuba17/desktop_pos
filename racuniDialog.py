from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
import os
import webbrowser  # Za otvaranje slike u podrazumevanoj aplikaciji
from datetime import datetime
import json
import psycopg2

class Ui_racuniDialog(object):
    def setupUi(self, racuniDialog):
        racuniDialog.setObjectName("racuniDialog")
        racuniDialog.resize(951, 536)
        racuniDialog.setStyleSheet("background-color: #e3e7f1;")
        self.svirnTab = QtWidgets.QTabWidget(parent=racuniDialog)
        self.svirnTab.setGeometry(QtCore.QRect(0, 0, 941, 531))
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.svirnTab.setFont(font)
        self.svirnTab.setObjectName("svirnTab")
        self.fiskalniTab = QtWidgets.QWidget()
        self.fiskalniTab.setObjectName("fiskalniTab")
        self.label = QtWidgets.QLabel(parent=self.fiskalniTab)
        self.label.setGeometry(QtCore.QRect(20, 10, 61, 21))
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setObjectName("label")
        self.pretrazifrEdit = QtWidgets.QLineEdit(parent=self.fiskalniTab)
        self.pretrazifrEdit.setGeometry(QtCore.QRect(90, 10, 291, 21))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.pretrazifrEdit.setFont(font)
        self.pretrazifrEdit.setObjectName("pretrazifrEdit")
        self.hdrTable = QtWidgets.QTableWidget(parent=self.fiskalniTab)
        self.hdrTable.setGeometry(QtCore.QRect(10, 40, 921, 192))
        self.hdrTable.setObjectName("hdrTable")
        self.hdrTable.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: #a2c4e0; }")
        self.hdrTable.setColumnCount(9)  # Dodajemo skrivenu kolonu za broj
        self.hdrTable.setRowCount(0)
        self.hdrTable.setHorizontalHeaderLabels([
            "Broj računa PU", "Vreme štampe računa", "Vrednost", 
            "Slika računa", "Akcije", "Broj (skriveno)", "Izaberi", "Tip transakcije (skriveno)", "Kopiraj"
        ])
        self.hdrTable.setColumnHidden(5, True)  # Sakrivamo kolonu `broj`
        self.hdrTable.setColumnHidden(7, True)  # Skrivena kolona `tip transakcije`

        self.hdrTable.horizontalHeader().setDefaultSectionSize(153)
        self.stavkeTable = QtWidgets.QTableWidget(parent=self.fiskalniTab)
        self.stavkeTable.setGeometry(QtCore.QRect(10, 240, 921, 261))
        self.stavkeTable.setObjectName("stavkeTable")
        self.stavkeTable.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: #a2c4e0; }")
        self.stavkeTable.setColumnCount(5)
        self.stavkeTable.setRowCount(0)
        self.stavkeTable.setHorizontalHeaderLabels(["Šifra", "Naziv", "Kolicina","Cena", "Vrednost"])
        self.stavkeTable.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Interactive)  # Šifra
        self.stavkeTable.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)      # Naziv
        self.stavkeTable.horizontalHeader().setStretchLastSection(False)
        self.svirnTab.addTab(self.fiskalniTab, "Fiskalni računi")
        #self.refundiraniTab = QtWidgets.QWidget()
        #self.refundiraniTab.setObjectName("refundiraniTab")
        #self.svirnTab.addTab(self.refundiraniTab, "Refundirani računi")

        self.retranslateUi(racuniDialog)
        self.svirnTab.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(racuniDialog)

    def retranslateUi(self, racuniDialog):
        _translate = QtCore.QCoreApplication.translate
        racuniDialog.setWindowTitle(_translate("racuniDialog", "Dialog"))
        self.label.setText(_translate("racuniDialog", "Pretraži"))
        self.pretrazifrEdit.setPlaceholderText(
            _translate("racuniDialog", "pretraga po delu fiskalnog računa (PFR broj)")
        )


LATIN_TO_CYRILLIC_MAP = {
        "A": "А", #"\u0410",  # А - Nije u PDV
        "G": "Г", #"\u0413",  # Г - Bez PDV
        "Đ": "Ђ", #"\u0402",  # Ђ - Opšta stopa (20%)
        "E": "Е" #"\u0415",  # Е - Posebna stopa (10%)
    }
class RacuniDialog(QtWidgets.QDialog, Ui_racuniDialog):
    # Signal za prenos podataka (broj računa PU, vreme transakcije)
    signal_prenesi_podatke = pyqtSignal(str, str)
    
    def __init__(self, kasasum, kasa, artikli, ip_stampe, lservis, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # ✅ Dodajemo potrebne podatke
        self.kasasum = kasasum  # Model za zaglavlja računa
        self.kasa = kasa        # Model za stavke računa
        self.artikli = artikli  # ✅ Dodato - sada imamo artikle!
        self.ip_stampe = ip_stampe  # IP adresa štampača
        self.lservis = lservis  # 📌 Da li je servisni mod
        
        # ✅ Povezivanje funkcionalnosti
        self.populate_hdr_table()  # Popunjavanje tabele sa računima
        self.pretrazifrEdit.textChanged.connect(self.filter_hdr_table)  # Filtriranje tabele
        self.hdrTable.cellClicked.connect(self.handle_hdr_table_click)  # Klik na tabelu
        self.hdrTable.cellClicked.connect(self.oznaci_red)
        # Dodajemo polja za prenos podataka nazad u glavni prozor
        self.selected_brracpu = None
        self.selected_vreme_stampe = None        
        
    def izaberi_racun(self, row):
        """
        Prenosi odabrane podatke u glavni prozor i zatvara dijalog.
        """
        try:
            # Dohvatanje podataka iz selektovanog reda
            broj_racuna_pu = self.hdrTable.item(row, 0).text()
            vreme_transakcije = self.hdrTable.item(row, 1).text()

            # Emitovanje signala za prenos podataka
            self.signal_prenesi_podatke.emit(broj_racuna_pu, vreme_transakcije)

            # Zatvaranje dijaloga
            self.accept()

        except Exception as e:
            print(f"❌ Greška u izaberi_racun: {e}")
        
    def handle_btn_izaberi(self, row):
        """
        Rukuje klikom na dugme 'Izaberi'.
        """
        try:
            # Dohvatamo vrednosti iz tabele
            self.selected_brracpu = self.hdrTable.item(row, 0).text()  # Broj računa PU
            self.selected_vreme_stampe = self.hdrTable.item(row, 1).text()  # Vreme transakcije
            
            # Debug poruke
            print(f"✔️ Izabran račun: {self.selected_brracpu}, Vreme: {self.selected_vreme_stampe}")
            
            # Zatvaramo dijalog
            self.accept()
        except Exception as e:
            print(f"❌ Greška u handle_btn_izaberi: {e}")

    def populate_hdr_table(self):
        """
        ✅ Popunjava hdrTable podacima iz modela kasasum, a refundirane račune ističe vizuelno.
        """
        self.hdrTable.setColumnCount(9)  # 📌 Dodajemo kolonu za tip transakcije
        self.hdrTable.setHorizontalHeaderLabels([
            "Broj računa PU", "Vreme štampe računa", "Vrednost",
            "Slika računa", "Akcije", "Broj (skriveno)", "Izaberi", "Tip transakcije (skriveno)", "Kopiraj"
        ])
        self.hdrTable.setColumnHidden(5, True)  # 📌 Skrivena kolona `broj`
        self.hdrTable.setColumnHidden(7, True)  # 📌 Skrivena kolona `tip transakcije`

        self.hdrTable.setRowCount(len(self.kasasum))

        for row, record in enumerate(self.kasasum):
            tip_transakcije = int(record.get("tiptransakcije", 0))  # 📌 Sigurnosno pretvaramo u `int`
            refundacija = (tip_transakcije == 1)

            # 📌 **Stilizacija redova**
            red_boja = QtGui.QColor(230, 230, 230) if refundacija else QtGui.QColor(255, 255, 255)  # Siva za refundaciju
            tekst_boja = QtGui.QColor(199, 16, 50) if refundacija else QtGui.QColor(0, 0, 0)  # Crvena za refundaciju

            # 📌 **Dodavanje podataka u tabelu sa bojama**
            for col, key in enumerate(["brracpu", "vreme_stampe", "vrednost"]):
                vrednost = str(record.get(key, ""))
                if key == "vrednost":
                    vrednost = f"{record.get('vrednost', 0):.2f}"

                item = QtWidgets.QTableWidgetItem(vrednost)
                item.setForeground(QtGui.QBrush(tekst_boja))  # 🔴 **Boja teksta**
                item.setBackground(QtGui.QBrush(red_boja))  # 🔳 **Boja pozadine**
                self.hdrTable.setItem(row, col, item)

            # 📌 **Kolona 3: Dugme "Prikaži sliku"**
            btn_prikazi_sliku = QtWidgets.QPushButton("Prikaži sliku")
            btn_prikazi_sliku.setStyleSheet("""
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
            btn_prikazi_sliku.clicked.connect(lambda _, r=row: self.oznaci_red(r))
            btn_prikazi_sliku.clicked.connect(lambda _, r=row: self.prikazi_sliku(r))
            self.hdrTable.setCellWidget(row, 3, btn_prikazi_sliku)

            # 📌 **Kolona 4: Dugme "Prikaži stavke"**
            btn_prikazi_stavke = QtWidgets.QPushButton("Prikaži stavke")
            btn_prikazi_stavke.setStyleSheet("""
                QPushButton {
                    background-color: lightgreen;
                    color: black;
                    border: 2px solid gray;
                    border-radius: 5px;
                    padding: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #90ee90;
                }
                QPushButton:pressed {
                    background-color: #32cd32;
                }
            """)
            btn_prikazi_stavke.clicked.connect(lambda _, r=row: self.oznaci_red(r))
            btn_prikazi_stavke.clicked.connect(lambda _, r=row: self.populate_stavke_table(r))
            self.hdrTable.setCellWidget(row, 4, btn_prikazi_stavke)

            # 📌 **Kolona 5 (skrivena): Interni broj računa**
            hidden_broj = QtWidgets.QTableWidgetItem(str(record["broj"]))
            hidden_broj.setForeground(QtGui.QBrush(tekst_boja))  
            hidden_broj.setBackground(QtGui.QBrush(red_boja))  
            self.hdrTable.setItem(row, 5, hidden_broj)

            # 📌 **Kolona 6: Dugme "Izaberi" (samo za fiskalne račune)**
            if not refundacija:
                btn_izaberi = QtWidgets.QPushButton("Izaberi")
                btn_izaberi.setStyleSheet("""
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
                        background-color: #ff8c00;
                    }
                """)
                btn_izaberi.clicked.connect(lambda _, r=row: self.oznaci_red(r))
                btn_izaberi.clicked.connect(lambda _, r=row: self.izaberi_racun(r))
                self.hdrTable.setCellWidget(row, 6, btn_izaberi)
            else:
                self.hdrTable.setItem(row, 6, QtWidgets.QTableWidgetItem(""))

            # 📌 **Kolona 7 (skrivena): Tip transakcije**
            hidden_tip = QtWidgets.QTableWidgetItem(str(tip_transakcije))
            self.hdrTable.setItem(row, 7, hidden_tip)
            
            # 📌 **Kolona 8: Dugme "Kopiraj" **
            btn_kopiraj = QtWidgets.QPushButton("Kopiraj")
            btn_kopiraj.setStyleSheet("""
                QPushButton {
                    background-color: yellow;
                    color: black;
                    border: 2px solid gray;
                    border-radius: 5px;
                    padding: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: lightyellow;
                }
                QPushButton:pressed {
                    background-color: lightyellow;
                }
            """)
            btn_kopiraj.clicked.connect(lambda _, r=row: self.oznaci_red(r))
            btn_kopiraj.clicked.connect(lambda _, r=row: self.stampaj_kopiju(r))
            self.hdrTable.setCellWidget(row, 8, btn_kopiraj)

        # 📌 **Podešavanje širine kolona**
        self.hdrTable.setColumnWidth(0, 210)  # Broj računa PU
        self.hdrTable.setColumnWidth(1, 155)  # Vreme transakcije
        self.hdrTable.setColumnWidth(2, 110)  # Vrednost
        self.hdrTable.setColumnWidth(3, 95)  # Prikaži sliku
        self.hdrTable.setColumnWidth(4, 99)  # Prikaži stavke
        self.hdrTable.setColumnWidth(6, 92)  # Izaberi
        self.hdrTable.setColumnWidth(8, 92)  # Kopiraj
        
    def oznaci_red(self, red):
        """
        Obeležava izabrani red u hdrTable tako što menja njegov stil.
        """
        # Resetujemo sve redove na podrazumevani stil
        for r in range(self.hdrTable.rowCount()):
            for c in range(self.hdrTable.columnCount()):
                item = self.hdrTable.item(r, c)
                if item:
                    font = item.font()
                    font.setBold(False)
                    font.setPointSize(9)
                    item.setFont(font)

        # Stilizujemo samo izabrani red
        for c in range(self.hdrTable.columnCount()):
            item = self.hdrTable.item(red, c)
            if item:
                font = item.font()
                font.setBold(True)
                font.setPointSize(10)  # Veći font za istaknuti red
                item.setFont(font)

    def filter_hdr_table(self):
        """
        Filtrira hdrTable na osnovu unosa u pretrazifrEdit.
        """
        search_term = self.pretrazifrEdit.text().lower()
        for row in range(self.hdrTable.rowCount()):
            item = self.hdrTable.item(row, 0)  # Broj računa PU
            self.hdrTable.setRowHidden(row, search_term not in item.text().lower())

    def handle_hdr_table_click(self, row, column):
        """
        Rukuje klikom na red u hdrTable i prikazuje stavke ili otvara sliku.
        """
        try:
            if column == 3:  # Kolona za sliku računa
                # Dohvatamo broj iz skrivene kolone
                broj = self.hdrTable.item(row, 5).text()
                
                # Dobijamo poslednje dve cifre trenutne godine
                trenutna_godina = datetime.now().year
                godina = str(trenutna_godina)[-2:]  # Poslednje dve cifre godine, kao string

                # Provera IP adrese za lokalnu putanju
                if self.ip_stampe == "127.0.0.1":
                    slika_putanja = f"C:\\myLPFR\\exchange\\from-sdc\\Receipt-{broj}-{godina}.png"
                else:
                    slika_putanja = f"\\\\{self.ip_stampe}\\MyLPFR\\exchange\\from-sdc\\Receipt-{broj}-{godina}.png"

                # Provera postojanja slike
                if os.path.exists(slika_putanja):
                #    print(f"✅ Slika pronađena: {slika_putanja}")  # Debug poruka za terminal
                    webbrowser.open(slika_putanja)  # Otvaranje slike u podrazumevanoj aplikaciji
                else:
                #    print(f"❌ Slika nije pronađena na putanji: {slika_putanja}")  # Debug poruka za terminal
                    QtWidgets.QMessageBox.warning(self, "Greška", f"Slika računa nije pronađena na putanji:\n{slika_putanja}")
            else:
                # Prikaz stavki računa pri kliku na bilo koji red osim kolone slike
                #print(f"📋 Prikazujem stavke za red: {row}")
                self.populate_stavke_table(row)

        except Exception as e:
            print(f"❌ Greška u handle_hdr_table_click: {e}")  # Debug poruka za terminal

    def prikazi_sliku(self, row):
        """
        Prikazuje sliku računa u podrazumevanoj aplikaciji.
        """
        try:
            broj = self.hdrTable.item(row, 5).text()  # Dohvatamo broj iz skrivene kolone
            trenutna_godina = datetime.now().year
            godina = str(trenutna_godina)[-2:]  # Poslednje dve cifre godine, kao string
            # Provera IP adrese za lokalnu putanju
            if self.ip_stampe == "127.0.0.1":
                slika_putanja = f"C:\\myLPFR\\exchange\\from-sdc\\Receipt-{broj}-{godina}.png"
            else:
                slika_putanja = f"\\\\{self.ip_stampe}\\MyLPFR\\exchange\\from-sdc\\Receipt-{broj}-{godina}.png"

            # Debug ispis za putanju slike
            #print(f"🛠️ Debug: Proveravam putanju slike: {slika_putanja}")

            # Provera postojanja slike
            if os.path.exists(slika_putanja):
            #    print(f"✅ Slika pronađena: {slika_putanja}")  # Debug poruka za terminal
                webbrowser.open(slika_putanja)  # Otvaranje slike u podrazumevanoj aplikaciji
            else:
            #    print(f"❌ Slika nije pronađena na putanji: {slika_putanja}")  # Debug poruka za terminal
                QtWidgets.QMessageBox.warning(self, "Greška", f"Slika računa nije pronađena na putanji:\n{slika_putanja}")

        except Exception as e:
            print(f"❌ Greška u prikazi_sliku: {e}")  # Debug poruka za terminal

    def populate_stavke_table(self, row):
        """
        Popunjava stavkeTable podacima iz modela kasa za izabrani račun.
        """
        try:
            # Dohvatamo broj računa PU iz hdrTable
            brracpu = self.hdrTable.item(row, 0).text()  # Pretpostavljamo da je u koloni 0 brracpu

            # Pronalazimo zapis u kasasum koristeći brracpu
            zapis_kasasum = next((record for record in self.kasasum if record["brracpu"] == brracpu), None)
            if not zapis_kasasum:
                raise ValueError(f"❌ Nema zapisa u kasasum za brracpu: {brracpu}")

            # Preuzimamo potrebna polja iz pronađenog zapisa
            god = zapis_kasasum.get("god")
            sifobj = zapis_kasasum.get("sifobj")
            kasa = zapis_kasasum.get("kasa")
            broj = zapis_kasasum.get("broj")

            #print(f"✅ Pronađeni podaci za brracpu: god={god}, sifobj={sifobj}, kasa={kasa}, broj={broj}")

            # Filtriramo stavke iz modela kasa koristeći ove parametre
            stavke = [
                stavka for stavka in self.kasa
                if stavka["god"] == god and stavka["sifobj"] == sifobj and stavka["kasa"] == kasa and stavka["broj"] == broj
            ]

            if not stavke:
                raise ValueError(f"❌ Nema stavki za brracpu: {brracpu} sa podacima god={god}, sifobj={sifobj}, kasa={kasa}, broj={broj}")

            # Popunjavanje stavkeTable sa pronađenim stavkama
            self.stavkeTable.setRowCount(len(stavke))
            for row, stavka in enumerate(stavke):
                self.stavkeTable.setItem(row, 0, QtWidgets.QTableWidgetItem(str(stavka["sifra"])))
                self.stavkeTable.setItem(row, 1, QtWidgets.QTableWidgetItem(stavka.get("naziv", "Nepoznato")))  # Dodajemo naziv
                self.stavkeTable.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{stavka['kolic']:.3f}"))
                self.stavkeTable.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{stavka['cena']:.2f}"))
                self.stavkeTable.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{stavka['kolic'] * stavka['cena']:.2f}"))  # Vrednost

            #print(f"✅ Stavke uspešno učitane za brracpu: {brracpu}")

        except Exception as e:
            print(f"❌ Greška pri popunjavanju stavki: {e}")
            QtWidgets.QMessageBox.critical(self, "Greška", f"Greška pri popunjavanju stavki:\n{e}")
        
######################################################################################################
# Stampa kopije racuna
    def stampaj_kopiju(self, row):
        """
        Štampa kopiju računa na osnovu izabranog reda u hdrTable.
        """
        try:
            # ✅ Dohvatamo PFR broj računa i vreme transakcije iz tabele
            broj_racuna = self.hdrTable.item(row, 0).text()
            vreme_transakcije = self.hdrTable.item(row, 1).text()
            broj_skriven = self.hdrTable.item(row, 5).text()  # Interni broj računa

            #print(f"🔍 Debug: broj_skriven = {broj_skriven} (tip: {type(broj_skriven)})")

            # ✅ Pronalazimo odgovarajući zapis u kasasum
            zapis_kasasum = next((r for r in self.kasasum if str(r["broj"]) == broj_skriven), None)
            if not zapis_kasasum:
                print("❌ Greška: Nije pronađen zapis u kasasum!")
                return
            
            #print(f"✅ Pronađen zapis u kasasum: {zapis_kasasum}")

            # ✅ Dohvatamo osnovne podatke
            god = zapis_kasasum.get("god")
            sifobj = zapis_kasasum.get("sifobj")
            kasa = zapis_kasasum.get("kasa")
            broj = zapis_kasasum.get("broj")
            tip_transakcije = int(zapis_kasasum.get("tiptransakcije", 0))  # 0 = Prodaja, 1 = Refundacija
            
            #print(f"🔍 Tražimo stavke sa: god={god}, sifobj={sifobj}, kasa={kasa}, broj={broj}")

            # ✅ Pronalazimo stavke iz `kasa`
            stavke_racuna = [
                stavka for stavka in self.kasa
                if stavka["god"] == god and stavka["sifobj"] == sifobj and stavka["kasa"] == kasa and stavka["broj"] == broj
            ]
            
            if not stavke_racuna:
                print("❌ Greška pri štampi kopije: ❌ Nema stavki za kopiju računa!")
                return
            
            #print(f"✅ Pronađeno {len(stavke_racuna)} stavki za kopiju.")

            # ✅ Pripremamo bazu za preuzimanje podataka
            try:
                conn = psycopg2.connect(
                    dbname=os.getenv("DB_NAME"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT")
                )
                cursor = conn.cursor()
            except Exception as e:
                print(f"❌ Greška pri povezivanju sa bazom: {e}")
                return

            # ✅ Računamo ukupan popust
            ukupni_popust = sum(float(stavka.get("popsum", 0)) for stavka in stavke_racuna)
            #print(f"✅ Ukupan popust (izračunat): {ukupni_popust:.2f} dinara")

            # ✅ Formiramo stavke za JSON
            json_stavke = []
            for stavka in stavke_racuna:
                sifra = stavka["sifra"]
                naziv = stavka["naziv"]
                kolicina = f"{stavka['kolic']:.2f}"
                cena = f"{stavka['cena']:.2f}"
                vrednost = f"{stavka['vrednost']:.2f}"
                popust = float(stavka.get("popsum", 0))

                # ✅ Dohvatamo jedinicu mere i poresku stopu iz baze
                try:
                    cursor.execute("""
                        SELECT jm.jm, p.slovo
                        FROM "kasa"."artikli" a
                        JOIN "kasa"."jedmere" jm ON a.jedinica_mere_id = jm.id
                        JOIN "kasa"."porezi" p ON a.porez_id = p.id
                        WHERE a.sifra = %s
                    """, (sifra,))
                    rezultat = cursor.fetchone()
                    
                    jedinica_mere = rezultat[0] if rezultat else "N/A"
                    porez_slovo = rezultat[1] if rezultat else "A"  # Podrazumevano "A"
                    
                except Exception as e:
                    print(f"❌ Greška pri preuzimanju podataka za artikal {sifra}: {e}")
                    jedinica_mere = "N/A"
                    porez_slovo = "A"

                # ✅ Koristimo tačnu poresku stopu
                porez_slovo = LATIN_TO_CYRILLIC_MAP.get(porez_slovo, "\u0410") if not self.lservis else "A"

                #print(f"🛠️ Debug: Stavka '{naziv}' -> Porez: {porez_slovo}, JM: {jedinica_mere}, Popust: {popust:.2f}")

                json_stavke.append({
                    "name": f"{naziv}/{jedinica_mere}",
                    "quantity": kolicina,
                    "unitPrice": cena,
                    "totalAmount": vrednost,
                    "labels": [porez_slovo]
                })

            # ✅ Kreiramo payment čvor
            placanja = []
            for tip, iznos in [
                ("1", zapis_kasasum.get("vrgotovina", 0)),
                ("2", zapis_kasasum.get("vrkartica", 0)),
                ("3", zapis_kasasum.get("vrcek", 0)),
                ("4", zapis_kasasum.get("vrfaktura", 0)),
            ]:
                if iznos > 0:
                    placanja.append({"paymentType": tip, "amount": f"{iznos:.2f}"})

            # ✅ Formiramo poruku za žurnal
            poruka = "HVALA NA POVERENJU"
            if ukupni_popust > 0:
                poruka = f"Ovom kupovinom ostvarili ste popust od {ukupni_popust:.2f} dinara. {poruka}"

            # ✅ Formiramo JSON podataka
            json_podaci = {
                "cashier": "Kasir 1",
                "invoiceNumber": "1161/1.0.128.0",
                "invoiceType": "2",  # Kopija računa
                "transactionType": tip_transakcije,  # 0 = Prodaja, 1 = Refundacija
                "referentDocumentNumber": broj_racuna,
                "referentDocumentDT": vreme_transakcije,
                "items": json_stavke,
                "payment": placanja,
                "journalOptions": {
                    "print": "true",
                    "message": poruka
                }
            }

            # ✅ Kreiramo putanju za JSON fajl
            godina = str(datetime.now().year)[-2:]
            json_putanja = f"\\\\{self.ip_stampe}\\MyLPFR\\exchange\\to-sdc\\CreateInvoice-K-{broj_racuna}-{godina}.json"

            #print(f"🛠️ Debug: JSON fajl će biti sačuvan u: {json_putanja}")

            # ✅ Čuvamo JSON fajl
            with open(json_putanja, "w", encoding="utf-8") as f:
                json.dump(json_podaci, f, ensure_ascii=False, indent=4)

            #print(f"✅ JSON fajl uspešno kreiran: {json_putanja}")

        except Exception as e:
            print(f"❌ Greška pri štampi kopije: {e}")
            
    def posalji_na_stampu(self, json_podaci):
        """
        Šalje JSON zahtev na fiskalni štampač.
        """
        try:
            # Simulacija slanja JSON-a na fiskalni uređaj
            #print("🖨️ Štampanje kopije računa...")
            #print(json.dumps(json_podaci, indent=4, ensure_ascii=False))
            QtWidgets.QMessageBox.information(self, "Štampa", "Kopija računa je poslata na štampu.")
        except Exception as e:
            print(f"❌ Greška pri slanju na štampu: {e}")
            QtWidgets.QMessageBox.critical(self, "Greška", f"Greška pri slanju na štampu:\n{e}")

    def snimi_json_fajl(self, podaci, broj_racuna, ip_stampe):
        """
        ✅ Snima JSON fajl u direktorijum za slanje na štampu.
        """
        try:
            # 📌 1. Dobijamo poslednje dve cifre godine
            godina = str(datetime.now().year)[-2:]

            # 📌 2. Definišemo putanju do štampača
            direktorijum = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\to-sdc"

            # 📌 3. Ime fajla za kopiju
            json_fajl = os.path.join(direktorijum, f"CreateInvoice-K-{broj_racuna}-{godina}.json")

            # 📌 4. Upisivanje JSON podataka u fajl
            with open(json_fajl, "w", encoding="utf-8") as f:
                json.dump(podaci, f, ensure_ascii=False, indent=4)

            #print(f"✅ JSON fajl uspešno sačuvan: {json_fajl}")

        except Exception as e:
            print(f"❌ Greška pri snimanju JSON fajla: {e}")