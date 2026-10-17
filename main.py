"""Point d'entrée de l'application de surveillance des sites web.

Crée les testeurs, la configuration et le registre, puis lance
l'interface choisie en ligne de commande :

    python main.py --interface simple
"""

import argparse
from datetime import datetime

from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.registre_sites import RegistreSites
from moniteur.testeurs.testeur_http import TesteurHttp

# Valeur provisoire, en attendant la réponse de la cliente (Q-07).
TIMEOUT_S = 5.0


def lire_arguments() -> argparse.Namespace:
    """Lit les arguments de la ligne de commande et les renvoie."""
    analyseur = argparse.ArgumentParser(
        description="Surveillance des sites web de M. Durant."
    )
    analyseur.add_argument(
        "--interface",
        choices=["simple"],
        default="simple",
        help="interface utilisateur à lancer (par défaut : simple)",
    )
    return analyseur.parse_args()


def main() -> None:
    """Assemble l'application et lance l'interface choisie."""
    arguments = lire_arguments()
    testeurs = [TesteurHttp()]
    config = ConfigurationTests(TIMEOUT_S)
    registre = RegistreSites()
    if arguments.interface == "simple":
        from moniteur.interface import tui_simple
        tui_simple.lancer(registre, testeurs, config, datetime.now)


if __name__ == "__main__":
    main()
