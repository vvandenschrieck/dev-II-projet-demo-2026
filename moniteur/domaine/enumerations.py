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
