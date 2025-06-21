import os
import sys
import psycopg2
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QTableWidgetItem, QPushButton, QMessageBox, QFileDialog
from PyQt6.QtGui import QColor, QBrush
from PyQt6 import uic
import configparser
import random
import mimetypes
from functools import partial
import json
import base64
from datetime import datetime
from lxml import etree
import requests
import datetime
import uuid



# Učitavanje konfiguracije iz kasa.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, "kasa.ini")
config = configparser.ConfigParser()
config.read(config_path)
GODINA = config.get('POS_Settings', 'god')
SIFOBJEKTA = config.get('POS_Settings', 'sifobj')
KASA = config.get('POS_Settings', 'kasa')

class eFaktureDialog(QDialog):
    def __init__(self, fakture_dialog, faktura_id, parent=None):  # bez tipa
        super().__init__(parent)
        self.fakture_dialog = fakture_dialog
        self.faktura_id = faktura_id  # sada imamo ID fakture na raspolaganju
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "eFakture.ui")
        uic.loadUi(ui_path, self)

        #print(f"Otvoren eFakture dijalog za fakturu ID: {self.faktura_id}")


        self.odustaniBtn.clicked.connect(self.reject)
        self.okruzenje_za_slanje()
        self.popuni_info2(self.faktura_id)

        #=== Dugmad za izbor priloga ===@
        self.prilog1Btn.clicked.connect(lambda: self.izaberi_prilog(self.prilog1Edit))
        self.prilog2Btn.clicked.connect(lambda: self.izaberi_prilog(self.prilog2Edit))

        #=== Generisanje XML ===#
        self.xmlBtn.clicked.connect(self.kreiraj_xml_efakturu)
        self.posaljiBtn.clicked.connect(self._posalji_na_sef)
        #self.posaljiBtn.clicked.connect(self.proveri_registrovanost_firme_na_sef_po_pibu())

   

    def okruzenje_za_slanje(self):
        """
        Određuje na osnovu baze da li se koristi testno ili produkciono okruženje za slanje eFakture.

        Vraća:
            - url (str): URL SEF endpointa
            - apikey (str): API ključ
            - demoef (bool): Da li je demo okruženje aktivno
            - pib (str): PIB korisnika
            - jbkjs (str): JBKJS broj korisnika
            - matbr (str): Matični broj korisnika
        """
        conn = None
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            cursor.execute("SELECT demoef, kljuc_api, kljuc_demo_api, pib, jbkjs, matbr FROM kasa.fvr LIMIT 1")
            fvr_demo, fvr_api, fvr_api_demo, pib, jbkjs, matbr = cursor.fetchone()

            if fvr_demo:
                url = "https://demoefaktura.mfin.gov.rs/api/publicApi/sales-invoice/ubl"
                apikey = fvr_api_demo
                self.info1Label.setText("Radite u TESTNOM okruženju")
                self.info1Label.setStyleSheet("background-color: #fff3cd;")
            else:
                url = "https://efaktura.mfin.gov.rs/api/publicApi/sales-invoice/ubl"
                apikey = fvr_api
                self.info1Label.setText("Radite u PRODUKCIONOM okruženju")
                self.info1Label.setStyleSheet("background-color: #d4edda;")

            return url, apikey, fvr_demo, pib, jbkjs, matbr

        except Exception as e:
            print("Greška prilikom određivanja okruženja za eFakturu:", e)
            return None, None, None, None, None, None

        finally:
            if conn:
                conn.close()
    
    def kupac_na_sefu(pib: str, matbr: str, jbkjs: str, demo: bool) -> bool:
        """
        Proverava da li je kupac registrovan na SEF-u.

        :param pib: PIB kupca
        :param matbr: Matični broj kupca
        :param jbkjs: JBKJS broj (ako postoji, u suprotnom prazno)
        :param demo: Da li koristiti demo SEF API
        :return: True ako je kupac registrovan, False ako nije
        """
        url = (
            "https://demoefaktura.mfin.gov.rs/api/publicApi/Company/CheckIfCompanyRegisteredOnEfaktura"
            if demo else
            "https://efaktura.mfin.gov.rs/api/publicApi/Company/CheckIfCompanyRegisteredOnEfaktura"
        )

        payload = {
            "registrationNumber": matbr,
            "jbkjs": jbkjs,
            "vatNumber": pib
        }

        try:
            response = requests.post(url, json=payload, headers={"Accept": "application/json"})
            if response.status_code == 200:
                data = response.json()
                return data.get("eFakturaRegisteredCompany", False)
            else:
                print(f"Greška prilikom provere kupca ({response.status_code}):", response.text)
                return False
        except Exception as e:
            print("Greška u kupac_na_sefu:", e)
            return False

    def popuni_info2(self, faktura_id: int):
        """
        Popunjava info2Label i postavlja crfCheck na osnovu podataka o kupcu,
        uključujući i proveru da li je kupac registrovan na SEF-u.
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
            # Dohvati podatke o okruzenju
            cursor.execute("SELECT demoef FROM kasa.fvr LIMIT 1")
            fvr_demo = cursor.fetchone()

            # Dohvati podatke o fakturi
            cursor.execute("""
                SELECT brojfakture, idpartneri FROM kasa.fakture WHERE id = %s
            """, (faktura_id,))
            rezultat = cursor.fetchone()
            if not rezultat:
                self.info2Label.setText("Faktura nije pronađena.")
                self.info2Label.setStyleSheet("background-color: #f8d7da;")
                return

            broj_fakture, id_partneri = rezultat

            # Dohvati podatke o kupcu
            cursor.execute("""
                SELECT naziv, pib, jbkjs, matbr FROM kasa.partneri WHERE id = %s
            """, (id_partneri,))
            kupac = cursor.fetchone()
            if not kupac:
                self.info2Label.setText("Kupac nije pronađen.")
                self.info2Label.setStyleSheet("background-color: #f8d7da;")
                return

            naziv, pib, jbkjs, matbr = kupac

            # === Priprema tela za SEF proveru ===
            body = {}
            if matbr:
                body["registrationNumber"] = matbr
            if pib:
                body["vatNumber"] = pib
            if jbkjs:
                body["jbkjs"] = jbkjs

            # === Odredi API ključ i URL za proveru u produkcionom okruženju ===
            cursor.execute("SELECT kljuc_api FROM kasa.fvr LIMIT 1")
            rezultat_api = cursor.fetchone()
            if not rezultat_api:
                self.info2Label.setText("Nedostaje API ključ.")
                self.info2Label.setStyleSheet("background-color: #f8d7da;")
                return

            api_key = rezultat_api[0]
            if fvr_demo:
                sef_url = "https://demoefaktura.mfin.gov.rs/api/publicApi/Company/CheckIfCompanyRegisteredOnEfaktura"
            else:
                sef_url = "https://efaktura.mfin.gov.rs/api/publicApi/Company/CheckIfCompanyRegisteredOnEfaktura"

            print("📡 Proveravam kupca na SEF-u:", body)

            # === Poziv REST API-ja ===
            firma_registrovana = False
            try:
                response = requests.post(
                    sef_url,
                    json=body,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "apikey": api_key
                    }
                )
                if response.status_code == 200:
                    odgovor = response.json()
                    firma_registrovana = odgovor.get("EFakturaRegisteredCompany") or odgovor.get("eFakturaRegisteredCompany")
            except Exception as e:
                print("⚠️ Greška pri proveri SEF kupca:", e)

            # === Detekcija da li treba slati u CRF ===
            salje_u_crf = False
            if jbkjs and str(jbkjs)[0] in "01246":
                salje_u_crf = True

            # === Postavi info i boje ===
            if firma_registrovana:
                if salje_u_crf:
                    self.info2Label.setText(f"Kupac je korisnik budžetskih sredstava.\nFaktura {broj_fakture} za {naziv} je spremna za slanje u CRF.")
                    self.crfCheck.setChecked(True)
                else:
                    self.info2Label.setText(f"Kupac je registrovan na SEF-u.\nFaktura {broj_fakture} za {naziv} je spremna za slanje u SEF.")
                    self.crfCheck.setChecked(False)
                self.info2Label.setStyleSheet("background-color: #d4edda;")  # zelena
            else:
                self.info2Label.setText(f"Kupac NIJE registrovan na SEF-u.\nFaktura {broj_fakture} za {naziv} će biti poslata u pojedinačnu evidenciju.")
                self.info2Label.setStyleSheet("background-color: #fff3cd;")  # žuta
                self.crfCheck.setChecked(False)

        except Exception as e:
            print("Greška u popuni_info2:", e)
            self.info2Label.setText("Greška prilikom učitavanja podataka.")
            self.info2Label.setStyleSheet("background-color: #f8d7da;")

        finally:
            if conn:
                conn.close()

    # === Funkcija za izbor priloga ===#
    def izaberi_prilog(self, target_edit):
        """
        Otvara dijalog za izbor fajla i upisuje izabranu putanju u odgovarajući QLineEdit.

        :param target_edit: QLineEdit u koji će biti upisana putanja fajla
        """
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Izaberite prilog uz fakturu",
                "",  # početna lokacija
                "Dokumenta (*.pdf *.jpg *.jpeg *.png *.doc *.docx);;Svi fajlovi (*)"
            )

            if file_path:
                target_edit.setText(file_path)

        except Exception as e:
            print("Greška prilikom izbora fajla:", e)

#=========== Fakture po UBL standardu ==============#
#=========== Faktura sa prilogom i popustima ========#

    def ucitaj_priloge(self):
        """
        Učitava dodatne priloge iz polja self.prilog1Edit i self.prilog2Edit.

        :return: Lista rečnika sa ključevima: 'naziv', 'sadrzaj', 'mime'
        """
        dodatni_prilozi = []

        for edit in [self.prilog1Edit, self.prilog2Edit]:
            putanja = edit.text().strip()
            if putanja:
                if not os.path.isfile(putanja):
                    QMessageBox.warning(self, "Greška", f"Fajl ne postoji:\n{putanja}")
                    continue

                velicina = os.path.getsize(putanja)
                if velicina > 25 * 1024 * 1024:
                    QMessageBox.warning(self, "Prevelik fajl", f"Fajl {os.path.basename(putanja)} je veći od 25MB i neće biti dodat.")
                    continue

                try:
                    with open(putanja, "rb") as f:
                        sadrzaj = f.read()
                        sadrzaj_b64 = base64.b64encode(sadrzaj).decode("utf-8")
                        mime = mimetypes.guess_type(putanja)[0] or "application/octet-stream"

                        dodatni_prilozi.append({
                            "naziv": os.path.basename(putanja),
                            "b64": sadrzaj_b64,
                            "mime": mime
                        })
                except Exception as e:
                    QMessageBox.critical(self, "Greška", f"Greška pri čitanju fajla:\n{putanja}\n\n{e}")

        return dodatni_prilozi
    
    def generisi_efaktura_xml(self, faktura_id, folder_izvestaja):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            cursor.execute("SELECT naziv, adresa, pobro, mesto, pib, banka, primarni_racun, tel, email, matbr, sifdel FROM kasa.fvr LIMIT 1")
            fvr = cursor.fetchone()
            fvr_banka = json.loads(fvr[5]) if isinstance(fvr[5], str) else {}
            fvr_dict = {
                "naziv": fvr[0],
                "adresa": fvr[1],
                "pobro": fvr[2],
                "mesto": fvr[3],
                "pib": fvr[4],
                "banka": fvr_banka.get("naziv", ""),
                "racun": fvr[6],
                "email": fvr[8],
                "matbr": fvr[9]
            }

            cursor.execute("SELECT brojfakture, datumpred, datumdpd, datumvazenja, idpartneri, brracpu, osnovica, ukupnopdv, vrednost, brugov, god, sifobj, vrsta FROM kasa.fakture WHERE id = %s", (faktura_id,))
            faktura = cursor.fetchone()
            brojfakture, datumpred, datumdpd, datumvazenja, idpartneri, brracpu, osnovica, ukupnopdv, vrednost, brugov, god, sifobj, vrsta = faktura

            cursor.execute("SELECT naziv, adresa, pobro, mesto, pib, matbr FROM kasa.partneri WHERE id = %s", (idpartneri,))
            partner = cursor.fetchone()
            kupac = {
                "naziv": partner[0],
                "adresa": partner[1],
                "pobro": partner[2],
                "mesto": partner[3],
                "pib": partner[4],
                "matbr": partner[5]
            }

            query = """
                SELECT
                    ka.sifra, a.naziv, jm.jm, ka.kolicina,
                    ROUND((ka.cenanabavna * (1 - ((ka.porezproc * 100)::numeric / (ka.porezproc + 100)::numeric) / 100))::numeric, 2),
                    ka.rabatproc,
                    ROUND((ka.cena * ka.kolicina)::numeric * (ka.rabatproc::numeric / 100), 2),
                    ROUND(ka.kolicina::numeric * ka.cena::numeric * ROUND((1 - ((ka.porezproc * 100)::numeric / (ka.porezproc + 100)::numeric) / 100)::numeric, 4),2),
                    ka.porezproc, ka.porez,
                    ROUND((ka.cena * ka.kolicina)::numeric, 2),
                    ka.tarifa, ka.id
                FROM kasa.karticaart ka
                LEFT JOIN kasa.artikli a ON a.sifra = ka.sifra
                LEFT JOIN kasa.jedmere jm ON jm.id = a.jedinica_mere_id
                WHERE ka.god = %s AND ka.sifobj = %s AND ka.brfakt = %s
                ORDER BY ka.id
            """
            cursor.execute(query, (god, sifobj, brojfakture))
            stavke = cursor.fetchall()

            for s in stavke:
                if None in s:
                    print("UPOZORENJE: Stavka sadrži None vrednosti:", s)

            pdv_pregled = {}
            for s in stavke:
                stopa = int(s[8])
                osnovica = float(s[7])
                iznos_pdv = float(s[9])

                if stopa not in pdv_pregled:
                    pdv_pregled[stopa] = {"osnovica": 0.0, "iznos": 0.0, "stopa": stopa}

                pdv_pregled[stopa]["osnovica"] += osnovica
                pdv_pregled[stopa]["iznos"] += iznos_pdv

            naziv_priloga = f"Racun_{brojfakture}.pdf"
            putanja_priloga = os.path.join(folder_izvestaja, naziv_priloga)
            if os.path.exists(putanja_priloga):
                with open(putanja_priloga, "rb") as f:
                    prilog_b64 = base64.b64encode(f.read()).decode("utf-8")
            else:
                prilog_b64 = "PDF nije pronađen"

            podaci = {
                "fvr": fvr_dict,
                "kupac": kupac,
                "faktura": {
                    "broj": brojfakture,
                    "ugovor": brugov,
                    "tip": "386" if vrsta == 3 else "380",
                    "datum": datumpred.strftime("%Y-%m-%d"),
                    "valuta": datumvazenja.strftime("%Y-%m-%d"),
                    "osnovica": float(osnovica),
                    "ukupnopdv": float(ukupnopdv),
                    "ukupno": float(vrednost),
                    "vrsta": vrsta,
                    "brracpu": brracpu
                },
                "stavke": stavke,
                "pdv": list(pdv_pregled.values()),
                "prilog_b64": prilog_b64,
                "god": god,
                "sifobj": sifobj
            }

            podaci["dodatni_prilozi"] = self.ucitaj_priloge()

            # ✳️ Dodavanje avansnih faktura kao veza za konačni račun (BillingReference)
            if vrsta == 1:
                detalji_avansa = self.fakture_dialog.izvuci_detaljne_avanse(brracpu)
                for d in detalji_avansa:
                    d["faktura_broj"] = d["brfakt"]
                    d["datum_izdavanja"] = d["datum"]
                podaci["detalji_avansa"] = detalji_avansa

            print("POZIV: napravi_efaktura_xml_iz_podataka će se izvršiti")
            return self.napravi_efaktura_xml_iz_podataka(podaci, folder_izvestaja)

        except Exception as e:
            print("Greška u pripremi podataka za eFakturu:", e)
            return None

        finally:
            if conn:
                conn.close()
    
    # === DRUGI DEO: Kreiranje i snimanje XML fajla ===
    def napravi_efaktura_xml_iz_podataka(self, podaci, folder_izvestaja):
        try:
            from lxml import etree
            import os

            nsmap = {
                None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
                "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
                "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
                "cec": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
                "sbt": "http://mfin.gov.rs/srbdt/srbdtext",
                "xsi": "http://www.w3.org/2001/XMLSchema-instance"
            }

            def el(tag, text=None, ns="cbc"):
                e = etree.Element(f"{{{nsmap[ns]}}}{tag}")
                if text is not None:
                    e.text = str(text)
                return e

            def safe_el(tag, text=None, ns="cbc", attribs=None):
                element = el(tag, text, ns)
                if attribs:
                    for k, v in attribs.items():
                        element.attrib[k] = v
                return element

            root = etree.Element("Invoice", nsmap=nsmap)

            # === UBL EXTENSIONS ako je konačni račun sa prethodnim avansima ===
            # === UBL Extensions: samo za konačni račun (vrsta == 1) koji ima prethodne avanse ===
            if podaci["faktura"].get("vrsta") == 1:
                brracpu_konacnog = podaci["faktura"].get("brracpu")
                detalji_avansi = self.fakture_dialog.izvuci_detaljne_avanse(brracpu_konacnog)

                if detalji_avansi:
                    ubl_extensions = etree.SubElement(root, f"{{{nsmap['cec']}}}UBLExtensions")
                    ubl_ext = etree.SubElement(ubl_extensions, f"{{{nsmap['cec']}}}UBLExtension")
                    ext_content = etree.SubElement(ubl_ext, f"{{{nsmap['cec']}}}ExtensionContent")
                    srbdt_ext = etree.SubElement(ext_content, f"{{{nsmap['sbt']}}}SrbDtExt")

                    # === InvoicedPrepaymentAmmount (lista prethodnih avansa sa PDV osnovicama i stopama) ===
                    for avans in detalji_avansi:
                        invprep = etree.SubElement(srbdt_ext, f"{{http://www.w3.org/2001/XMLSchema}}InvoicedPrepaymentAmmount")

                        etree.SubElement(invprep, f"{{{nsmap['cbc']}}}ID").text = avans["brfakt"]

                        tax_total = etree.SubElement(invprep, f"{{{nsmap['cac']}}}TaxTotal")
                        ukupno_pdv = avans["pdv_opsta"] + avans["pdv_posebna"]
                        etree.SubElement(tax_total, f"{{{nsmap['cbc']}}}TaxAmount", currencyID="RSD").text = f"{ukupno_pdv:.2f}"

                        def dodaj_pdv(tarifa_id, osnovica, pdv, procenat):
                            if osnovica + pdv > 0:
                                tax_sub = etree.SubElement(tax_total, f"{{{nsmap['cac']}}}TaxSubtotal")
                                etree.SubElement(tax_sub, f"{{{nsmap['cbc']}}}TaxableAmount", currencyID="RSD").text = f"{osnovica:.2f}"
                                etree.SubElement(tax_sub, f"{{{nsmap['cbc']}}}TaxAmount", currencyID="RSD").text = f"{pdv:.2f}"
                                tax_cat = etree.SubElement(tax_sub, f"{{{nsmap['cac']}}}TaxCategory")
                                etree.SubElement(tax_cat, f"{{{nsmap['cbc']}}}ID").text = tarifa_id
                                etree.SubElement(tax_cat, f"{{{nsmap['cbc']}}}Percent").text = f"{procenat}"
                                tax_scheme = etree.SubElement(tax_cat, f"{{{nsmap['cac']}}}TaxScheme")
                                etree.SubElement(tax_scheme, f"{{{nsmap['cbc']}}}ID").text = "VAT"

                        # PDV po opštoj i posebnoj stopi
                        dodaj_pdv("S", avans["osn_opsta"], avans["pdv_opsta"], 20)
                        dodaj_pdv("O", avans["osn_posebna"], avans["pdv_posebna"], 0)

                    # === ReducedTotals (sumirani iznosi avansa) ===
                    suma_osn = sum(a["osn_opsta"] + a["osn_posebna"] for a in detalji_avansi)
                    suma_pdv = sum(a["pdv_opsta"] + a["pdv_posebna"] for a in detalji_avansi)

                    reduced = etree.SubElement(srbdt_ext, f"{{http://www.w3.org/2001/XMLSchema}}ReducedTotals")
                    tax_total_r = etree.SubElement(reduced, f"{{{nsmap['cac']}}}TaxTotal")
                    etree.SubElement(tax_total_r, f"{{{nsmap['cbc']}}}TaxAmount", currencyID="RSD").text = "0.00"

                    # PDV 20%
                    tax_sub1 = etree.SubElement(tax_total_r, f"{{{nsmap['cac']}}}TaxSubtotal")
                    etree.SubElement(tax_sub1, f"{{{nsmap['cbc']}}}TaxableAmount", currencyID="RSD").text = "0.00"
                    etree.SubElement(tax_sub1, f"{{{nsmap['cbc']}}}TaxAmount", currencyID="RSD").text = "0.00"
                    cat1 = etree.SubElement(tax_sub1, f"{{{nsmap['cac']}}}TaxCategory")
                    etree.SubElement(cat1, f"{{{nsmap['cbc']}}}ID").text = "S"
                    etree.SubElement(cat1, f"{{{nsmap['cbc']}}}Percent").text = "20"
                    etree.SubElement(etree.SubElement(cat1, f"{{{nsmap['cac']}}}TaxScheme"), f"{{{nsmap['cbc']}}}ID").text = "VAT"

                    # PDV 0%
                    tax_sub2 = etree.SubElement(tax_total_r, f"{{{nsmap['cac']}}}TaxSubtotal")
                    etree.SubElement(tax_sub2, f"{{{nsmap['cbc']}}}TaxableAmount", currencyID="RSD").text = "0.00"
                    etree.SubElement(tax_sub2, f"{{{nsmap['cbc']}}}TaxAmount", currencyID="RSD").text = "0.00"
                    cat2 = etree.SubElement(tax_sub2, f"{{{nsmap['cac']}}}TaxCategory")
                    etree.SubElement(cat2, f"{{{nsmap['cbc']}}}ID").text = "O"
                    etree.SubElement(cat2, f"{{{nsmap['cbc']}}}Percent").text = "0"
                    etree.SubElement(etree.SubElement(cat2, f"{{{nsmap['cac']}}}TaxScheme"), f"{{{nsmap['cbc']}}}ID").text = "VAT"

                    # Ukupan iznos avansa
                    legal_total = etree.SubElement(reduced, f"{{{nsmap['cac']}}}LegalMonetaryTotal")
                    etree.SubElement(legal_total, f"{{{nsmap['cbc']}}}TaxExclusiveAmount", currencyID="RSD").text = f"{suma_osn:.2f}"
                    etree.SubElement(legal_total, f"{{{nsmap['cbc']}}}TaxInclusiveAmount", currencyID="RSD").text = "0.00"
                    etree.SubElement(legal_total, f"{{{nsmap['cbc']}}}PayableAmount", currencyID="RSD").text = "0.00"

            # === Zaglavlje ===
            root.append(safe_el("CustomizationID", "urn:cen.eu:en16931:2017#compliant#urn:mfin.gov.rs:srbdt:2022#conformant#urn:mfin.gov.rs:srbdtext:2022"))
            root.append(safe_el("ID", podaci["faktura"]["broj"]))
            root.append(safe_el("IssueDate", podaci["faktura"]["datum"]))
            root.append(safe_el("DueDate", podaci["faktura"]["valuta"]))
            root.append(safe_el("InvoiceTypeCode", podaci["faktura"].get("tip", "380")))
            root.append(safe_el("DocumentCurrencyCode", "RSD"))

            # === Period fakturisanja ===
            inv_period = etree.SubElement(root, f"{{{nsmap['cac']}}}InvoicePeriod")
            description_code = "432" if podaci["faktura"]["tip"] == "386" else "35"
            inv_period.append(safe_el("DescriptionCode", description_code))

            # === Referenciranje prethodnih avansa (BillingReference) — samo za konačne račune (vrsta == 1) ===
            if podaci["faktura"].get("vrsta") == 1:
                brracpu_konacnog = podaci["faktura"].get("brracpu")
                detalji_avansi = self.fakture_dialog.izvuci_detaljne_avanse(brracpu_konacnog)

                for avans in detalji_avansi:
                    billing = etree.SubElement(root, f"{{{nsmap['cac']}}}BillingReference")
                    invoice_ref = etree.SubElement(billing, f"{{{nsmap['cac']}}}InvoiceDocumentReference")
                    invoice_ref.append(safe_el("ID", avans["brfakt"]))

                    datum_str = avans["datum"]
                    try:
                        datum_fmt = datetime.datetime.strptime(datum_str, "%d.%m.%Y").strftime("%Y-%m-%d")
                    except ValueError:
                        datum_fmt = datum_str  # fallback ako je već OK

                    invoice_ref.append(safe_el("IssueDate", datum_fmt))

            # === Ugovor (mora ići posle BillingReference) ===
            contract_ref = etree.SubElement(root, f"{{{nsmap['cac']}}}ContractDocumentReference")
            contract_ref.append(safe_el("ID", podaci["faktura"].get("ugovor", "N/A")))

            # === Prilog (PDF) ===
            prilog_naziv = f"Racun_{podaci['faktura']['broj']}.pdf"
            doc_ref = etree.SubElement(root, f"{{{nsmap['cac']}}}AdditionalDocumentReference")
            doc_ref.append(safe_el("ID", prilog_naziv))
            attachment = etree.SubElement(doc_ref, f"{{{nsmap['cac']}}}Attachment")
            binary = safe_el("EmbeddedDocumentBinaryObject", podaci["prilog_b64"], attribs={"mimeCode": "application/pdf", "filename": prilog_naziv})
            attachment.append(binary)

            # === Prodavac ===
            supplier_party = etree.SubElement(root, f"{{{nsmap['cac']}}}AccountingSupplierParty")
            supplier = etree.SubElement(supplier_party, f"{{{nsmap['cac']}}}Party")
            supplier.append(safe_el("EndpointID", podaci["fvr"]["pib"], attribs={"schemeID": "9948"}))
            party_name = etree.SubElement(supplier, f"{{{nsmap['cac']}}}PartyName")
            party_name.append(safe_el("Name", podaci["fvr"]["naziv"]))
            addr = etree.SubElement(supplier, f"{{{nsmap['cac']}}}PostalAddress")
            addr.append(safe_el("StreetName", podaci["fvr"]["adresa"]))
            addr.append(safe_el("CityName", podaci["fvr"]["mesto"]))
            addr.append(safe_el("PostalZone", podaci["fvr"]["pobro"]))
            country = etree.SubElement(addr, f"{{{nsmap['cac']}}}Country")
            country.append(safe_el("IdentificationCode", "RS"))
            tax = etree.SubElement(supplier, f"{{{nsmap['cac']}}}PartyTaxScheme")
            tax.append(safe_el("CompanyID", f"RS{podaci['fvr']['pib']}"))
            tax_scheme = etree.SubElement(tax, f"{{{nsmap['cac']}}}TaxScheme")
            tax_scheme.append(safe_el("ID", "VAT"))
            legal = etree.SubElement(supplier, f"{{{nsmap['cac']}}}PartyLegalEntity")
            legal.append(safe_el("RegistrationName", podaci["fvr"]["naziv"]))
            legal.append(safe_el("CompanyID", podaci["fvr"]["matbr"]))
            contact = etree.SubElement(supplier, f"{{{nsmap['cac']}}}Contact")
            contact.append(safe_el("ElectronicMail", podaci["fvr"]["email"]))

            # === Kupac ===
            customer_party = etree.SubElement(root, f"{{{nsmap['cac']}}}AccountingCustomerParty")
            customer = etree.SubElement(customer_party, f"{{{nsmap['cac']}}}Party")
            customer.append(safe_el("EndpointID", podaci["kupac"]["pib"], attribs={"schemeID": "9948"}))
            party_name = etree.SubElement(customer, f"{{{nsmap['cac']}}}PartyName")
            party_name.append(safe_el("Name", podaci["kupac"]["naziv"]))
            addr = etree.SubElement(customer, f"{{{nsmap['cac']}}}PostalAddress")
            addr.append(safe_el("StreetName", podaci["kupac"]["adresa"]))
            addr.append(safe_el("CityName", podaci["kupac"]["mesto"]))
            addr.append(safe_el("PostalZone", podaci["kupac"]["pobro"]))
            country = etree.SubElement(addr, f"{{{nsmap['cac']}}}Country")
            country.append(safe_el("IdentificationCode", "RS"))
            tax = etree.SubElement(customer, f"{{{nsmap['cac']}}}PartyTaxScheme")
            tax.append(safe_el("CompanyID", f"RS{podaci['kupac']['pib']}"))
            tax_scheme = etree.SubElement(tax, f"{{{nsmap['cac']}}}TaxScheme")
            tax_scheme.append(safe_el("ID", "VAT"))
            legal = etree.SubElement(customer, f"{{{nsmap['cac']}}}PartyLegalEntity")
            legal.append(safe_el("RegistrationName", podaci["kupac"]["naziv"]))
            legal.append(safe_el("CompanyID", podaci["kupac"]["matbr"]))

            # === Isporuka samo za tip 380 ===
            if podaci["faktura"]["tip"] == "380":
                delivery = etree.SubElement(root, f"{{{nsmap['cac']}}}Delivery")
                delivery.append(safe_el("ActualDeliveryDate", podaci["faktura"]["datum"]))

            # === Način plaćanja ===
            payment = etree.SubElement(root, f"{{{nsmap['cac']}}}PaymentMeans")
            payment.append(safe_el("PaymentMeansCode", "30"))
            payment.append(safe_el("PaymentID", podaci["faktura"]["broj"]))
            account = etree.SubElement(payment, f"{{{nsmap['cac']}}}PayeeFinancialAccount")
            account.append(safe_el("ID", podaci["fvr"]["racun"]))

            # === PDV ===
            tax_total = etree.SubElement(root, f"{{{nsmap['cac']}}}TaxTotal")
            tax_total.append(safe_el("TaxAmount", f"{podaci['faktura']['ukupnopdv']:.2f}", attribs={"currencyID": "RSD"}))
            for p in podaci["pdv"]:
                tax_sub = etree.SubElement(tax_total, f"{{{nsmap['cac']}}}TaxSubtotal")
                tax_sub.append(safe_el("TaxableAmount", f"{p['osnovica']:.2f}", attribs={"currencyID": "RSD"}))
                tax_sub.append(safe_el("TaxAmount", f"{p['iznos']:.2f}", attribs={"currencyID": "RSD"}))
                tax_cat = etree.SubElement(tax_sub, f"{{{nsmap['cac']}}}TaxCategory")
                tax_cat.append(safe_el("ID", "S"))
                tax_cat.append(safe_el("Percent", int(p['stopa'])))
                tax_scheme = etree.SubElement(tax_cat, f"{{{nsmap['cac']}}}TaxScheme")
                tax_scheme.append(safe_el("ID", "VAT"))

            # === Sumarni deo ===
            legal_total = etree.SubElement(root, f"{{{nsmap['cac']}}}LegalMonetaryTotal")
            legal_total.append(safe_el("LineExtensionAmount", f"{podaci['faktura']['osnovica']:.2f}", attribs={"currencyID": "RSD"}))
            legal_total.append(safe_el("TaxExclusiveAmount", f"{podaci['faktura']['osnovica']:.2f}", attribs={"currencyID": "RSD"}))
            legal_total.append(safe_el("TaxInclusiveAmount", f"{podaci['faktura']['ukupno']:.2f}", attribs={"currencyID": "RSD"}))
            legal_total.append(safe_el("AllowanceTotalAmount", "0", attribs={"currencyID": "RSD"}))
            #legal_total.append(safe_el("PrepaidAmount", "0", attribs={"currencyID": "RSD"}))
            legal_total.append(safe_el("PayableAmount", f"{podaci['faktura']['ukupno']:.2f}", attribs={"currencyID": "RSD"}))

            # === Stavke ===
            for idx, s in enumerate(podaci["stavke"], start=1):
                line = etree.SubElement(root, f"{{{nsmap['cac']}}}InvoiceLine")
                line.append(safe_el("ID", idx))
                line.append(safe_el("InvoicedQuantity", f"{s[3]:.3f}", attribs={"unitCode": s[2]}))
                line.append(safe_el("LineExtensionAmount", f"{s[7]:.2f}", attribs={"currencyID": "RSD"}))

                charge = etree.SubElement(line, f"{{{nsmap['cac']}}}AllowanceCharge")
                charge.append(safe_el("ChargeIndicator", "false"))
                charge.append(safe_el("Amount", "0", attribs={"currencyID": "RSD"}))

                item = etree.SubElement(line, f"{{{nsmap['cac']}}}Item")
                item.append(safe_el("Name", s[1]))
                seller_id = etree.SubElement(item, f"{{{nsmap['cac']}}}SellersItemIdentification")
                seller_id.append(safe_el("ID", s[0]))
                taxcat = etree.SubElement(item, f"{{{nsmap['cac']}}}ClassifiedTaxCategory")
                taxcat.append(safe_el("ID", "S"))
                taxcat.append(safe_el("Percent", int(s[8])))
                tax_scheme = etree.SubElement(taxcat, f"{{{nsmap['cac']}}}TaxScheme")
                tax_scheme.append(safe_el("ID", "VAT"))

                price = etree.SubElement(line, f"{{{nsmap['cac']}}}Price")
                price.append(safe_el("PriceAmount", f"{s[4]:.2f}", attribs={"currencyID": "RSD"}))

            # === Snimi fajl ===
            xml_path = os.path.join(folder_izvestaja, f"eFaktura_{podaci['faktura']['broj']}.xml")
            tree = etree.ElementTree(root)
            tree.write(xml_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")
            return xml_path

        except Exception as e:
            print("Greška pri generisanju XML fajla:", e)
            return None
        
    def izvuci_avansne_fakture_za_fakturu(self, faktura_id):
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()

            # Nađi brracpu fakture
            cursor.execute("SELECT brracpu FROM kasa.fakture WHERE id = %s", (faktura_id,))
            red = cursor.fetchone()
            if not red:
                return []
            brracpu_konacnog = red[0]

            # Nađi refbrracpu koji je povezan sa avansima
            cursor.execute("SELECT refbrracpu FROM kasa.kasasum WHERE brracpu = %s", (brracpu_konacnog,))
            red = cursor.fetchone()
            if not red or not red[0]:
                return []

            brracpu_ref = red[0]

            # Pronađi sve prethodne avanse
            avansi = []
            trenutni = brracpu_ref
            while trenutni:
                cursor.execute("""
                    SELECT refbrracpu, tipracuna, tiptransakcije, datum, broj
                    FROM kasa.kasasum
                    WHERE brracpu = %s
                """, (trenutni,))
                red = cursor.fetchone()
                if not red:
                    break
                refbrracpu, tipracuna, tiptransakcije, datum, broj = red

                if tipracuna == '4' and tiptransakcije == '0':
                    # Nađi povezanu fakturu
                    cursor.execute("""
                        SELECT brojfakture, datumpred
                        FROM kasa.fakture
                        WHERE brracpu = %s AND vrsta = 3 AND invoiceid IS NOT NULL
                    """, (trenutni,))
                    fakt = cursor.fetchone()
                    if fakt:
                        brojfakture, datumpred = fakt
                        avansi.append({
                            "broj": brojfakture,
                            "datum": datumpred.strftime("%Y-%m-%d")
                        })

                if not refbrracpu:
                    break
                trenutni = refbrracpu

            return list(reversed(avansi))

        except Exception as e:
            print(f"❌ Greška u izvuci_avansne_fakture_za_fakturu: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def kreiraj_xml_efakturu(self):
        try:
            # Osnovna putanja (gde se nalazi .py ili .exe fajl)
            if getattr(sys, 'frozen', False):  # ako je aplikacija pretvorena u .exe
                BASE_DIR = os.path.dirname(sys.executable)
            else:  # ako se pokreće kao .py fajl
                BASE_DIR = os.path.dirname(os.path.abspath(__file__))

            # Putanja ka folderu za izveštaje
            folder_izvestaja = os.path.join(BASE_DIR, "izvestaji\efakture")
            os.makedirs(folder_izvestaja, exist_ok=True)

            #folder_izvestaja = r"D:\pos_desktop\desktop_pos\izvestaji\efakture"  # stari deo koda gde je explicitno naveden folder
            xml_putanja = self.generisi_efaktura_xml(self.faktura_id, folder_izvestaja)

            if not xml_putanja or not os.path.exists(xml_putanja):
                QMessageBox.critical(self, "Greška", "XML fajl nije uspešno generisan.")
                return

            QMessageBox.information(self, "Uspeh", f"XML fajl je generisan:\n{xml_putanja}")

        except Exception as e:
            print("Greška prilikom kreiranja XML fajla:", e)
            QMessageBox.critical(self, "Greška", f"Greška:\n{str(e)}")


    def _posalji_na_sef(self):
        # Osnovna putanja (gde se nalazi .py ili .exe fajl)
        if getattr(sys, 'frozen', False):  # ako je aplikacija pretvorena u .exe
            BASE_DIR = os.path.dirname(sys.executable)
        else:  # ako se pokreće kao .py fajl
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))

        # Putanja ka folderu za izveštaje
        folder_izvestaja = os.path.join(BASE_DIR, "izvestaji\\efakture")
        os.makedirs(folder_izvestaja, exist_ok=True)
        #folder_izvestaja = r"D:\pos_desktop\desktop_pos\izvestaji\efakture"   # stari deo koda gde je explicitno naveden folder
        xml_path = self.generisi_efaktura_xml(self.faktura_id, folder_izvestaja)
        print("DEBUG xml_path:", xml_path, type(xml_path))
        if xml_path:
            self.posalji_efakturu_na_sef(xml_path)
        else:
            QMessageBox.critical(self, "Greška", "Generisanje XML fajla nije uspelo. Proverite podatke fakture.") 
    
    def posalji_efakturu_na_sef(self, xml_putanja):
        # === Preuzimanje podataka iz baze ===
        url, apikey, demo, pib, jbkjs, matbr = self.okruzenje_za_slanje()

        if not url or not apikey:
            QMessageBox.warning(self, "Greška", "Nisu pronađeni parametri za slanje na SEF.")
            return

        try:
            with open(xml_putanja, "rb") as f:
                xml_sadrzaj = f.read()

            request_id = str(uuid.uuid4())
            send_to_cir = "Yes" if self.crfCheck.isChecked() else "No"
            url_sa_parametrima = f"{url}?requestId={request_id}&sendToCir={send_to_cir}"

            print("DEBUG: Slanje na URL:", url_sa_parametrima)

            headers = {
                "Content-Type": "application/xml",
                "Accept": "application/json",
                "apikey": apikey
            }

            print("DEBUG: Slanje POST zahteva...")
            response = requests.post(url_sa_parametrima, headers=headers, data=xml_sadrzaj)
            print("DEBUG: Status:", response.status_code)

            if response.status_code == 200:
                odgovor = response.json()
                print("✅ SEF odgovor:", odgovor)

                invoice_id = odgovor.get("InvoiceId")
                sales_id = odgovor.get("SalesInvoiceId")
                cir_id = odgovor.get("circularInvoiceNumber")

                try:
                    with psycopg2.connect(
                        dbname=os.getenv("DB_NAME"),
                        user=os.getenv("DB_USER"),
                        password=os.getenv("DB_PASSWORD"),
                        host=os.getenv("DB_HOST"),
                        port=os.getenv("DB_PORT")
                    ) as conn:
                        with conn.cursor() as cursor:
                            # 1. Ažuriranje fakture
                            cursor.execute("""
                                UPDATE kasa.fakture
                                SET invoiceid = %s,
                                    salesinvoiceid = %s,
                                    cirinvoiceid = %s,
                                    status_salinv = %s,
                                    datum_stat_salinv = %s
                                WHERE id = %s
                            """, (
                                invoice_id,
                                sales_id,
                                cir_id,
                                'Sent',
                                datetime.datetime.now(),
                                self.faktura_id
                            ))

                            # 2. Dohvatanje brojfakture za ažuriranje stavki
                            cursor.execute("""
                                SELECT brojfakture
                                FROM kasa.fakture
                                WHERE id = %s
                            """, (self.faktura_id,))
                            rezultat = cursor.fetchone()

                            if rezultat:
                                brojfakture = rezultat[0]

                                # 3. UVEK postavljamo vrsta = 3 za eFakture
                                cursor.execute("""
                                    UPDATE kasa.karticaart
                                    SET vrsta = 3,
                                        opis = 'eFaktura'
                                    WHERE god = %s
                                    AND sifobj = %s
                                    AND brfakt = %s
                                """, (GODINA, SIFOBJEKTA, brojfakture))

                        conn.commit()
                        print("✅ Podaci uspešno upisani u bazu.")
                except Exception as db_e:
                    print("❌ Greška pri upisu u bazu:", db_e)

                QMessageBox.information(self, "Uspeh", f"Faktura uspešno poslata.\nInvoiceId: {invoice_id}")

            else:
                print("❌ Greška pri slanju:", response.status_code, response.text)
                QMessageBox.critical(self, "Greška", f"Greška pri slanju fakture:\n{response.status_code}\n{response.text}")

        except Exception as e:
            print("❌ Izuzetak:", e)
            QMessageBox.critical(self, "Greška", f"Greška prilikom slanja XML-a:\n{e}")

    #=== Provera registrovanosti kupca ===#
    #=== ne koristim je sluzila za proveru, razmisliti o njenoj prineni ===# 
    def proveri_registrovanost_firme_na_sef_po_pibu(self):
        """
        Proverava da li je firma registrovana na SEF-u (produkcija),
        slanjem svih parametara (PIB, matični broj, JBKJS).
        """
        conn = None
        try:
            # Povezivanje sa bazom i čitanje podataka
            conn = psycopg2.connect(
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            cursor = conn.cursor()
            cursor.execute("SELECT kljuc_api, pib, matbr, jbkjs FROM kasa.fvr LIMIT 1")
            rezultat = cursor.fetchone()

            if not rezultat:
                QMessageBox.warning(self, "Greška", "Nema podataka o API ključu, PIB-u, matičnom broju ili JBKJS-u.")
                return

            api_key, pib, matbr, jbkjs = rezultat

            if not pib and not matbr:
                QMessageBox.warning(self, "Greška", "PIB ili Matični broj nisu uneti.")
                return

            url = "https://demoefaktura.mfin.gov.rs/api/publicApi/Company/CheckIfCompanyRegisteredOnEfaktura"
            body = {
                "registrationNumber": matbr or "",
                "vatNumber": pib or "",
                "jbkjs": jbkjs or ""
            }

            print("🔍 PROVERA KUPCA NA SEF-u (produkcija)")
            print("URL:", url)
            print("BODY:", body)

            response = requests.post(
                url,
                json=body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "apikey": api_key
                }
            )

            if response.status_code == 200:
                rezultat = response.json()
                print("✅ Odgovor:", rezultat)
                if rezultat.get("eFakturaRegisteredCompany") is True:
                    QMessageBox.information(self, "Provera SEF", f"✅ Kupac je registrovan na SEF-u.\nPIB: {pib}")
                else:
                    QMessageBox.warning(self, "Provera SEF", f"❌ Kupac NIJE registrovan na SEF-u.\nPIB: {pib}")
            else:
                print("⚠️ Greška:", response.status_code, response.text)
                QMessageBox.critical(self, "Greška", f"Greška pri proveri SEF-a:\n{response.status_code}\n{response.text}")

        except Exception as e:
            print("❌ Izuzetak:", e)
            QMessageBox.critical(self, "Greška", f"Greška prilikom provere SEF-a:\n{e}")

        finally:
            if conn:
                conn.close()

        