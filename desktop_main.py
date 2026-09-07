import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QListWidget, QListWidgetItem, QPushButton,
    QTableWidgetItem, QButtonGroup, QDialog, QMessageBox, QHeaderView, QStyledItemDelegate,
    QLineEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6 import uic
import psycopg2
import random
from datetime import datetime
import time
from dotenv import load_dotenv
import configparser
from functools import partial
from PyQt6.QtGui import QFont
from select_customer import SelectCustomerDialog
from racuniDialog import Ui_racuniDialog
from periodicni import PeriodicniDialog  # Importujemo klasu iz periodicni.py
from racuniDialog import RacuniDialog
from pazar import PazarDialog
from analiticki import AnalitickaDialog
from sinteticki import SintetickiDialog
from neobradjeni import NeobradjeniDialog
from nivelacija import NivelacijaDialog
from avans import AvansDialog
from artiklibu import ArtiklibuDialog
from refundirani_avansi import RefundiraniAvansDialog
from kep import KepDialog
from fakture import FaktureDialog
from partneri import PartneriDialog
from zalihe import ZaliheDialog
from cene import CeneDialog
import json
from PyQt6.QtGui import QAction
from functools import partial
import warnings



# 📌 Automatsko prepoznavanje apsolutne putanje
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path)

# ✅ Učitavanje konfiguracije
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)

GODINA = config.get('POS_Settings', 'god')
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')
KASA = config.get('POS_Settings', 'kasa')
PIN = config.get('POS_Settings', 'PIN')

GLAVNA_LOKACIJA_ID = None


def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )


def ucitaj_glavnu_lokaciju(conn, sifobj):
    """
    Vraća ID glavne aktivne lokacije za dati objekat.
    POS uvek radi sa glavnom lokacijom objekta.
    """
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id
            FROM kasa.lokacija
            WHERE sifobj = %s
              AND glavna = TRUE
              AND aktivna = TRUE
            LIMIT 1
        """, (sifobj,))
        row = cursor.fetchone()

    if not row:
        raise Exception(f"Nije pronađena glavna aktivna lokacija za objekat {sifobj}.")

    return row[0]


def inicijalizuj_glavnu_lokaciju():
    global GLAVNA_LOKACIJA_ID

    conn = None
    try:
        conn = get_db_connection()
        GLAVNA_LOKACIJA_ID = ucitaj_glavnu_lokaciju(conn, SIFOBJEKTA)
        #print(f"✅ Glavna lokacija za objekat {SIFOBJEKTA}: {GLAVNA_LOKACIJA_ID}")
    finally:
        if conn:
            conn.close()

################################################################

LATIN_TO_CYRILLIC_MAP = {
        "A": "А", #"\u0410",  # А - Nije u PDV
        "G": "Г", #"\u0413",  # Г - Bez PDV
        "Đ": "Ђ", #"\u0402",  # Ђ - Opšta stopa (20%)
        "E": "Е" #"\u0415",  # Е - Posebna stopa (10%)
    }


# Funkcija za slanje pina
def salji_pin():
    """
    Funkcija za slanje PIN-a za bezbednosni element.
    """
    try:
        # Učitavanje IP adrese i konfiguracije PIN-a
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        cursor = conn.cursor()
        cursor.execute("SELECT ipstampe FROM \"kasa\".\"confkasa\" WHERE kasa = %s AND sifobj = %s", (KASA, SIFOBJEKTA))
        result = cursor.fetchone()
        ip_stampe = result[0] if result else None
        conn.close()

        if not ip_stampe:
            raise ValueError("❌ IP adresa nije pronađena u konfiguraciji.")

        pin = PIN  # PIN iz konfiguracije

        # Generisanje putanje
        base_path = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\to-sdc"
        if not os.path.exists(base_path):
            os.makedirs(base_path)

        # Provera da li fajl već postoji
        today_str = datetime.now().strftime("%Y%m%d")
        json_file_path = os.path.join(base_path, f"VerifyPin-{today_str}.json")
        if os.path.exists(json_file_path):
            os.remove(json_file_path)

        # Generisanje sadržaja JSON fajla
        pin_data = json.dumps(pin, ensure_ascii=False)

        # Pisanje u fajl
        with open(json_file_path, "w", encoding="utf-8") as f:
            f.write(pin_data)

        #print(f"✅ PIN je uspešno poslat: {json_file_path}")

    except Exception as e:
        print(f"❌ Greška prilikom slanja PIN-a: {e}")
        
################################################################
# Stampe izvestaja presek stanja, dnevni i periodicni izvestaj
# Presek stanja
def stampaj_presek_stanja(ip_stampe):
    if not ip_stampe:
        print("❌ IP štampača nije pronađen. Prekidam postupak.")
        return
    
    # Kreiranje putanje za JSON fajl
    direktorijum = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\to-sdc"
    if not os.path.exists(direktorijum):
        print(f"❌ Direktorijum ne postoji: {direktorijum}")
        return

    # Kreiranje naziva fajla sa datumom i vremenom
    sada = datetime.now()
    presek_vreme = f"Presek {sada.strftime('%Y-%m-%d-%H-%M')}"
    json_fajl = os.path.join(direktorijum, f"GetReport-{presek_vreme}.json")

    # Kreiranje JSON sadržaja
    podaci = {
        "reportType": "Daily",
        "closeDay": False
    }

    # Upisivanje JSON podataka u fajl
    try:
        with open(json_fajl, "w", encoding="utf-8") as f:
            json.dump(podaci, f, indent=4)
        print(f"✅ Presek stanja uspešno sačuvan: {json_fajl}")
    except Exception as e:
        print(f"❌ Greška pri upisu JSON fajla: {e}")

# Dnevni izvestaj
def stampaj_dnevni_izvestaj(ip_stampe):
    if not ip_stampe:
        print("❌ IP štampača nije pronađen. Prekidam postupak.")
        return
    
    # Kreiranje putanje za JSON fajl
    direktorijum = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\to-sdc"
    if not os.path.exists(direktorijum):
        print(f"❌ Direktorijum ne postoji: {direktorijum}")
        return

    # Kreiranje naziva fajla sa datumom i vremenom
    sada = datetime.now()
    dnevni_vreme = f"Dnevni {sada.strftime('%Y-%m-%d-%H-%M')}"
    json_fajl = os.path.join(direktorijum, f"GetReport-{dnevni_vreme}.json")

    # Kreiranje JSON sadržaja
    podaci = {
        "reportType": "Daily",
        "closeDay": True
    }

    # Upisivanje JSON podataka u fajl
    try:
        with open(json_fajl, "w", encoding="utf-8") as f:
            json.dump(podaci, f, indent=4)
        print(f"✅ Dnevni izveštaj uspešno sačuvan: {json_fajl}")
    except Exception as e:
        print(f"❌ Greška pri upisu JSON fajla: {e}")

class EditableDelegate(QStyledItemDelegate):
    def __init__(self, parent, editabilna_kolona):
        super().__init__(parent)
        self.parent = parent
        self.editabilna_kolona = editabilna_kolona

    def createEditor(self, parent, option, index):
        # Omogućavanje uređivanja samo u modu "refundacija" za kolonu "Količina"
        if self.parent.aktivan_mod == "refundacija" and index.column() == self.editabilna_kolona:
            return super().createEditor(parent, option, index)
        return None

class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()

        inicijalizuj_glavnu_lokaciju()

        # 📌 Učitavanje UI fajla
        ui_path = os.path.join(BASE_DIR, "ui", "main_window.ui")
        uic.loadUi(ui_path, self)

        if __name__ == "__main__":
            from login import LoginDialog
            app = QApplication(sys.argv)
            app.setStyle("Fusion")
            app.setFont(QFont("Segoe UI", 10))

            qss_path = os.path.join(os.path.dirname(__file__), "style.qss")

            with open(qss_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())

            from login import LoginDialog  # Ova import ostaje

            login = LoginDialog()
            if login.exec():
                from desktop_main import MainWindow
                window = MainWindow()
                window.showMaximized()
                sys.exit(app.exec())
            else:
                sys.exit()
        
        # Provera da li stavka actionPIN postoji
        if not hasattr(self, 'actionPIN'):
            print("❌ Stavka 'actionPIN' nije pronađena u UI fajlu.")
            return

        # Povezivanje stavke iz menija sa funkcijom
        self.actionPIN.triggered.connect(salji_pin)

        # Automatsko slanje PIN-a pri inicijalizaciji prozora
        salji_pin()
        
        # Pokretanje funkcije za stampu preseka stanja, dnevnog izvestaja, periodicnog izvestaja iz menija
        self.actionPresek_stanja.triggered.connect(self.napravi_presek_stanja)
        self.actionDnevni_izvestaj.triggered.connect(self.napravi_dnevni_izvestaj)
        self.actionPeriodicni_izvestaj.triggered.connect(self.otvori_periodicni_dialog)
        self.actionPIN.triggered.connect(self.ponovo_posalji_pin)
        
        #####################################################################################
        # Meni Ostalo
        self.actionFaktura.triggered.connect(self.otvori_fakture_dialog)
        self.actionAvans.triggered.connect(self.otvori_avans_dialog)
        self.actionPregled_pazara.triggered.connect(self.otvori_pazar_dialog)
        self.actionAnalitika.triggered.connect(self.otvori_analiticki_dialog)
        self.actionSintetika.triggered.connect(self.otvori_sinteticki_dialog)
        self.actionNeobradjeni.triggered.connect(self.otvori_neobradjeni_dialog)
        self.actionKEP.triggered.connect(self.otvori_kep_dialog)
        self.actionNivelacija.triggered.connect(self.otvori_nivelacija_dialog)
        self.actionArtiklibu.triggered.connect(self.otvori_artiklibu_dialog)
        self.actionZalihe.triggered.connect(self.otvori_zalihe_dialog)
        self.actionCene.triggered.connect(self.otvori_cene_dialog)
        
        # 📌 Primena stilizacije menija
        self.stilizuj_meni()
        
        # Povezivanje dugmeta sa funkcijom
        self.btnIzaberiKupca.clicked.connect(self.open_select_customer_dialog)
        self.brisiKupcaBtn.clicked.connect(self.clear_customer_fields)
        
        # ✅ Inicijalizacija broja računa
        self.trenutni_broj_racuna = random.randint(int(KASA) * 1000, int(KASA) * 1999)

        # ✅ Inicijalizacija liste predloga BEZ STILIZACIJE
        self.suggestions_list = QListWidget(self)
        self.suggestions_list.setStyleSheet('background-color:#F0E9E9')
        self.suggestions_list.hide()
        self.suggestions_list.itemClicked.connect(self.artikal_izabran)
        ###############################################################
        # Postavljanje dugmadi za izbor kupca i pozivanje stilizacije
        
        # ✅ Postavljanje inicijalnog kupca PRE POZIVA stilizacije
        self.aktivan_kupac = 1
        
        # ✅ Inicijalizacija QButtonGroup i povezivanje signala
        self.button_group = QButtonGroup(self)
        self.button_group.addButton(self.btnKupac1, 1)
        self.button_group.addButton(self.btnKupac2, 2)
        self.button_group.addButton(self.btnKupac3, 3)

        # ✅ Korektno povezivanje signala
        self.button_group.buttonClicked.connect(lambda button: self.postavi_aktivnog_kupca(self.button_group.id(button)))
        
        # ✅ Postavljanje inicijalnog moda prometa
        self.aktivan_mod = "promet"
        self.btnPromet.clicked.connect(lambda: self.postavi_aktivan_mod("promet"))
        ip_stampe, lservis = self.ucitaj_konfiguraciju_kase()
        self.btnRefundacija.clicked.connect(lambda: self.postavi_aktivan_mod("refundacija"))
        self.btnRefundacija.clicked.connect(self.otvori_racuni_dialog)
        self.azuriraj_vidljivost_puFrame()
        self.stavkeTable.itemChanged.connect(self.azuriraj_kolicinu)
        self.btnAvans.clicked.connect(lambda: self.postavi_aktivan_mod("avans"))
        self.btnAvans.clicked.connect(self.otvori_refundirani_avansi)

        # ✅ Stilizacija nakon povezivanja signala
        self.stilizuj_dugmad_kupaca()
        self.stilizuj_dugmad_modova()
        ###############################################################
        
        # ✅ Stilizacija numeričkih polja
        self.kolicinaEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.zalihaEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.cenaEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.procPopEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.popustEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.iznosEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.popCeoRnEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.procPopEdit.focusInEvent = self.selektuj_tekst_u_fokusu(self.procPopEdit)
        self.iznosEdit.focusInEvent = self.selektuj_tekst_u_fokusu(self.iznosEdit)
        self.label_3.setHidden(True)
        self.popCeoRnEdit.setHidden(True)
        self.gotovinaEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.karticaEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.cekEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.racunEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.totalEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.ostPopEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.kusurEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        # Kontrole za izradu konacnog racuna kod avansa
        self.iznosRefundacijeEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.iznosRefundacijeEdit.setHidden(True)
        self.poslednjiAvansEdit.setHidden(True)
        
        # ✅ Stilizacija tabele (font samo za podatke u tabeli)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        self.stavkeTable.setFont(font)
        self.stavkeTable.horizontalHeader().setFont(font)
        
        # ✅ Automatsko prilagođavanje širine kolona
        self.stavkeTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)  # Šifra
        self.stavkeTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)      # Naziv
        self.stavkeTable.horizontalHeader().setStretchLastSection(False)
        
        # ✅ Sakrivanje kolone ID
        self.stavkeTable.setColumnHidden(0, True)

        # ✅ Povezivanje signala
        self.sifraEdit.textChanged.connect(self.pretrazi_artikle)
        self.btnReset.clicked.connect(self.obrisi_unos)
        self.kolicinaEdit.textChanged.connect(self.validacija_kolicine)
        self.kolicinaEdit.textChanged.connect(self.azuriraj_iznos_automatski)
        self.procPopEdit.editingFinished.connect(self.izracunaj_popust)
        self.iznosEdit.editingFinished.connect(self.azuriraj_popust_iz_iznosa)
        # Potvrda kolicine 1 bez prekucavanja
        self.kolicinaEdit.returnPressed.connect(self.potvrdi_kolicinu)
        
        # ✅ Dodato prebacivanje fokusa
        self.kolicinaEdit.returnPressed.connect(self.pozicioniraj_na_popust)
        self.procPopEdit.returnPressed.connect(self.pozicioniraj_na_iznos)
        self.iznosEdit.returnPressed.connect(self.pozicioniraj_na_korpa)
        
        # ✅ Dugme za zatvaranje aplikacije
        self.btnKraj.clicked.connect(self.zatvori_aplikaciju)
        self.btnKorpa.clicked.connect(self.dodaj_u_kasa1)  # Povezivanje sa bazom podataka
        
        ####################################################################################
        # Inicijalne postavke za dugme Stampa
        # ✅ Povezivanje signala za praćenje promena u poljima plaćanja
        self.gotovinaEdit.textChanged.connect(self.proveri_placanje)
        self.karticaEdit.textChanged.connect(self.proveri_placanje)
        self.cekEdit.textChanged.connect(self.proveri_placanje)
        self.racunEdit.textChanged.connect(self.proveri_placanje)

        # ✅ Početno stanje dugmeta
        self.btnStampa.setEnabled(False)
        
        # ✅ Povezivanje dugmeta 'btnStampa' sa funkcijom 'snimi_racun'
        #self.btnStampa.clicked.connect(self.snimi_racun)
        #self.btnStampa.clicked.connect(self.fiskalizuj_korpu)
        self.btnStampa.clicked.connect(self.izvrsi_stampu)
        ####################################################################################

        # ✅ Test konekcije
        self.test_db_connection()

        # ✅ Učitavanje konfiguracije popusta
        self.ucitaj_konfiguraciju_popusta()
        
        # ✅ Učitavanje konfiguracije kase
        self.ucitaj_konfiguraciju_kase()
        
        # ✅ Automatsko učitavanje stavki za podrazumevanog kupca
        self.ucitaj_stavke_iz_baze()
        
    #########################################################    
    def napravi_presek_stanja(self):
        ip_stampe, _ = self.ucitaj_konfiguraciju_kase()
        stampaj_presek_stanja(ip_stampe)
            
    def napravi_dnevni_izvestaj(self):
        ip_stampe, _ = self.ucitaj_konfiguraciju_kase()
        stampaj_dnevni_izvestaj(ip_stampe)
        
    def otvori_periodicni_dialog(self):
        ip_stampe, _ = self.ucitaj_konfiguraciju_kase()
        if not ip_stampe:
            print("❌ IP štampača nije pronađen.")
            return
        
        dialog = PeriodicniDialog(self, ip_stampe)
        dialog.exec()  # Prikaz dijaloga
        
    def ponovo_posalji_pin(self):
        salji_pin()
        print("✅ PIN je ponovo poslat.")
        
    #########################################################
    # Otvaranje dialoga iz menija
    def otvori_fakture_dialog(self):
        """Otvara dijalog za formiranje faktura."""
        self.fakture_dialog = FaktureDialog(self)  # Kreiraj instancu dijaloga
        self.fakture_dialog.exec()  # Prikazi dijalog modalno

    def otvori_pazar_dialog(self):
        """Otvara dijalog za pregled pazara."""
        self.pazar_dialog = PazarDialog(self)  # Kreiraj instancu dijaloga
        self.pazar_dialog.exec()  # Prikazi dijalog modalno

    def otvori_analiticki_dialog(self):
        """Otvara dijalog za analiticki izvestaj o prodatim artiklima."""
        self.analiticki_dialog = AnalitickaDialog(self)  # Kreiraj instancu dijaloga
        self.analiticki_dialog.exec()  # Prikazi dijalog modalno

    def otvori_sinteticki_dialog(self):
        """Otvara dijalog za analiticki izvestaj o prodatim artiklima."""
        self.sinteticki_dialog = SintetickiDialog(self)  # Kreiraj instancu dijaloga
        self.sinteticki_dialog.exec()  # Prikazi dijalog modalno

    def otvori_neobradjeni_dialog(self):
        """Otvara dijalog za neobradjene racune koji nisu dobili PFR broj."""
        self.neobradjeni_dialog = NeobradjeniDialog(self)  # Kreiraj instancu dijaloga
        self.neobradjeni_dialog.exec()  # Prikazi dijalog modalno

    def otvori_avans_dialog(self):
        """Otvara dijalog za avansne racune."""
        self.avansni_dialog = AvansDialog(self)  # Kreiraj instancu dijaloga
        self.avansni_dialog.exec()  # Prikazi dijalog modalno

    def otvori_kep_dialog(self):
        """Otvara dijalog za KEP knjigu."""
        self.kep_dialog = KepDialog(self)  # Kreiraj instancu dijaloga
        self.kep_dialog.exec()  # Prikazi dijalog modalno

    def otvori_nivelacija_dialog(self):
        """Otvara dijalog za nivelaciju."""
        self.nivelacija_dialog = NivelacijaDialog(self)  # Kreiraj instancu dijaloga
        self.nivelacija_dialog.exec()  # Prikazi dijalog modalno

    def otvori_artiklibu_dialog(self):
        """Otvara dijalog za brzi unos artikala."""
        self.artiklibu_dialog = ArtiklibuDialog(self)  # Kreiraj instancu dijaloga
        self.artiklibu_dialog.exec()  # Prikazi dijalog modalno

    def otvori_zalihe_dialog(self):
        """Otvara dijalog za stanje zaiha."""
        self.zalihe_dialog = ZaliheDialog(self)  # Kreiraj instancu dijaloga
        self.zalihe_dialog.exec()  # Prikazi dijalog modalno

    def otvori_cene_dialog(self):
        """Otvara dijalog za izmenu cena."""
        self.cene_dialog = CeneDialog(self)  # Kreiraj instancu dijaloga
        self.cene_dialog.exec()  # Prikazi dijalog modalno
    
    #########################################################
    #########################################################
    ### Otvaranje dijaloga za refundirane avanse kod izrade konacnog racuna
    def otvori_refundirani_avansi(self):
        """Otvara dijalog za refundirane avanse kod izrade konacnog racuna."""
        self.refundirani_dialog = RefundiraniAvansDialog(self)  # Kreiraj instancu dijaloga
        self.refundirani_dialog.exec()  # Prikazi dijalog modalno
    #########################################################
    #Stilizuj meni i njegove stavke
    def stilizuj_meni(self):
        """Stilizuje meni i njegove stavke."""
        menu_style = """
            QMenu {
                background-color: #e3e7f1; /* Pozadina menija */
                color: black; /* Boja teksta */
                border: 1px solid #52688f; /* Okvir */
            }
            QMenu::item {
                background-color: transparent; /* Transparentna pozadina stavki */
                color: black; /* Boja teksta stavki */
                padding: 5px 20px; /* Unutrašnja margina */
            }
            QMenu::item:selected {
                background-color: #52688f; /* Boja pozadine na hover */
                color: white; /* Boja teksta na hover */
                font-weight: bold; /* Bold tekst */
            }
        """
        self.setStyleSheet(menu_style)

    #########################################################
        
    ######################################################
    # Ukoliko je inicijalno izabran kupac promenjen i stilizacija dugmadi kupca
    def postavi_aktivnog_kupca(self, broj_kupca):
        """✅ Postavljanje aktivnog kupca i ažuriranje stila."""
        self.aktivan_kupac = broj_kupca
        self.stilizuj_dugmad_kupaca()
        self.ucitaj_stavke_iz_baze()

    def stilizuj_dugmad_kupaca(self):
        default_style = """
            QPushButton {
                background-color: #e3e7f1;
                color: white;
                border-style: outset;
                border-width: 4px;
                border-radius: 10px;
                border-color: #4c6084;
                padding: 10px;
            }
        """
        active_style = """
            QPushButton {
                background-color: #FF5733;
                color: white;
                border-style: outset;
                border-width: 4px;
                border-radius: 10px;
                border-color: red;
                padding: 10px;
            }
        """

        for button in [self.btnKupac1, self.btnKupac2, self.btnKupac3]:
            button.setStyleSheet(default_style)

        active_button = self.button_group.button(self.aktivan_kupac)
        if active_button:
            active_button.setStyleSheet(active_style)
            
    #################################################################
    
    ######################################################
    # Inicijalno izabrano je dugme prometa i stilovi tih dugmadi
    def postavi_aktivan_mod(self, mod):
        self.aktivan_mod = mod

        self.brrnpuEdit.clear()
        self.vremeTransEdit.clear()
        self.tipEdit.clear()
        self.kupacEdit.clear()
        self.poslednjiAvansEdit.clear()
        self.iznosRefundacijeEdit.clear()
        
        self.stilizuj_dugmad_modova()
        self.azuriraj_vidljivost_puFrame()
        self.postavi_stavkeTable_editabilnost()

        if mod == "refundacija":
            self.stavkeTable.itemChanged.connect(self.azuriraj_kolicinu)
            self.sifraEdit.setEnabled(False)
            self.kolicinaEdit.setEnabled(False)
            self.procPopEdit.setEnabled(False)
            self.iznosEdit.setEnabled(False)
            self.btnKorpa.setEnabled(False)

        elif mod == "avans":
            self.stavkeTable.itemChanged.connect(self.azuriraj_kolicinu)
            self.sifraEdit.setEnabled(True)
            self.kolicinaEdit.setEnabled(True)
            self.procPopEdit.setEnabled(True)
            self.iznosEdit.setEnabled(True)
            self.btnKorpa.setEnabled(True)

        else:  # promet
            self.stavkeTable.itemChanged.disconnect(self.azuriraj_kolicinu)
            self.sifraEdit.setEnabled(True)
            self.kolicinaEdit.setEnabled(True)
            self.procPopEdit.setEnabled(True)
            self.iznosEdit.setEnabled(True)
            self.btnKorpa.setEnabled(True)
        
    def azuriraj_vidljivost_puFrame(self):
        """Ažurira vidljivost `puFrame` na osnovu aktivnog moda."""
        if self.aktivan_mod in ["refundacija", "avans"]:
            self.puFrame.setVisible(True)
        else:
            self.puFrame.setVisible(False)
    
    def stilizuj_dugmad_modova(self):
        default_style = """
            QPushButton {
                background-color: #e3e7f1;
                color: black;
                border-style: outset;
                border-width: 4px;
                border-radius: 10px;
                border-color: #4c6084;
                padding: 10px;
            }
        """
        active_style = """
            QPushButton {
                background-color: #FF5733;
                color: white;
                border-style: outset;
                border-width: 4px;
                border-radius: 15px;
                border-color: red;
                padding: 10px;
            }
        """
        self.btnPromet.setStyleSheet(default_style if self.aktivan_mod != "promet" else active_style)
        self.btnRefundacija.setStyleSheet(default_style if self.aktivan_mod != "refundacija" else active_style)
        self.btnAvans.setStyleSheet(default_style if self.aktivan_mod != "avans" else active_style) 

    ######################################################
        
    def zatvori_aplikaciju(self):
        self.close()
    # Selekcija cele vrednosti u popustima
    def selektuj_tekst_u_fokusu(self, line_edit):
        def event_handler(event):
            QLineEdit.focusInEvent(line_edit, event)
            QTimer.singleShot(0, line_edit.selectAll)
        return event_handler
        
    def ucitaj_konfiguraciju_popusta(self):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            query = """
            SELECT popdane FROM "kasa"."confkasa"
            WHERE kasa = %s AND sifobj = %s
            """

            cursor.execute(query, (KASA, SIFOBJEKTA))
            result = cursor.fetchone()

            if result is not None and result[0]:
                self.popustFrame.setVisible(True)
            else:
                self.popustFrame.setVisible(False)


            cursor.close()
            conn.close()
        except Exception as e:
            print(f"❌ Greška pri učitavanju konfiguracije kase: {e}")
            self.popustFrame.setVisible(False)
            
    def pozicioniraj_na_iznos(self):
        self.iznosEdit.setFocus()
            
    def pozicioniraj_na_popust(self):
        if self.popustFrame.isVisible():
            self.procPopEdit.setFocus()
            kolicina = float(self.kolicinaEdit.text() or 0)
            cena = float(self.cenaEdit.text() or 0)
            self.iznosEdit.setText(f"{kolicina * cena:.2f}")
        else:
            self.btnKorpa.setFocus()
            
    def pozicioniraj_na_korpa(self):
        self.btnKorpa.setFocus()
        
    def validacija_kolicine(self):
        """✅ Validacija i automatsko postavljanje količine."""
        jm = self.jmEdit.text().strip().lower()
        text = self.kolicinaEdit.text().strip()

        if jm in ['kom', 'komad']:
            # Dozvoljen unos samo celobrojnih vrednosti
            if not text.isdigit() or text == "":
                self.kolicinaEdit.setText("1")
        else:
            # Dozvoljen unos decimalnih brojeva sa 3 decimale
            try:
                float(text)
            except ValueError:
                if text not in ("", "."):
                    self.kolicinaEdit.setText("1.000")
                    
    def potvrdi_kolicinu(self):
        """✅ Potvrda unete količine i premeštanje fokusa."""
        self.validacija_kolicine()  # Osigurava validaciju unete količine
        if self.popustFrame.isVisible():
            self.procPopEdit.setFocus()  # Fokus na polje za popust ako je vidljivo
        else:
            self.btnKorpa.setFocus()  # Inače fokus na dugme za dodavanje u korpu
                    
    def azuriraj_iznos_automatski(self):
        try:
            kolicina = float(self.kolicinaEdit.text()) if self.kolicinaEdit.text() else 0
            cena = float(self.cenaEdit.text()) if self.cenaEdit.text() else 0
            self.iznosEdit.setText(f"{kolicina * cena:.2f}")
        except ValueError:
            self.iznosEdit.setText("0.00")
                    
    def izracunaj_popust(self):
        try:
            proc_popust = float(self.procPopEdit.text() or 0)
            kolicina = float(self.kolicinaEdit.text())
            cena = float(self.cenaEdit.text())

            iznos = kolicina * cena
            if proc_popust == 0:
                self.popustEdit.setText("0.00")
                self.iznosEdit.setText(f"{iznos:.2f}")
            else:
                popust_iznos = iznos * (proc_popust / 100)
                ukupno_za_placanje = iznos - popust_iznos

                self.popustEdit.setText(f"{popust_iznos:.2f}")
                self.iznosEdit.setText(f"{ukupno_za_placanje:.2f}")
        except ValueError:
            self.popustEdit.setText("0.00")
            self.iznosEdit.setText("0.00")
            self.popCeoRnEdit.setText("0.00")
    
    def azuriraj_popust_iz_iznosa(self):
        try:
            kolicina = float(self.kolicinaEdit.text())
            cena = float(self.cenaEdit.text())
            iznos_unet = float(self.iznosEdit.text())

            iznos = kolicina * cena
            if iznos_unet == iznos:
                self.procPopEdit.setText("0.0000")
                self.popustEdit.setText("0.00")
            else:
                popust_iznos = iznos - iznos_unet
                proc_popust = (popust_iznos / iznos) * 100

                self.procPopEdit.setText(f"{proc_popust:.4f}")
                self.popustEdit.setText(f"{popust_iznos:.2f}")
        except ValueError:
            self.procPopEdit.setText("0.0000")
            self.popustEdit.setText("0.00")
            self.popCeoRnEdit.setText("0.00")

    def obrisi_unos(self):
        """✅ Resetovanje polja i skrivanje liste."""
        self.clear_fields()
        self.suggestions_list.hide()
        self.sifraEdit.setFocus()

    def clear_fields(self):
        self.sifraEdit.clear()
        self.nazivEdit.clear()
        self.jmEdit.clear()
        self.kolicinaEdit.clear()
        self.zalihaEdit.clear()
        self.cenaEdit.clear()
        self.procPopEdit.clear()
        self.popustEdit.clear()
        self.iznosEdit.clear()
        self.popCeoRnEdit.clear()

    def test_db_connection(self):
        """✅ Test konekcije sa bazom."""
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            #print("✅ Uspešna konekcija sa bazom!")
            conn.close()
        except Exception as e:
            print(f"❌ Greška pri konekciji: {e}")

    def pretrazi_artikle(self):
        """✅ Pretraga artikala (šifra, naziv, barkod)."""
        search_text = self.sifraEdit.text().strip()
        if not search_text or len(search_text) < 2:
            self.suggestions_list.hide()
            return

        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # ✅ SQL upit bez DISTINCT i sa delimičnim poklapanjem
            query = """
            SELECT a.sifra, a.naziv, COALESCE(b.barkod, '')
            FROM "kasa"."artikli" a
            LEFT JOIN "kasa"."barkodovi" b ON a.id = b.artikli_id
            WHERE a.sifra ILIKE %s 
               OR a.naziv ILIKE %s 
               OR b.barkod ILIKE %s
            LIMIT 20;
            """
            cursor.execute(query, (f"%{search_text}%", f"%{search_text}%", f"%{search_text}%"))
            results = cursor.fetchall()

            # ✅ Punjenje liste predloga
            self.suggestions_list.clear()
            self.suggestions_list.clear()
            if results:
                for res in results:
                    item_text = f"{res[0]} - {res[1]} ({res[2]})"
                    self.suggestions_list.addItem(QListWidgetItem(item_text))

                edit_pos = self.sifraEdit.mapToGlobal(self.sifraEdit.rect().bottomLeft())
                self.suggestions_list.move(edit_pos.x(), edit_pos.y())
                self.suggestions_list.resize(max(400, self.sifraEdit.width()), 200)
                self.suggestions_list.show()
                self.suggestions_list.setCurrentRow(0)
            else:
                self.suggestions_list.hide()

            cursor.close()
            conn.close()

        except Exception as e:
            print(f"❌ Greška pri pretrazi: {e}")

    def artikal_izabran(self, item):
        """✅ Izbor artikla klikom ili Enter-om."""
        if item:
            sifra_izabrana = item.text().split(" - ")[0].strip()
            self.sifraEdit.setText(sifra_izabrana)
            self.ucitaj_artikal_po_sifri(sifra_izabrana)
            self.suggestions_list.hide()

    def ucitaj_artikal_po_sifri(self, sifra):
        """✅ Učitavanje detalja artikla sa podrškom za tip=1 (roba), tip=2 (usluga), tip=3 (set)."""
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # Dohvati podatke o artiklu i njegov tip
            query = """
            SELECT a.sifra, a.naziv, jm.jm, a.tip, z.cena, z.zaliha
            FROM "kasa"."artikli" a
            LEFT JOIN "kasa"."zaliheart" z ON a.sifra = z.sifra AND z.god = %s AND z.sifobj = %s AND z.lokacija_id = %s
            LEFT JOIN "kasa"."jedmere" jm ON a.jedinica_mere_id = jm.id
            WHERE a.sifra = %s;
            """
            cursor.execute(query, (GODINA, SIFOBJEKTA, GLAVNA_LOKACIJA_ID, sifra))
            result = cursor.fetchone()

            if result:
                sifra_artikla, naziv, jm, tip, cena, zaliha = result
                self.trenutni_tip = tip  # čuvamo tip za keyPressEvent

                # tip 2 (usluge) nemaju zalihe
                if tip == 2:
                    zaliha = 0.0
                    self.cenaEdit.setEnabled(True)     # uključi polje ako je bilo onemogućeno u Qt Designeru
                    self.cenaEdit.setReadOnly(False)   # omogući unos cene
                    cena = 0.0                         # prazna cena, unosi korisnik
                else:
                    self.cenaEdit.setEnabled(True)
                    self.cenaEdit.setReadOnly(True)

                # tip 3 (set) → cena artikala iz tabele setsastav
                if tip == 3:
                    cursor.execute("""
                        SELECT SUM(cena * kolicina)
                        FROM "kasa"."setsastav"
                        WHERE sifra = %s
                    """, (sifra,))
                    set_cena = cursor.fetchone()[0]
                    cena = set_cena if set_cena else 0.0

                self.popuni_polja((sifra_artikla, naziv, jm, cena, zaliha), tip)

                # fokus nakon učitavanja
                if tip == 2:
                    self.cenaEdit.setFocus()
                    self.cenaEdit.selectAll()
                else:
                    self.kolicinaEdit.setFocus()
                    self.kolicinaEdit.selectAll()
            else:
                self.clear_fields()
                self.nazivEdit.setText("Nema rezultata")

            cursor.close()
            conn.close()

        except Exception as e:
            print(f"❌ Greška pri učitavanju artikla: {e}")

    def popuni_polja(self, result, tip_artikla=None):
        """✅ Popunjavanje polja sa podacima artikla."""
        sifra, naziv, jm, cena, zaliha = result
        self.sifraEdit.setText(sifra)
        self.nazivEdit.setText(naziv)
        self.jmEdit.setText(jm or "N/A")
        self.kolicinaEdit.setText("1")

        if tip_artikla == 2:
            # usluga → polje za cenu je editabilno i prazno
            self.cenaEdit.setEnabled(True)
            self.cenaEdit.setReadOnly(False)
            self.cenaEdit.setText("")
            self.cenaEdit.setFocus()
        else:
            # roba i set → cena zaključana
            self.cenaEdit.setEnabled(True)
            self.cenaEdit.setReadOnly(True)
            self.cenaEdit.setText(f"{(cena or 0):.2f}")
            self.kolicinaEdit.setFocus()
            self.kolicinaEdit.selectAll()

        self.zalihaEdit.setText(str(zaliha or 0))

    def keyPressEvent(self, event):
        """✅ Navigacija po listi i potvrda unosa + podrška za tip=2 (usluge)."""
        if self.suggestions_list.isVisible():
            if event.key() == Qt.Key.Key_Down:
                current_row = self.suggestions_list.currentRow()
                self.suggestions_list.setCurrentRow(min(current_row + 1, self.suggestions_list.count() - 1))
            elif event.key() == Qt.Key.Key_Up:
                current_row = self.suggestions_list.currentRow()
                self.suggestions_list.setCurrentRow(max(current_row - 1, 0))
            elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
                item = self.suggestions_list.currentItem()
                if item:
                    self.artikal_izabran(item)
        else:
            # Enter dok je fokus na dugmetu → klikni na njega
            if self.btnKorpa.hasFocus() and event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
                self.btnKorpa.click()
            # + znak dodaje artikal u korpu
            elif event.key() == Qt.Key.Key_Plus:
                self.dodaj_u_kasa1()
            # Ako je artikal tip = 2 → nakon unosa količine fokus ide na cenu
            elif hasattr(self, "trenutni_tip") and self.trenutni_tip == 2:
                if self.kolicinaEdit.hasFocus() and event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
                    self.cenaEdit.setEnabled(True)
                    self.cenaEdit.setReadOnly(False)
                    self.cenaEdit.setFocus()
                    self.cenaEdit.selectAll()
                    return
            else:
                super().keyPressEvent(event)
    
    #################################################################################################
    # Dodavanje artikla u bazu i prikaz u tabeli prozora, brisanje stavki i azuriranje totala    
    def dodaj_u_kasa1(self):
        try:
            # Validacija unosa
            sifra = self.sifraEdit.text().strip()
            if not sifra:
                print("❌ Greška: Nedostaje šifra artikla.")
                return

            try:
                kolicina = float(self.kolicinaEdit.text() or 0)
                if kolicina <= 0:
                    print("❌ Greška: Količina mora biti veća od 0.")
                    return
            except ValueError:
                print("❌ Greška: Neispravna količina.")
                return

            try:
                cena_bez_popusta = float(self.cenaEdit.text() or 0)
                if cena_bez_popusta <= 0:
                    print("❌ Greška: Cena mora biti veća od 0.")
                    return
            except ValueError:
                print("❌ Greška: Neispravna cena.")
                return

            # Preuzimanje artiklid i tip iz baze
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()
            cursor.execute("""SELECT id, tip FROM "kasa"."artikli" WHERE sifra = %s""", (sifra,))
            result = cursor.fetchone()
            if not result:
                print(f"❌ Greška: Artikal sa šifrom {sifra} nije pronađen.")
                return

            artiklid, tip = result

            # Popust
            proc_popust = float(self.procPopEdit.text() or 0)
            popust_iznos = round(cena_bez_popusta * proc_popust / 100, 2)
            cena_sa_popustom = round(cena_bez_popusta - popust_iznos, 2)

            sifobj = SIFOBJEKTA
            datum = datetime.now().date()
            kasa = int(KASA)
            god = int(GODINA)
            ststatus = "A"
            sto = self.aktivan_kupac

            # Ako je artikal SET (tip=3) → učitaj komponente
            if tip == 3:
                cursor.execute("""
                    SELECT s.sifraart, s.kolicina, s.cena, a.naziv
                    FROM "kasa"."setsastav" s
                    JOIN "kasa"."artikli" a ON s.sifraart = a.sifra
                    WHERE s.sifra = %s
                """, (sifra,))
                komponente = cursor.fetchall()

                for sifra_komp, kol_komp, cena_komp, naziv_komp in komponente:
                    ukupna_kolicina = kolicina * kol_komp
                    vrednost = round(ukupna_kolicina * cena_komp, 2)

                    cursor.execute("""
                        INSERT INTO "kasa"."kasa1"
                        (sifra, sifobj, cena, datum, kolic, broj, kasa, smena, 
                        cena2, popproc1, popdin1, popsum, god, kar, ststatus, 
                        kreirao, sto, artikliid, tip)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,
                                %s,%s,%s,%s,%s,%s,%s,
                                'sistem',%s,
                                (SELECT id FROM "kasa"."artikli" WHERE sifra = %s), 1)
                        RETURNING id
                    """, (sifra_komp, sifobj, cena_komp, datum, ukupna_kolicina,
                        self.trenutni_broj_racuna, kasa, 1, cena_komp, 0, 0, 0,
                        god, 1, ststatus, sto, sifra_komp))

                    inserted_id = cursor.fetchone()[0]
                    self.dodaj_u_korpu(inserted_id, sifra_komp, f"{naziv_komp} (SET)",
                                    ukupna_kolicina, cena_komp, 0,
                                    cena_komp, vrednost)
            else:
                # Standardan unos artikla (tip 1 ili 2)
                vrednost = round(cena_sa_popustom * kolicina, 2)
                cursor.execute("""
                    INSERT INTO "kasa"."kasa1"
                    (sifra, sifobj, cena, datum, kolic, broj, kasa, smena, 
                    cena2, popproc1, popdin1, popsum, god, kar, ststatus, 
                    kreirao, sto, artikliid, tip)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,
                            %s,%s,%s,%s,%s,%s,%s,
                            'sistem',%s,%s,%s)
                    RETURNING id
                """, (sifra, sifobj, cena_sa_popustom, datum, kolicina,
                    self.trenutni_broj_racuna, kasa, 1,
                    cena_bez_popusta, proc_popust, popust_iznos,
                    popust_iznos * kolicina, god, 1, ststatus,
                    sto, artiklid, tip))

                inserted_id = cursor.fetchone()[0]
                self.dodaj_u_korpu(inserted_id, sifra, self.nazivEdit.text(),
                                kolicina, cena_bez_popusta, proc_popust,
                                cena_sa_popustom, vrednost)

            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            print(f"❌ Greška pri upisu u bazu `kasa1`: {e}")

    def dodaj_u_korpu(self, id_stavke, sifra, naziv, kolicina, cena_bez_popusta, proc_popust, cena_sa_popustom, vrednost):
        row_count = self.stavkeTable.rowCount()
        self.stavkeTable.insertRow(row_count)

        # Popunjavanje kolona
        self.stavkeTable.setItem(row_count, 0, QTableWidgetItem(str(id_stavke)))
        self.stavkeTable.setItem(row_count, 1, QTableWidgetItem(sifra))
        self.stavkeTable.setItem(row_count, 2, QTableWidgetItem(naziv))
        self.stavkeTable.setItem(row_count, 3, QTableWidgetItem(f"{kolicina:.3f}"))
        self.stavkeTable.setItem(row_count, 4, QTableWidgetItem(f"{cena_bez_popusta:.2f}"))
        self.stavkeTable.setItem(row_count, 5, QTableWidgetItem(f"{proc_popust:.2f}"))
        self.stavkeTable.setItem(row_count, 6, QTableWidgetItem(f"{cena_sa_popustom:.2f}"))
        self.stavkeTable.setItem(row_count, 7, QTableWidgetItem(f"{vrednost:.2f}"))

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
        self.stavkeTable.setCellWidget(row_count, 8, btn_obrisi)

        # Ažuriranje ukupne vrednosti
        self.azuriraj_total()
        self.clear_fields()
        self.sifraEdit.setFocus()

    def obrisi_stavku(self, id_stavke):
        """✅ Brisanje artikla iz baze `kasa1` i tabele `stavkeTable`."""
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

            # ✅ Brisanje iz tabele
            for row in range(self.stavkeTable.rowCount()):
                if int(self.stavkeTable.item(row, 0).text()) == id_stavke:
                    self.stavkeTable.removeRow(row)
                    break

            self.azuriraj_total()
            #print(f"✅ Stavka sa ID-om {id_stavke} uspešno obrisana.")

        except Exception as e:
            print(f"❌ Greška pri brisanju stavke: {e}")

    def azuriraj_total(self):
        total = 0
        ukupni_popust = 0
        for row in range(self.stavkeTable.rowCount()):
            vrednost = float(self.stavkeTable.item(row, 7).text())
            popust = float(self.stavkeTable.item(row, 5).text())
            ukupni_popust += float(self.stavkeTable.item(row, 4).text()) * float(self.stavkeTable.item(row, 3).text()) - vrednost
            total += vrednost

        self.totalEdit.setText(f"{total:.2f}")
        self.ostPopEdit.setText(f"{ukupni_popust:.2f}")
        
    #################################################################################################
    # Pri izboru aktivnog kupca ukoliko je racun nezavrsen ucitavaju se stavke racuna,
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
                "SELECT id, sifra, (SELECT naziv FROM \"kasa\".\"artikli\" WHERE sifra = k.sifra), kolic, cena2, popproc1, cena, kolic*cena FROM \"kasa\".\"kasa1\" k WHERE sto = %s AND kasa = %s AND zatvoren = False",
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
                self.stavkeTable.setCellWidget(row_count, 8, btn_obrisi)
                self.azuriraj_total()
                self.clear_fields()
                self.sifraEdit.setFocus()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"❌ Greška pri učitavanju stavki iz baze: {e}")
    #################################################################################################
    #################################################################################################
    def proveri_placanje(self):
        """✅ Provera uslova za omogućavanje dugmeta 'btnStampa'."""
        try:
            gotovina = float(self.gotovinaEdit.text() or 0)
            kartica = float(self.karticaEdit.text() or 0)
            cek = float(self.cekEdit.text() or 0)
            racun = float(self.racunEdit.text() or 0)
            ukupno_placanje = gotovina + kartica + cek + racun
            ukupno_avans = float(self.iznosRefundacijeEdit.text() or 0)

            ukupno_za_placanje = float(self.totalEdit.text() or 0)
            tip = self.tipEdit.text().strip()
            kupac = self.kupacEdit.text().strip()

            if racun > 0 and (not tip or not kupac):
                self.btnStampa.setEnabled(False)
                self.kusurEdit.setText("0.00")
                self.show_warning_message("Unesite tip i podatke o kupcu za plaćanje preko računa.")
                return

            if self.aktivan_mod == "promet":
                if ukupno_placanje >= ukupno_za_placanje:
                    self.btnStampa.setEnabled(True)
                    kusur = ukupno_placanje - ukupno_za_placanje
                    self.kusurEdit.setText(f"{kusur:.2f}")
                else:
                    self.btnStampa.setEnabled(False)
                    self.kusurEdit.setText("0.00")
            elif self.aktivan_mod == "refundacija":
                if ukupno_placanje == ukupno_za_placanje:
                    self.btnStampa.setEnabled(True)
                else:
                    self.btnStampa.setEnabled(False)
                    self.kusurEdit.setText("0.00")
            elif self.aktivan_mod == "avans":
                if ukupno_placanje + ukupno_avans >= ukupno_za_placanje:
                    self.btnStampa.setEnabled(True)
                else:
                    self.btnStampa.setEnabled(False)
                    self.kusurEdit.setText("0.00")
        except ValueError:
            self.btnStampa.setEnabled(False)
            self.kusurEdit.setText("0.00")
            
    def izvrsi_stampu(self):
        """✅ Pokreće odgovarajuću funkciju za fiskalizaciju u zavisnosti od aktivnog moda."""
        if self.aktivan_mod == "promet":
            self.fiskalizuj_korpu()
        elif self.aktivan_mod == "refundacija":
            self.fiskalizuj_racun_refundacije()
        elif self.aktivan_mod == "avans":
            self.fiskalizuj_konacni_racun()
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
    #################################################################################################
    #################################################################################################
    # Klasa za otvaranje dialoga za izbor kupca
    def open_select_customer_dialog(self):
        dialog = SelectCustomerDialog(self)
        if dialog.exec():
            tip_value, kupac_tip_value = dialog.get_selected_customer()  # Ispravljeno ime metode
            self.tipEdit.setText(tip_value)  # Ažuriramo polje tipEdit
            self.kupacEdit.setText(kupac_tip_value) 
            
    def clear_customer_fields(self):
        """Čisti polja za unos tipa i identifikacije kupca."""
        self.tipEdit.clear()
        self.kupacEdit.clear()
            
    #################################################################################################
    #################################################################################################
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
                tipracuna = 0
                tiptransakcije = 0
                dokstatus = 'PP'
                ui = 'i'
            elif self.aktivan_mod == "refundacija":
                tipracuna = 0
                tiptransakcije = 1
                dokstatus = 'PR'
                ui = 'u'
            else:
                raise Exception("Nepoznat mod transakcije.")

            # Dohvatanje podataka o kupcu
            kodkupca = self.tipEdit.text().strip() if self.tipEdit.text() else None
            oznakakupca = self.kupacEdit.text().strip() if self.kupacEdit.text() else None

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
            (god, kar, broj, datum, kasa, sifobj, smena, vrgotovina, vrkartica, vrfaktura, vrcek, ukiznos, idpartneri, kodkupca, oznakakupca, tipplacanja, tipracuna, tiptransakcije, dokstatus, kreirao)
            VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, 'sistem')
            """, (
                int(GODINA), 1, novi_broj_racuna, int(KASA), SIFOBJEKTA, 1,
                round(float(self.gotovinaEdit.text() or 0) - float(self.kusurEdit.text() or 0), 2),
                round(float(self.karticaEdit.text() or 0), 2),
                round(float(self.racunEdit.text() or 0), 2),
                round(float(self.cekEdit.text() or 0), 2),
                round(float(self.totalEdit.text() or 0), 2),
                kodkupca, oznakakupca,
                1 if float(self.gotovinaEdit.text() or 0) - float(self.kusurEdit.text() or 0) > 0 else 0,
                tipracuna, tiptransakcije, dokstatus
            ))

            # Snimanje podataka u `karticaart`
            cursor.execute("""
                SELECT
                    k.sifra,
                    k.cena AS prodajna_cena,
                    k.cena2 AS originalna_cena,
                    SUM(k.kolic) AS ukupna_kolicina,
                    MAX(z.cenanabavna) AS nabavna_cena,
                    MAX(k.popproc1) AS rabat_proc,
                    SUM(k.popsum) AS ukupan_popust,
                    MAX(k.artikliid) AS artikli_id,
                    MAX(a.robna_grupa_id) AS grupa,
                    MAX(a.porez_id) AS porezid,
                    MAX(p.tarifa) AS tarifa,
                    MAX(p.stopa) AS stopa
                FROM "kasa"."kasa1" k
                LEFT JOIN "kasa"."artikli" a
                    ON a.id = k.artikliid
                LEFT JOIN "kasa"."porezi" p
                    ON p.id = a.porez_id
                LEFT JOIN "kasa"."zaliheart" z
                    ON z.god = k.god
                AND z.sifobj = k.sifobj
                AND z.lokacija_id = %s
                AND z.artikliid = k.artikliid
                WHERE k.zatvoren = TRUE
                AND k.kasa = %s
                AND k.broj = %s
                GROUP BY
                    k.sifra,
                    k.cena,
                    k.cena2
                """, (
                    GLAVNA_LOKACIJA_ID,
                    int(KASA),
                    novi_broj_racuna
                ))

            artikli = cursor.fetchall()

            for artikal in artikli:
                (
                    sifra,
                    prodajna_cena,
                    originalna_cena,
                    ukupna_kolicina,
                    nabavna_cena,
                    rabat_proc,
                    ukupan_popust,
                    artikli_id,
                    grupa,
                    porezid,
                    tarifa,
                    stopa
                ) = artikal

                nabavna_cena = nabavna_cena or 0

                # Računanje poreza
                preracunata_stopa = float((stopa * 100) / (stopa + 100)) if stopa else 0
                porez = round(float((prodajna_cena * preracunata_stopa / 100) * ukupna_kolicina), 2)

                cursor.execute("""
                INSERT INTO "kasa"."karticaart"
                (
                    god, kar, broj, sifra,
                    cena, staracena, cenanabavna,
                    kolicina, rabatproc, rabatdinarski,
                    porez, porezproc, tarifa, grupa,
                    vrsta, dokstatus, datum, opis,
                    artikliid, sifobj, lokacija_id,
                    porezid, ui, kasa,
                    idpartneri, kreirao, kreirano
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, CURRENT_DATE, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    NULL, 'sistem', CURRENT_TIMESTAMP
                )
                """, (
                    GODINA,
                    1,
                    novi_broj_racuna,
                    sifra,
                    round(prodajna_cena, 2),
                    round(originalna_cena, 2),
                    round(nabavna_cena, 2),
                    round(ukupna_kolicina, 3),
                    round(rabat_proc or 0, 2),
                    round(ukupan_popust or 0, 2),
                    porez,
                    stopa,
                    tarifa,
                    grupa,
                    8 if tiptransakcije == 0 else 9,
                    dokstatus,
                    f"Fiskalni račun {dokstatus}",
                    artikli_id,
                    SIFOBJEKTA,
                    GLAVNA_LOKACIJA_ID,
                    porezid,
                    ui,
                    int(KASA)
                ))
                
                #sifra, prodajna_cena, ukupna_kolicina, *_ = artikal
                #self.azuriraj_zalihe(sifra, ukupna_kolicina, dodaj=False)  # Smanjujemo zalihu

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

    #################################################################################################
    #################################################################################################
    # Funkcije za stampu fiskalnih racuna
    def ucitaj_konfiguraciju_kase(self):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            query = """
            SELECT ipstampe, lservis
            FROM "kasa"."confkasa"
            WHERE kasa = %s AND sifobj = %s
            """
            cursor.execute(query, (KASA, SIFOBJEKTA))
            rezultat = cursor.fetchone()

            if rezultat:
                ip_stampe, lservis = rezultat
                #print(f"✅ Učitana konfiguracija: IP: {ip_stampe}, lservis: {lservis}")
                return ip_stampe, lservis
            else:
                print("❌ Nije pronađena konfiguracija u bazi.")
                return None, None
        except Exception as e:
            print(f"❌ Greška pri učitavanju konfiguracije kase: {e}")
            return None, None
        finally:
            if conn:
                conn.close()
    
    def generisi_json_racun(self, broj_racuna, stavke, placanja, kasir, tip_racuna, tip_transakcije, ip_stampe, tip_kupca=None, oznaka_kupca=None):
        """
        Generiše JSON fajl za fiskalni račun, uključujući informacije o kupcu i propratni tekst za popust.
        """
        try:
            godina = str(datetime.now().year)[-2:]
            direktorijum = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\to-sdc"
            json_fajl = os.path.join(direktorijum, f"CreateInvoice-{broj_racuna}-{godina}.json")

            # Priprema poruke na osnovu ostvarenog popusta
            ukupni_popust = float(self.ostPopEdit.text() or 0)  # Preuzimanje vrednosti iz ostPopEdit
            if ukupni_popust > 0:
                poruka = f"Ovom kupovinom ostvarili ste popust od: {ukupni_popust:.2f} dinara. HVALA NA POVERENJU"
            else:
                poruka = "HVALA NA POVERENJU"

            # Priprema podataka za JSON
            racun = {
                "cashier": kasir,
                "invoiceNumber": "1161/1.0.128.0",  # Direkno upisana vrednost
                "invoiceType": str(tip_racuna),
                "transactionType": str(tip_transakcije),
                "items": stavke,
                "payment": placanja,
                "journalOptions": {
                    "print": "true",
                    "message": poruka
                }
            }

            # Dodavanje informacija o kupcu ako su dostupne
            if tip_kupca and oznaka_kupca:
                racun["buyerId"] = f"{tip_kupca}:{oznaka_kupca}"

            # Kreiranje direktorijuma ako ne postoji
            os.makedirs(direktorijum, exist_ok=True)

            # Upis JSON fajla
            with open(json_fajl, "w", encoding="utf-8") as f:
                json.dump(racun, f, ensure_ascii=False, indent=4)

            print(f"✅ JSON fajl generisan: {json_fajl}")
            return json_fajl

        except Exception as e:
            print(f"❌ Greška pri generisanju JSON fajla: {e}")
            return None

    def obradi_odgovor(self, broj_racuna, ip_stampe):
        """
        Čeka i obrađuje odgovor na fiskalni račun iz direktorijuma `from-sdc`.
        """
        try:
            godina = str(datetime.now().year)[-2:]
            direktorijum_odgovora = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\from-sdc"
            fajl_ok = os.path.join(direktorijum_odgovora, f"InvoiceResponse-{broj_racuna}-{godina}.json")
            fajl_greska = os.path.join(direktorijum_odgovora, f"Error-{broj_racuna}-{godina}.json")

            # Čekanje na fajl sa odgovorom
            for _ in range(20):  # Maksimalno 10 sekundi (20 * 0.5s)
                if os.path.exists(fajl_ok):
                    print(f"✅ Odgovor uspešan: {fajl_ok}")
                    return "success", fajl_ok
                if os.path.exists(fajl_greska):
                    print(f"❌ Greška u odgovoru: {fajl_greska}")
                    return "error", fajl_greska
                time.sleep(0.5)

            print("❌ Odgovor nije stigao u zadatom vremenu.")
            return "timeout", None

        except Exception as e:
            print(f"❌ Greška pri obradi odgovora: {e}")
            return "error", None

    def fiskalizuj_racun(self, broj_racuna, stavke, placanja, kasir, tip_racuna, tip_transakcije, ip_stampe, tip_kupca=None, oznaka_kupca=None):
        """
        Glavna funkcija za fiskalizaciju računa.
        """
        try:
            # Generisanje JSON-a
            json_fajl = self.generisi_json_racun(broj_racuna, stavke, placanja, kasir, tip_racuna, tip_transakcije, ip_stampe,
                                                tip_kupca=tip_kupca, oznaka_kupca=oznaka_kupca
                                                )
            if not json_fajl:
                raise Exception("Generisanje JSON fajla nije uspelo.")

            # Čekanje i obrada odgovora
            status, fajl_odgovora = self.obradi_odgovor(broj_racuna, ip_stampe)
            if status == "success":
                print("✅ Račun je uspešno fiskalizovan.")
                # Obrada uspešnog odgovora
                with open(fajl_odgovora, "r", encoding="utf-8") as f:
                    odgovor = json.load(f)
                    broj_fiskalnog_racuna = odgovor.get("invoiceNumber", "Nepoznato")
                    print(f"Broj fiskalnog računa: {broj_fiskalnog_racuna}")
                # Ažuriranje kasasum
                self.azuriraj_kasasum(broj_racuna, ip_stampe)
            elif status == "error":
                print("❌ Greška pri fiskalizaciji. Proverite fajl sa greškom.")
            else:
                print("❌ Odgovor nije stigao u zadatom vremenu.")

        except Exception as e:
            print(f"❌ Greška pri fiskalizaciji: {e}")
        

    def pripremi_stavke(self, lservis):
        """
        Priprema stavke iz tabele za JSON, uključujući porez na osnovu baze.
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

            for row in range(self.stavkeTable.rowCount()):
                sifra = self.stavkeTable.item(row, 1).text()  # Šifra artikla
                naziv = self.stavkeTable.item(row, 2).text()
                kolicina = self.stavkeTable.item(row, 3).text()
                cena = self.stavkeTable.item(row, 6).text()
                vrednost = self.stavkeTable.item(row, 7).text()
                
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
                porez_slovo = "A" if lservis else "Ђ" #"\u0402"  # "A" za test režim, inače default na 20% (Ђ)

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
                    # Koristi ćirilično slovo iz mape ili default "А" 
                    #porez_slovo = LATIN_TO_CYRILLIC_MAP.get(latinsko_slovo, "\u0410") if not lservis else "A"
                    porez_slovo = LATIN_TO_CYRILLIC_MAP.get(latinsko_slovo, "Ђ") if not lservis else "A"
                    
                # Dodavanje stavke u listu
                stavke.append({
                    "name": naziv_sa_jedinicom,
                    "quantity": kolicina,
                    "unitPrice": cena,
                    "totalAmount": vrednost,
                    "labels": [porez_slovo]
                })

            return stavke

        except Exception as e:
            print(f"❌ Greška pri pripremi stavki: {e}")
            return []

        finally:
            if conn:
                conn.close()

    def pripremi_placanja(self):
        """
        Priprema podataka o plaćanju za JSON.
        """
        placanja = []

        if self.aktivan_mod == "avans":
            try:
                iznos_refundacije = float(self.iznosRefundacijeEdit.text() or 0)
                ukupno_robe = float(self.racunEdit.text() or 0)

                if abs(iznos_refundacije - ukupno_robe) < 0.01:
                    # Cela roba je pokrivena refundacijom
                    placanja.append({
                        "paymentType": "4",
                        "amount": f"{iznos_refundacije:.2f}"
                    })
                else:
                    # Deo je pokriven avansom (refundacijom), a ostatak se plaća sada
                    if iznos_refundacije > 0:
                        placanja.append({
                            "paymentType": "4",
                            "amount": f"{iznos_refundacije:.2f}"
                        })

                    gotovina = float(self.gotovinaEdit.text() or 0)
                    if gotovina > 0:
                        placanja.append({"paymentType": "1", "amount": f"{gotovina:.2f}"})

                    kartica = float(self.karticaEdit.text() or 0)
                    if kartica > 0:
                        placanja.append({"paymentType": "2", "amount": f"{kartica:.2f}"})

                    cek = float(self.cekEdit.text() or 0)
                    if cek > 0:
                        placanja.append({"paymentType": "3", "amount": f"{cek:.2f}"})

            except Exception as e:
                print(f"[GRESKA] Neuspešno čitanje avansnih vrednosti: {e}")
                # Možeš po potrebi ovde prikazati poruku korisniku

        else:
            # Standardni režim
            gotovina = float(self.gotovinaEdit.text() or 0)
            if gotovina > 0:
                placanja.append({"paymentType": "1", "amount": f"{gotovina:.2f}"})

            kartica = float(self.karticaEdit.text() or 0)
            if kartica > 0:
                placanja.append({"paymentType": "2", "amount": f"{kartica:.2f}"})

            cek = float(self.cekEdit.text() or 0)
            if cek > 0:
                placanja.append({"paymentType": "3", "amount": f"{cek:.2f}"})

            racun = float(self.racunEdit.text() or 0)
            if racun > 0:
                placanja.append({"paymentType": "4", "amount": f"{racun:.2f}"})

        return placanja

    
    def fiskalizuj_korpu(self):
        """
        Fiskalizuje korpu i generiše JSON fajl za fiskalni štampač.
        """
        try:
            # Dohvat konfiguracije kase
            ip_stampe, lservis = self.ucitaj_konfiguraciju_kase()
            if not ip_stampe:
                raise Exception("IP adresa štampača nije pronađena u konfiguraciji.")

            # Priprema podataka
            broj_racuna = self.snimi_racun()
            if not broj_racuna:
                raise Exception("Generisanje broja računa nije uspelo.")
            #broj_racuna = self.trenutni_broj_racuna
            stavke = self.pripremi_stavke(lservis)
            placanja = self.pripremi_placanja()
            kasir = "Kasir 1"
            tip_racuna = 0  # Promet
            tip_transakcije = 0  # Prodaja

            # Dohvatanje informacija o kupcu
            tip_kupca = self.tipEdit.text().strip()
            oznaka_kupca = self.kupacEdit.text().strip()

            # Poziv funkcije za fiskalizaciju
            self.fiskalizuj_racun(
                broj_racuna, stavke, placanja, kasir, tip_racuna, tip_transakcije,
                ip_stampe, tip_kupca=tip_kupca, oznaka_kupca=oznaka_kupca
            )
            self.resetuj_kontrole()
        
        except Exception as e:
            print(f"❌ Greška pri fiskalizaciji: {e}")

    def azuriraj_zalihe(self, broj_racunaPU):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # 1. Pronađi zaglavlje iz kasasum
            cursor.execute("""
                SELECT god, sifobj, broj, dokstatus
                FROM "kasa"."kasasum"
                WHERE brracpu = %s
            """, (broj_racunaPU,))
            kasasum = cursor.fetchone()

            if not kasasum:
                print("Nije pronađen fiskalni račun.")
                return

            god, sifobj, broj, dokstatus = kasasum

            if dokstatus not in ('PP', 'PR'):
                print(f"Dokument nije prometna prodaja/refundacija: {dokstatus}")
                return

            # 2. Izvuci stavke iz karticaart
            cursor.execute("""
                SELECT sifra, SUM(kolicina)
                FROM "kasa"."karticaart"
                WHERE god = %s AND sifobj = %s AND broj = %s AND vrsta IN (8, 9)
                GROUP BY sifra
            """, (god, sifobj, broj))
            stavke = cursor.fetchall()  # [(sifra, suma_kolicina), ...]

            if not stavke:
                print("Nema stavki za dati račun.")
                return

            # 3. Dohvati tipove artikala
            sifre = tuple([s[0] for s in stavke])
            cursor.execute(f"""
                SELECT sifra, tip
                FROM "kasa"."artikli"
                WHERE sifra IN %s
            """, (sifre,))
            artikli_tipovi = dict(cursor.fetchall())  # {sifra: tip}

            # 4. Ažuriraj zalihe za tip = 1 (roba)
            for sifra, suma_kolicina in stavke:
                tip = artikli_tipovi.get(sifra)
                if tip != 1:
                    continue  # preskoči usluge i setove

                # pronađi trenutnu zalihu
                cursor.execute("""
                    SELECT zaliha
                    FROM "kasa"."zaliheart"
                    WHERE god = %s AND sifobj = %s AND lokacija_id = %s AND sifra = %s 
                    FOR UPDATE
                """, (god, sifobj, GLAVNA_LOKACIJA_ID, sifra))
                zaliha_row = cursor.fetchone()

                if not zaliha_row:
                    #print(f"Zaliha ne postoji za šifru {sifra} na lokaciji {GLAVNA_LOKACIJA_ID}")
                    continue

                trenutna_zaliha = zaliha_row[0]
                nova_zaliha = trenutna_zaliha - suma_kolicina  # suma_kolicina već sadrži - ili +
                #print(f"Zaliha ne postoji za šifru {sifra, trenutna_zaliha, suma_kolicina, nova_zaliha}")
                # ažuriraj zalihu
                cursor.execute("""
                    UPDATE "kasa"."zaliheart"
                    SET zaliha = %s
                    WHERE god = %s AND sifobj = %s AND lokacija_id = %s AND sifra = %s
                """, (nova_zaliha, god, sifobj, GLAVNA_LOKACIJA_ID, sifra))

                print(
                    f"✅ Artikal: {sifra} | "
                    f"Lokacija: {GLAVNA_LOKACIJA_ID} | "
                    f"Staro: {trenutna_zaliha} | "
                    f"Promena: {-suma_kolicina} | "
                    f"Novo: {nova_zaliha}"
                )

            conn.commit()
            print(f"Zalihe uspešno ažurirane. {god, sifobj, sifra, nova_zaliha}")

        except Exception as e:
            conn.rollback()
            print(f"Greška prilikom ažuriranja zaliha: {e}")

        finally:
            cursor.close()
            conn.close()
            
    def azuriraj_kasasum(self, broj_racuna, ip_stampe):
        """
        Ažurira polja 'brracpu', 'vremetransakcije' i 'verificationurl' u modelu 'kasasum'
        na osnovu odgovora iz PU (JSON fajla).
        """
        try:
            godina = str(datetime.now().year)[-2:]
            direktorijum_odgovora = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\from-sdc"
            fajl_odgovora = os.path.join(direktorijum_odgovora, f"InvoiceResponse-{broj_racuna}-{godina}.json")

            # Proveravamo da li fajl postoji
            if not os.path.exists(fajl_odgovora):
                raise Exception(f"Fajl odgovora nije pronađen: {fajl_odgovora}")

            # Čitamo sadržaj JSON fajla
            with open(fajl_odgovora, "r", encoding="utf-8") as f:
                odgovor = json.load(f)

            # Ekstrakcija podataka iz odgovora
            broj_fiskalnog_racuna = odgovor.get("invoiceNumber")
            vreme_transakcije = odgovor.get("sdcDateTime")
            verification_url = odgovor.get("verificationUrl")

            if not broj_fiskalnog_racuna or not vreme_transakcije or not verification_url:
                raise Exception("Nedostaju podaci u odgovoru PU (broj fiskalnog računa, vreme transakcije ili URL).")

            # Ažuriranje modela kasasum
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
                UPDATE "kasa"."kasasum"
                SET brracpu = %s,
                    vremetransakcije = %s,
                    verificationurl = %s
                WHERE broj = %s AND god = %s AND sifobj = %s
                """,
                (broj_fiskalnog_racuna, vreme_transakcije, verification_url, broj_racuna, GODINA, SIFOBJEKTA)
            )
            conn.commit()
            cursor.close()
            conn.close()

            self.azuriraj_zalihe(broj_fiskalnog_racuna)  # Smanjujemo zalihu

        #    print(f"✅ Ažurirani podaci za račun {broj_racuna}: Broj fiskalnog računa: {broj_fiskalnog_racuna}, "
        #        f"Vreme transakcije: {vreme_transakcije}, URL: {verification_url}")

        except Exception as e:
            print(f"❌ Greška pri ažuriranju kasasum: {e}")

    ######################################################################
    # Konacni racun snimanje u bazu i stampa
    def snimi_konacni_racun(self):
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
                raise Exception("Neuspešno generisanje broja konacnog računa.")

            # Određivanje tipa računa i transakcije
            tipracuna = 0
            tiptransakcije = 0  # Refundacija
            dokstatus = 'PP'
            ui = 'i'

            # Dohvatanje podataka o kupcu i referentnom računu
            kodkupca = self.tipEdit.text().strip() if self.tipEdit.text() else None
            oznakakupca = self.kupacEdit.text().strip() if self.kupacEdit.text() else None
            referentni_racun = self.brrnpuEdit.text().strip()  # Broj fiskalnog računa koji je refundiran
            vreme_referentnog = self.vremeTransEdit.text().strip()  # Vreme referentnog računa

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
            (god, kar, broj, datum, kasa, sifobj, smena, vrgotovina, vrkartica, vrfaktura, vrcek, ukiznos, idpartneri, kodkupca, oznakakupca, tipplacanja, tipracuna, tiptransakcije, dokstatus, refbrracpu, kreirao)
            VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, 'sistem')
            """, (
                int(GODINA), 1, novi_broj_racuna, int(KASA), SIFOBJEKTA, 1,
                round(float(self.gotovinaEdit.text() or 0), 2),
                round(float(self.karticaEdit.text() or 0), 2),
                round(float(self.iznosRefundacijeEdit.text() or 0), 2),  #(float(self.racunEdit.text() or 0), 2)
                round(float(self.cekEdit.text() or 0), 2),
                round(float(self.totalEdit.text() or 0), 2),
                kodkupca, oznakakupca,
                1 if float(self.gotovinaEdit.text() or 0) > 0 else 0,
                tipracuna, tiptransakcije, dokstatus,
                referentni_racun
            ))

            # Snimanje podataka u `karticaart` (pozitivna količina)
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
                    8, dokstatus,
                    "Fiskalni račun PP", artikli_id, SIFOBJEKTA, GLAVNA_LOKACIJA_ID, porezid, ui, int(KASA)
                ))
                
                sifra, prodajna_cena, ukupna_kolicina, *_ = artikal
                #self.azuriraj_zalihe(sifra, ukupna_kolicina, dodaj=True)  # Vraćamo robu na zalihu

            conn.commit()
            #print(f"✅ Refundacija uspešno snimljena u bazi sa brojem {novi_broj_racuna}.")
            return novi_broj_racuna  # Vraćamo broj refundiranog računa

        except Exception as e:
            print(f"❌ Greška pri snimanju refundacije: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()      
    
    def generisi_json_konacni(self, broj_racuna, stavke, placanja, kasir, ip_stampe, tip_kupca=None, oznaka_kupca=None):
        """Generiše JSON fajl za fiskalizaciju konačnog računa (refundacija avansa)."""
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            godina = str(datetime.now().year)[-2:]
            direktorijum = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\to-sdc"
            json_fajl = os.path.join(direktorijum, f"CreateInvoice-{broj_racuna}-{godina}.json")

            # 1. Preuzimanje podataka iz edit polja
            poslednji_avans = self.poslednjiAvansEdit.text()
            brracpu = self.brrnpuEdit.text()

            # 2. PRVA PRETRAGA: Informacije o poslednjem avansu
            cursor.execute("""
                SELECT brracpu, datum 
                FROM kasa.kasasum 
                WHERE brracpu = %s
            """, (poslednji_avans,))
            rezultat = cursor.fetchone()

            if rezultat:
                brracpu_avans, datum = rezultat
                poruka = f"Poslednji uplaćeni avans {brracpu_avans} od {datum.strftime('%d.%m.%Y')}"
            else:
                poruka = "Poslednji uplaćeni avans nije pronađen"

            # 3. DRUGA PRETRAGA: Podaci za referentni račun
            cursor.execute("""
                SELECT god, sifobj, broj 
                FROM kasa.kasasum 
                WHERE brracpu = %s
            """, (brracpu,))
            rezultat = cursor.fetchone()

            ukupni_avans = 0.0
            ukupni_porez = 0.0

            if rezultat:
                god, sifobj, broj = rezultat

                # 4. Preuzimanje stavki za avansni račun (vrsta = 9)
                cursor.execute("""
                    SELECT cena, porez 
                    FROM kasa.karticaart 
                    WHERE god = %s AND sifobj = %s AND broj = %s AND vrsta = 9
                """, (god, sifobj, broj))

                rows = cursor.fetchall()
                for cena, porez in rows:
                    ukupni_avans += float(cena)
                    ukupni_porez += float(porez)

            # 5. Formiranje konačnog JSON objekta
            racun = {
                "cashier": kasir,
                "invoiceNumber": broj_racuna,
                "invoiceType": "0",
                "transactionType": "0",
                "referentDocumentNumber": brracpu,
                "referentDocumentDT": self.vremeTransEdit.text(),
                "items": stavke,
                "payment": placanja,
                "journalOptions": {
                    "print": "true",
                    "message": poruka,
                    "advance": f"{ukupni_avans:.2f}",
                    "advanceTax": f"{ukupni_porez:.2f}"
                }
            }

            # Dodavanje kupca ako je prosleđen
            if tip_kupca and oznaka_kupca:
                racun["buyerId"] = f"{tip_kupca}:{oznaka_kupca}"

            # 6. Upisivanje JSON fajla
            with open(json_fajl, "w", encoding="utf-8") as f:
                json.dump(racun, f, ensure_ascii=False, indent=4)

            return json_fajl

        except Exception as e:
            print(f"❌ Greška pri generisanju JSON-a konačnog računa: {e}")
            return None

        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()           

    def fiskalizuj_konacni_racun(self):
        """Fiskalizuje konacni račun i šalje ga PU."""
        try:
            # Učitavanje konfiguracije kase
            ip_stampe, lservis = self.ucitaj_konfiguraciju_kase()
            if not ip_stampe:
                raise Exception("IP adresa štampača nije pronađena u konfiguraciji.")

            # Snimanje refundiranog računa u bazu
            broj_racuna = self.snimi_konacni_racun()
            if not broj_racuna:
                raise Exception("Generisanje broja konacnog računa nije uspelo.")

            # Priprema podataka
            stavke = self.pripremi_stavke(lservis)
            placanja = self.pripremi_placanja()
            kasir = "Kasir 1"

            # Generisanje JSON-a i slanje na štampač
            json_fajl = self.generisi_json_konacni(broj_racuna, stavke, placanja, kasir, ip_stampe, tip_kupca=None, oznaka_kupca=None)
            if not json_fajl:
                raise Exception("Generisanje JSON fajla za refundaciju nije uspelo.")

            # Čekanje na odgovor iz PU
            status, fajl_odgovora = self.obradi_odgovor(broj_racuna, ip_stampe)
            if status == "success":
                #print("✅ Refundacija uspešno fiskalizovana.")
                self.azuriraj_kasasum(broj_racuna, ip_stampe)
                self.resetuj_kontrole()
            elif status == "error":
                print("❌ Greška pri fiskalizaciji refundacije. Proverite fajl sa greškom.")
            else:
                print("❌ Odgovor nije stigao u zadatom vremenu.")

        except Exception as e:
            print(f"❌ Greška pri fiskalizaciji refundacije: {e}")
            
    ######################################################################
    # Refundacija
    # Otvaranje dialoga refundacije
    def otvori_racuni_dialog(self):
        """
        Otvara dijalog za pregled i selekciju fiskalnih računa.
        """
        try:
            # ✅ Dohvatanje podataka iz baze za kasasum i kasa
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # ✅ Dohvatanje podataka iz kasasum (zaglavlja računa) - dodajemo kodkupca i oznakakupca
            cursor.execute("""
            SELECT brracpu, vremetransakcije, ukiznos, broj, kasa, god, sifobj, tiptransakcije, 
                vrgotovina, vrkartica, vrcek, vrfaktura, kodkupca, oznakakupca  
            FROM "kasa"."kasasum"
            WHERE sifobj = %s AND brracpu IS NOT NULL AND tipracuna = '0'
            ORDER BY vremetransakcije DESC
            """, (SIFOBJEKTA,))
            self.kasasum = [  
                {
                    "brracpu": row[0],
                    "vreme_stampe": row[1],
                    "vrednost": row[2],
                    "broj": row[3],
                    "kasa": row[4],
                    "god": row[5],
                    "sifobj": row[6],
                    "tiptransakcije": row[7],  
                    "vrgotovina": row[8],  
                    "vrkartica": row[9],  
                    "vrcek": row[10],  
                    "vrfaktura": row[11],  
                    "kodkupca": row[12],  # ✅ Dodato!
                    "oznakakupca": row[13]  # ✅ Dodato!
                }
                for row in cursor.fetchall()
            ]

            # ✅ Dohvatanje podataka iz kasa (stavke računa) - dodajemo popsum
            cursor.execute("""
            SELECT k.broj, k.sifra, a.naziv, k.kolic, k.cena, (k.kolic * k.cena) AS vrednost, 
                k.popsum, k.god, k.sifobj, k.kasa
            FROM "kasa"."kasa" k
            LEFT JOIN "kasa"."artikli" a ON a.sifra = k.sifra
            WHERE k.sifobj = %s
            """, (SIFOBJEKTA,))
            self.kasa = [  
                {
                    "broj": row[0],
                    "sifra": row[1],
                    "naziv": row[2],
                    "kolic": row[3],
                    "cena": row[4],
                    "vrednost": row[5],
                    "popsum": row[6],  # ✅ Dodato!
                    "god": row[7],
                    "sifobj": row[8],
                    "kasa": row[9]
                }
                for row in cursor.fetchall()
            ]

            # ✅ Dohvatanje podataka iz artikli
            cursor.execute("""
            SELECT id, sifra, naziv, tip
            FROM "kasa"."artikli"
            """)
            self.artikli = [
                {
                    "id": row[0],  
                    "sifra": row[1],
                    "naziv": row[2],
                    "tip": row[3]
                }
                for row in cursor.fetchall()
            ]

            conn.close()

            # ✅ IP adresa štampača (pročitana iz baze ili konfiguracije)
            ip_stampe, lservis = self.ucitaj_konfiguraciju_kase()

            # ✅ Otvaranje dijaloga
            dialog = RacuniDialog(self.kasasum, self.kasa, self.artikli, ip_stampe, lservis, parent=self)

            # ✅ Povezivanje signala za prenos podataka
            dialog.signal_prenesi_podatke.connect(self.prenesi_podatke_iz_dijaloga)
            dialog.signal_prenesi_podatke.connect(self.prikazi_stavke_na_osnovu_brracpu)

            # Prikaz dijaloga
            dialog.exec()

        except Exception as e:
            print(f"❌ Greška pri otvaranju dijaloga: {e}")

    # Funkcija za prenos broja računa PU i vremena transakcije
    def prenesi_podatke_iz_dijaloga(self, broj_racuna_pu, vreme_transakcije):
        """
        Prima podatke iz dijaloga i unosi ih u glavna polja.
        """
        self.brrnpuEdit.setText(broj_racuna_pu)
        self.vremeTransEdit.setText(vreme_transakcije)

    # Funkcija za učitavanje IP adrese štampača
    def ucitaj_ip_stampe(self):
        """
        Dohvata IP adresu štampača iz baze podataka.
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
            query = """
            SELECT ipstampe FROM "kasa"."confkasa"
            WHERE kasa = %s AND sifobj = %s
            """
            cursor.execute(query, (KASA, SIFOBJEKTA))
            result = cursor.fetchone()
            conn.close()
            if result and result[0]:
                return result[0]  # Vraćamo IP adresu štampača
            else:
                raise ValueError("IP adresa štampača nije pronađena.")
        except Exception as e:
            print(f"❌ Greška pri dohvatanju IP adrese štampača: {e}")
            return None

    # Funkcija za prikaz stavki na osnovu izabranog broja računa PU
    def prikazi_stavke_na_osnovu_brracpu(self, brracpu, vreme_transakcije):
        """
        Prebacuje stavke iz izabranog računa u stavkeTable glavnog prozora i model kasa1.
        Takođe snima stavke u bazu u model kasa1.
        """
        try:
            # Pronalazimo zapis u kasasum koristeći brracpu
            zapis_kasasum = next((record for record in self.kasasum if record["brracpu"] == brracpu), None)
            if not zapis_kasasum:
                raise ValueError(f"❌ Nema zapisa u kasasum za brracpu: {brracpu}")

            # Preuzimamo potrebna polja iz pronađenog zapisa
            god = zapis_kasasum.get("god")
            sifobj = zapis_kasasum.get("sifobj")
            kasa = zapis_kasasum.get("kasa")
            broj = zapis_kasasum.get("broj")

            #print(f"✅ Pronađeni podaci u kasasum: god={god}, sifobj={sifobj}, kasa={kasa}, broj={broj}")

            if god is None or sifobj is None or kasa is None or broj is None:
                raise ValueError(f"❌ Nedostaju podaci u zapisu kasasum za brracpu: {brracpu}")

            # Generisanje privremenog broja računa
            trenutni_broj_racuna = random.randint(int(kasa) * 1000, int(kasa) * 1999)

            # Filtriramo stavke iz modela kasa koristeći god, sifobj, kasa i broj
            stavke = [
                stavka for stavka in self.kasa
                if stavka["god"] == god and stavka["sifobj"] == sifobj and stavka["kasa"] == kasa and stavka["broj"] == broj
            ]

            if not stavke:
                raise ValueError(f"❌ Nema stavki za brracpu: {brracpu} sa podacima god={god}, sifobj={sifobj}, kasa={kasa}, broj={broj}")

            # Provera aktivnog kupca
            aktivan_kupac = self.button_group.checkedId()
            if aktivan_kupac == -1:  # Ako nijedno dugme nije označeno, podrazumevano na 1
                print("⚠️ Nije izabran nijedan aktivan kupac. Podrazumevana vrednost 'sto' postavljena na 1.")
                aktivan_kupac = 1

            # Dodavanje stavki u model kasa1 sa ažuriranim privremenim brojem računa
            self.kasa1 = []
            datum = datetime.now().date()

            for stavka in stavke:
                # Preuzimanje podataka iz modela artikli za trenutnu šifru
                sifra = stavka["sifra"]
                artikl = next((art for art in self.artikli if art["sifra"] == sifra), None)
                if not artikl:
                    raise ValueError(f"❌ Artikli podaci nisu pronađeni za šifru: {sifra}")

                nova_stavka = {
                    "sifra": sifra,
                    "kolic": stavka["kolic"],
                    "cena": stavka["cena"],
                    "cena2": stavka.get("cena2", stavka["cena"]),  # Cena sa popustom
                    "god": GODINA,  # Postavljamo trenutnu godinu iz konfiguracije
                    "broj": trenutni_broj_racuna,  # Ažuriramo broj na privremeni
                    "sifobj": sifobj,
                    "kasa": kasa,
                    "kar": 1,  # Dodajemo kar (fiksna vrednost)
                    "smena": 1,  # Dodajemo smena (fiksna vrednost)
                    "sto": aktivan_kupac,  # Dodajemo aktivan kupac (sto)
                    "popproc1": stavka.get("popproc1", 0),  # Popust u procentima
                    "popdin1": stavka.get("popdin1", 0),  # Popust u dinarima
                    "datum": datum,
                    "kreirao": "sistem",
                    "ststatus": "A",
                    "zatvoren": False,
                    "tip": artikl["tip"],  # Tip artikla
                    "artikliid": artikl["id"]  # ID iz artikli
                }
                self.kasa1.append(nova_stavka)

            # Snimanje stavki iz kasa1 u bazu (tabela kasa1) sa ID dohvatom
            try:
                conn = psycopg2.connect(
                    dbname=os.getenv("DB_NAME"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT")
                )
                cursor = conn.cursor()

                for stavka in self.kasa1:
                    cursor.execute("""
                    INSERT INTO "kasa"."kasa1" 
                    (sifra, kolic, cena, cena2, god, broj, sifobj, kasa, kar, smena, sto, popproc1, popdin1, datum, kreirao, ststatus, zatvoren, tip, artikliid)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """, (
                        stavka["sifra"],
                        stavka["kolic"],
                        stavka["cena"],
                        stavka["cena2"],
                        stavka["god"],
                        stavka["broj"],
                        stavka["sifobj"],
                        stavka["kasa"],
                        stavka["kar"],
                        stavka["smena"],
                        stavka["sto"],
                        stavka["popproc1"],
                        stavka["popdin1"],
                        stavka["datum"],
                        stavka["kreirao"],
                        stavka["ststatus"],
                        stavka["zatvoren"],
                        stavka["tip"],
                        stavka["artikliid"]
                    ))
                    generisani_id = cursor.fetchone()[0]  # Dohvatamo generisani ID
                    stavka["id"] = generisani_id  # Čuvamo ID u stavku

                conn.commit()
                conn.close()
                #print(f"✅ Stavke su uspešno snimljene u bazu (kasa1) za privremeni broj računa: {trenutni_broj_racuna}")

            except Exception as e:
                print(f"❌ Greška pri snimanju u bazu: {e}")
                raise

            # Popunjavanje stavkeTable sa stavkama iz kasa1
            self.populate_stavkeTable()

        except Exception as e:
            print(f"❌ Greška pri prikazu stavki: {e}")
            QMessageBox.critical(self, "Greška", f"Greška pri prikazu stavki:\n{e}")

    def populate_stavkeTable(self):
        """
        Popunjava stavkeTable podacima iz modela kasa1.
        """
        self.stavkeTable.setRowCount(len(self.kasa1))
        for row, stavka in enumerate(self.kasa1):
            artikl = next((art for art in self.artikli if art["sifra"] == stavka["sifra"]), None)
            self.stavkeTable.setItem(row, 0, QTableWidgetItem(str(stavka["id"])))  # ID stavke
            self.stavkeTable.setItem(row, 1, QTableWidgetItem(stavka["sifra"]))
            self.stavkeTable.setItem(row, 2, QTableWidgetItem(artikl["naziv"] if artikl else "Nepoznato"))  # Naziv
            self.stavkeTable.setItem(row, 3, QTableWidgetItem(f"{stavka['kolic']:.3f}"))  # Količina
            self.stavkeTable.setItem(row, 4, QTableWidgetItem(f"{stavka['cena']:.2f}"))  # Cena
            self.stavkeTable.setItem(row, 5, QTableWidgetItem(f"{stavka['popproc1']:.2f}"))  # Popust (%)
            self.stavkeTable.setItem(row, 6, QTableWidgetItem(f"{stavka['cena2']:.2f}"))  # Cena sa popustom
            self.stavkeTable.setItem(row, 7, QTableWidgetItem(f"{stavka['kolic'] * stavka['cena2']:.2f}"))  # Ukupna vrednost

            # Dodavanje dugmeta za brisanje
            btn_obrisi = QPushButton("Obriši")
            btn_obrisi.clicked.connect(partial(self.obrisi_stavku, stavka["id"]))
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
            self.stavkeTable.setCellWidget(row, 8, btn_obrisi)

        # Ažuriramo ukupan iznos
        self.refund_total()
    
    def azuriraj_kolicinu(self, item):
        try:
            if self.aktivan_mod != "refundacija":
                return

            row = item.row()
            column = item.column()

            if column != 3:
                return

            nova_kolicina = float(item.text()) if item.text() else 0
            if nova_kolicina <= 0:
                raise ValueError("❌ Količina mora biti veća od 0.")

            id_stavke_item = self.stavkeTable.item(row, 0)
            if not id_stavke_item:
                raise ValueError("❌ ID stavke nije pronađen.")

            id_stavke = int(id_stavke_item.text())
            stavka = next((s for s in self.kasa1 if s["id"] == id_stavke), None)
            if not stavka:
                raise ValueError(f"❌ Stavka sa ID-jem {id_stavke} nije pronađena u modelu kasa1.")

            originalna_kolicina = stavka["kolic"]
            if nova_kolicina > originalna_kolicina:
                QMessageBox.warning(self, "Greška", f"Količina ne može biti veća od originalne ({originalna_kolicina:.3f}).")
                item.setText(f"{originalna_kolicina:.3f}")
                return

            stavka["kolic"] = nova_kolicina
            stavka["vrednost"] = nova_kolicina * stavka["cena"]

            vrednost_item = self.stavkeTable.item(row, 7)
            if vrednost_item is None:
                vrednost_item = QTableWidgetItem()
                self.stavkeTable.setItem(row, 7, vrednost_item)

            vrednost_item.setText(f"{stavka['vrednost']:.2f}")
            self.refund_total()
            self.azuriraj_kolicinu_u_bazi(id_stavke, nova_kolicina)

        except ValueError as ve:
            print(f"❌ Greška pri ažuriranju količine: {ve}")
            QMessageBox.warning(self, "Greška", str(ve))
        except Exception as e:
            print(f"❌ Greška pri ažuriranju količine: {e}")
            QMessageBox.critical(self, "Greška", f"Greška pri ažuriranju količine:\n{e}")


    def azuriraj_kolicinu_u_bazi(self, id_stavke, nova_kolicina):
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
            UPDATE "kasa"."kasa1"
            SET kolic = %s
            WHERE id = %s
            """, (nova_kolicina, id_stavke))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ Greška pri ažuriranju baze: {e}")


    def povezi_signale_stavkeTable(self):
        self.stavkeTable.itemChanged.connect(self.azuriraj_kolicinu)


    def postavi_stavkeTable_editabilnost(self):
        for row in range(self.stavkeTable.rowCount()):
            for column in range(self.stavkeTable.columnCount()):
                item = self.stavkeTable.item(row, column)

                if item is None:
                    print(f"Upozorenje: item na ({row}, {column}) je None, preskačem.")
                    continue  # Preskačemo iteraciju ako item ne postoji

                if column == 3 and self.aktivan_mod == "refundacija":
                    item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)


    def refund_total(self):
        try:
            total = 0
            for row in range(self.stavkeTable.rowCount()):
                vrednost_item = self.stavkeTable.item(row, 7)
                vrednost = float(vrednost_item.text()) if vrednost_item else 0
                total += vrednost
            self.totalEdit.setText(f"{total:.2f}")
        except Exception as e:
            print(f"❌ Greška pri ažuriranju ukupnog iznosa: {e}")
            
    ######################################################################
    # Refundacija snimanje u bazu i stampa
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
            tipracuna = 0
            tiptransakcije = 1  # Refundacija
            dokstatus = 'PR'
            ui = 'u'

            # Dohvatanje podataka o kupcu i referentnom računu
            kodkupca = self.tipEdit.text().strip() if self.tipEdit.text() else None
            oznakakupca = self.kupacEdit.text().strip() if self.kupacEdit.text() else None
            referentni_racun = self.brrnpuEdit.text().strip()  # Broj fiskalnog računa koji refundiramo
            vreme_referentnog = self.vremeTransEdit.text().strip()  # Vreme referentnog računa

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
            (god, kar, broj, datum, kasa, sifobj, smena, vrgotovina, vrkartica, vrfaktura, vrcek, ukiznos, refundacija, idpartneri, kodkupca, oznakakupca, tipplacanja, tipracuna, tiptransakcije, dokstatus, refbrracpu, kreirao)
            VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, 'sistem')
            """, (
                int(GODINA), 1, novi_broj_racuna, int(KASA), SIFOBJEKTA, 1,
                round(float(self.gotovinaEdit.text() or 0), 2),
                round(float(self.karticaEdit.text() or 0), 2),
                round(float(self.racunEdit.text() or 0), 2),
                round(float(self.cekEdit.text() or 0), 2),
                round(float(self.totalEdit.text() or 0), 2),
                round(float(self.totalEdit.text() or 0), 2),  # Refundacija
                kodkupca, oznakakupca,
                1 if float(self.gotovinaEdit.text() or 0) > 0 else 0,
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
                    "Fiskalni račun PR", artikli_id, SIFOBJEKTA, GLAVNA_LOKACIJA_ID, porezid, ui, int(KASA)
                ))
                
                sifra, prodajna_cena, ukupna_kolicina, *_ = artikal
                #self.azuriraj_zalihe(sifra, ukupna_kolicina, dodaj=True)  # Vraćamo robu na zalihu

            conn.commit()
            #print(f"✅ Refundacija uspešno snimljena u bazi sa brojem {novi_broj_racuna}.")
            return novi_broj_racuna  # Vraćamo broj refundiranog računa

        except Exception as e:
            print(f"❌ Greška pri snimanju refundacije: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def generisi_json_refundacija(self, broj_racuna, stavke, placanja, kasir, ip_stampe):
        """Generiše JSON fajl za fiskalizaciju refundacije."""
        try:
            godina = str(datetime.now().year)[-2:]
            direktorijum = f"\\\\{ip_stampe}\\MyLPFR\\exchange\\to-sdc"
            json_fajl = os.path.join(direktorijum, f"CreateInvoice-{broj_racuna}-{godina}.json")
            racun = {
                "cashier": kasir,
                "invoiceNumber": "1161/1.0.128.0",
                "invoiceType": "0",
                "transactionType": "1",
                "referentDocumentNumber": self.brrnpuEdit.text(),
                "referentDocumentDT": self.vremeTransEdit.text(),
                "items": stavke,
                "payment": placanja,
                "journalOptions": {"print": "true", "message": "REFUNDACIJA IZVRŠENA"}
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
            ip_stampe, lservis = self.ucitaj_konfiguraciju_kase()
            if not ip_stampe:
                raise Exception("IP adresa štampača nije pronađena u konfiguraciji.")

            # Snimanje refundiranog računa u bazu
            broj_racuna = self.snimi_racun_refundacije()
            if not broj_racuna:
                raise Exception("Generisanje broja refundiranog računa nije uspelo.")

            # Priprema podataka
            stavke = self.pripremi_stavke(lservis)
            placanja = self.pripremi_placanja()
            kasir = "Kasir 1"

            # Generisanje JSON-a i slanje na štampač
            json_fajl = self.generisi_json_refundacija(broj_racuna, stavke, placanja, kasir, ip_stampe)
            if not json_fajl:
                raise Exception("Generisanje JSON fajla za refundaciju nije uspelo.")

            # Čekanje na odgovor iz PU
            status, fajl_odgovora = self.obradi_odgovor(broj_racuna, ip_stampe)
            if status == "success":
                #print("✅ Refundacija uspešno fiskalizovana.")
                self.azuriraj_kasasum(broj_racuna, ip_stampe)
                self.resetuj_kontrole()
            elif status == "error":
                print("❌ Greška pri fiskalizaciji refundacije. Proverite fajl sa greškom.")
            else:
                print("❌ Odgovor nije stigao u zadatom vremenu.")

        except Exception as e:
            print(f"❌ Greška pri fiskalizaciji refundacije: {e}")

    def resetuj_kontrole(self):
        """
        Resetuje sve kontrole glavnog prozora nakon štampe fiskalnog računa ili refundacije.
        """
        # Reset polja za unos
        self.gotovinaEdit.clear()
        self.karticaEdit.clear()
        self.cekEdit.clear()
        self.racunEdit.clear()
        self.ostPopEdit.setText("0.00")
        self.kusurEdit.setText("0.00")
        self.totalEdit.setText("0.00")
        self.tipEdit.clear()
        self.kupacEdit.clear()
        self.brrnpuEdit.clear()
        self.vremeTransEdit.clear()
        self.poslednjiAvansEdit.clear()
        self.iznosRefundacijeEdit.clear()

        # Prazni tabelu stavkeTable
        self.stavkeTable.setRowCount(0)

        # Reset aktivnog kupca
        self.aktivan_kupac = 1

        # Onemogućavanje dugmeta za štampu
        self.btnStampa.setEnabled(False)

        #print("✅ Sve kontrole su resetovane.")
        
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())
