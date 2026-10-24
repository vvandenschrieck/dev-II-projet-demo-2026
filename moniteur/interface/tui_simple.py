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

    registre, testeurs, config et horloge sont créés par main.py et
    transmis tels quels au domaine.

    PRE : config.timeout_s > 0.
    POST : affiche l'état des sites puis le menu après chaque action
           (page MVP, section 2.2), jusqu'au choix « 0 » ou jusqu'à la
           fin de la saisie (Ctrl+D, Ctrl+C), puis affiche « Au revoir. ».
           Modifie registre (sites ajoutés) et les sites testés
           (nouvelles batteries).
           Exception ValueError : si testeurs est vide et qu'un site est
           testé.
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

    PRE : aucune.
    POST : affiche un titre, puis un message si le registre est vide, ou
           sinon un en-tête et une ligne par site, dans l'ordre du
           registre (voir afficher_site). Ne modifie rien.
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
    """Affiche une ligne colorée selon le statut du site (EF-02.4).

    PRE : aucune.
    POST : affiche une ligne avec le nom, le statut, l'horodatage du
           dernier test (EF-02.2), le diagnostic et l'URI principale.
           Horodatage et diagnostic valent « - » si le site n'a jamais
           été testé. Ne modifie rien.
    """
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
    """Affiche le menu et renvoie le choix saisi.

    PRE : aucune.
    POST : affiche le menu, puis renvoie la saisie de l'utilisatrice
           sans les espaces de début et de fin. Ne modifie rien.
           Exception EOFError : si l'entrée standard est fermée.
    """
    print()
    print("1. Ajouter un site")
    print("2. Tester un site")
    print("3. Tester tous les sites")
    print("0. Quitter")
    return input("Votre choix : ").strip()


def ajouter_site(registre: RegistreSites) -> None:
    """Demande le nom et l'URI principale d'un site, puis l'ajoute.

    PRE : aucune.
    POST : demande un nom puis une URI principale. Si le domaine les
           accepte, le site est ajouté à registre et une confirmation
           est affichée. Sinon (nom déjà utilisé, nom ou URI vide,
           EF-01.2 et EF-01.3), « Refus : » suivi du motif est affiché
           et registre n'est pas modifié.
           Exception EOFError : si l'entrée standard est fermée.
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
    """Demande le nom d'un site et lance une batterie sur lui (EF-03.1).

    PRE : config.timeout_s > 0.
    POST : demande le nom d'un site. Si aucun site ne porte ce nom,
           « Refus : » suivi du motif est affiché et rien n'est testé.
           Sinon un message est affiché et une batterie est lancée sur
           ce site : elle rejoint son historique.
           Exception ValueError : si testeurs est vide.
           Exception EOFError : si l'entrée standard est fermée.
    """
    nom = input("Nom du site à tester : ")
    try:
        site = registre.trouver_site(nom)
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
    """Lance une batterie sur chaque site du registre (EF-03.4).

    PRE : config.timeout_s > 0.
    POST : pour chaque site de registre, dans l'ordre, affiche un
           message puis lance une batterie : elle rejoint l'historique
           du site. Ne fait rien si le registre est vide.
           Exception ValueError : si testeurs est vide et que le
           registre contient au moins un site.
    """
    for site in registre.sites:
        print(f"Test de « {site.nom} » en cours...")
        site.lancer_batterie(testeurs, config, horloge)
