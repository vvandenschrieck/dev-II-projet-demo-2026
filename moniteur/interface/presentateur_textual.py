"""Présentateur de l'interface Textual : prépare l'affichage et agit.

Le présentateur s'abonne au registre (patron Observer). À chaque
changement, il relit les sites et donne à la vue une ligne par site et
par page, avec un texte par colonne et une couleur (EF-02.1, EF-02.4).
Il reçoit aussi les demandes de la vue (ajouter ou modifier un site,
ajouter ou supprimer une page, lancer des tests), les exécute sur le
domaine et explique à la vue ce qui s'est passé par un message. Les
tests tournent dans un fil de travail, pour que l'écran reste utilisable.
La vue ne contient donc aucune règle d'affichage ni aucun appel au
domaine : elle ne connaît ni le registre ni les règles de couleur. Ce
module n'importe pas Textual, ce qui permet de le vérifier sans écran.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
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

VERT = "vert"
ORANGE = "orange"
ROUGE = "rouge"
JAUNE = "jaune"
# Couleur d'une page jamais testée, ou d'un message sans gravité.
AUCUNE = ""

COULEURS = {
    StatutDisponibilite.DISPONIBLE: VERT,
    StatutDisponibilite.PARTIELLEMENT_INDISPONIBLE: ORANGE,
    StatutDisponibilite.INDISPONIBLE: ROUGE,
    StatutDisponibilite.INCONNU: JAUNE,
}

FORMAT_HORODATAGE = "%d/%m/%Y %H:%M:%S"

# Ajouté à l'horodatage d'un site dont les statuts datent de trop longtemps.
MARQUE_ANCIEN = " (ancien)"


@dataclass(frozen=True)
class LigneTextual:
    """Ligne du tableau : un site ou une page, prête à être affichée.

    cellules contient huit textes (nom ou page, statut ou verdict,
    performance, RTT, chargement, dernier test, diagnostic, URI) ;
    couleur vaut VERT, ORANGE, ROUGE, JAUNE ou AUCUNE (EF-02.4).
    nom_site et nom_page disent de quel site et de quelle page il s'agit
    (nom_page vaut None pour la ligne d'un site) : la vue les rend au
    présentateur pour désigner la ligne sélectionnée.

    INVARIANT : les champs ne changent jamais après la création (classe
    figée).
    """

    cellules: tuple[str, ...]
    couleur: str
    nom_site: str
    nom_page: str | None


class PresentateurTextual:
    """Présentateur de l'interface Textual (EF-02.1, EF-02.3, EF-03.1).

    INVARIANT : le registre, les testeurs, la configuration, l'horloge,
    la fréquence et les fonctions d'affichage reçus à la création ne
    sont jamais remplacés ; un site n'est jamais testé deux fois en même
    temps par ce présentateur.
    """

    def __init__(
        self,
        registre: RegistreSites,
        testeurs: list[Testeur],
        config: ConfigurationTests,
        horloge: Callable[[], datetime],
        frequence_min: int,
        afficher: Callable[[tuple[LigneTextual, ...]], None],
        afficher_message: Callable[[str, str], None],
        vider_formulaire: Callable[[], None],
    ) -> None:
        """Crée le présentateur et l'abonne au registre.

        frequence_min est le délai, en minutes, entre deux tests
        automatiques d'un même site (EF-03.7). afficher reçoit les
        lignes à montrer ; afficher_message reçoit un texte et sa
        couleur (ROUGE pour un refus, AUCUNE sinon) ; vider_formulaire
        est appelée quand une saisie a été acceptée. Ces fonctions
        peuvent être appelées depuis n'importe quel fil d'exécution :
        c'est à la vue de s'en protéger.

        PRE : aucune.
        POST : le présentateur est abonné au registre : afficher est
               appelée à chaque changement d'état (EF-02.3). Rien n'est
               affiché à la création : la vue demande l'état avec
               rafraichir.
        """
        self.__registre = registre
        self.__testeurs = testeurs
        self.__config = config
        self.__horloge = horloge
        self.__frequence_min = frequence_min
        self.__afficher = afficher
        self.__afficher_message = afficher_message
        self.__vider_formulaire = vider_formulaire
        self.__en_cours: set[Site] = set()
        self.__verrou = threading.Lock()
        registre.abonner(self.rafraichir)

    def rafraichir(self) -> None:
        """Donne l'état actuel des sites à la vue (EF-02.1, EF-02.3).

        Chaque site est suivi d'une ligne par page. La couleur de chaque
        ligne met en évidence les sites indisponibles, jamais testés ou
        aux performances dégradées, et les pages en erreur ou lentes
        (EF-02.4). Appelée par le registre à chaque changement.

        PRE : aucune.
        POST : afficher est appelée une fois, avec un tuple de lignes
               dans l'ordre du registre. Ne modifie ni le registre ni
               ses sites.
        """
        lignes: list[LigneTextual] = []
        for site in self.__registre.sites:
            lignes.append(self.__ligne_site(site))
            lignes.extend(self.__ligne_page(site, p) for p in site.pages)
        self.__afficher(tuple(lignes))

    def ajouter_site(self, nom: str, uri_principale: str) -> None:
        """Ajoute un site au registre (EF-01.1).

        PRE : aucune.
        POST : si le domaine accepte le nom et l'URI, le site est ajouté,
               une confirmation est envoyée à la vue et le formulaire
               est vidé. Sinon (nom déjà utilisé, nom ou URI vide,
               EF-01.2 et EF-01.3), le refus est envoyé à la vue en
               rouge, le formulaire est conservé et le registre n'est
               pas modifié.
        """
        try:
            site = self.__registre.ajouter_site(nom, uri_principale)
        except ValueError as erreur:
            self.__refuser(erreur)
            return
        self.__vider_formulaire()
        self.__afficher_message(f"Site « {site.nom} » ajouté.", AUCUNE)

    def modifier_site(
        self, nom_site: str | None, nouveau_nom: str, nouvelle_uri: str
    ) -> None:
        """Change le nom et l'URI principale d'un site (EF-01.2).

        nom_site est le site de la ligne sélectionnée, ou None si
        aucune ligne n'est sélectionnée. Une saisie vide n'est pas
        remplacée par la valeur actuelle (EF-01.3).

        PRE : aucune.
        POST : si le domaine accepte la modification, le site a son
               nouveau nom et sa nouvelle URI, une confirmation est
               envoyée à la vue et le formulaire est vidé. Sinon
               (aucune sélection, site inconnu, nom déjà utilisé, nom
               ou URI vide, EF-01.2 et EF-01.3, URI déjà portée par une
               autre page du site, EF-01.6), le refus est envoyé à la
               vue en rouge, le formulaire est conservé et le site
               n'est pas modifié.
        """
        if nom_site is None:
            self.__afficher_message("Aucun site sélectionné.", ROUGE)
            return
        try:
            self.__registre.modifier_site(
                nom_site, nouveau_nom, nouvelle_uri
            )
            site = self.__registre.trouver_site(nouveau_nom)
        except ValueError as erreur:
            self.__refuser(erreur)
            return
        self.__vider_formulaire()
        self.__afficher_message(f"Site « {site.nom} » modifié.", AUCUNE)

    def ajouter_page(
        self, nom_site: str | None, nom: str, uri: str
    ) -> None:
        """Ajoute une page au site de la ligne sélectionnée (EF-01.4).

        nom_site est le site de la ligne sélectionnée, ou None si
        aucune ligne n'est sélectionnée.

        PRE : aucune.
        POST : si le domaine l'accepte, la page est ajoutée au site, une
               confirmation est envoyée à la vue et le formulaire est
               vidé. Sinon (aucune sélection, nom de page déjà utilisé,
               EF-01.4, URI déjà utilisée, EF-01.6, nom ou URI vide),
               le refus est envoyé à la vue en rouge, le formulaire est
               conservé et le site n'est pas modifié.
        """
        if nom_site is None:
            self.__afficher_message("Aucun site sélectionné.", ROUGE)
            return
        try:
            site = self.__registre.trouver_site(nom_site)
            page = site.ajouter_page(nom, uri)
        except ValueError as erreur:
            self.__refuser(erreur)
            return
        self.__vider_formulaire()
        self.__afficher_message(
            f"Page « {page.nom} » ajoutée au site « {site.nom} ».", AUCUNE
        )

    def supprimer_page(
        self, nom_site: str | None, nom_page: str | None
    ) -> None:
        """Retire la page de la ligne sélectionnée (EF-01.5).

        nom_site et nom_page désignent la ligne sélectionnée ; nom_page
        vaut None si c'est la ligne d'un site, nom_site vaut None si
        aucune ligne n'est sélectionnée.

        PRE : aucune.
        POST : si le domaine l'accepte, la page est retirée du site (ses
               mesures restent dans l'historique) et une confirmation
               est envoyée à la vue. Sinon (aucune page sélectionnée,
               page principale), le refus est envoyé à la vue en rouge
               et le site n'est pas modifié.
        """
        if nom_site is None or nom_page is None:
            self.__afficher_message(
                "Sélectionnez la ligne de la page à supprimer.", ROUGE
            )
            return
        try:
            site = self.__registre.trouver_site(nom_site)
            site.supprimer_page(nom_page)
        except ValueError as erreur:
            self.__refuser(erreur)
            return
        self.__afficher_message(
            f"Page « {nom_page} » supprimée "
            "(ses mesures restent dans l'historique).", AUCUNE
        )

    def tester_site(self, nom_site: str | None) -> None:
        """Lance une batterie de tests sur un site (EF-03.1).

        nom_site est le site de la ligne sélectionnée, ou None si le
        tableau est vide. Le test s'exécute dans un fil de travail : la
        méthode rend la main tout de suite.

        PRE : aucune.
        POST : si le site n'est pas déjà en test, une batterie manuelle
               est lancée sur lui ; elle rejoint son historique et la
               vue est rafraîchie à la fin du test. Sinon un message
               explique à la vue pourquoi rien n'est lancé (aucun site,
               site inconnu, test déjà en cours).
        """
        if nom_site is None:
            self.__afficher_message("Aucun site à tester.", AUCUNE)
            return
        try:
            site = self.__registre.trouver_site(nom_site)
        except ValueError as erreur:
            self.__refuser(erreur)
            return
        self.__demarrer([site], Declenchement.MANUEL)

    def tester_tous(self) -> None:
        """Lance une batterie de tests sur chaque site (EF-03.4).

        PRE : aucune.
        POST : une batterie manuelle est lancée, l'une après l'autre
               dans un fil de travail, sur chaque site du registre qui
               n'est pas déjà en test ; la vue est rafraîchie après
               chaque site. La méthode rend la main tout de suite. Un
               message explique à la vue pourquoi rien n'est lancé si
               tous les sites sont déjà en test. Ne fait rien si le
               registre est vide.
        """
        self.__demarrer(list(self.__registre.sites), Declenchement.MANUEL)

    def tester_echeances(self) -> None:
        """Lance le test automatique des sites à tester (EF-03.7).

        Un site est à tester s'il n'a jamais été testé ou si son dernier
        test date d'au moins la fréquence donnée à la création. Prévue
        pour être appelée à intervalles réguliers par la vue.

        PRE : aucune.
        POST : une batterie périodique est lancée, l'une après l'autre
               dans un fil de travail, sur chaque site à tester qui
               n'est pas déjà en test. La méthode rend la main tout de
               suite et n'envoie aucun message si rien n'est lancé.
        """
        a_tester = [
            site for site in self.__registre.sites
            if site.est_a_tester(self.__frequence_min, self.__horloge)
        ]
        self.__demarrer(a_tester, Declenchement.PERIODIQUE)

    def __refuser(self, erreur: ValueError) -> None:
        """Envoie à la vue le motif d'un refus du domaine, en rouge."""
        self.__afficher_message(f"Refus : {erreur}", ROUGE)

    def __demarrer(
        self, sites: list[Site], declenchement: Declenchement
    ) -> None:
        """Marque les sites libres « en cours » et démarre leur test.

        Envoie « Test déjà en cours. » si un test demandé à la main
        porte sur des sites tous déjà en cours de test.
        """
        with self.__verrou:
            libres = [s for s in sites if s not in self.__en_cours]
            self.__en_cours.update(libres)
        if len(libres) == 0:
            if declenchement == Declenchement.MANUEL and len(sites) > 0:
                self.__afficher_message("Test déjà en cours.", AUCUNE)
            return
        threading.Thread(
            target=self.__tester, args=(libres, declenchement), daemon=True
        ).start()

    def __tester(
        self, sites: list[Site], declenchement: Declenchement
    ) -> None:
        """Teste les sites un par un (exécuté dans un fil de travail).

        Chaque site est libéré à la fin de son test, même en cas
        d'erreur. Le suivi se fait par site et non par nom : un site
        renommé pendant son test reste bien identifié.
        """
        debut = ("Test automatique"
                 if declenchement == Declenchement.PERIODIQUE else "Test")
        for site in sites:
            self.__afficher_message(
                f"{debut} de « {site.nom} » en cours...", AUCUNE
            )
            try:
                site.lancer_batterie(
                    self.__testeurs, self.__config, declenchement,
                    self.__horloge,
                )
            except ValueError as erreur:
                self.__refuser(erreur)
            finally:
                with self.__verrou:
                    self.__en_cours.discard(site)
        self.__afficher_message("Tests terminés.", AUCUNE)

    def __ligne_site(self, site: Site) -> LigneTextual:
        """Prépare la ligne d'un site : textes et couleur (EF-02.4).

        La couleur suit le statut de disponibilité, mais passe au jaune
        pour un site disponible aux performances dégradées. Les colonnes
        sont le nom, les statuts de disponibilité et de performance
        (EF-02.1), le RTT moyen de la dernière fenêtre avec son écart
        par rapport à la moyenne globale (« 85 ms (+37 %) »), une
        colonne de chargement laissée vide (il se lit sur les lignes des
        pages), l'horodatage du dernier test (EF-02.2), suivi de
        « (ancien) » si les statuts datent de trop longtemps, les
        diagnostics des mesures L3 et L4, précédés de leur couche
        (« L3: 6/6 sondes »), et l'URI principale. Horodatage et
        diagnostic valent « - » si le site n'a jamais été testé.
        """
        statut = site.statut_disponibilite
        batterie = site.derniere_batterie
        if batterie is None:
            horodatage = "-"
            diagnostic = "-"
        else:
            horodatage = batterie.horodatage.strftime(FORMAT_HORODATAGE)
            if site.statut_est_ancien(self.__config, self.__horloge):
                horodatage += MARQUE_ANCIEN
            diagnostic = ", ".join(
                f"{mesure.couche.name}: {mesure.diagnostic}"
                for mesure in batterie.mesures
                if mesure.couche != Couche.L7
                and mesure.diagnostic is not None
            )
        performance = site.statut_performance(self.__config)
        couleur = COULEURS[statut]
        if (statut == StatutDisponibilite.DISPONIBLE
                and performance == StatutPerformance.DEGRADEES):
            couleur = JAUNE
        rtt = formater_duree(
            site.rtt_moyen(self.__config), site.ecart_rtt(self.__config)
        )
        cellules = (
            site.nom, statut.name, performance.name, rtt, "", horodatage,
            diagnostic, site.uri_principale,
        )
        return LigneTextual(cellules, couleur, site.nom, None)

    def __ligne_page(self, site: Site, page: Page) -> LigneTextual:
        """Prépare la ligne d'une page : textes et couleur (EF-02.1).

        Le nom est en retrait. Le verdict et le diagnostic sont ceux de
        la dernière mesure de la page, « - » si elle n'a jamais été
        testée. Le chargement est la moyenne de la page avec son écart
        par rapport à sa moyenne globale.
        """
        mesures = site.historique_page(page)
        derniere = mesures[-1] if len(mesures) > 0 else None
        chargement_s = site.chargement_moyen(self.__config, page)
        if derniere is None:
            verdict = "-"
            diagnostic = "-"
        else:
            verdict = derniere.verdict.name
            diagnostic = derniere.diagnostic or "-"
        chargement = formater_duree(
            chargement_s, site.ecart_chargement(self.__config, page)
        )
        cellules = (
            "  " + page.nom, verdict, "", "", chargement, "", diagnostic,
            page.uri,
        )
        return LigneTextual(
            cellules, self.__couleur_page(derniere, chargement_s),
            site.nom, page.nom,
        )

    def __couleur_page(
        self, derniere: Mesure | None, chargement_s: float | None
    ) -> str:
        """Renvoie la couleur de la ligne d'une page.

        ROUGE si la dernière mesure est KO, JAUNE si elle est OK mais que
        le chargement moyen dépasse le seuil L7 (RM-08), VERT sinon, et
        AUCUNE si la page n'a jamais été testée.
        """
        if derniere is None:
            return AUCUNE
        if derniere.verdict == Verdict.KO:
            return ROUGE
        if (chargement_s is not None
                and chargement_s > self.__config.seuil_l7_s):
            return JAUNE
        return VERT


if __name__ == "__main__":
    import time

    INSTANT = datetime(2026, 10, 17, 14, 30)
    CONFIG = ConfigurationTests(5.0)

    class FauxTesteur(Testeur):
        """Testeur de test : une mesure L7 au verdict fixé, sans réseau.

        Si une barrière est donnée, le test attend qu'elle soit levée :
        cela permet d'observer le site « en cours de test ».
        """

        def __init__(
            self, verdict: Verdict, barriere: threading.Event | None = None
        ) -> None:
            """Mémorise le verdict et la barrière éventuelle."""
            self.__verdict = verdict
            self.__barriere = barriere

        @property
        def couche(self) -> Couche:
            """Donne la couche simulée (L7)."""
            return Couche.L7

        def executer(
            self, site: Site, timeout_s: float, horodatage: datetime
        ) -> list[Mesure]:
            """Renvoie une mesure par page du site."""
            if self.__barriere is not None:
                self.__barriere.wait(5)
            return [
                Mesure(horodatage, Couche.L7, self.__verdict, 0.05, "200",
                       page)
                for page in site.pages
            ]

    recu: list[tuple[LigneTextual, ...]] = []
    messages: list[tuple[str, str]] = []
    formulaires = [0]
    registre = RegistreSites()
    barriere = threading.Event()
    presentateur = PresentateurTextual(
        registre, [FauxTesteur(Verdict.OK, barriere)], CONFIG,
        lambda: INSTANT, 15, recu.append,
        lambda texte, couleur: messages.append((texte, couleur)),
        lambda: formulaires.__setitem__(0, formulaires[0] + 1),
    )

    def attendre(condition: Callable[[], bool]) -> None:
        """Attend (3 s au plus) qu'un fil de travail ait terminé."""
        fin = time.time() + 3
        while not condition() and time.time() < fin:
            time.sleep(0.01)

    def verifier(description: str, attendu: object, obtenu: object) -> None:
        """Affiche un scénario au format du cours."""
        print(f"Scénario : {description}")
        print(f"  attendu : {attendu}")
        print(f"  obtenu  : {obtenu}")
        print("  → OK" if obtenu == attendu else "  → ÉCHEC")
        print("-" * 40)

    presentateur.ajouter_site("Alpha", "alpha.be")
    verifier("l'ajout d'un site (EF-01.1) rafraîchit la vue sans action "
             "de l'utilisatrice (EF-02.3) : une ligne de site jaune, une "
             "ligne de page sans couleur (EF-02.4), formulaire vidé",
             ([JAUNE, AUCUNE], [None, "Page d'accueil"], 1),
             ([ligne.couleur for ligne in recu[-1]],
              [ligne.nom_page for ligne in recu[-1]], formulaires[0]))

    messages.clear()
    presentateur.ajouter_site("alpha", "autre.be")
    verifier("ajout d'un site au nom déjà utilisé (EF-01.2) : refus en "
             "rouge, formulaire conservé, registre inchangé",
             ([("Refus : Un site nommé « Alpha » existe déjà.", ROUGE)],
              1, 1),
             (messages, formulaires[0], len(registre.sites)))

    messages.clear()
    presentateur.supprimer_page("Alpha", None)
    verifier("supprimer sans avoir sélectionné une page : refus en rouge",
             [("Sélectionnez la ligne de la page à supprimer.", ROUGE)],
             messages)

    messages.clear()
    presentateur.tester_site("Alpha")
    attendre(lambda: len(messages) > 0)
    presentateur.tester_site("Alpha")
    verifier("tester un site (EF-03.1) pendant qu'il est déjà en test : "
             "un seul test est lancé, un message l'explique",
             ("Test déjà en cours.", 1),
             (messages[-1][0],
              sum(1 for texte, _ in messages if "en cours..." in texte)))

    barriere.set()
    attendre(lambda: messages[-1][0] == "Tests terminés.")
    verifier("fin du test : site disponible en vert, page OK en vert, "
             "date de l'horloge (EF-02.2)",
             ([VERT, VERT], "DISPONIBLE", "17/10/2026 14:30:00"),
             ([ligne.couleur for ligne in recu[-1]],
              recu[-1][0].cellules[1], recu[-1][0].cellules[5]))

    registre.ajouter_site("Beta", "beta.be")
    messages.clear()
    presentateur.tester_echeances()
    attendre(lambda: len(messages) > 0 and messages[-1][0] ==
             "Tests terminés.")
    verifier("tests automatiques (EF-03.7) : seul Beta, jamais testé, est "
             "testé ; Alpha vient de l'être",
             [("Test automatique de « Beta » en cours...", AUCUNE),
              ("Tests terminés.", AUCUNE)], messages)
