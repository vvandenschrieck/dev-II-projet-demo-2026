"""Interface texte simple : menus en print() et input().

Cette interface est la vue d'un présentateur (voir presentateur_simple).
Elle affiche l'état des sites, avec une ligne par page, puis propose un
menu pour ajouter ou modifier un site, ajouter ou supprimer une page,
tester un site, tester tous les sites ou surveiller les sites. Elle
lit les saisies et les transmet au présentateur ; elle ne connaît ni le
registre ni les règles de couleur. L'écran est réaffiché après chaque
action et, pendant la surveillance, après chaque test automatique
(EF-02.3).
"""

import threading
import time
from collections.abc import Callable
from datetime import datetime

from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.registre_sites import RegistreSites
from moniteur.domaine.testeur import Testeur
from moniteur.interface.presentateur_simple import (
    AUCUNE,
    JAUNE,
    ORANGE,
    ROUGE,
    VERT,
    BlocSite,
    PresentateurSimple,
)

# Codes ANSI : le terminal colore le texte qui les suit.
CODES_ANSI = {
    VERT: "\033[32m",
    ORANGE: "\033[38;5;208m",
    ROUGE: "\033[31m",
    JAUNE: "\033[33m",
    AUCUNE: "",
}
REINITIALISER = "\033[0m"

# Délai, en secondes, entre deux vérifications des échéances de test.
INTERVALLE_REVEIL_S = 60


def lancer(
    registre: RegistreSites,
    testeurs: list[Testeur],
    config: ConfigurationTests,
    horloge: Callable[[], datetime],
    frequence_min: int,
    interruption: threading.Event | None = None,
) -> None:
    """Affiche les sites et le menu jusqu'à ce que l'utilisatrice quitte.

    registre, testeurs, config, horloge et frequence_min sont créés par
    main.py et transmis tels quels au présentateur. interruption, si
    elle est donnée, permet à un autre fil d'exécution d'arrêter la
    surveillance (voir surveiller) ; sinon Ctrl+C s'en charge.

    PRE : config.timeout_s > 0.
    POST : affiche l'état des sites puis le menu après chaque action,
           jusqu'au choix « 0 » ou jusqu'à la fin de la saisie (Ctrl+D,
           Ctrl+C), puis affiche « Au revoir. ». Si un autre fil
           d'exécution modifie le registre (test lancé depuis le
           dashboard) pendant que l'interface attend un choix, l'état
           des sites et le menu sont réaffichés (EF-02.3). Le choix
           « 4 » lance la surveillance (voir surveiller). Modifie
           registre (sites ajoutés ou modifiés), les pages des sites
           (ajoutées ou supprimées) et les sites testés (nouvelles
           batteries).
           Exception ValueError : si testeurs est vide et qu'un site est
           testé.
    """
    en_attente = threading.Event()
    en_surveillance = threading.Event()

    def reafficher(blocs: tuple[BlocSite, ...]) -> None:
        """Réaffiche l'écran si l'interface attend ou surveille."""
        if en_attente.is_set():
            print()
            afficher_blocs(blocs)
            afficher_menu()
            print("Votre choix : ", end="", flush=True)
        elif en_surveillance.is_set():
            afficher_blocs(blocs)

    presentateur = PresentateurSimple(
        registre, testeurs, config, horloge, reafficher, print
    )
    try:
        while True:
            afficher_blocs(presentateur.blocs())
            en_attente.set()
            choix = demander_choix()
            en_attente.clear()
            if choix == "1":
                ajouter_site(presentateur)
            elif choix == "2":
                tester_site(presentateur)
            elif choix == "3":
                presentateur.tester_tous()
            elif choix == "4":
                en_surveillance.set()
                try:
                    surveiller(presentateur, frequence_min, interruption)
                finally:
                    en_surveillance.clear()
            elif choix == "5":
                modifier_site(presentateur)
            elif choix == "6":
                ajouter_page(presentateur)
            elif choix == "7":
                supprimer_page(presentateur)
            elif choix == "0":
                break
            else:
                print("Choix inconnu.")
    except (EOFError, KeyboardInterrupt):
        print()
    print("Au revoir.")


def afficher_blocs(blocs: tuple[BlocSite, ...]) -> None:
    """Affiche la liste des sites avec leurs statuts (EF-02.1).

    PRE : aucune.
    POST : affiche un titre, puis un message si blocs est vide, ou sinon
           un en-tête et un bloc par site, dans l'ordre reçu (voir
           afficher_bloc). Ne modifie rien.
    """
    print()
    print("=== État des sites ===")
    if len(blocs) == 0:
        print("Aucun site. Ajoutez-en un avec le choix 1.")
        return
    print(f"{'Nom':<17} {'Statut':<26} {'Performance':<11} "
          f"{'RTT L3/L4':<16} {'Dernier test':<28} Diagnostic L3/L4")
    print(f"  {'Page':<15} {'Verdict':<8} {'Chargement L7':<16} "
          f"{'Diagnostic':<27} URI")
    for bloc in blocs:
        print()
        afficher_bloc(bloc)


def afficher_bloc(bloc: BlocSite) -> None:
    """Affiche le bloc d'un site : sa ligne, puis une ligne par page.

    PRE : aucune.
    POST : affiche la ligne du site (nom, statuts, RTT, dernier test,
           diagnostics) puis une ligne par page, en retrait (nom,
           verdict, chargement, diagnostic, URI), chacune dans la
           couleur donnée par le présentateur (EF-02.4). Ne modifie
           rien.
    """
    nom, statut, performance, rtt, horodatage, diagnostic = bloc.site.cellules
    ligne = (f"{nom:<17} {statut:<26} {performance:<11} "
             f"{rtt:<16} {horodatage:<28} {diagnostic}")
    print(colorer(bloc.site.couleur, ligne))
    for page in bloc.pages:
        nom, verdict, chargement, diagnostic, uri = page.cellules
        ligne = (f"  {nom:<15} {verdict:<8} {chargement:<16} "
                 f"{diagnostic:<27} {uri}")
        print(colorer(page.couleur, ligne))


def colorer(couleur: str, texte: str) -> str:
    """Entoure un texte des codes ANSI de la couleur donnée.

    PRE : couleur est l'une des couleurs du présentateur (VERT, ORANGE,
          ROUGE, JAUNE ou AUCUNE).
    POST : renvoie le texte précédé du code de la couleur et suivi du
           code de réinitialisation, ou le texte tel quel pour AUCUNE.
           Ne modifie rien.
    """
    if couleur == AUCUNE:
        return texte
    return CODES_ANSI[couleur] + texte + REINITIALISER


def afficher_menu() -> None:
    """Affiche les choix du menu.

    PRE : aucune.
    POST : affiche une ligne vide puis une ligne par choix. Ne modifie
           rien.
    """
    print()
    print("1. Ajouter un site")
    print("2. Tester un site")
    print("3. Tester tous les sites")
    print("4. Surveiller (tests automatiques)")
    print("5. Modifier un site")
    print("6. Ajouter une page à un site")
    print("7. Supprimer une page d'un site")
    print("0. Quitter")


def demander_choix() -> str:
    """Affiche le menu et renvoie le choix saisi.

    PRE : aucune.
    POST : affiche le menu, puis renvoie la saisie de l'utilisatrice
           sans les espaces de début et de fin. Ne modifie rien.
           Exception EOFError : si l'entrée standard est fermée.
    """
    afficher_menu()
    return input("Votre choix : ").strip()


def ajouter_site(presentateur: PresentateurSimple) -> None:
    """Demande le nom et l'URI principale d'un site, puis l'ajoute.

    PRE : aucune.
    POST : demande un nom puis une URI principale, et les transmet au
           présentateur, qui ajoute le site ou le refuse (EF-01.2 et
           EF-01.3).
           Exception EOFError : si l'entrée standard est fermée.
    """
    nom = input("Nom du site : ")
    uri_principale = input("URI principale : ")
    presentateur.ajouter_site(nom, uri_principale)


def tester_site(presentateur: PresentateurSimple) -> None:
    """Demande le nom d'un site et lance une batterie sur lui (EF-03.1).

    PRE : aucune.
    POST : demande le nom d'un site et le transmet au présentateur, qui
           teste le site ou le refuse.
           Exception EOFError : si l'entrée standard est fermée.
    """
    presentateur.tester_site(input("Nom du site à tester : "))


def modifier_site(presentateur: PresentateurSimple) -> None:
    """Demande un site, puis son nouveau nom et sa nouvelle URI (EF-01.2).

    PRE : aucune.
    POST : demande le nom d'un site. Si le présentateur le refuse, rien
           d'autre n'est demandé. Sinon affiche son nom et son URI
           actuels, demande un nouveau nom et une nouvelle URI
           principale, et les transmet au présentateur, qui modifie le
           site ou le refuse. Une saisie vide n'est pas remplacée par la
           valeur actuelle.
           Exception EOFError : si l'entrée standard est fermée.
    """
    nom = input("Nom du site à modifier : ")
    if not presentateur.verifier_site(nom):
        return
    print(presentateur.decrire_site(nom))
    nouveau_nom = input("Nouveau nom : ")
    nouvelle_uri = input("Nouvelle URI principale : ")
    presentateur.modifier_site(nom, nouveau_nom, nouvelle_uri)


def ajouter_page(presentateur: PresentateurSimple) -> None:
    """Demande un site, puis le nom et l'URI d'une page à lui ajouter.

    PRE : aucune.
    POST : demande le nom d'un site. Si le présentateur le refuse, rien
           d'autre n'est demandé. Sinon demande le nom et l'URI de la
           page, et les transmet au présentateur, qui ajoute la page ou
           la refuse (EF-01.4, EF-01.6).
           Exception EOFError : si l'entrée standard est fermée.
    """
    nom_site = input("Nom du site : ")
    if not presentateur.verifier_site(nom_site):
        return
    nom = input("Nom de la page : ")
    uri = input("URI de la page : ")
    presentateur.ajouter_page(nom_site, nom, uri)


def supprimer_page(presentateur: PresentateurSimple) -> None:
    """Demande un site, puis le nom de la page à lui retirer (EF-01.5).

    PRE : aucune.
    POST : demande le nom d'un site. Si le présentateur le refuse, rien
           d'autre n'est demandé. Sinon demande le nom de la page et le
           transmet au présentateur, qui retire la page ou la refuse.
           Exception EOFError : si l'entrée standard est fermée.
    """
    nom_site = input("Nom du site : ")
    if not presentateur.verifier_site(nom_site):
        return
    nom = input("Nom de la page à supprimer : ")
    presentateur.supprimer_page(nom_site, nom)


def surveiller(
    presentateur: PresentateurSimple,
    frequence_min: int,
    interruption: threading.Event | None = None,
) -> None:
    """Teste automatiquement les sites jusqu'à Ctrl+C (EF-03.7).

    Toutes les INTERVALLE_REVEIL_S secondes, demande au présentateur de
    tester les sites dont l'échéance est atteinte. Le menu n'est pas
    utilisable pendant la surveillance. Quand le dashboard est ouvert,
    Ctrl+C n'arrive pas dans ce fil d'exécution : un autre fil
    déclenche interruption.

    PRE : aucune.
    POST : affiche un message, puis répète tester_echeances du
           présentateur toutes les INTERVALLE_REVEIL_S secondes jusqu'à
           ce que l'utilisatrice tape Ctrl+C ou que interruption soit
           déclenchée (elle est alors remise à zéro, et l'arrêt est pris
           en compte au plus tard à la fin du test en cours). Affiche
           alors « Surveillance arrêtée. » et rend la main au menu.
           Exception ValueError : si les testeurs du présentateur sont
           vides et qu'un site est testé.
    """
    print(f"Surveillance en cours : un test tous les {frequence_min} "
          "minutes par site (Ctrl+C pour arrêter).")
    if interruption is not None:
        interruption.clear()
    try:
        while True:
            presentateur.tester_echeances(frequence_min)
            if interruption is None:
                time.sleep(INTERVALLE_REVEIL_S)
            elif interruption.wait(INTERVALLE_REVEIL_S):
                interruption.clear()
                break
    except KeyboardInterrupt:
        pass
    print()
    print("Surveillance arrêtée.")
