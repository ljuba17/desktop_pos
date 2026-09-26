def proveri_aktivnu_godinu(cursor, godina_pos):
    """
    Poredi godinu koju trenutni POS proces koristi sa aktivnom godinom u bazi.
    Pozivalac zadržava transakciju do završetka upisa.
    """
    cursor.execute("""
        SELECT god
        FROM kasa.poslovna_godina
        WHERE aktivna IS TRUE
        FOR SHARE
    """)
    godine = cursor.fetchall()

    if len(godine) != 1:
        raise RuntimeError(
            "U bazi mora postojati tačno jedna aktivna poslovna godina."
        )

    aktivna_godina = int(godine[0][0])
    godina_pos = int(godina_pos)

    if godina_pos != aktivna_godina:
        raise RuntimeError(
            f"POS radi u {godina_pos}, a aktivna godina u bazi je "
            f"{aktivna_godina}. Ponovo pokreni POS."
        )