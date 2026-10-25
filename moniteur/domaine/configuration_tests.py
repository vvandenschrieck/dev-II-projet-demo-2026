"""Configuration des tests : paramètres communs à tous les sites."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigurationTests:
    """Paramètres utilisés lors du lancement d'une batterie de tests.

    timeout_s est le délai maximal d'attente d'une réponse, en secondes.
    Au-delà, le test est considéré en échec (EF-03.5). La valeur reste
    à fixer avec la cliente (Q-07) ; main.py en choisit une en
    attendant (5 secondes).

    Les autres paramètres définissent les performances dégradées
    (RM-08) :
    - fenetre_performance_min : durée, en minutes, des batteries prises
      en compte pour les moyennes (RTT_SLOT et TIME_SLOT) ;
    - seuil_l3_s : RTT moyen maximal, en secondes (RTT_MAX), 100 ms par
      défaut ;
    - seuil_l7_s : temps de chargement moyen maximal d'une page, en
      secondes (MAX_LOADING_TIME), 0,5 s par défaut.

    age_max_statut_min est l'âge, en minutes, au-delà duquel les statuts
    d'un site sont signalés comme anciens.

    INVARIANT : les paramètres ne changent jamais après la création
    (classe figée) : une configuration se remplace plutôt qu'elle ne se
    modifie. Le constructeur, généré par la dataclass, ne contrôle pas
    les valeurs reçues.
    """

    timeout_s: float
    fenetre_performance_min: int = 30
    seuil_l3_s: float = 0.1
    seuil_l7_s: float = 0.5
    age_max_statut_min: int = 30
