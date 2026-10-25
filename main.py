"""Point d'entrée de l'application de surveillance des sites web.

Crée les testeurs, la configuration et le registre, puis lance
l'interface choisie en ligne de commande :

    python main.py --interface simple   (valeur par défaut)
    python main.py --interface textual
"""

import argparse
from datetime import datetime

from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.registre_sites import RegistreSites
from moniteur.testeurs.testeur_http import TesteurHttp
from moniteur.testeurs.testeur_icmp import TesteurIcmp
from moniteur.testeurs.testeur_tcp import TesteurTcp

# Valeur provisoire, en attendant la réponse de la cliente (Q-07).
TIMEOUT_S = 5.0


def lire_arguments() -> argparse.Namespace:
    """Lit les arguments de la ligne de commande et les renvoie.

    PRE : aucune.
    POST : renvoie les arguments lus, dont l'attribut interface vaut
           « simple » (par défaut) ou « textual ». Ne modifie rien.
           Exception SystemExit : si les arguments sont invalides ou si
           l'aide est demandée (comportement d'argparse).
    """
    analyseur = argparse.ArgumentParser(
        description="Surveillance des sites web de M. Durant."
    )
    analyseur.add_argument(
        "--interface",
        choices=["simple", "textual"],
        default="simple",
        help="interface utilisateur à lancer (par défaut : simple)",
    )
    return analyseur.parse_args()


def main() -> None:
    """Assemble l'application et lance l'interface choisie.

    PRE : aucune.
    POST : crée les testeurs ICMP, TCP et HTTP, la configuration
           (TIMEOUT_S) et un registre vide, puis lance l'interface choisie avec
           l'horloge système. Ne rend la main que lorsque l'utilisatrice
           quitte.
           Exception SystemExit : si les arguments sont invalides ou si
           l'aide est demandée.
           Exception ImportError : si l'interface textual est choisie et
           que textual n'est pas installé.
    """
    arguments = lire_arguments()
    testeurs = [TesteurIcmp(), TesteurTcp(), TesteurHttp()]
    config = ConfigurationTests(TIMEOUT_S)
    registre = RegistreSites()
    if arguments.interface == "simple":
        from moniteur.interface import tui_simple
        tui_simple.lancer(registre, testeurs, config, datetime.now)
    else:
        # textual n'est importé que si cette interface est choisie : la
        # TUI simple fonctionne donc même sans textual installé.
        from moniteur.interface import tui_textual
        tui_textual.lancer(registre, testeurs, config, datetime.now)


if __name__ == "__main__":
    main()
