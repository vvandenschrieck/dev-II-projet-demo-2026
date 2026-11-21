"""Interface texte simple : menus en print() et input().

Cette interface affiche l'état des sites, avec une ligne par page, puis
propose un menu pour ajouter ou modifier un site, ajouter ou supprimer une
page, tester un site, tester tous les sites ou surveiller les sites.
L'écran est réaffiché après chaque action (page MVP, section 2.2) et,
pendant la surveillance, après chaque test automatique (EF-02.3).
"""

import threading
import time
from collections.abc import Callable
from datetime import datetime

from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.enumerations import (
    Couche,
    Declenchement,
    StatutDisponibilite,
    StatutPerformance,
    Verdict,
)
from moniteur.domaine.formatage import formater_duree
from moniteur.domaine.mesure import Mesure
from moniteur.domaine.page import Page
from moniteur.domaine.registre_sites import RegistreSites
from moniteur.domaine.site import Site
from moniteur.domaine.testeur import Testeur

# Codes ANSI : le terminal colore le texte qui les suit.
VERT = "\033[32m"
ROUGE = "\033[31m"
JAUNE = "\033[33m"
ORANGE = "\033[38;5;208m"
REINITIALISER = "\033[0m"

COULEURS = {
    StatutDisponibilite.DISPONIBLE: VERT,
    StatutDisponibilite.PARTIELLEMENT_INDISPONIBLE: ORANGE,
    StatutDisponibilite.INDISPONIBLE: ROUGE,
    StatutDisponibilite.INCONNU: JAUNE,
}

FORMAT_HORODATAGE = "%d/%m/%Y %H:%M:%S"

# Ajouté à l'horodatage d'un site dont les statuts datent de trop longtemps.
MARQUE_ANCIEN = " (ancien)"

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
    main.py et transmis tels quels au domaine. interruption, si elle est
    donnée, permet à un autre fil d'exécution d'arrêter la surveillance
    (voir surveiller) ; sinon Ctrl+C s'en charge.

    PRE : config.timeout_s > 0.
    POST : affiche l'état des sites puis le menu après chaque action
           (page MVP, section 2.2), jusqu'au choix « 0 » ou jusqu'à la
           fin de la saisie (Ctrl+D, Ctrl+C), puis affiche « Au revoir. ».
           Si un autre fil d'exécution modifie le registre (test lancé
           depuis le dashboard) pendant que l'interface attend un choix,
           l'état des sites et le menu sont réaffichés (EF-02.3).
           Le choix « 4 » lance la surveillance (voir surveiller).
           Modifie registre (sites ajoutés ou modifiés), les pages des
           sites (ajoutées ou supprimées) et les sites testés (nouvelles
           batteries).
           Exception ValueError : si testeurs est vide et qu'un site est
           testé.
    """
    en_attente = threading.Event()

    def reafficher() -> None:
        """Réaffiche l'écran si l'interface attend un choix du menu."""
        if en_attente.is_set():
            print()
            afficher_sites(registre, config, horloge)
            afficher_menu()
            print("Votre choix : ", end="", flush=True)

    registre.abonner(reafficher)
    try:
        while True:
            afficher_sites(registre, config, horloge)
            en_attente.set()
            choix = demander_choix()
            en_attente.clear()
            if choix == "1":
                ajouter_site(registre)
            elif choix == "2":
                tester_site(registre, testeurs, config, horloge)
            elif choix == "3":
                tester_tous_les_sites(registre, testeurs, config, horloge)
            elif choix == "4":
                surveiller(
                    registre, testeurs, config, horloge, frequence_min,
                    interruption,
                )
            elif choix == "5":
                modifier_site(registre)
            elif choix == "6":
                ajouter_page(registre)
            elif choix == "7":
                supprimer_page(registre)
            elif choix == "0":
                break
            else:
                print("Choix inconnu.")
    except (EOFError, KeyboardInterrupt):
        print()
    print("Au revoir.")


def afficher_sites(
    registre: RegistreSites,
    config: ConfigurationTests,
    horloge: Callable[[], datetime],
) -> None:
    """Affiche la liste des sites avec leurs statuts (EF-02.1).

    PRE : aucune.
    POST : affiche un titre, puis un message si le registre est vide, ou
           sinon un en-tête et un bloc par site, dans l'ordre du
           registre (voir afficher_site). Ne modifie rien.
    """
    print()
    print("=== État des sites ===")
    if len(registre.sites) == 0:
        print("Aucun site. Ajoutez-en un avec le choix 1.")
        return
    print(f"{'Nom':<17} {'Statut':<26} {'Performance':<11} "
          f"{'RTT L3/L4':<16} {'Dernier test':<28} Diagnostic L3/L4")
    print(f"  {'Page':<15} {'Verdict':<8} {'Chargement L7':<16} "
          f"{'Diagnostic':<27} URI")
    for site in registre.sites:
        print()
        afficher_site(site, config, horloge)


def afficher_site(
    site: Site,
    config: ConfigurationTests,
    horloge: Callable[[], datetime],
) -> None:
    """Affiche le bloc d'un site : sa ligne, puis une ligne par page.

    PRE : aucune.
    POST : affiche une ligne colorée selon le statut du site (EF-02.4)
           avec le nom, les statuts de disponibilité et de performance
           (EF-02.1), le RTT moyen de la dernière fenêtre avec son écart
           par rapport à la moyenne globale (« 85 ms (+37 %) »),
           l'horodatage du dernier test (EF-02.2) et les diagnostics des
           mesures L3 et L4, précédés de leur couche (« L3: 6/6
           sondes »). La couleur suit le statut de disponibilité, mais
           passe au jaune pour un site disponible aux performances
           dégradées. L'horodatage est suivi de « (ancien) » si les
           statuts datent de trop longtemps. Horodatage et diagnostic
           valent « - » si le site n'a jamais été testé. Affiche ensuite
           une ligne par page, la page principale en premier (voir
           afficher_page). Ne modifie rien.
    """
    statut = site.statut_disponibilite
    batterie = site.derniere_batterie
    if batterie is None:
        horodatage = "-"
        diagnostic = "-"
    else:
        horodatage = batterie.horodatage.strftime(FORMAT_HORODATAGE)
        if site.statut_est_ancien(config, horloge):
            horodatage += MARQUE_ANCIEN
        diagnostic = ", ".join(
            f"{mesure.couche.name}: {mesure.diagnostic}"
            for mesure in batterie.mesures
            if mesure.couche != Couche.L7 and mesure.diagnostic is not None
        )
    performance = site.statut_performance(config)
    couleur = COULEURS[statut]
    if (statut == StatutDisponibilite.DISPONIBLE
            and performance == StatutPerformance.DEGRADEES):
        couleur = JAUNE
    rtt = formater_duree(site.rtt_moyen(config), site.ecart_rtt(config))
    ligne = (f"{site.nom:<17} {statut.name:<26} {performance.name:<11} "
             f"{rtt:<16} {horodatage:<28} {diagnostic}")
    print(couleur + ligne + REINITIALISER)
    for page in site.pages:
        afficher_page(site, page, config)


def afficher_page(
    site: Site, page: Page, config: ConfigurationTests
) -> None:
    """Affiche la ligne d'une page, en retrait sous son site (EF-02.1).

    PRE : page est une page de site.
    POST : affiche une ligne avec le nom de la page, le verdict et le
           diagnostic de sa dernière mesure, son temps de chargement
           moyen avec son écart par rapport à la moyenne globale, et son
           URI. Le verdict et le diagnostic valent « - » si la page n'a
           jamais été testée. La ligne est rouge si le verdict est KO,
           jaune si la page est OK mais son chargement moyen dépasse
           config.seuil_l7_s (RM-08), verte sinon, et sans couleur si la
           page n'a jamais été testée. Ne modifie rien.
    """
    mesures = site.historique_page(page)
    derniere = mesures[-1] if len(mesures) > 0 else None
    chargement_s = site.chargement_moyen(config, page)
    chargement = formater_duree(
        chargement_s, site.ecart_chargement(config, page)
    )
    if derniere is None:
        verdict = "-"
        diagnostic = "-"
    else:
        verdict = derniere.verdict.name
        diagnostic = derniere.diagnostic or "-"
    ligne = (f"  {page.nom:<15} {verdict:<8} {chargement:<16} "
             f"{diagnostic:<27} {page.uri}")
    print(couleur_page(derniere, chargement_s, config) + ligne
          + REINITIALISER)


def couleur_page(
    derniere: Mesure | None,
    chargement_s: float | None,
    config: ConfigurationTests,
) -> str:
    """Renvoie le code ANSI de la ligne d'une page.

    PRE : aucune.
    POST : renvoie ROUGE si derniere est une mesure KO, JAUNE si elle
           est OK mais que chargement_s dépasse config.seuil_l7_s, VERT
           si elle est OK sinon, et une chaîne vide (aucune couleur) si
           derniere est None. Ne modifie rien.
    """
    if derniere is None:
        return ""
    if derniere.verdict == Verdict.KO:
        return ROUGE
    if chargement_s is not None and chargement_s > config.seuil_l7_s:
        return JAUNE
    return VERT


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


def demander_site(registre: RegistreSites, invite: str) -> Site | None:
    """Demande le nom d'un site et renvoie le site correspondant.

    PRE : aucune.
    POST : affiche invite et lit un nom. Renvoie le site de registre qui
           porte ce nom, ou None après avoir affiché « Refus : » suivi
           du motif si aucun site ne le porte. Ne modifie rien.
           Exception EOFError : si l'entrée standard est fermée.
    """
    nom = input(invite)
    try:
        return registre.trouver_site(nom)
    except ValueError as erreur:
        print(f"Refus : {erreur}")
        return None


def modifier_site(registre: RegistreSites) -> None:
    """Demande un site, puis son nouveau nom et sa nouvelle URI (EF-01.2).

    PRE : aucune.
    POST : demande le nom d'un site, affiche son nom et son URI actuels,
           puis demande un nouveau nom et une nouvelle URI principale.
           Une saisie vide n'est pas remplacée par la valeur actuelle.
           Si le domaine accepte la modification, une confirmation est
           affichée. Sinon (site inconnu, nom déjà utilisé, nom ou URI
           vide, EF-01.2 et EF-01.3, URI déjà portée par une autre page
           du site, EF-01.6), « Refus : » suivi du motif est affiché et
           le site n'est pas modifié.
           Exception EOFError : si l'entrée standard est fermée.
    """
    site = demander_site(registre, "Nom du site à modifier : ")
    if site is None:
        return
    print(f"Nom actuel : {site.nom} — "
          f"URI principale actuelle : {site.uri_principale}")
    nouveau_nom = input("Nouveau nom : ")
    nouvelle_uri = input("Nouvelle URI principale : ")
    try:
        registre.modifier_site(site.nom, nouveau_nom, nouvelle_uri)
        print(f"Site « {site.nom} » modifié.")
    except ValueError as erreur:
        print(f"Refus : {erreur}")


def ajouter_page(registre: RegistreSites) -> None:
    """Demande un site, puis le nom et l'URI d'une page à lui ajouter.

    PRE : aucune.
    POST : demande le nom d'un site, puis le nom et l'URI de la page. Si
           le domaine l'accepte, la page est ajoutée au site et une
           confirmation est affichée. Sinon (site inconnu, nom de page
           déjà utilisé, EF-01.4, URI déjà utilisée, EF-01.6, nom ou
           URI vide), « Refus : » suivi du motif est affiché et le
           site n'est pas modifié.
           Exception EOFError : si l'entrée standard est fermée.
    """
    site = demander_site(registre, "Nom du site : ")
    if site is None:
        return
    nom = input("Nom de la page : ")
    uri = input("URI de la page : ")
    try:
        page = site.ajouter_page(nom, uri)
        print(f"Page « {page.nom} » ajoutée.")
    except ValueError as erreur:
        print(f"Refus : {erreur}")


def supprimer_page(registre: RegistreSites) -> None:
    """Demande un site, puis le nom de la page à lui retirer (EF-01.5).

    PRE : aucune.
    POST : demande le nom d'un site, puis celui de la page. Si le
           domaine l'accepte, la page est retirée du site (ses mesures
           restent dans l'historique) et une confirmation est affichée.
           Sinon (site inconnu, page inexistante, page principale),
           « Refus : » suivi du motif est affiché et le site n'est pas
           modifié.
           Exception EOFError : si l'entrée standard est fermée.
    """
    site = demander_site(registre, "Nom du site : ")
    if site is None:
        return
    nom = input("Nom de la page à supprimer : ")
    try:
        site.supprimer_page(nom)
        print(f"Page « {nom.strip()} » supprimée "
              "(ses mesures restent dans l'historique).")
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
    site = demander_site(registre, "Nom du site à tester : ")
    if site is None:
        return
    print(f"Test de « {site.nom} » en cours...")
    site.lancer_batterie(testeurs, config, Declenchement.MANUEL, horloge)


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
        site.lancer_batterie(
            testeurs, config, Declenchement.MANUEL, horloge
        )


def tester_echeances(
    registre: RegistreSites,
    testeurs: list[Testeur],
    config: ConfigurationTests,
    horloge: Callable[[], datetime],
    frequence_min: int,
) -> int:
    """Teste les sites dont l'échéance est atteinte (EF-03.7).

    PRE : config.timeout_s > 0.
    POST : pour chaque site de registre qui n'a jamais été testé ou dont
           le dernier test date d'au moins frequence_min minutes, affiche
           un message, lance une batterie PERIODIQUE puis réaffiche
           l'état des sites (EF-02.3). Renvoie le nombre de sites testés.
           Exception ValueError : si testeurs est vide et qu'un site est
           testé.
    """
    nombre = 0
    for site in registre.sites:
        if site.est_a_tester(frequence_min, horloge):
            print(f"Test automatique de « {site.nom} » en cours...")
            site.lancer_batterie(
                testeurs, config, Declenchement.PERIODIQUE, horloge
            )
            afficher_sites(registre, config, horloge)
            nombre += 1
    return nombre


def surveiller(
    registre: RegistreSites,
    testeurs: list[Testeur],
    config: ConfigurationTests,
    horloge: Callable[[], datetime],
    frequence_min: int,
    interruption: threading.Event | None = None,
) -> None:
    """Teste automatiquement les sites jusqu'à Ctrl+C (EF-03.7).

    Toutes les INTERVALLE_REVEIL_S secondes, teste les sites dont
    l'échéance est atteinte. Le menu n'est pas utilisable pendant la
    surveillance. Quand le dashboard est ouvert, Ctrl+C n'arrive pas
    dans ce fil d'exécution : un autre fil déclenche interruption.

    PRE : config.timeout_s > 0.
    POST : affiche l'état des sites, puis répète tester_echeances toutes
           les INTERVALLE_REVEIL_S secondes jusqu'à ce que l'utilisatrice
           tape Ctrl+C ou que interruption soit déclenchée (elle est
           alors remise à zéro, et l'arrêt est pris en compte au plus
           tard à la fin du test en cours). Affiche alors « Surveillance
           arrêtée. » et rend la main au menu. Modifie les sites testés
           (nouvelles batteries).
           Exception ValueError : si testeurs est vide et qu'un site est
           testé.
    """
    print(f"Surveillance en cours : un test tous les {frequence_min} "
          "minutes par site (Ctrl+C pour arrêter).")
    if interruption is not None:
        interruption.clear()
    try:
        while True:
            tester_echeances(
                registre, testeurs, config, horloge, frequence_min
            )
            if interruption is None:
                time.sleep(INTERVALLE_REVEIL_S)
            elif interruption.wait(INTERVALLE_REVEIL_S):
                interruption.clear()
                break
    except KeyboardInterrupt:
        pass
    print()
    print("Surveillance arrêtée.")
