import configparser
import os
import sys
import tempfile

import psycopg2
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INI_PATH = os.path.join(BASE_DIR, "kasa.ini")
load_dotenv(os.path.join(BASE_DIR, ".env"))


def procitaj_aktivnu_godinu():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT god
                FROM kasa.poslovna_godina
                WHERE aktivna IS TRUE
            """)
            godine = cursor.fetchall()
    finally:
        conn.close()

    if len(godine) != 1:
        raise RuntimeError(
            "U bazi mora postojati tačno jedna aktivna poslovna godina."
        )

    return int(godine[0][0])


def uskladi_ini():
    config = configparser.ConfigParser()
    if not config.read(INI_PATH, encoding="utf-8"):
        raise RuntimeError("Datoteka kasa.ini nije pronađena.")

    if not config.has_option("POS_Settings", "god"):
        raise RuntimeError("U kasa.ini nedostaje POS_Settings/god.")

    aktivna_godina = procitaj_aktivnu_godinu()
    godina_u_ini = config.getint("POS_Settings", "god")

    if godina_u_ini == aktivna_godina:
        return

    config.set("POS_Settings", "god", str(aktivna_godina))

    privremeni_fajl = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=BASE_DIR,
            prefix="kasa-",
            suffix=".tmp",
            delete=False,
        ) as fajl:
            privremeni_fajl = fajl.name
            config.write(fajl)

        os.replace(privremeni_fajl, INI_PATH)
    finally:
        if privremeni_fajl and os.path.exists(privremeni_fajl):
            os.remove(privremeni_fajl)

    print(
        f"Poslovna godina u kasa.ini usklađena je sa bazom: "
        f"{godina_u_ini} -> {aktivna_godina}."
    )


if __name__ == "__main__":
    try:
        uskladi_ini()
    except Exception as exc:
        print(f"POS nije pokrenut: {exc}", file=sys.stderr)
        sys.exit(1)