"""Énumérations du domaine : couche, verdict, statuts d'un site.

Ces ensembles fermés de valeurs viennent du diagramme de classes.
"""

from enum import Enum, auto


class Couche(Enum):
    """Couche réseau sur laquelle porte un test.

    L3 (réseau, sondes ICMP), L4 (transport, connexion TCP) et L7
    (applicative, requête HTTP). L'ordre de déclaration est l'ordre
    dans lequel les tests sont appliqués (EF-03.2).
    """

    L3 = auto()
    L4 = auto()
    L7 = auto()

    @property
    def bloquante(self) -> bool:
        """Dit si l'échec d'un test sur cette couche arrête la batterie.

        PRE : aucune.
        POST : renvoie True pour L4 et False pour L3 et L7 (EF-03.2).
               Ne modifie rien.
        """
        return self == Couche.L4


class Verdict(Enum):
    """Résultat d'une mesure : réussie (OK) ou échouée (KO).

    Dans le MVP, un site injoignable donne aussi un verdict KO
    (page MVP, section 5).
    """

    OK = auto()
    KO = auto()


class StatutDisponibilite(Enum):
    """Statut de disponibilité d'un site, calculé sur sa dernière batterie.

    INCONNU tant que le site n'a jamais été testé ou que sa dernière
    batterie n'a aucune mesure (RM-03, RM-06, page MVP section 2.1).
    """

    DISPONIBLE = auto()
    INDISPONIBLE = auto()
    INCONNU = auto()


class StatutPerformance(Enum):
    """Statut de performance d'un site, calculé sur ses dernières batteries.

    NORMALES ou DEGRADEES selon les conditions de RM-08. INCONNU quand
    aucune mesure ne permet de conclure.
    """

    NORMALES = auto()
    DEGRADEES = auto()
    INCONNU = auto()


if __name__ == "__main__":
    print("Scénario : seul un échec en L4 arrête la batterie (EF-03.2)")
    attendu = [Couche.L4]
    obtenu = [couche for couche in Couche if couche.bloquante]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : l'ordre des couches est L3, L4, L7 (EF-03.2)")
    attendu = [Couche.L3, Couche.L4, Couche.L7]
    obtenu = list(Couche)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
