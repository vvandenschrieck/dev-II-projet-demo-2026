"""Formatage de texte commun à toutes les interfaces.

Ces fonctions ne font aucun affichage : elles renvoient du texte que
chaque interface place où elle veut. Elles sont ici pour ne pas être
copiées dans chaque interface.
"""


def formater_duree(duree_s: float | None, ecart: float | None) -> str:
    """Formate une durée en millisecondes, suivie de son écart en %.

    PRE : aucune.
    POST : renvoie « - » si duree_s est None. Sinon renvoie la durée en
           millisecondes (deux décimales sous 1 ms, une sous 10 ms,
           aucune au-delà), suivie de l'écart entre parenthèses
           (« 85 ms (+37 %) »), ou de « (-) » si ecart est None. Ne
           modifie rien.
    """
    if duree_s is None:
        return "-"
    ms = duree_s * 1000
    if ms < 1:
        texte = f"{ms:.2f} ms"
    elif ms < 10:
        texte = f"{ms:.1f} ms"
    else:
        texte = f"{ms:.0f} ms"
    if ecart is None:
        return f"{texte} (-)"
    return f"{texte} ({ecart * 100:+.0f} %)"


if __name__ == "__main__":
    CAS = [
        ("durée inconnue", (None, 0.5), "-"),
        ("sous 1 ms : deux décimales", (0.00042, None), "0.42 ms (-)"),
        ("sous 10 ms : une décimale", (0.0042, 0.1), "4.2 ms (+10 %)"),
        ("au-delà : aucune décimale", (0.0853, 0.37), "85 ms (+37 %)"),
        ("écart négatif", (0.05, -0.2), "50 ms (-20 %)"),
    ]
    for description, arguments, attendu in CAS:
        print(f"Scénario : {description}")
        obtenu = formater_duree(*arguments)
        print(f"  attendu : {attendu}")
        print(f"  obtenu  : {obtenu}")
        print("  → OK" if obtenu == attendu else "  → ÉCHEC")
        print("-" * 40)
