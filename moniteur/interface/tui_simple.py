"""Interface texte simple : menus en print() et input().

Cette interface affiche l'état des sites, puis propose un menu pour
ajouter un site, tester un site ou tester tous les sites. L'écran est
réaffiché après chaque action (page MVP, section 2.2).
"""

from collections.abc import Callable
from datetime import datetime

from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.enumerations import StatutDisponibilite
from moniteur.domaine.registre_sites import RegistreSites
from moniteur.domaine.site import Site
from moniteur.domaine.testeur import Testeur

# Codes ANSI : le terminal colore le texte qui les suit.
VERT = "\033[32m"
ROUGE = "\033[31m"
JAUNE = "\033[33m"
REINITIALISER = "\033[0m"

COULEURS = {
    StatutDisponibilite.DISPONIBLE: VERT,
    StatutDisponibilite.INDISPONIBLE: ROUGE,
    StatutDisponibilite.INCONNU: JAUNE,
}

FORMAT_HORODATAGE = "%d/%m/%Y %H:%M:%S"


def lancer(
    registre: RegistreSites,
    testeurs: list[Testeur],
    config: ConfigurationTests,
    horloge: Callable[[], datetime],
) -> None:
    """Affiche les sites et le menu jusqu'à ce que l'utilisatrice quitte.

    Reçoit le registre, les testeurs, la configuration et l'horloge,
    créés par main.py et transmis tels quels au domaine.
    """
    try:
        while True:
            afficher_sites(registre)
            choix = demander_choix()
            if choix == "1":
                ajouter_site(registre)
            elif choix == "2":
                tester_site(registre, testeurs, config, horloge)
            elif choix == "3":
                tester_tous_les_sites(registre, testeurs, config, horloge)
            elif choix == "0":
                break
            else:
                print("Choix inconnu.")
    except (EOFError, KeyboardInterrupt):
        print()
    print("Au revoir.")


def afficher_sites(registre: RegistreSites) -> None:
    """Affiche la liste des sites avec leur statut (EF-02.1).

    Chaque ligne indique le statut, l'horodatage du dernier test
    (EF-02.2) et le diagnostic. Sa couleur met en évidence les sites
    indisponibles ou jamais testés (EF-02.4).
    """
    print()
    print("=== État des sites ===")
    if len(registre.sites) == 0:
        print("Aucun site. Ajoutez-en un avec le choix 1.")
        return
    print(f"{'Nom':<15} {'Statut':<12} {'Dernier test':<19} "
          f"{'Diagnostic':<26} URI")
    for site in registre.sites:
        afficher_site(site)


def afficher_site(site: Site) -> None:
    """Affiche une ligne colorée selon le statut du site."""
    statut = site.statut_disponibilite
    batterie = site.derniere_batterie
    if batterie is None:
        horodatage = "-"
        diagnostic = "-"
    else:
        horodatage = batterie.horodatage.strftime(FORMAT_HORODATAGE)
        diagnostic = ", ".join(
            mesure.diagnostic for mesure in batterie.mesures
            if mesure.diagnostic is not None
        )
    ligne = (f"{site.nom:<15} {statut.name:<12} {horodatage:<19} "
             f"{diagnostic:<26} {site.uri_principale}")
    print(COULEURS[statut] + ligne + REINITIALISER)


def demander_choix() -> str:
    """Affiche le menu et renvoie le choix saisi."""
    print()
    print("1. Ajouter un site")
    print("2. Tester un site")
    print("3. Tester tous les sites")
    print("0. Quitter")
    return input("Votre choix : ").strip()


def ajouter_site(registre: RegistreSites) -> None:
    """Demande le nom et l'URI principale d'un site, puis l'ajoute.

    Un refus du domaine (nom déjà utilisé, nom ou URI vide, EF-01.2 et
    EF-01.3) est affiché sans interrompre le programme.
    """
    nom = input("Nom du site : ")
    uri_principale = input("URI principale : ")
    try:
        site = registre.ajouter_site(nom, uri_principale)
        print(f"Site « {site.nom} » ajouté.")
    except ValueError as erreur:
        print(f"Refus : {erreur}")


def tester_site(
    registre: RegistreSites,
    testeurs: list[Testeur],
    config: ConfigurationTests,
    horloge: Callable[[], datetime],
) -> None:
    """Demande le nom d'un site et lance une batterie sur lui (EF-03.1)."""
    nom = input("Nom du site à tester : ")
    try:
        site = registre.site(nom)
    except ValueError as erreur:
        print(f"Refus : {erreur}")
        return
    print(f"Test de « {site.nom} » en cours...")
    site.lancer_batterie(testeurs, config, horloge)


def tester_tous_les_sites(
    registre: RegistreSites,
    testeurs: list[Testeur],
    config: ConfigurationTests,
    horloge: Callable[[], datetime],
) -> None:
    """Lance une batterie sur chaque site du registre (EF-03.4)."""
    for site in registre.sites:
        print(f"Test de « {site.nom} » en cours...")
        site.lancer_batterie(testeurs, config, horloge)
