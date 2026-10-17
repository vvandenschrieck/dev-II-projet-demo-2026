"""Testeur : classe abstraite de tous les testeurs de sites."""

# Site annote Testeur et Testeur annote Site : chaque module aurait besoin
# d'importer l'autre, ce qui crée un import circulaire. On évite le
# problème ainsi :
# - « from __future__ import annotations » : les annotations ne sont plus
#   évaluées à l'exécution, elles restent du simple texte ;
# - « if TYPE_CHECKING » : l'import de Site n'est fait que par les outils
#   de vérification de types (éditeur, mypy), jamais à l'exécution.
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from moniteur.domaine.mesure import Mesure

if TYPE_CHECKING:
    from moniteur.domaine.site import Site


class Testeur(ABC):
    """Service qui réalise un type de test sur un site.

    Le site appelle executer() sans savoir quel testeur concret il
    utilise (patron Stratégie). On peut ainsi ajouter un nouveau type de
    test sans modifier Site, et tester Site avec de faux testeurs.

    Les testeurs concrets, qui accèdent au réseau, se trouvent dans le
    paquet moniteur.testeurs. Le domaine ne connaît que cette
    abstraction.
    """

    @abstractmethod
    def executer(
        self, site: Site, timeout_s: float, horodatage: datetime
    ) -> list[Mesure]:
        """Teste le site et renvoie les mesures obtenues.

        Reçoit le site à tester, le délai maximal d'attente en secondes
        (EF-03.5) et l'horodatage de la batterie, à reporter dans
        chaque mesure. Un site injoignable n'est pas une erreur : il
        donne une mesure KO.
        """


if __name__ == "__main__":
    from moniteur.domaine.enumerations import Verdict

    class FauxTesteur(Testeur):
        """Testeur de test : renvoie une mesure fixée, sans réseau."""

        def __init__(self, verdict: Verdict, diagnostic: str) -> None:
            """Mémorise le verdict et le diagnostic à renvoyer."""
            self.__verdict = verdict
            self.__diagnostic = diagnostic

        def executer(
            self, site: Site, timeout_s: float, horodatage: datetime
        ) -> list[Mesure]:
            """Renvoie une seule mesure, datée de l'horodatage reçu."""
            return [Mesure(horodatage, self.__verdict, 0.1,
                           self.__diagnostic)]

    class TesteurIncomplet(Testeur):
        """Sous-classe qui oublie de définir executer()."""

    instant = datetime(2026, 10, 17, 14, 30)

    print("Scénario : instancier la classe abstraite Testeur")
    attendu = "TypeError"
    try:
        Testeur()
        obtenu = "aucune erreur"
    except TypeError:
        obtenu = "TypeError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : instancier une sous-classe sans executer()")
    attendu = "TypeError"
    try:
        TesteurIncomplet()
        obtenu = "aucune erreur"
    except TypeError:
        obtenu = "TypeError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    # Site n'existe pas encore (étape 6) : le faux testeur ne lit pas le
    # site, on lui passe donc None.
    print("Scénario : un faux testeur renvoie la mesure fixée")
    faux_testeur = FauxTesteur(Verdict.OK, "200")
    attendu = [Mesure(instant, Verdict.OK, 0.1, "200")]
    obtenu = faux_testeur.executer(None, 5.0, instant)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : la mesure porte l'horodatage reçu par executer()")
    autre_instant = datetime(2026, 10, 18, 9, 0)
    attendu = autre_instant
    obtenu = faux_testeur.executer(None, 5.0, autre_instant)[0].horodatage
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
