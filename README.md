1. # FiskalPOS

Windows desktop aplikacija za maloprodaju i izdavanje fiskalnih računa.  
Razvijena u Python / PyQt6 okruženju, uz PostgreSQL bazu podataka.

## 🧾 Glavne funkcije

- Izdavanje i štampanje fiskalnih računa
- Sinhronizacija šifarnika sa centralnom bazom
- Pregled i štampa prodajnih izveštaja (dnevni i periodični)
- Offline rad sa lokalnom bazom
- Automatizovani PDF izveštaji

## 🖥️ Tehnologije

- Python 3.10+
- PyQt6 (grafički interfejs)
- PostgreSQL
- ReportLab (PDF generacija)
- python-dotenv (učitavanje `.env` fajla)
- configparser (učitavanje `kasa.ini` fajla)

2. desktop_pos/
│
├── database/         	 	# (prazan, planirano za buduću logiku baze)
├── env/              	 	# Virtuelno okruženje (NE dodavati na GitHub)
├── fonts/            		# TTF fontovi za PDF izveštaje
├── icons/            	 	# Ikone za PyQt interfejs
├── izvestaji/        	 	# Generisani PDF izveštaji
├── models/           		# (prazan, može služiti za buduće modele)
├── resources/        		# Ikone, slike i drugi grafički resursi
├── ui/               		# .ui fajlovi kreirani u Qt Designer-u
├── utils/            		# Pomoćne funkcije i alati
├── main.py           		# Glavni ulazni fajl aplikacije
├── .env              		# Parametri za konekciju ka bazi
├── README.md         		# Dokumentacija
├── requirements.txt  		# Python zavisnosti
├── analiticki.py     		# analiticki izvestaj dijalog
├── avans.py          		# dijalog za avansne racune
├── efakture.py       		# dijalog za slanje n SEF
├── fakture.py        		# dijalog za formiranje i pregled faktura
├── kasa.ini          		# ini fajl za konfiguracije
├── kep_stampa_dijalog.py      # dijalog za stampu KEP knjige
├── kep.py          		# dijalog za unos podataka u KWP knjigu
├── neobradjeni.py             # dijalog za neobradjene racune
├── partneri.py                # dijalog za unos novog poslvnog partnera
├── pazar.py                   # dijalog za pregled pazara
├── periodicni.py              # dijalog za periodicni pregled prodaje
├── porkat.py                  # dijalog za pretragu poreskih kategorija
├── racuniDijalog.py           # dijalog za pregled izdatih fiskalnih racuna
├── refundirani_avansi.py      # dijalog za izbor refundiranog avansa kod izdavanja konacnog racuna
├── select_customer.py         # dijalog za izbor kupca kod izdavanja fiskalnog racuna
├── sinteticki.py              # dijalog za sinteticki (zbirni) pregled prodaje
├── trazi_avans.py             # dijalog za izbor predhodnog avansa u lancu avansnih racuna
├── trazi_partnera.py          # dijalog za pretragu partnera pri formiranju facture

3. ## 📦 Instalacija

1. Klonirajte ili kopirajte ceo folder na drugi Windows računar (npr. na `D:\pos_desktop\desktop_pos`).

2. Preporučeno: kreirati virtuelno okruženje:
   ```cmd
   python -m venv env
   env\Scripts\activate

4. Instalirajte potrebne pakete:
   pip install -r requirements.txt

5. Uverite se da fajl `.env` postoji u glavnom folderu i sadrži sledeće:

   ```env
   DB_NAME=ime_baze
   DB_USER=korisnik
   DB_PASSWORD=lozinka
   DB_HOST=localhost
   DB_PORT=5432 ili PORT vase baze ukoliko je drugaciji od navedenog

6. Mali dodatak za korisnike koji koriste PowerShell:
```md
7. Pokretanje aplikacije iz terminala:

   ```bash
   py desktop_main.py
   # ili
   python desktop_main.py

8. 👨‍💻 Autor

  Aplikaciju su razvili:  
**Ljubomir Martinović** i **OpenAI ChatGPT asistent**

Za tehničku podršku, predloge ili nadogradnje, kontaktirajte autora.
