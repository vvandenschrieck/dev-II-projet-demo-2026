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
        """Teste le site et renvoie les mesures obtenues (EF-03.1).

        timeout_s est le délai maximal d'attente en secondes (EF-03.5) ;
        horodatage est celui de la batterie, à reporter dans chaque
        mesure.

        PRE : timeout_s > 0.
        POST : renvoie la liste des mesures obtenues, chacune datée de
               horodatage. Un site injoignable ne provoque pas
               d'exception : il donne une mesure de verdict KO.
               Ne modifie ni site ni les autres paramètres.
        """
