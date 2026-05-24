import os
import psycopg2
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QTableWidgetItem, QPushButton, QMessageBox, QVBoxLayout
from trazi_avans import TraziAvansDialog
from PyQt6.QtGui import QFont, QColor, QBrush, QIcon
from PyQt6 import uic
from PyQt6.QtWidgets import QTreeWidgetItem
import configparser
import random
from functools import partial
import json
from datetime import datetime
from collections import defaultdict


# Učitavanje konfiguracije iz kasa.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)
GODINA = config.get('POS_Settings', 'god')
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')
KASA = config.get('POS_Settings', 'kasa')
GLAVNA_LOKACIJA_ID = None


def ucitaj_glavnu_lokaciju():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM kasa.lokacija
        WHERE sifobj = %s
          AND glavna = TRUE
          AND aktivna = TRUE
        LIMIT 1
    """, (SIFOBJEKTA,))

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        raise Exception(f"Nije pronađena glavna lokacija za objekat {SIFOBJEKTA}")

    return row[0]

LATIN_TO_CYRILLIC_MAP = {
        "A": "А", #"\u0410",  # А - Nije u PDV
        "G": "Г", #"\u0413",  # Г - Bez PDV
        "Đ": "Ђ", #"\u0402",  # Ђ - Opšta stopa (20%)
        "E": "Е" #"\u0415",  # Е - Posebna stopa (10%)
    }

class AvansDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "avans.ui")
        uic.loadUi(ui_path, self)

        self.glavna_lokacija_id = ucitaj_glavnu_lokaciju()
        print(f"✅ Avansi koriste glavnu lokaciju: {self.glavna_lokacija_id}")

        # Postavljamo da se otvara prvi page (indeks 0)
        self.stackedWidget.setCurrentIndex(0)

        # ✅ Postavljanje inicijalnog kupca PRE POZIVA stilizacije
        self.aktivan_kupac = 4

        # ✅ Postavljanje inicijalnog moda prometa
        self.aktivan_mod = "promet"

        # ✅ Inicijalizacija broja računa
        self.trenutni_broj_racuna = random.randint(int(KASA) * 1000, int(KASA) * 1999)

        # ✅ Pozivanje funkcija za otvaranje stranica
        self.prviBtn.clicked.connect(self.prebaci_na_prviRN)
        self.naredniBtn.clicked.connect(self.prebaci_na_naredniRN)
        self.refundacijaBtn.clicked.connect(self.prebaci_na_refundacijaRN)
        self.konacniBtn.clicked.connect(self.prebaci_na_konacniRN)
        self.pregledBtn.clicked.connect(self.prebaci_na_pregledRN)
        self.pregledBtn.clicked.connect(self.popuni_treewidget)

        self.konacniBtn.setHidden(True)

        # ✅ Kontrole na prviRN Page sa indeksom 0
        # ✅ Povezivanje signala za praćenje promena u poljima plaćanja na prviRN
        self.gotovinaEdit.textChanged.connect(self.proveri_placanje)
        self.karticaEdit.textChanged.connect(self.proveri_placanje)
        self.cekEdit.textChanged.connect(self.proveri_placanje)
        self.racunEdit.textChanged.connect(self.proveri_placanje)
        # ✅ Početno stanje dugmeta
        self.btnStampa.setEnabled(False)

        # ✅ Automatsko učitavanje stavki ukoliko je avansni racun nezavrsen
        self.ucitaj_stavke_iz_baze()

        # ✅ Sakrivanje kolone slovo u stavkeTable na prviRN page
        self.stavkeTable.setColumnWidth(0, 70)  # Prva kolona širine 70 -id
        self.stavkeTable.setColumnWidth(1, 90)  # kolona širine 90 - sifra
        self.stavkeTable.setColumnWidth(2, 180)  # kolona širine 180 - naziv
        self.stavkeTable.setColumnWidth(3, 90)  # kolona širine 90 - kolicina
        self.stavkeTable.setColumnWidth(4, 100)  # kolona širine 100 - cena
        self.stavkeTable.setColumnWidth(5, 100)  # kolona širine 100 - dugme obrisi
        self.stavkeTable.setColumnHidden(0, True)  # sakrivam kolonu u kojoj je id stavke
        self.stavkeTable.setColumnHidden(6, True)  # sakrivam kolonu u kojoj je slovo poreza
        
        # ✅ Stilizacija numeričkih polja
        # Page 0
        self.kolicinaEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.kolicinaEdit.setText("1")
        self.cenaEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.slovoEdit.setVisible(False)
        self.totalEdit.setAlignment(Qt.AlignmentFlag.AlignRight)   

        # ✅ Povezivanje događaja u prviRN page
        self.comboAvans.currentIndexChanged.connect(self.update_avans_edit)  # Ažuriranje avansa na osnovu izbora u comboAvans
        self.tipCombo.currentIndexChanged.connect(self.update_tip_edit)  # Ažuriranje tipEdit na osnovu izbora u tipCombo

        # ✅ Početno stanje dugmeta
        self.btnStampa.setEnabled(False)

        self.dodajBtn.clicked.connect(self.dodaj_u_kasa1)  # Povezivanje sa bazom podataka

        self.btnStampa.clicked.connect(self.izvrsi_stampu)
        # ✅ Kraj kontrola na prviRN
        # ✅ Kontrole na drugoj strani Page sa indeksom 1
        # Page naredniRN Page sa indeksom 1
        self.stavkeTable_2.setColumnWidth(0, 70)  # Prva kolona širine 70 -id
        self.stavkeTable_2.setColumnWidth(1, 90)  # kolona širine 90 - sifra
        self.stavkeTable_2.setColumnWidth(2, 180)  # kolona širine 180 - naziv
        self.stavkeTable_2.setColumnWidth(3, 90)  # kolona širine 90 - kolicina
        self.stavkeTable_2.setColumnWidth(4, 100)  # kolona širine 100 - cena
        self.stavkeTable_2.setColumnWidth(5, 100)  # kolona širine 100 - dugme obrisi
        self.stavkeTable_2.setColumnHidden(0, True)  # sakrivam kolonu u kojoj je id stavke
        self.stavkeTable_2.setColumnHidden(6, True)  # sakrivam kolonu u kojoj je slovo poreza
        # ✅ Stilizacija numeričkih polja
        self.kolicinaEdit_2.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.kolicinaEdit_2.setText("1")
        self.cenaEdit_2.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.slovoEdit_2.setVisible(False)
        self.totalEdit_2.setAlignment(Qt.AlignmentFlag.AlignRight)

        # ✅ Povezivanje događaja u naredniRN page
        self.comboAvans_2.currentIndexChanged.connect(self.update_avans_edit) # Ažuriranje avansa na osnovu izbora u comboAvans_2
        # ✅ Povezivanje signala za praćenje promena u poljima plaćanja

        # ✅ Početno stanje dugmeta
        self.gotovinaEdit_2.textChanged.connect(self.proveri_placanje)
        self.karticaEdit_2.textChanged.connect(self.proveri_placanje)
        self.cekEdit_2.textChanged.connect(self.proveri_placanje)
        self.racunEdit_2.textChanged.connect(self.proveri_placanje)
        self.totalEdit_2.textChanged.connect(self.proveri_placanje)

        self.btnStampa_2.setEnabled(False)
        # 🔹 Povezivanje dugmeta sa metodom za otvaranje TraziAvansDialog
        self.dodajBtn_2.clicked.connect(self.dodaj_u_kasa1)  # Povezivanje sa bazom podataka

        self.izaberiRnBtn.clicked.connect(self.otvori_trazi_avans)

        self.btnStampa_2.clicked.connect(self.izvrsi_stampu) 
                
        # ✅ Kraj kontrola na naredniRN
        # Page refundacijaRN Page sa indeksom 2
        
        # 🔹 Povezivanje dugmeta sa metodom za otvaranje pregledRN Page sa indeksom 4
        self.izaberiRnBtn_2.clicked.connect(self.prebaci_na_pregledRN)
        self.izaberiRnBtn_2.clicked.connect(self.popuni_treewidget)
        
        self.stavkeTable_3.setColumnWidth(0, 70)  # Prva kolona širine 70 -id
        self.stavkeTable_3.setColumnWidth(1, 110)  # kolona širine 90 - sifra
        self.stavkeTable_3.setColumnWidth(2, 240)  # kolona širine 180 - naziv
        self.stavkeTable_3.setColumnWidth(3, 100)  # kolona širine 90 - kolicina
        self.stavkeTable_3.setColumnWidth(4, 100)  # kolona širine 100 - cena
        self.stavkeTable_3.setColumnHidden(0, True)  # sakrivam kolonu u kojoj je id stavke

        self.btnStampa_3.clicked.connect(self.fiskalizuj_racun_refundacije) 
        #self.btnStampa_3.clicked.connect(self.snimi_racun_refundacije) 
        # ✅ Kraj kontrola na refundacijaRN
        # Page pregledRN Page sa indeksom 4
        # ✅ Kolone u avansiTree na page pregledRN - indeksa 4
        self.avansiTree.setColumnWidth(0, 220)  # PFR broj
        self.avansiTree.setColumnWidth(1, 150)  # vreme transakcije
        self.avansiTree.setColumnWidth(2, 75)   # Datum
        self.avansiTree.setColumnWidth(3, 65)   # Vrednost
        self.avansiTree.setColumnWidth(4, 155)  # Referentni racun
        self.avansiTree.setColumnWidth(5, 60)  # kod kupca
        self.avansiTree.setColumnWidth(6, 90)  # Kupac
        self.avansiTree.setColumnWidth(7, 60)  # Godina
        self.avansiTree.setColumnWidth(8, 70)  # Broj
        self.avansiTree.setColumnWidth(9, 70)  # Tip racuna
        self.avansiTree.setColumnWidth(10, 70)  # Tip transakcije
        self.avansiTree.setColumnHidden(1, True)  # Sakrijemo vreme transakcije
        self.avansiTree.setColumnHidden(5, True)  # Sakrijemo kod kupca
        self.avansiTree.setColumnHidden(7, True)  # Sakrijemo godinu
        self.avansiTree.setColumnHidden(8, True)  # Sakrijemo broj
        self.avansiTree.setColumnHidden(9, True)  # Tip racuna
        self.avansiTree.setColumnHidden(10, True)  # Tip transakcije
        # ✅ Kolone u stavkeRnTable na page pregledRN
        self.stavkeRnTable.setColumnWidth(0, 90)  # # kolona širine 90 - sifra
        self.stavkeRnTable.setColumnWidth(1, 190)  # kolona širine 190 - naziv
        self.stavkeRnTable.setColumnWidth(2, 80)  # kolona širine 80 - kolicina
        self.stavkeRnTable.setColumnWidth(3, 100)  # kolona širine 100 - cena
        self.stavkeRnTable.setColumnWidth(4, 100)  # kolona širine 100 - vrednost
        self.stavkeRnTable.setColumnWidth(5, 60)  # # kolona širine 60 - artikliid
        self.stavkeRnTable.setColumnWidth(6, 60)  # # kolona širine 60 - tarifa
        self.stavkeRnTable.setColumnWidth(7, 90)  # # kolona širine 90 - vrednost poreza
        self.stavkeRnTable.setColumnWidth(8, 70)  # # kolona širine 70 - porezproc stopa poreza
        self.stavkeRnTable.setColumnWidth(9, 60)  # # kolona širine 60 - porezid
        self.stavkeRnTable.setColumnWidth(10, 60)  # # kolona širine 60 - grupa - robna grupa
        self.stavkeRnTable.setColumnHidden(5, True)  # sakrivam kolonu 
        self.stavkeRnTable.setColumnHidden(6, True)  # sakrivam kolonu 
        self.stavkeRnTable.setColumnHidden(7, True)  # sakrivam kolonu 
        self.stavkeRnTable.setColumnHidden(8, True)  # sakrivam kolonu
        self.stavkeRnTable.setColumnHidden(9, True)  # sakrivam kolonu 
        self.stavkeRnTable.setColumnHidden(10, True)  # sakrivam kolonu
        # ✅ Pozivanje funkcija za treeWidget
        self.avansiTree.itemSelectionChanged.connect(self.prikazi_stavke_racuna)
        self.greskaBtn.clicked.connect(self.proveri_i_refundiraj)
        #self.rnzaRefBtn.clicked.connect(self.pokreni_refundaciju_avansa)
        #self.rnzaRefBtn.clicked.connect(self.proveri_validnost_refundacije)
        # Postavljanje UI komponenti
        #self.rnzaRefBtn = QPushButton("Pokreni lanci avansa", self)

        # Povezivanje dugmeta sa slot funkcijom
        self.rnzaRefBtn.clicked.connect(self.nadji_citav_lanac_avansa)

        # Postavljanje layout-a
        #layout = QVBoxLayout(self)
        #layout.addWidget(self.rnzaRefBtn)

        #self.setLayout(layout)   

    def otvori_trazi_avans(self):
        """ Otvara dijalog za pretragu avansa """
        dialog = TraziAvansDialog(self)  # Prosleđujemo `self` kao parent
        dialog.exec()  # Pokrećemo dijalog modalno
    
    # ✅ Funkcije u dijalogu za page
    def prebaci_na_prviRN(self):
        self.stackedWidget.setCurrentIndex(0)
        self.aktivan_mod = "promet"
        #print(self.aktivan_mod)

    def prebaci_na_naredniRN(self):
        self.stackedWidget.setCurrentIndex(1)
        self.aktivan_mod = "promet"
        #print(self.aktivan_mod)

    def prebaci_na_refundacijaRN(self):
        self.stackedWidget.setCurrentIndex(2)
        self.aktivan_mod = "refundacija"
        #print(self.aktivan_mod)

    def prebaci_na_konacniRN(self):
        self.stackedWidget.setCurrentIndex(3)
        self.aktivan_mod = "promet"
        #print(self.aktivan_mod)

    def prebaci_na_pregledRN(self):
        self.stackedWidget.setCurrentIndex(4)
        self.aktivan_mod = "promet"
        #print(self.aktivan_mod)

    # ✅ Funkcije za preuzimanje dinamickih imena polja sa razlicitih stranica
    # 0 je prva stranica, 1 je druga stranica...
    def preuzmi_vrednosti(self):
        kontrole_map = {
            0: {
                "sifra": self.sifraEdit,  
                "naziv": self.nazivEdit,
                "jedmere": self.jmEdit, 
                "kolicina": self.kolicinaEdit,
                "cena": self.cenaEdit, 
                "stopa": self.stopaEdit,
                "slovo": self.slovoEdit,
                "tip_kupca": self.tipEdit,  
                "oznaka_kupca": self.oznakaEdit,  
                "dodatni_tekst": self.dodatniEdit,
                "gotovina": self.gotovinaEdit,
                "kartica": self.karticaEdit,
                "cek": self.cekEdit,
                "racun": self.racunEdit,
                "total": self.totalEdit,
                "stavke_table": self.stavkeTable
            },
            1: {  
                "sifra": self.sifraEdit_2,  
                "naziv": self.nazivEdit_2, 
                "jedmere": self.jmEdit_2, 
                "kolicina": self.kolicinaEdit_2, 
                "cena": self.cenaEdit_2, 
                "stopa": self.stopaEdit_2,
                "slovo": self.slovoEdit_2,
                "tip_kupca": self.tipEdit_2,  
                "oznaka_kupca": self.oznakaEdit_2,
                "referentni_broj": self.brrapuEdit,  
                "vreme_transakcije": self.vremeTranEdit,
                "dodatni_tekst": self.dodatniEdit_2,
                "gotovina": self.gotovinaEdit_2,
                "kartica": self.karticaEdit_2,
                "cek": self.cekEdit_2,
                "racun": self.racunEdit_2,
                "total": self.totalEdit_2,
                "stavke_table": self.stavkeTable_2
            },
            2: {
                "tip_kupca": self.tipEdit_3,  
                "oznaka_kupca": self.oznakaEdit_3,
                "referentni_broj": self.brrapuEdit_2,  
                "vreme_transakcije": self.vremeTranEdit_2,
                "total": self.totalEdit_3,
                "stavke_table": self.stavkeTable_3
            }
        }

        trenutna_strana = self.stackedWidget.currentIndex()
        kontrole = kontrole_map.get(trenutna_strana, {})

        def get_value(kontrola):
            return kontrola.text().strip() if kontrola else ""

        sifra = get_value(kontrole.get("sifra"))
        naziv = get_value(kontrole.get("naziv"))
        cena = get_value(kontrole.get("cena"))
        referentni_broj = get_value(kontrole.get("referentni_broj"))
        vreme_transakcije = get_value(kontrole.get("vreme_transakcije"))

        stavke_table = kontrole.get("stavke_table")
        stavke = []
        if stavke_table:
            for row in range(stavke_table.rowCount()):
                red_stavke = [
                    (stavke_table.item(row, col).text().strip() if stavke_table.item(row, col) else "")
                    for col in range(stavke_table.columnCount())
                ]
                stavke.append(red_stavke)

        return sifra, naziv, cena, referentni_broj, vreme_transakcije, stavke

    def update_avans_edit(self):
        """Ažurira vrednosti u sifraEdit, nazivEdit, stopaEdit i slovoEdit na osnovu izbora u comboAvans."""
        
        trenutna_strana = self.stackedWidget.currentIndex()
        #print(f"Aktivna stranica: {trenutna_strana}")  # TEST
        
        # Određivanje koji combobox koristiti
        combo_avans = self.comboAvans if trenutna_strana == 0 else self.comboAvans_2
        if combo_avans is None:
            print("Greška: comboAvans nije pronađen!")
            return

        selected_text = combo_avans.currentText()
        #print(f"Izabrana vrednost: {selected_text}")  # TEST
        
        # Mapa koja povezuje vrednosti iz comboAvans sa podacima
        avans_map = {
            "": {"sifra": "", "stopa": "", "slovo": "", "jedmere": ""},
            "10": {"sifra": "999996", "stopa": "20%", "slovo": "Đ", "jedmere": "KOM"},
            "11": {"sifra": "999997", "stopa": "10%", "slovo": "E", "jedmere": "KOM"},
            "12": {"sifra": "999998", "stopa": "0%", "slovo": "G", "jedmere": "KOM"},
            "13": {"sifra": "999999", "stopa": "0%", "slovo": "A", "jedmere": "KOM"}
        }

        tip_avans = selected_text.split(':')[0]
        tip_naziv = selected_text.split(' ')[0]  

        # Provera kontrola
        kontrole_map = {
            0: {
                "sifra": self.sifraEdit,
                "naziv": self.nazivEdit,
                "jm": self.jmEdit,
                "stopa": self.stopaEdit,
                "slovo": self.slovoEdit,
                "cena": self.cenaEdit
            },
            1: {
                "sifra": getattr(self, "sifraEdit_2", None),
                "naziv": getattr(self, "nazivEdit_2", None),
                "jm": getattr(self, "jmEdit_2", None),
                "stopa": getattr(self, "stopaEdit_2", None),
                "slovo": getattr(self, "slovoEdit_2", None),
                "cena": getattr(self, "cenaEdit_2", None)
            }
        }

        kontrole = kontrole_map.get(trenutna_strana, None)
        if not kontrole or None in kontrole.values():
            print("Greška: neke kontrole nisu pronađene!")
            return

        if tip_avans in avans_map:
            #print("Ažuriram polja...")  # TEST
            kontrole["sifra"].setText(avans_map[tip_avans]["sifra"])
            kontrole["naziv"].setText(tip_naziv)
            kontrole["jm"].setText(avans_map[tip_avans]["jedmere"])
            kontrole["stopa"].setText(avans_map[tip_avans]["stopa"])
            kontrole["slovo"].setText(avans_map[tip_avans]["slovo"])
            kontrole["cena"].setFocus()

    def update_tip_edit(self):
        """Ažurira vrednost u tipEdit na osnovu izbora u tipCombo."""
        selected_tip = self.tipCombo.currentText()
        tip_value = selected_tip.split(' ')[0]  # Ekstrahujemo broj pre razmaka
        self.tipEdit.setText(tip_value)

    # Dodavanje artikla u bazu i prikaz u tabeli prozora, brisanje stavki i azuriranje totala    
    def dodaj_u_kasa1(self):
        try:
            trenutna_strana = self.stackedWidget.currentIndex()

            # Mapiranje kontrola na osnovu aktivne strane
            kontrole_map = {
                0: {
                    "sifra": self.sifraEdit,
                    "naziv": self.nazivEdit,
                    "kolicina": self.kolicinaEdit,
                    "cena": self.cenaEdit
                },
                1: {
                    "sifra": getattr(self, "sifraEdit_2", None),
                    "naziv": getattr(self, "nazivEdit_2", None),
                    "kolicina": getattr(self, "kolicinaEdit_2", None),
                    "cena": getattr(self, "cenaEdit_2", None)
                }
            }

            kontrole = kontrole_map.get(trenutna_strana, None)
            if not kontrole or None in kontrole.values():
                print("❌ Greška: Kontrole nisu pravilno mapirane!")
                return

            # Validacija unosa
            sifra = kontrole["sifra"].text().strip()
            if not sifra:
                print("❌ Greška: Nedostaje šifra artikla.")
                return

            try:
                kolicina = float(kontrole["kolicina"].text() or 0)
                if kolicina <= 0:
                    print("❌ Greška: Količina mora biti veća od 0.")
                    return
            except ValueError:
                print("❌ Greška: Neispravna količina.")
                return

            try:
                cena_bez_popusta = float(kontrole["cena"].text() or 0)
                if cena_bez_popusta <= 0:
                    print("❌ Greška: Cena mora biti veća od 0.")
                    return
            except ValueError:
                print("❌ Greška: Neispravna cena.")
                return

            # Preuzimanje artiklid i tip iz baze
            artiklid, tip = None, None
            try:
                conn = psycopg2.connect(
                    dbname=os.getenv("DB_NAME"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT")
                )
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, tip
                    FROM "kasa"."artikli"
                    WHERE sifra = %s
                    """,
                    (sifra,)
                )
                result = cursor.fetchone()
                if result:
                    artiklid, tip = result
                else:
                    print(f"❌ Greška: Artikal sa šifrom {sifra} nije pronađen.")
                    return
            except Exception as e:
                print(f"❌ Greška pri dohvatanju artikla: {e}")
                return
            finally:
                cursor.close()
                conn.close()

            # Izračunavanje vrednosti i popusta
            proc_popust = 0
            popust_iznos = 0
            cena_sa_popustom = round(cena_bez_popusta, 2)
            vrednost = round(cena_sa_popustom * kolicina, 2)

            sifobj = SIFOBJEKTA
            datum = datetime.now().date()
            kasa = int(KASA)
            god = int(GODINA)
            ststatus = "A"
            sto = self.aktivan_kupac

            # Unos u bazu
            try:
                conn = psycopg2.connect(
                    dbname=os.getenv("DB_NAME"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT")
                )
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO "kasa"."kasa1" 
                    (sifra, sifobj, cena, datum, kolic, broj, kasa, smena, cena2, popproc1, popdin1, popsum, god, kar, ststatus, kreirao, sto, artikliid, tip) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'sistem', %s, %s, %s) 
                    RETURNING id
                    """,
                    (sifra, sifobj, cena_sa_popustom, datum, kolicina, self.trenutni_broj_racuna, kasa, 1,
                    cena_bez_popusta, proc_popust, popust_iznos, popust_iznos * kolicina, god, 1, ststatus, sto, artiklid, tip)
                )

                inserted_id = cursor.fetchone()[0]
                conn.commit()
            except Exception as e:
                print(f"❌ Greška pri upisu u bazu `kasa1`: {e}")
                return
            finally:
                cursor.close()
                conn.close()

            # Dodavanje u tabelu
            self.dodaj_u_korpu(inserted_id, sifra, kontrole["naziv"].text(), kolicina, cena_bez_popusta)

        except Exception as e:
            print(f"❌ Greška pri izvršavanju `dodaj_u_kasa1`: {e}")

    def dodaj_u_korpu(self, id_stavke, sifra, naziv, kolicina, cena_bez_popusta):
        # Odabir tabele na osnovu trenutne strane
        trenutna_strana = self.stackedWidget.currentIndex()
        tabela = self.stavkeTable if trenutna_strana == 0 else self.stavkeTable_2

        row_count = tabela.rowCount()
        tabela.insertRow(row_count)

        # Popunjavanje kolona
        tabela.setItem(row_count, 0, QTableWidgetItem(str(id_stavke)))
        tabela.setItem(row_count, 1, QTableWidgetItem(sifra))
        tabela.setItem(row_count, 2, QTableWidgetItem(naziv))
        tabela.setItem(row_count, 3, QTableWidgetItem(f"{kolicina:.3f}"))
        tabela.setItem(row_count, 4, QTableWidgetItem(f"{cena_bez_popusta:.2f}"))

        # Dodavanje dugmeta za brisanje
        btn_obrisi = QPushButton("Obriši")
        btn_obrisi.clicked.connect(partial(self.obrisi_stavku, id_stavke))
        btn_obrisi.setStyleSheet("""
            QPushButton {
                background-color: red;
                color: white;
                border: 2px solid black;
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: darkred;
            }
            QPushButton:pressed {
                background-color: #ff5555;
            }
        """)
        tabela.setCellWidget(row_count, 5, btn_obrisi)

        # Ažuriranje ukupne vrednosti
        self.azuriraj_total()
        self.clear_fields()
        self.sifraEdit.setFocus()

    def obrisi_stavku(self, id_stavke):
        """✅ Brisanje artikla iz baze `kasa1` i tabele `stavkeTable` ili `stavkeTable_2`."""
        try:
            # ✅ Brisanje iz baze
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()
            cursor.execute("""DELETE FROM "kasa"."kasa1" WHERE id = %s;""", (id_stavke,))
            conn.commit()
            cursor.close()
            conn.close()

            # ✅ Odabir tabele na osnovu trenutne strane
            trenutna_strana = self.stackedWidget.currentIndex()
            tabela = self.stavkeTable if trenutna_strana == 0 else self.stavkeTable_2

            # ✅ Brisanje iz tabele
            for row in range(tabela.rowCount()):
                if int(tabela.item(row, 0).text()) == id_stavke:
                    tabela.removeRow(row)
                    break

            self.azuriraj_total()
            #print(f"✅ Stavka sa ID-om {id_stavke} uspešno obrisana.")

        except Exception as e:
            print(f"❌ Greška pri brisanju stavke: {e}")

    def azuriraj_total(self):
        """✅ Ažurira ukupnu vrednost računa za odgovarajuću stranicu."""
        total = 0
        trenutna_strana = self.stackedWidget.currentIndex()
        tabela = self.stavkeTable if trenutna_strana == 0 else self.stavkeTable_2 if trenutna_strana == 1 else self.stavkeTable_3
        totalEdit = self.totalEdit if trenutna_strana == 0 else self.totalEdit_2  if trenutna_strana == 1 else self.totalEdit_3

        for row in range(tabela.rowCount()):
            vrednost = float(tabela.item(row, 4).text())
            total += vrednost

        totalEdit.setText(f"{total:.2f}")

    def clear_fields(self):
        """✅ Resetuje polja u dijalogu na osnovu aktivne strane."""
        trenutna_strana = self.stackedWidget.currentIndex()

        if trenutna_strana == 0:
            self.sifraEdit.clear()
            self.nazivEdit.clear()
            self.jmEdit.clear()
            self.cenaEdit.clear()
            self.stopaEdit.clear()
            self.slovoEdit.clear()
        else:
            self.sifraEdit_2.clear()
            self.nazivEdit_2.clear()
            self.jmEdit_2.clear()
            self.cenaEdit_2.clear()
            self.stopaEdit_2.clear()
            self.slovoEdit_2.clear()

    # Ukoliko je avansni racun ostao nezavrsen ucitavaju se stavke racuna
    def ucitaj_stavke_iz_baze(self):
        """✅ Učitavanje stavki iz baze za aktivnog kupca"""
        self.stavkeTable.setRowCount(0)
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, sifra, (SELECT naziv FROM \"kasa\".\"artikli\" WHERE sifra = k.sifra), kolic, cena FROM \"kasa\".\"kasa1\" k WHERE sto = %s AND kasa = %s AND zatvoren = False",
                (self.aktivan_kupac, KASA)
            )
            rows = cursor.fetchall()
            for row in rows:
                row_count = self.stavkeTable.rowCount()
                self.stavkeTable.insertRow(row_count)
                for col, value in enumerate(row):
                    self.stavkeTable.setItem(row_count, col, QTableWidgetItem(str(value)))
                btn_obrisi = QPushButton("Obriši")
                btn_obrisi.clicked.connect(partial(self.obrisi_stavku, row[0]))
                btn_obrisi.setStyleSheet("""
                    QPushButton {
                        background-color: red;
                        color: white;
                        border: 2px solid black;
                        border-radius: 5px;
                        padding: 5px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: darkred;
                    }
                    QPushButton:pressed {
                        background-color: #ff5555;
                    }
                """)
                self.stavkeTable.setCellWidget(row_count, 5, btn_obrisi)
                self.azuriraj_total()
                self.clear_fields()
                self.sifraEdit.setFocus()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"❌ Greška pri učitavanju stavki iz baze: {e}")

    def proveri_placanje(self):
        """✅ Provera uslova za omogućavanje dugmadi 'btnStampa' i 'btnStampa_2'."""
        try:
            trenutna_strana = self.stackedWidget.currentIndex()

            # Definišemo kontrole za obe strane
            if trenutna_strana == 0:
                gotovina = float(self.gotovinaEdit.text() or 0)
                kartica = float(self.karticaEdit.text() or 0)
                cek = float(self.cekEdit.text() or 0)
                racun = float(self.racunEdit.text() or 0)
                ukupno_za_placanje = float(self.totalEdit.text() or 0)
                tip = self.tipEdit.text().strip()
                kupac = self.oznakaEdit.text().strip()
                dugme = self.btnStampa
            elif trenutna_strana == 1:
                gotovina = float(self.gotovinaEdit_2.text() or 0)
                kartica = float(self.karticaEdit_2.text() or 0)
                cek = float(self.cekEdit_2.text() or 0)
                racun = float(self.racunEdit_2.text() or 0)
                ukupno_za_placanje = float(self.totalEdit_2.text() or 0)
                tip = self.tipEdit_2.text().strip()
                kupac = self.oznakaEdit_2.text().strip()
                dugme = self.btnStampa_2
            else:
                print("❌ Nepoznata stranica!")
                return

            ukupno_placanje = gotovina + kartica + cek + racun

            # Omogućavamo dugme ako su iznosi jednaki
            dugme.setEnabled(ukupno_placanje == ukupno_za_placanje)

        except ValueError:
            dugme.setEnabled(False)

    def izvrsi_stampu(self):
        """✅ Pokreće odgovarajuću funkciju za fiskalizaciju u zavisnosti od aktivnog moda."""
        if self.aktivan_mod == "promet":
            self.fiskalizuj_avans()
        #elif self.aktivan_mod == "refundacija":
           #self.fiskalizuj_racun_refundacije()
        else:
            self.show_warning_message("Nepoznat mod rada!")
    
    def show_warning_message(self, message):
        """Prikazuje upozorenje korisniku."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Upozorenje")
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    # Generisanje sledeceg broja racuna
    def dohvati_broj_racuna(self):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(MAX(broj), 0) + 1
                FROM "kasa"."kasasum"
                WHERE god = %s AND sifobj = %s
                """,
                (GODINA, SIFOBJEKTA)
            )
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            print(f"❌ Greška pri dohvatanju broja računa: {e}")
            return None
        
    # Cuvanje podataka u bazi
    def snimi_racun(self):
        """✅ Snimanje podataka o računu u bazu."""
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # Početak transakcije
            conn.autocommit = False

            # Dohvatanje novog broja računa
            novi_broj_racuna = self.dohvati_broj_racuna()
            if novi_broj_racuna is None:
                raise Exception("Neuspešno generisanje broja računa.")

            # Određivanje tipa računa i transakcije
            if self.aktivan_mod == "promet":
                tipracuna = 4
                tiptransakcije = 0
                dokstatus = 'AP'
                ui = 'i'
            elif self.aktivan_mod == "refundacija":
                tipracuna = 4
                tiptransakcije = 1
                dokstatus = 'AR'
                ui = 'u'
            else:
                raise Exception("Nepoznat mod transakcije.")

            # Dohvatanje podataka o kupcu
            if self.stackedWidget.currentIndex() == 0:
                tip_kupca = self.tipEdit.text().strip() if self.tipEdit.text() else None
                oznaka_kupca = self.oznakaEdit.text().strip() if self.oznakaEdit.text() else None
                gotovina = round(float(self.gotovinaEdit.text() or 0), 2)
                kartica = round(float(self.karticaEdit.text() or 0), 2)
                cek = round(float(self.cekEdit.text() or 0), 2)
                racun = round(float(self.racunEdit.text() or 0), 2)
                svega = round(float(self.totalEdit.text() or 0), 2)
                # Provera da li smo na stranici 1 i uzimanje refbrracpu vrednosti
                refbrracpu = None
            elif self.stackedWidget.currentIndex() == 1:  # Proveravamo aktivnu stranicu
                tip_kupca = self.tipEdit_2.text().strip() if self.tipEdit_2.text() else None
                oznaka_kupca = self.oznakaEdit_2.text().strip() if self.oznakaEdit_2.text() else None
                refbrracpu = self.brrapuEdit.text().strip() if self.brrapuEdit.text() else None
                gotovina = round(float(self.gotovinaEdit_2.text() or 0), 2)
                kartica = round(float(self.karticaEdit_2.text() or 0), 2)
                cek = round(float(self.cekEdit_2.text() or 0), 2)
                racun = round(float(self.racunEdit_2.text() or 0), 2)
                svega = round(float(self.totalEdit_2.text() or 0), 2)

            # Snimanje podataka iz `kasa1` u `kasa`
            cursor.execute("""
            INSERT INTO "kasa"."kasa" 
            (god, kar, broj, sto, zatvoren, kasa, smena, sifra, kolic, cena, popproc1, popdin1, popsum, datum, sifobj, dokstatus, kreirao, artikliid, tip, cena2, ststatus)
            SELECT god, kar, %s, sto, TRUE, kasa, smena, sifra, kolic, cena, popproc1, popdin1, popsum, datum, sifobj, %s, 'sistem', artikliid, tip, cena2, ststatus
            FROM "kasa"."kasa1"
            WHERE zatvoren = FALSE AND kasa = %s AND sto = %s
            """, (novi_broj_racuna, dokstatus, int(KASA), self.aktivan_kupac))

            # Ažuriranje podataka u `kasa1` kao zatvorenih
            cursor.execute("""
            UPDATE "kasa"."kasa1"
            SET broj = %s, zatvoren = TRUE, kreirao = 'sistem'
            WHERE zatvoren = FALSE AND kasa = %s AND sto = %s
            """, (novi_broj_racuna, int(KASA), self.aktivan_kupac))

            # Snimanje podataka u `kasasum`
            cursor.execute("""
            INSERT INTO "kasa"."kasasum"
            (god, kar, broj, datum, kasa, sifobj, smena, vrgotovina, vrkartica, vrfaktura, vrcek, ukiznos, vravans, idpartneri, kodkupca, oznakakupca, tipplacanja, tipracuna, tiptransakcije, dokstatus, kreirao, refbrracpu)
            VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, 'sistem', %s)
            """, (
                int(GODINA), 1, novi_broj_racuna, int(KASA), SIFOBJEKTA, 1,
                gotovina, kartica, racun, cek, svega, svega,  # Avans
                tip_kupca, oznaka_kupca,
                1 if float(self.gotovinaEdit.text() or 0) > 0 else 0,
                tipracuna, tiptransakcije, dokstatus,
                refbrracpu  # Dodato polje refbrracpu ako smo na stranici 1
            ))
            
            # Snimanje podataka u `karticaart`
            cursor.execute("""
            SELECT 
                k.sifra,
                k.cena,
                SUM(k.kolic) AS ukupna_kolicina,
                MAX(k.cena2) AS nabavna_cena,
                MAX(k.popproc1) AS rabat_proc,
                SUM(k.popsum) AS ukupna_vrednost,
                MAX(k.artikliid) AS artikli_id,
                MAX(a.robna_grupa_id) AS grupa,
                MAX(a.porez_id) AS porezid,
                MAX(p.tarifa) AS tarifa,
                MAX(p.stopa) AS stopa
            FROM "kasa"."kasa1" k
            LEFT JOIN "kasa"."artikli" a ON a.sifra = k.sifra
            LEFT JOIN "kasa"."porezi" p ON p.id = a.porez_id
            WHERE k.zatvoren = TRUE AND k.kasa = %s AND k.broj = %s
            GROUP BY k.sifra, k.cena
            """, (int(KASA), novi_broj_racuna))

            artikli = cursor.fetchall()

            for artikal in artikli:
                sifra, prodajna_cena, ukupna_kolicina, nabavna_cena, rabat_proc, ukupna_vrednost, artikli_id, grupa, porezid, tarifa, stopa = artikal

                # Računanje poreza
                preracunata_stopa = float((stopa * 100) / (stopa + 100)) if stopa else 0
                porez = round(float((prodajna_cena * preracunata_stopa / 100) * ukupna_kolicina), 2)

                cursor.execute("""
                INSERT INTO "kasa"."karticaart"
                (god, kar, broj, sifra, cena, cenanabavna, kolicina, rabatproc, rabatdinarski, porez, porezproc, tarifa, grupa, vrsta, dokstatus, datum, opis, artikliid, sifobj, lokacija_id, porezid, ui, kasa, idpartneri, kreirao, kreirano)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, NULL, 'sistem', CURRENT_TIMESTAMP)
                """, (
                    GODINA, 1, novi_broj_racuna, sifra, round(prodajna_cena, 2), round(nabavna_cena, 2), round(ukupna_kolicina, 3),
                    round(rabat_proc, 2), round(ukupna_vrednost, 2), porez, stopa, tarifa, grupa,
                    8 if tiptransakcije == 0 else 9, dokstatus,
                    f"Fiskalni račun {dokstatus}", artikli_id, SIFOBJEKTA, self.glavna_lokacija_id, porezid, ui, int(KASA)
                ))
                
                sifra, prodajna_cena, ukupna_kolicina, *_ = artikal

            conn.commit()
            print(f"✅ Račun uspešno snimljen u bazi sa brojem {novi_broj_racuna}.")
            return novi_broj_racuna  # Vraćamo broj računa

        except Exception as e:
            print(f"❌ Greška pri snimanju računa: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()


    def generisi_json_avansni_racun(self, broj_racuna, stavke, placanja, kasir, ip_stampe, tip_kupca, oznaka_kupca, dodatni_tekst, referentni, vremetransakcije):
        """
        Generiše JSON fajl za avansni fiskalni račun sa obaveznim podacima o kupcu i opcionim dodatnim tekstom.
        """
        try:
            godina = str(datetime.now().year)[-2:]
            direktorijum = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\to-sdc"
            json_fajl = os.path.join(direktorijum, f"CreateInvoice-{broj_racuna}-{godina}.json")

            trenutna_strana = self.stackedWidget.currentIndex()
            if trenutna_strana == 0:
                dodatni_tekst = self.dodatniEdit.toPlainText().strip()
            elif trenutna_strana == 1:
                dodatni_tekst = self.dodatniEdit_2.toPlainText().strip()
            else:
                print("❌ Nepoznata stranica!")
                return            

            # Ako postoji dodatni tekst, koristi njega, inače koristi podrazumevanu poruku
            poruka = dodatni_tekst.strip() if dodatni_tekst else "HVALA NA POVERENJU"
            kasir = "Kasir 1"

            # Priprema podataka za JSON
            if trenutna_strana == 0:
                racun = {
                    "cashier": kasir,
                    "invoiceNumber": "1161/1.0.128.0",  # Direkno upisana vrednost
                    "invoiceType": "4",  # Avansni račun
                    "transactionType": "0",
                    "buyerId": f"{tip_kupca}:{oznaka_kupca}",  # Obavezni podaci o kupcu
                    "items": stavke,
                    "payment": placanja,
                    "journalOptions": {
                        "print": "true",
                        "message": poruka  # Dodatni tekst ili "HVALA NA POVERENJU"
                    }
                }
            elif trenutna_strana == 1:
                racun = {
                    "cashier": kasir,
                    "invoiceNumber": "1161/1.0.128.0",  # Direkno upisana vrednost
                    "invoiceType": "4",  # Avansni račun
                    "transactionType": "0",
                    "referentDocumentNumber": referentni,
                    "referentDocumentDT": vremetransakcije,
                    "buyerId": f"{tip_kupca}:{oznaka_kupca}",  # Obavezni podaci o kupcu
                    "items": stavke,
                    "payment": placanja,
                    "journalOptions": {
                        "print": "true",
                        "message": poruka  # Dodatni tekst ili "HVALA NA POVERENJU"
                    }
                }
            else:
                print("❌ Nepoznata stranica!")
                return

            # Kreiranje direktorijuma ako ne postoji
            os.makedirs(direktorijum, exist_ok=True)

            # Upis JSON fajla
            with open(json_fajl, "w", encoding="utf-8") as f:
                json.dump(racun, f, ensure_ascii=False, indent=4)

            print(f"✅ JSON fajl za avansni račun generisan: {json_fajl}")
            return json_fajl

        except Exception as e:
            print(f"❌ Greška pri generisanju JSON fajla za avansni račun: {e}")

    def pripremi_stavke_avans(self, lservis):
        """
        Priprema stavke iz tabele za JSON, uključujući porez na osnovu baze (za avansne račune).
        """
        stavke = []
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            trenutna_strana = self.stackedWidget.currentIndex()
            if trenutna_strana == 0:
                for row in range(self.stavkeTable.rowCount()):
                    sifra = self.stavkeTable.item(row, 1).text()  # Šifra artikla
                    naziv = self.stavkeTable.item(row, 2).text()
                    kolicina = self.stavkeTable.item(row, 3).text()
                    cena = self.stavkeTable.item(row, 4).text()
            elif trenutna_strana == 1:
                for row in range(self.stavkeTable_2.rowCount()):
                    sifra = self.stavkeTable_2.item(row, 1).text()  # Šifra artikla
                    naziv = self.stavkeTable_2.item(row, 2).text()
                    kolicina = self.stavkeTable_2.item(row, 3).text()
                    cena = self.stavkeTable_2.item(row, 4).text()
            else:
                print("❌ Nepoznata stranica!")
                return
                
            # Preuzimanje jedinice mere iz baze
            try:
                cursor.execute("""
                    SELECT jm.jm
                    FROM "kasa"."artikli" a
                    JOIN "kasa"."jedmere" jm ON a.jedinica_mere_id = jm.id
                    WHERE a.sifra = %s
                """, (sifra,))
                result = cursor.fetchone()
                jedinica_mere = result[0] if result else "N/A"
            except Exception as e:
                print(f"❌ Greška pri preuzimanju jedinice mere za artikal {sifra}: {e}")
                jedinica_mere = "N/A"

            # Dodavanje jedinice mere uz naziv artikla
            naziv_sa_jedinicom = f"{naziv}/{jedinica_mere}"

            # Podrazumevana vrednost poreza
            porez_slovo = "A" if lservis else "Ђ"

            # Dohvatanje poreza iz baze
            cursor.execute("""
            SELECT p.slovo
            FROM "kasa"."artikli" a
            JOIN "kasa"."porezi" p ON a.porez_id = p.id
            WHERE a.sifra = %s
            """, (sifra,))
            rezultat = cursor.fetchone()

            if rezultat:
                latinsko_slovo = rezultat[0]
                porez_slovo = LATIN_TO_CYRILLIC_MAP.get(latinsko_slovo, "Ђ") if not lservis else "A"

            # Dodavanje stavke u listu
            stavke.append({
                "name": naziv_sa_jedinicom,
                "quantity": kolicina,
                "unitPrice": cena,
                "totalAmount": cena,  # OVA PROMENA! totalAmount = cena jer je kolicina = 1
                "labels": [porez_slovo]
            })

            return stavke

        except Exception as e:
            print(f"❌ Greška pri pripremi stavki za avansni račun: {e}")
            return []
        
        finally:
            if conn:
                conn.close()

    def pripremi_placanja_avans(self):
        """
        Priprema podataka o plaćanju za avansni račun u JSON formatu.
        """
        trenutna_strana = self.stackedWidget.currentIndex()
        if trenutna_strana == 0:
            gotovina = float(self.gotovinaEdit.text() or 0)
            kartica = float(self.karticaEdit.text() or 0)
            cek = float(self.cekEdit.text() or 0)
            racun = float(self.racunEdit.text() or 0)
        elif trenutna_strana == 1:
            gotovina = float(self.gotovinaEdit_2.text() or 0)
            kartica = float(self.karticaEdit_2.text() or 0)
            cek = float(self.cekEdit_2.text() or 0)
            racun = float(self.racunEdit_2.text() or 0)
        else:
            print("❌ Nepoznata stranica!")
            return
         
        placanja = []

        if gotovina > 0:
            placanja.append({"paymentType": "1", "amount": f"{gotovina:.2f}"})

        if kartica > 0:
            placanja.append({"paymentType": "2", "amount": f"{kartica:.2f}"})

        if cek > 0:
            placanja.append({"paymentType": "3", "amount": f"{cek:.2f}"})

        if racun > 0:
            placanja.append({"paymentType": "4", "amount": f"{racun:.2f}"})
  
        return placanja
    
    
    def fiskalizuj_avansni_racun(self, broj_racuna, stavke, placanja, kasir, ip_stampe, tip_kupca, oznaka_kupca, dodatni_tekst, referentni, vremetransakcije):
        """
        Glavna funkcija za fiskalizaciju avansnog računa.
        """
        try:
            # Generisanje JSON-a za avansni račun
            json_fajl = self.generisi_json_avansni_racun(
                broj_racuna, stavke, placanja, kasir, ip_stampe,
                tip_kupca=tip_kupca, oznaka_kupca=oznaka_kupca, dodatni_tekst=dodatni_tekst,
                referentni=referentni, vremetransakcije=vremetransakcije
            )

            if not json_fajl:
                raise Exception("Generisanje JSON fajla nije uspelo.")

            # Čekanje i obrada odgovora
            status, fajl_odgovora = self.main_window.obradi_odgovor(broj_racuna, ip_stampe)
            if status == "success":
                print("✅ Avansni račun je uspešno fiskalizovan.")
                # Obrada uspešnog odgovora
                with open(fajl_odgovora, "r", encoding="utf-8") as f:
                    odgovor = json.load(f)
                    broj_fiskalnog_racuna = odgovor.get("invoiceNumber", "Nepoznato")
                    print(f"Broj fiskalnog računa: {broj_fiskalnog_racuna}")
                # Ažuriranje kasasum
                self.main_window.azuriraj_kasasum(broj_racuna, ip_stampe)
            elif status == "error":
                print("❌ Greška pri fiskalizaciji. Proverite fajl sa greškom.")
            else:
                print("❌ Odgovor nije stigao u zadatom vremenu.")

        except Exception as e:
            print(f"❌ Greška pri fiskalizaciji avansnog računa: {e}")

    def fiskalizuj_avans(self):
        """
        Fiskalizuje korpu i generiše JSON fajl za fiskalni štampač.
        """
        try:
            # Dohvat konfiguracije kase
            ip_stampe, lservis = self.main_window.ucitaj_konfiguraciju_kase()
            #print(f"✅ Učitana konfiguracija: IP: {ip_stampe}, lservis: {lservis}")
            if not ip_stampe:
                raise Exception("IP adresa štampača nije pronađena u konfiguraciji.")

            # Priprema podataka
            broj_racuna = self.snimi_racun()
            if not broj_racuna:
                raise Exception("Generisanje broja računa nije uspelo.")
            #broj_racuna = self.trenutni_broj_racuna
            stavke = self.pripremi_stavke_avans(lservis)
            placanja = self.pripremi_placanja_avans()
            kasir = "Kasir 1"
            tip_racuna = 4  # Promet
            tip_transakcije = 0  # Prodaja

            trenutna_strana = self.stackedWidget.currentIndex()
            if trenutna_strana == 0:
                # Dohvatanje informacija o kupcu
                tip_kupca = self.tipEdit.text().strip() if self.tipEdit else ""
                oznaka_kupca = self.oznakaEdit.text().strip() if self.oznakaEdit else ""
                referentni = ""
                vremetransakcije = ""
            elif trenutna_strana == 1:
                # Dohvatanje informacija o kupcu
                tip_kupca = self.tipEdit_2.text().strip() if self.tipEdit_2 else ""
                oznaka_kupca = self.oznakaEdit_2.text().strip() if self.oznakaEdit_2 else ""
                # Dohvati referentni racun i vreme transakcije
                referentni = self.brrapuEdit.text()
                vremetransakcije = self.vremeTranEdit.text()
            else:
                print("❌ Nepoznata stranica!")
                return

            # Poziv funkcije za fiskalizaciju
            self.fiskalizuj_avansni_racun(
            broj_racuna, stavke, placanja, kasir, ip_stampe,
            tip_kupca=tip_kupca, oznaka_kupca=oznaka_kupca, dodatni_tekst="",
            referentni=referentni, vremetransakcije=vremetransakcije
        )
            #self.resetuj_kontrole()
        
        except Exception as e:
            print(f"❌ Greška pri fiskalizaciji: {e}")


    # Prikaz i funkcije za TreeWidget
    def dodaj_racune_u_tree(self, prvi_avans_item, trenutni_brracpu, cursor, font_stavke):
        """Dodaje sve povezane račune pod prvi avansni račun (NE pod poslednji avansni)."""
        
        poslednji_validan_avans_bez_refundacije = None

        # 1️⃣ Dodaj sve naredne avanse pod PRVI avans
        cursor.execute("""
            SELECT brracpu, vremetransakcije, datum, ukiznos, refbrracpu, kodkupca, oznakakupca, god, broj, tipracuna, tiptransakcije
            FROM "kasa"."kasasum"
            WHERE sifobj = %s 
                AND tipracuna = '4'  
                AND tiptransakcije = '0' 
                AND refbrracpu = %s
            ORDER BY datum DESC
        """, (SIFOBJEKTA, trenutni_brracpu))

        avansi = cursor.fetchall()

        for avans in avansi:
            avans_item = QTreeWidgetItem(prvi_avans_item, [str(i) for i in avans])
            for i in range(avans_item.columnCount()):
                avans_item.setFont(i, font_stavke)
                avans_item.setIcon(0, QIcon("icons/avans.gif"))

            # Proveri da li ovaj avans ima refundaciju
            cursor.execute("""
                SELECT 1
                FROM "kasa"."kasasum"
                WHERE sifobj = %s 
                    AND tipracuna = '4' 
                    AND tiptransakcije = '1'
                    AND refbrracpu = %s
                LIMIT 1
            """, (SIFOBJEKTA, avans[0]))
            
            ima_refundaciju = cursor.fetchone()
            if not ima_refundaciju:
                poslednji_validan_avans_bez_refundacije = avans_item

            # 🔁 Rekurzivno idi dalje
            self.dodaj_racune_u_tree(prvi_avans_item, avans[0], cursor, font_stavke)

        # 2️⃣ Refundacija (ostaje pod trenutnim avansom)
        cursor.execute("""
            SELECT brracpu, vremetransakcije, datum, ukiznos, refbrracpu, kodkupca, oznakakupca, god, broj, tipracuna, tiptransakcije
            FROM "kasa"."kasasum"
            WHERE sifobj = %s 
                AND tipracuna = '4' 
                AND tiptransakcije = '1'
                AND refbrracpu = %s
            ORDER BY datum DESC
        """, (SIFOBJEKTA, trenutni_brracpu))

        refundacija = cursor.fetchone()
        if refundacija:
            refundacija_item = QTreeWidgetItem(prvi_avans_item, [str(i) for i in refundacija])
            for i in range(refundacija_item.columnCount()):
                refundacija_item.setFont(i, font_stavke)
                refundacija_item.setForeground(i, QBrush(QColor("red")))
                refundacija_item.setIcon(0, QIcon("icons/refund.png"))

            # 3️⃣ Konačni račun (pod PRVI avans, ne pod refundacijom)
            cursor.execute("""
                SELECT brracpu, vremetransakcije, datum, ukiznos, refbrracpu, kodkupca, oznakakupca, god, broj, tipracuna, tiptransakcije
                FROM "kasa"."kasasum"
                WHERE sifobj = %s 
                    AND tipracuna = '0'  
                    AND tiptransakcije = '0'
                    AND refbrracpu = %s
                ORDER BY datum DESC
            """, (SIFOBJEKTA, refundacija[0]))

            konacni_racun = cursor.fetchone()
            if konacni_racun:
                konacni_item = QTreeWidgetItem(prvi_avans_item, [str(i) for i in konacni_racun])  # Dodaj konačni račun pod PRVI avans
                for i in range(konacni_item.columnCount()):
                    konacni_item.setFont(i, font_stavke)
                    konacni_item.setForeground(i, QBrush(QColor("darkblue")))
                    konacni_item.setIcon(0, QIcon("icons/final.png"))

        # 4️⃣ Oboj poslednji validan avans koji NEMA refundaciju
        if poslednji_validan_avans_bez_refundacije:
            for i in range(poslednji_validan_avans_bez_refundacije.columnCount()):
                poslednji_validan_avans_bez_refundacije.setForeground(i, QBrush(QColor("darkgreen")))

    def popuni_treewidget(self):
        """Punjenje TreeWidget-a podacima iz kasasum tabele."""
        try:
            # Konekcija na bazu
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # 1️⃣ Dohvati sve PRVE avansne račune
            cursor.execute("""
                SELECT brracpu, vremetransakcije, datum, ukiznos, refbrracpu, kodkupca, oznakakupca, god, broj, tipracuna, tiptransakcije
                FROM "kasa"."kasasum"
                WHERE sifobj = %s 
                    AND tipracuna = '4'  
                    AND tiptransakcije = '0'
                    AND (refbrracpu IS NULL OR refbrracpu = '')
                ORDER BY datum DESC
            """, (SIFOBJEKTA,))
            
            prvi_avansni_racuni = cursor.fetchall()

            # 🎨 Postavljanje fontova
            font_stavke = QFont()
            font_stavke.setPointSize(8)

            font_header = QFont()
            font_header.setPointSize(10)
            self.avansiTree.header().setFont(font_header)

            # Čišćenje stabla pre unosa novih podataka
            self.avansiTree.clear()

            for prvi_avans in prvi_avansni_racuni:
                item = QTreeWidgetItem(self.avansiTree, [str(i) for i in prvi_avans])

                for i in range(item.columnCount()):
                    item.setFont(i, font_stavke)
                    item.setForeground(i, QBrush(QColor("navy")))  # NAVY TEKST

                # 🔄 Rekurzivno dodaj SVE povezane račune pod prvi avans
                self.dodaj_racune_u_tree(item, prvi_avans[0], cursor, font_stavke)

            cursor.close()
            conn.close()

        except Exception as e:
            print(f"❌ Greška pri učitavanju računa u TreeWidget: {e}")

    def prikazi_stavke_racuna(self):
        """Prikazuje stavke selektovanog računa u tabeli stavkeRnTable."""
        try:
            # Dohvati selektovani red iz TreeWidget-a
            selected_item = self.avansiTree.currentItem()
            if not selected_item:
                print("⚠️ Nema selektovanog računa!")
                return

            # Broj fiskalnog računa (brracpu) je u prvoj koloni (indeks 0)
            brracpu = selected_item.text(0)
            #print(f"ℹ️ Selektovani račun: {brracpu}")

            # Konekcija na bazu
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # Dohvati podatke o računu iz kasasum
            cursor.execute(
                """
                SELECT god, sifobj, broj, tiptransakcije
                FROM "kasa"."kasasum"
                WHERE brracpu = %s
                """,
                (brracpu,)
            )
            kasasum_podaci = cursor.fetchone()
            
            if not kasasum_podaci:
                print("❌ Nema podataka u kasasum za ovaj račun!")
                return

            god, sifobj, broj, tiptransakcije = kasasum_podaci
            #print(f"🔍 Pronađen račun: GOD={god}, SIFOBJ={sifobj}, BROJ={broj}, TIPTRANSAKCIJE={tiptransakcije}")

            # Odredi vrstu prometa (8 = regularan avans, 9 = refundacija)
            vrsta_prometa = 8 if tiptransakcije == '0' else 9
            #print(f"🛒 Filtriranje stavki sa vrsta={vrsta_prometa}")

            # Dohvati stavke računa iz karticaart i pridruži artikle
            cursor.execute(
                """
                SELECT k.sifra, a.naziv, k.kolicina, k.cena, (k.kolicina * k.cena) AS ukupno, k.artikliid, k.tarifa,
                k.porez, k.porezproc, k.porezid, k.grupa
                FROM "kasa"."karticaart" k
                JOIN "kasa"."artikli" a ON k.sifra = a.sifra
                WHERE k.god = %s AND k.sifobj = %s AND k.broj = %s AND k.vrsta = %s
                ORDER BY k.sifra
                """,
                (god, sifobj, broj, vrsta_prometa)
            )
            rows = cursor.fetchall()
            #print(f"📊 Broj pronađenih stavki: {len(rows)}")

            # Zatvori konekciju
            cursor.close()
            conn.close()

            # Očisti tabelu pre unosa novih podataka
            self.stavkeRnTable.setRowCount(0)
            #print("🧹 Tabela očišćena")

            # Unesi podatke u tabelu
            for row_idx, row in enumerate(rows):
                #print(f"➕ Dodajem u tabelu: {row}")
                self.stavkeRnTable.insertRow(row_idx)
                for col_idx, value in enumerate(row):
                    self.stavkeRnTable.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

            #print("✅ Stavke uspešno prikazane!")
        
        except Exception as e:
            print(f"❌ Greška pri učitavanju stavki računa: {e}")

    # kopiranje stavki iz kasa u kasa1 pri formiranju racuna za refundaciju
    def kopiraj_stavke_u_kasa1(self):
        """Kopira stavke selektovanog računa iz kasa u kasa1 sa novim brojem računa (refundacija)."""
        try:
            # Provera da li postoji već generisan broj računa
            if not hasattr(self, 'trenutni_broj_racuna'):
                self.trenutni_broj_racuna = random.randint(int(KASA) * 1000, int(KASA) * 1999)
                print(f"🔢 Generisan novi broj računa: {self.trenutni_broj_racuna}")
            else:
                print(f"📌 Koristi se postojeći broj računa: {self.trenutni_broj_racuna}")

            # Dohvati selektovani red iz TreeWidget-a
            selected_item = self.avansiTree.currentItem()
            if not selected_item:
                print("⚠️ Nema selektovanog računa!")
                return

            brracpu = selected_item.text(0)

            # Konekcija na bazu
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # Dohvati podatke o računu iz kasasum
            cursor.execute(
                """
                SELECT god, sifobj, broj
                FROM "kasa"."kasasum"
                WHERE brracpu = %s
                """,
                (brracpu,)
            )
            kasasum_podaci = cursor.fetchone()
            
            if not kasasum_podaci:
                print("❌ Nema podataka u kasasum za ovaj račun!")
                return

            god, sifobj, stari_broj = kasasum_podaci
            novi_broj_racuna = self.trenutni_broj_racuna

            # Kopiraj stavke iz kasa u kasa1 sa novim brojem računa
            cursor.execute(
                """
                INSERT INTO "kasa"."kasa1" (sifra, sifobj, cena, datum, kolic, broj, kasa, smena, 
                                            cena2, popproc1, popdin1, popsum, god, kar, ststatus, 
                                            kreirao, sto, artikliid, tip)
                SELECT sifra, sifobj, cena, datum, kolic, %s, kasa, smena, 
                    cena2, popproc1, popdin1, popsum, god, kar, ststatus, 
                    'sistem', sto, artikliid, tip
                FROM "kasa"."kasa"
                WHERE god = %s AND sifobj = %s AND broj = %s
                """,
                (novi_broj_racuna, god, sifobj, stari_broj)
            )

            # Sačuvaj promene
            conn.commit()
            print(f"✅ Refundacija kreirana! Novi broj računa: {novi_broj_racuna}")

            # Zatvori konekciju
            cursor.close()
            conn.close()

        except Exception as e:
            print(f"❌ Greška pri kopiranju stavki u kasa1: {e}")

    # Funkcija koju koristim za refundaciju pojedinacnog avansa koji je uradjen sa greskom
    def proveri_i_refundiraj(self):
        """Proverava da li je račun podoban za refundaciju i prebacuje korisnika na stranicu refundacije."""
        try:
            # Dohvati selektovani red iz TreeWidget-a
            selected_item = self.avansiTree.currentItem()
            if not selected_item:
                print("⚠️ Nema selektovanog računa!")
                return

            brracpu = selected_item.text(0)  # PFR broj računa
            vreme_transakcije = selected_item.text(1)  # Vreme transakcije

            # Konekcija na bazu
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # Dohvati podatke o računu iz kasasum
            cursor.execute(
                """
                SELECT tipracuna, tiptransakcije, refbrracpu
                FROM "kasa"."kasasum"
                WHERE brracpu = %s
                """,
                (brracpu,)
            )
            kasasum_podaci = cursor.fetchone()

            if not kasasum_podaci:
                print("❌ Nema podataka u kasasum za ovaj račun!")
                return

            tipracuna, tiptransakcije, refbrracpu = kasasum_podaci

            # Debug ispis da vidimo šta baza vraća
            print(f"ℹ️ DEBUG: tipracuna={tipracuna}, tiptransakcije={tiptransakcije}, refbrracpu={refbrracpu}")

            # ❌ Koji računi NE MOGU da budu refundirani
            if (tipracuna == 0 and tiptransakcije == 0 and refbrracpu is not None) or \
            (tipracuna == 4 and tiptransakcije == 1):
                print("❌ Ovaj račun NE MOŽE biti refundiran!")
                return

            # ✅ Ako nije u gornjoj grupi, može biti refundiran
            print("✅ Ovaj račun može biti refundiran!")

            # Dohvati PIB iz tabele fvr
            cursor.execute("SELECT pib FROM \"kasa\".\"fvr\" LIMIT 1")
            pib_podaci = cursor.fetchone()
            oznaka_pib = pib_podaci[0] if pib_podaci else "N/A"

            # Postavljamo vrednosti u polja
            self.tipEdit_3.setText("10")  # Refundacija avansa sa greškom
            self.oznakaEdit_3.setText(oznaka_pib)  # PIB firme
            self.brrapuEdit_2.setText(brracpu)  # Povezivanje sa originalnim računom
            self.vremeTranEdit_2.setText(vreme_transakcije)  # Vreme transakcije originalnog računa

            # Kopiranje stavki u kasa1
            self.kopiraj_stavke_u_kasa1()

            # Prebacivanje na stranicu refundacije
            self.stackedWidget.setCurrentIndex(2)
            self.prikazi_stavke_refundacije()

            # Zatvori konekciju
            cursor.close()
            conn.close()

        except Exception as e:
            print(f"❌ Greška pri proveri refundacije: {e}")


    def prikazi_stavke_refundacije(self):
        """✅ Prikazuje stavke refundacije u stavkeTable_3"""
        self.stavkeTable_3.setRowCount(0)
        self.stavkeTable_3.clearContents()
        
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, sifra, 
                    (SELECT naziv FROM "kasa"."artikli" WHERE sifra = k.sifra) AS naziv, 
                    kolic, cena 
                FROM "kasa"."kasa1" k 
                WHERE sto = %s AND kasa = %s AND zatvoren = False
                ORDER BY id
                """,
                (self.aktivan_kupac, KASA)
            )
            rows = cursor.fetchall()

            for row in rows:
                row_count = self.stavkeTable_3.rowCount()
                self.stavkeTable_3.insertRow(row_count)
                for col, value in enumerate(row):
                    self.stavkeTable_3.setItem(row_count, col, QTableWidgetItem(str(value)))

            self.azuriraj_total()  # Ažuriranje ukupnog iznosa
            
            cursor.close()
            conn.close()

            print("✅ Stavke refundacije uspešno učitane!")

        except Exception as e:
            print(f"❌ Greška pri učitavanju stavki iz baze: {e}")

    # Pravljenje stavki za refundaciju koja predhodi izdavanju konacnog racuna
    # Koristi se rekurzivni upit za kumulativno sabiranje svih stavki
    def nadji_citav_lanac_avansa(self):
        try:
            selected_item = self.avansiTree.currentItem()
            if not selected_item:
                print("⚠️ Nijedan avans nije selektovan.")
                return

            pocetni_brracpu = selected_item.text(0)
            vreme_transakcije = selected_item.text(1)
            kodkupca = selected_item.text(5)
            oznakakupca = selected_item.text(6)

            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # Nađi sve račune u lancu, uključujući refundacije
            query = """
                WITH RECURSIVE lanac AS (
                    SELECT god, broj, brracpu, refbrracpu, datum, tiptransakcije
                    FROM kasa.kasasum
                    WHERE sifobj = %s AND brracpu = %s AND tipracuna = '4'

                    UNION ALL

                    SELECT ks.god, ks.broj, ks.brracpu, ks.refbrracpu, ks.datum, ks.tiptransakcije
                    FROM kasa.kasasum ks
                    INNER JOIN lanac l ON ks.brracpu = l.refbrracpu
                    WHERE ks.sifobj = %s AND ks.tipracuna = '4'
                )
                SELECT god, broj, brracpu, refbrracpu, datum, tiptransakcije
                FROM lanac
                ORDER BY datum DESC
            """
            cursor.execute(query, (SIFOBJEKTA, pocetni_brracpu, SIFOBJEKTA))
            rezultati = cursor.fetchall()

            if not rezultati:
                print("⚠️ Lanac nije pronađen.")
                return

            # 1. Pronađi sve refundacije u lancu
            refundisani_brracpu = set()
            for red in rezultati:
                _, _, brracpu, refbrracpu, _, tiptransakcije = red
                if tiptransakcije == 1 and refbrracpu:
                    refundisani_brracpu.add(refbrracpu)  # Originalni avans koji je refundiran
                    refundisani_brracpu.add(brracpu)     # I sam refundacioni račun

            # 2. Filtriraj samo validne avanse
            validni_avansi = [r for r in rezultati if r[2] not in refundisani_brracpu]

            # 3. Pronađi najnoviji avans iz preostalog lanca (po datumu i broju)
            poslednji_avans = max(validni_avansi, key=lambda x: (x[4], x[1]))  # x[4]=datum, x[1]=broj

            # 4. Skupi sve stavke validnih avansa
            zbirne_stavke = {}
            for red in validni_avansi:
                god, broj, brracpu, _, _, _ = red
                cursor.execute("""
                    SELECT sifra, cena
                    FROM kasa.kasa
                    WHERE god = %s AND sifobj = %s AND broj = %s
                """, (god, SIFOBJEKTA, broj))
                stavke = cursor.fetchall()

                for sifra, cena in stavke:
                    if sifra in zbirne_stavke:
                        zbirne_stavke[sifra] += cena
                    else:
                        zbirne_stavke[sifra] = cena

            # 5. Priprema za upis u kasa1
            if not hasattr(self, 'trenutni_broj_racuna'):
                self.trenutni_broj_racuna = random.randint(int(KASA) * 1000, int(KASA) * 1999)

            broj = self.trenutni_broj_racuna
            datum = datetime.now().date()
            kasa = int(KASA)
            smena = 1
            kar = 1
            ststatus = "A"
            sto = self.aktivan_kupac
            god = int(GODINA)

            for sifra, ukupno in zbirne_stavke.items():
                cursor.execute("""
                    INSERT INTO kasa.kasa1 (
                        sifra, sifobj, cena, datum, kolic, broj, kasa, smena, cena2,
                        popproc1, popdin1, popsum, god, kar, ststatus, kreirao,
                        sto, artikliid, tip
                    )
                    SELECT
                        a.sifra, %s, %s, %s, %s, %s, %s, %s, %s,
                        0, 0, 0, %s, %s, %s, 'sinhronizacija',
                        %s, a.artikliid, a.tip
                    FROM kasa.kasa a
                    WHERE a.sifra = %s AND a.sifobj = %s
                    LIMIT 1
                """, (
                    SIFOBJEKTA, ukupno, datum, 1, broj, kasa, smena, ukupno,
                    god, kar, ststatus, sto, sifra, SIFOBJEKTA
                ))

            conn.commit()
            print("\n✅ Uspešno snimljene zbirne stavke u kasa1.")

            # 6. Podesi podatke za refundaciju na osnovu poslednjeg validnog avansa
            self.tipEdit_3.setText(kodkupca)
            self.oznakaEdit_3.setText(oznakakupca)
            self.brrapuEdit_2.setText(poslednji_avans[2])  # brracpu
            self.vremeTranEdit_2.setText(vreme_transakcije)

            self.stackedWidget.setCurrentIndex(2)
            self.prikazi_stavke_refundacije()

            cursor.close()
            conn.close()

        except Exception as e:
            print("❌ Greška pri traženju lanca avansa:", e)


    # Refundacija snimanje u bazu i stampa
    def pripremi_placanja_refundacija(self):
        """
        Priprema podatke o plaćanju za refundaciju — uvek preko računa.
        """
        uplata = []
        try:
            iznos = float(self.totalEdit_3.text() or 0)
            if iznos > 0:
                uplata.append({"paymentType": "4", "amount": f"{iznos:.2f}"})
            else:
                print("⚠️ Iznos refundacije je nula ili nije validan.")
        except Exception as e:
            print(f"❌ Greška u pripremi refundacije: {e}")
        return uplata
    
    def snimi_racun_refundacije(self):
        """
        ✅ Snima refundaciju računa u baze: kasa, kasasum i karticaart.
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
            conn.autocommit = False  # Početak transakcije

            # Dohvatanje novog broja računa
            novi_broj_racuna = self.dohvati_broj_racuna()
            if novi_broj_racuna is None:
                raise Exception("Neuspešno generisanje broja refundiranog računa.")

            # Određivanje tipa računa i transakcije
            tipracuna = 4    # Avans
            tiptransakcije = 1  # Refundacija
            dokstatus = 'AR'   # Avans refundacija
            ui = 'u'

            # Dohvatanje podataka o kupcu i referentnom računu
            kodkupca = self.tipEdit_3.text().strip() if self.tipEdit_3.text() else None
            oznakakupca = self.oznakaEdit_3.text().strip() if self.oznakaEdit_3.text() else None
            referentni_racun = self.brrapuEdit_2.text().strip()  # Broj fiskalnog računa koji refundiramo
            vreme_referentnog = self.vremeTranEdit_2.text().strip()  # Vreme referentnog računa

            # Snimanje podataka iz `kasa1` u `kasa` (pozitivna količina)
            cursor.execute("""
            INSERT INTO "kasa"."kasa" 
            (god, kar, broj, sto, zatvoren, kasa, smena, sifra, kolic, cena, popproc1, popdin1, popsum, datum, sifobj, dokstatus, kreirao, artikliid, tip, cena2, ststatus)
            SELECT god, kar, %s, sto, TRUE, kasa, smena, sifra, ABS(kolic), cena, popproc1, popdin1, popsum, datum, sifobj, %s, 'sistem', artikliid, tip, cena2, ststatus
            FROM "kasa"."kasa1"
            WHERE zatvoren = FALSE AND kasa = %s AND sto = %s
            """, (novi_broj_racuna, dokstatus, int(KASA), self.aktivan_kupac))

            # Ažuriranje podataka u `kasa1` kao zatvorenih
            cursor.execute("""
            UPDATE "kasa"."kasa1"
            SET broj = %s, zatvoren = TRUE, kreirao = 'sistem'
            WHERE zatvoren = FALSE AND kasa = %s AND sto = %s
            """, (novi_broj_racuna, int(KASA), self.aktivan_kupac))

            # Snimanje podataka u `kasasum`
            cursor.execute("""
            INSERT INTO "kasa"."kasasum"
            (god, kar, broj, datum, kasa, sifobj, smena, vrfaktura, ukiznos, refundacija, idpartneri, kodkupca, oznakakupca, tipplacanja, tipracuna, tiptransakcije, dokstatus, refbrracpu, kreirao)
            VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, 'sistem')
            """, (
                int(GODINA), 1, novi_broj_racuna, int(KASA), SIFOBJEKTA, 1,
                round(float(self.totalEdit_3.text() or 0), 2),
                round(float(self.totalEdit_3.text() or 0), 2),
                round(float(self.totalEdit_3.text() or 0), 2),  # Refundacija
                kodkupca, oznakakupca,
                4 if float(self.totalEdit_3.text() or 0) > 0 else 0,
                tipracuna, tiptransakcije, dokstatus,
                referentni_racun
            ))

            # Snimanje podataka u `karticaart` (negativna količina)
            cursor.execute("""
            SELECT 
                k.sifra,
                k.cena,
                SUM(k.kolic) AS ukupna_kolicina,
                MAX(k.cena2) AS nabavna_cena,
                MAX(k.popproc1) AS rabat_proc,
                SUM(k.popsum) AS ukupna_vrednost,
                MAX(k.artikliid) AS artikli_id,
                MAX(a.robna_grupa_id) AS grupa,
                MAX(a.porez_id) AS porezid,
                MAX(p.tarifa) AS tarifa,
                MAX(p.stopa) AS stopa
            FROM "kasa"."kasa1" k
            LEFT JOIN "kasa"."artikli" a ON a.sifra = k.sifra
            LEFT JOIN "kasa"."porezi" p ON p.id = a.porez_id
            WHERE k.zatvoren = TRUE AND k.kasa = %s AND k.broj = %s
            GROUP BY k.sifra, k.cena
            """, (int(KASA), novi_broj_racuna))

            artikli = cursor.fetchall()

            for artikal in artikli:
                sifra, prodajna_cena, ukupna_kolicina, nabavna_cena, rabat_proc, ukupna_vrednost, artikli_id, grupa, porezid, tarifa, stopa = artikal

                # Računanje poreza
                preracunata_stopa = float((stopa * 100) / (stopa + 100)) if stopa else 0
                porez = round(float((prodajna_cena * preracunata_stopa / 100) * ukupna_kolicina), 2)

                cursor.execute("""
                INSERT INTO "kasa"."karticaart"
                (god, kar, broj, sifra, cena, cenanabavna, kolicina, rabatproc, rabatdinarski, porez, porezproc, tarifa, grupa, vrsta, dokstatus, datum, opis, artikliid, sifobj, lokacija_id, porezid, ui, kasa, idpartneri, kreirao, kreirano)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, NULL, 'sistem', CURRENT_TIMESTAMP)
                """, (
                    GODINA, 1, novi_broj_racuna, sifra, round(prodajna_cena, 2), round(nabavna_cena, 2), -round(ukupna_kolicina, 3),
                    round(rabat_proc, 2), round(ukupna_vrednost, 2), porez, stopa, tarifa, grupa,
                    9, dokstatus,
                    "Fiskalni račun AR", artikli_id, SIFOBJEKTA, self.glavna_lokacija_id, porezid, ui, int(KASA)
                ))
                
                sifra, prodajna_cena, ukupna_kolicina, *_ = artikal
                #self.azuriraj_zalihe(sifra, ukupna_kolicina, dodaj=True)  # Vraćamo robu na zalihu

            conn.commit()
            print(f"✅ Refundacija uspešno snimljena u bazi sa brojem {novi_broj_racuna}.")
            return novi_broj_racuna  # Vraćamo broj refundiranog računa

        except Exception as e:
            print(f"❌ Greška pri snimanju refundacije: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def pripremi_stavke_refundacije(self, lservis):
        stavke = []
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            for row in range(self.stavkeTable_3.rowCount()):
                sifra = self.stavkeTable_3.item(row, 1).text()
                naziv = self.stavkeTable_3.item(row, 2).text()
                kolicina = self.stavkeTable_3.item(row, 3).text()
                cena = self.stavkeTable_3.item(row, 4).text()

                # Dohvati jedinicu mere
                try:
                    cursor.execute("""
                        SELECT jm.jm
                        FROM "kasa"."artikli" a
                        JOIN "kasa"."jedmere" jm ON a.jedinica_mere_id = jm.id
                        WHERE a.sifra = %s
                    """, (sifra,))
                    result = cursor.fetchone()
                    jedinica_mere = result[0] if result else "N/A"
                except Exception as e:
                    print(f"❌ Greška pri preuzimanju jedinice mere za artikal {sifra}: {e}")
                    jedinica_mere = "N/A"

                naziv_sa_jedinicom = f"{naziv}/{jedinica_mere}"
                porez_slovo = "A" if lservis else "Ђ"

                # Dohvati porez
                try:
                    cursor.execute("""
                        SELECT p.slovo
                        FROM "kasa"."artikli" a
                        JOIN "kasa"."porezi" p ON a.porez_id = p.id
                        WHERE a.sifra = %s
                    """, (sifra,))
                    rezultat = cursor.fetchone()
                    if rezultat:
                        latinsko_slovo = rezultat[0]
                        porez_slovo = LATIN_TO_CYRILLIC_MAP.get(latinsko_slovo, "Ђ") if not lservis else "A"
                except Exception as e:
                    print(f"❌ Greška pri preuzimanju poreza za artikal {sifra}: {e}")

                stavke.append({
                    "name": naziv_sa_jedinicom,
                    "quantity": kolicina,
                    "unitPrice": cena,
                    "totalAmount": cena,
                    "labels": [porez_slovo]
                })

            return stavke

        except Exception as e:
            print(f"❌ Greška pri pripremi stavki za refundaciju avansnog računa: {e}")
            return []

        finally:
            if conn:
                conn.close()


    # Funkcija za pravljenje JSON fajla kojim se salje refundacija na fiskalizaciju
    def generisi_json_refundacija(self, broj_racuna, stavke, uplata, kasir, ip_stampe):
        """Generiše JSON fajl za fiskalizaciju refundacije."""
        try:
            godina = str(datetime.now().year)[-2:]
            direktorijum = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\to-sdc"
            json_fajl = os.path.join(direktorijum, f"CreateInvoice-{broj_racuna}-{godina}.json")
            racun = {
                "cashier": kasir,
                "invoiceNumber": "1161/1.0.128.0",
                "invoiceType": "4",
                "transactionType": "1",
                "referentDocumentNumber": self.brrapuEdit_2.text(),
                "referentDocumentDT": self.vremeTranEdit_2.text(),
                "buyerId": f"{self.tipEdit_3.text()}:{self.oznakaEdit_3.text()}",  # Obavezni podaci o kupcu
                "items": stavke,
                "payment": uplata,
                "journalOptions": {"print": "true", "message": "REFUNDACIJA AVANSA SE NE PREDAJE KUPCU"}
            }
            with open(json_fajl, "w", encoding="utf-8") as f:
                json.dump(racun, f, ensure_ascii=False, indent=4)
            #print(f"✅ JSON refundacije generisan: {json_fajl}")
            return json_fajl
        except Exception as e:
            print(f"❌ Greška pri generisanju JSON-a refundacije: {e}")
            return None

    def fiskalizuj_racun_refundacije(self):
        """Fiskalizuje refundirani račun i šalje ga PU."""
        try:
            # Učitavanje konfiguracije kase
            ip_stampe, lservis = self.main_window.ucitaj_konfiguraciju_kase()
            if not ip_stampe:
                raise Exception("IP adresa štampača nije pronađena u konfiguraciji.")

            # Snimanje refundiranog računa u bazu
            broj_racuna = self.snimi_racun_refundacije()
            if not broj_racuna:
                raise Exception("Generisanje broja refundiranog računa nije uspelo.")

            # Priprema podataka
            stavke = self.pripremi_stavke_refundacije(lservis)
            uplata = self.pripremi_placanja_refundacija()
            kasir = "Kasir 1"

            # Generisanje JSON-a i slanje na štampač
            json_fajl = self.generisi_json_refundacija(broj_racuna, stavke, uplata, kasir, ip_stampe)
            if not json_fajl:
                raise Exception("Generisanje JSON fajla za refundaciju nije uspelo.")

            # Čekanje na odgovor iz PU
            status, fajl_odgovora = self.main_window.obradi_odgovor(broj_racuna, ip_stampe)
            if status == "success":
                #print("✅ Refundacija uspešno fiskalizovana.")
                self.main_window.azuriraj_kasasum(broj_racuna, ip_stampe)
                #self.resetuj_kontrole()
            elif status == "error":
                print("❌ Greška pri fiskalizaciji refundacije. Proverite fajl sa greškom.")
            else:
                print("❌ Odgovor nije stigao u zadatom vremenu.")

        except Exception as e:
            print(f"❌ Greška pri fiskalizaciji refundacije: {e}")
