"""Énumérations du domaine : verdict d'une mesure et statut d'un site.

Ces ensembles fermés de valeurs viennent du diagramme de classes du MVP.
"""

from enum import Enum, auto


class Verdict(Enum):
    """Résultat d'une mesure : réussie (OK) ou échouée (KO).

    Dans le MVP, un site injoignable donne aussi un verdict KO
    (page MVP, section 5).
    """

    OK = auto()
    KO = auto()


class StatutDisponibilite(Enum):
    """Statut de disponibilité d'un site, calculé sur sa dernière batterie.

    INCONNU tant que le site n'a jamais été testé (RM-03, RM-06,
    page MVP section 2.1).
    """

    DISPONIBLE = auto()
    INDISPONIBLE = auto()
    INCONNU = auto()


if __name__ == "__main__":
    print("Scénario : membres de Verdict")
    attendu = ["OK", "KO"]
    obtenu = [membre.name for membre in Verdict]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : membres de StatutDisponibilite")
    attendu = ["DISPONIBLE", "INDISPONIBLE", "INCONNU"]
    obtenu = [membre.name for membre in StatutDisponibilite]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : accès à un membre par son nom")
    attendu = Verdict.KO
    obtenu = Verdict["KO"]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : Verdict.INCONNU n'existe pas dans le MVP "
          "(page MVP, section 5)")
    attendu = "AttributeError"
    try:
        Verdict.INCONNU
        obtenu = "aucune erreur"
    except AttributeError:
        obtenu = "AttributeError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
