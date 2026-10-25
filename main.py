"""Point d'entrée de l'application de surveillance des sites web.

Crée les testeurs, la configuration et le registre, puis lance
l'interface choisie en ligne de commande :

    python main.py --interface simple   (valeur par défaut)
    python main.py --interface textual

L'option --demo ajoute au registre des sites d'essai, pour tester
l'application sans les saisir (voir docs/verification-manuelle.md).
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

# Durée de la fenêtre de performance (RM-08), en minutes. Pour une
# démonstration, une valeur de 1 ou 2 minutes rend les écarts visibles.
FENETRE_PERFORMANCE_MIN = 30

# Délai, en minutes, entre deux tests automatiques d'un même site
# (réponse à Q-01).
FREQUENCE_MIN = 15

# Sites d'essai (nom, URI) ajoutés par l'option --demo : ils couvrent les
# cas de figure de la vérification manuelle. Ils contactent de vrais sites.
SITES_DEMO = (
    ("Google", "www.google.com"),
    ("Erreur 404", "https://www.google.com/page-inexistante-ephec"),
    ("DNS KO", "site-inexistant.invalid"),
    ("ICMP Bloqués", "https://httpbin.org/get"),
    ("Port Fermé", "http://www.google.com:81"),
    ("Lent", "https://httpbin.org/delay/1"),
    ("Local", "localhost"),
)


def lire_arguments() -> argparse.Namespace:
    """Lit les arguments de la ligne de commande et les renvoie.

    PRE : aucune.
    POST : renvoie les arguments lus : l'attribut interface vaut
           « simple » (par défaut) ou « textual », et l'attribut demo
           vaut True si --demo est présent. Ne modifie rien.
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
    analyseur.add_argument(
        "--demo",
        action="store_true",
        help="ajoute des sites d'essai au registre",
    )
    return analyseur.parse_args()


def precharger_sites(registre: RegistreSites) -> None:
    """Ajoute les sites d'essai au registre.

    PRE : aucune.
    POST : les sites de SITES_DEMO sont ajoutés à registre, dans l'ordre,
           sans avoir été testés (statut INCONNU).
           Exception ValueError : si registre contient déjà un site de
           même nom que l'un des sites d'essai.
    """
    for nom, uri in SITES_DEMO:
        registre.ajouter_site(nom, uri)


def main() -> None:
    """Assemble l'application et lance l'interface choisie.

    PRE : aucune.
    POST : crée les testeurs ICMP, TCP et HTTP, la configuration
           (TIMEOUT_S, FENETRE_PERFORMANCE_MIN) et un registre vide,
           auquel elle ajoute les sites d'essai si --demo est présent.
           Lance ensuite l'interface choisie avec l'horloge système. Ne
           rend la main que lorsque l'utilisatrice quitte.
           Exception SystemExit : si les arguments sont invalides ou si
           l'aide est demandée.
           Exception ImportError : si l'interface textual est choisie et
           que textual n'est pas installé.
    """
    arguments = lire_arguments()
    testeurs = [TesteurIcmp(), TesteurTcp(), TesteurHttp()]
    config = ConfigurationTests(
        TIMEOUT_S, fenetre_performance_min=FENETRE_PERFORMANCE_MIN
    )
    registre = RegistreSites()
    if arguments.demo:
        precharger_sites(registre)
    if arguments.interface == "simple":
        from moniteur.interface import tui_simple
        tui_simple.lancer(
            registre, testeurs, config, datetime.now, FREQUENCE_MIN
        )
    else:
        # textual n'est importé que si cette interface est choisie : la
        # TUI simple fonctionne donc même sans textual installé.
        from moniteur.interface import tui_textual
        tui_textual.lancer(
            registre, testeurs, config, datetime.now, FREQUENCE_MIN
        )


if __name__ == "__main__":
    main()
