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
    def afficher(scenario: str, attendu: object, obtenu: object) -> None:
        """Affiche un scénario de test manuel et son verdict."""
        print(f"Scénario : {scenario}")
        print(f"  attendu : {attendu}")
        print(f"  obtenu  : {obtenu}")
        print("  → OK" if attendu == obtenu else "  → ÉCHEC")

    afficher(
        "membres de Verdict",
        ["OK", "KO"],
        [membre.name for membre in Verdict],
    )
    afficher(
        "membres de StatutDisponibilite",
        ["DISPONIBLE", "INDISPONIBLE", "INCONNU"],
        [membre.name for membre in StatutDisponibilite],
    )
    afficher(
        "accès à un membre par son nom",
        Verdict.KO,
        Verdict["KO"],
    )
    try:
        Verdict.INCONNU
        obtenu = "aucune erreur"
    except AttributeError:
        obtenu = "AttributeError"
    afficher(
        "Verdict.INCONNU n'existe pas dans le MVP (page MVP, section 5)",
        "AttributeError",
        obtenu,
    )
