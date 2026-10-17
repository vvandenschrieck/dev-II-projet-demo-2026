"""Configuration des tests : paramètres communs à tous les sites."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigurationTests:
    """Paramètres utilisés lors du lancement d'une batterie de tests.

    Dans le MVP, la configuration ne contient que le délai maximal
    d'attente d'une réponse, en secondes. Au-delà, le test est
    considéré en échec (EF-03.5). La valeur reste à fixer avec la
    cliente (Q-07) ; 5 secondes sont utilisées en attendant (page MVP,
    section 5).

    La classe est figée : une configuration se remplace plutôt qu'elle
    ne se modifie.
    """

    timeout_s: float
