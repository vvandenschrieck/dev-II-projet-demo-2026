"""Présentateur du dashboard : prépare l'affichage et lance les tests.

Le présentateur s'abonne au registre (patron Observer). À chaque
changement, il relit les sites, prépare un texte et une couleur par
site, et les donne à la vue. Il reçoit aussi les demandes de test de la
vue (tester un site, tester tous les sites, EF-03.1, EF-03.4) et les
exécute dans un fil de travail. La vue n'a donc aucune logique : elle ne
connaît ni le registre ni les règles de couleur. Ce module n'importe
aucune bibliothèque graphique, ce qui permet de le vérifier sans
fenêtre.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.enumerations import (
    Declenchement,
    StatutDisponibilite,
    StatutPerformance,
)
from moniteur.domaine.formatage import formater_duree
from moniteur.domaine.registre_sites import RegistreSites
from moniteur.domaine.site import Site
from moniteur.domaine.testeur import Testeur

COLONNES = (
    "Site", "Disponibilité", "Performance", "RTT L3/L4", "Dernier test"
)

VERT = "vert"
ORANGE = "orange"
ROUGE = "rouge"
JAUNE = "jaune"

COULEURS = {
    StatutDisponibilite.DISPONIBLE: VERT,
    StatutDisponibilite.PARTIELLEMENT_INDISPONIBLE: ORANGE,
    StatutDisponibilite.INDISPONIBLE: ROUGE,
    StatutDisponibilite.INCONNU: JAUNE,
}

FORMAT_HORODATAGE = "%d/%m/%Y %H:%M:%S"

# Ajouté à l'horodatage d'un site dont les statuts datent de trop longtemps.
MARQUE_ANCIEN = " (ancien)"

# Ajouté à l'horodatage d'un site dont un test est demandé ou en cours.
MARQUE_EN_COURS = " (test en cours)"


@dataclass(frozen=True)
class LigneDashboard:
    """Ligne du tableau de bord : un site, prêt à être affiché.

    cellules contient un texte par colonne de COLONNES ; couleur vaut
    VERT, ORANGE, ROUGE ou JAUNE (EF-02.4).

    INVARIANT : les deux champs ne changent jamais après la création
    (classe figée).
    """

    cellules: tuple[str, ...]
    couleur: str


class PresentateurDashboard:
    """Présentateur du dashboard (ENF-05, EF-02.1, EF-02.3, EF-03.1).

    INVARIANT : le registre, les testeurs, la configuration, l'horloge et
    les fonctions d'affichage reçus à la création ne sont jamais
    remplacés ; un site n'est jamais testé deux fois en même temps par
    ce présentateur ; la seule modification du registre est le lancement
    de batteries de tests manuelles.
    """

    def __init__(
        self,
        registre: RegistreSites,
        testeurs: list[Testeur],
        afficher: Callable[[tuple[LigneDashboard, ...]], None],
        afficher_message: Callable[[str], None],
        config: ConfigurationTests,
        horloge: Callable[[], datetime],
    ) -> None:
        """Crée le présentateur, s'abonne au registre et affiche l'état.

        afficher et afficher_message sont les méthodes de la vue qui
        reçoivent les lignes et les messages à montrer. Elles peuvent
        être appelées depuis n'importe quel fil d'exécution : c'est à la
        vue de s'en protéger.

        PRE : aucune.
        POST : le présentateur est abonné au registre : afficher est
               appelée à chaque changement d'état (EF-02.3). Elle est
               aussi appelée une première fois, avec l'état actuel.
        """
        self.__registre = registre
        self.__testeurs = testeurs
        self.__afficher = afficher
        self.__afficher_message = afficher_message
        self.__config = config
        self.__horloge = horloge
        self.__en_cours: set[Site] = set()
        self.__verrou = threading.Lock()
        registre.abonner(self.rafraichir)
        self.rafraichir()

    def rafraichir(self) -> None:
        """Relit le registre et donne une ligne par site à la vue (EF-02.1).

        Appelée par le registre à chaque changement, et à intervalles
        réguliers par la vue : le marqueur « (ancien) » dépend de
        l'horloge et non d'un changement du registre.

        PRE : aucune.
        POST : afficher est appelée une fois, avec un tuple de lignes
               dans l'ordre du registre. Ne modifie ni le registre ni
               ses sites.
        """
        lignes = tuple(self.__ligne(site) for site in self.__registre.sites)
        self.__afficher(lignes)

    def tester_site(self, nom: str | None) -> None:
        """Lance une batterie de tests sur le site choisi (EF-03.1).

        nom est le nom du site sélectionné dans la vue, ou None si
        aucun site n'est sélectionné. Le test s'exécute dans un fil de
        travail : la méthode rend la main tout de suite.

        PRE : aucune.
        POST : si un site porte ce nom et n'est pas déjà en test, une
               batterie manuelle est lancée sur lui ; il rejoint son
               historique, la vue est rafraîchie et le message précédent
               est effacé (message vide). Sinon un message
               explique à la vue pourquoi rien n'est lancé (aucune
               sélection, site inconnu, test déjà en cours).
        """
        if nom is None:
            self.__afficher_message("Sélectionnez d'abord un site.")
            return
        try:
            site = self.__registre.trouver_site(nom)
        except ValueError as erreur:
            self.__afficher_message(str(erreur))
            return
        self.__lancer([site])

    def tester_tous(self) -> None:
        """Lance une batterie de tests sur chaque site (EF-03.4).

        PRE : aucune.
        POST : une batterie manuelle est lancée, l'une après l'autre
               dans un fil de travail, sur chaque site du registre qui
               n'est pas déjà en test. La méthode rend la main tout de
               suite. Un message explique à la vue pourquoi rien n'est
               lancé si le registre est vide ou si tous les sites sont
               déjà en test ; sinon le message précédent est effacé.
        """
        sites = list(self.__registre.sites)
        if len(sites) == 0:
            self.__afficher_message("Aucun site à tester.")
            return
        self.__lancer(sites)

    def __lancer(self, sites: list[Site]) -> None:
        """Marque les sites libres « en cours » et démarre leur test."""
        with self.__verrou:
            libres = [s for s in sites if s not in self.__en_cours]
            self.__en_cours.update(libres)
        if len(libres) < len(sites):
            self.__afficher_message("Test déjà en cours.")
        if len(libres) == 0:
            return
        self.__afficher_message("")
        self.rafraichir()
        threading.Thread(
            target=self.__tester, args=(libres,), daemon=True
        ).start()

    def __tester(self, sites: list[Site]) -> None:
        """Teste les sites l'un après l'autre (exécuté dans un fil).

        Chaque site est libéré à la fin de son test, même en cas
        d'erreur, et la vue est rafraîchie.
        """
        for site in sites:
            try:
                site.lancer_batterie(
                    self.__testeurs, self.__config, Declenchement.MANUEL,
                    self.__horloge,
                )
            except ValueError as erreur:
                self.__afficher_message(str(erreur))
            finally:
                with self.__verrou:
                    self.__en_cours.discard(site)
                self.rafraichir()

    def __ligne(self, site: Site) -> LigneDashboard:
        """Prépare la ligne d'un site : textes et couleur (EF-02.4).

        La couleur suit le statut de disponibilité, mais passe au jaune
        pour un site disponible aux performances dégradées.
        """
        statut = site.statut_disponibilite
        performance = site.statut_performance(self.__config)
        couleur = COULEURS[statut]
        if (statut == StatutDisponibilite.DISPONIBLE
                and performance == StatutPerformance.DEGRADEES):
            couleur = JAUNE
        rtt = formater_duree(
            site.rtt_moyen(self.__config), site.ecart_rtt(self.__config)
        )
        cellules = (
            site.nom,
            statut.name,
            performance.name,
            rtt,
            self.__dernier_test(site),
        )
        return LigneDashboard(cellules, couleur)

    def __dernier_test(self, site: Site) -> str:
        """Renvoie l'horodatage du dernier test, « - » si jamais testé."""
        batterie = site.derniere_batterie
        if batterie is None:
            texte = "-"
        else:
            texte = batterie.horodatage.strftime(FORMAT_HORODATAGE)
            if site.statut_est_ancien(self.__config, self.__horloge):
                texte += MARQUE_ANCIEN
        with self.__verrou:
            en_cours = site in self.__en_cours
        if en_cours:
            texte += MARQUE_EN_COURS
        return texte


if __name__ == "__main__":
    import time
    from datetime import timedelta

    from moniteur.domaine.enumerations import Couche, Verdict
    from moniteur.domaine.mesure import Mesure

    INSTANT = datetime(2026, 10, 17, 14, 30)
    CONFIG = ConfigurationTests(5.0)

    class FauxTesteur(Testeur):
        """Testeur de test : renvoie une mesure L7 au verdict fixé.

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
            """Renvoie une mesure par page du site, sans réseau."""
            if self.__barriere is not None:
                self.__barriere.wait(5)
            return [
                Mesure(horodatage, Couche.L7, self.__verdict, 0.05, "200",
                       page)
                for page in site.pages
            ]

    maintenant = [INSTANT]
    recu: list[tuple[LigneDashboard, ...]] = []
    messages: list[str] = []
    registre = RegistreSites()
    barriere = threading.Event()
    presentateur = PresentateurDashboard(
        registre, [FauxTesteur(Verdict.OK, barriere)], recu.append,
        messages.append, CONFIG, lambda: maintenant[0],
    )

    def tester(nom: str, verdict: Verdict) -> None:
        """Lance sur le site une batterie automatique au verdict choisi."""
        registre.trouver_site(nom).lancer_batterie(
            [FauxTesteur(verdict)], CONFIG, Declenchement.PERIODIQUE,
            lambda: INSTANT,
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

    verifier("à la création, la vue reçoit l'état (vide) du registre "
             "(EF-02.1)", [()], recu)

    registre.ajouter_site("Alpha", "alpha.be")
    verifier("l'ajout d'un site rafraîchit la vue sans action de "
             "l'utilisatrice (EF-02.3) : site jamais testé, en jaune",
             (("Alpha", "INCONNU", "INCONNU", "-", "-"), JAUNE),
             (recu[-1][0].cellules, recu[-1][0].couleur))

    appels = len(recu)
    tester("Alpha", Verdict.KO)
    verifier("un test automatique, lancé hors de l'interface, rafraîchit "
             "la vue : site indisponible, en rouge (EF-02.4)",
             (appels + 1, ROUGE, "17/10/2026 14:30:00"),
             (len(recu), recu[-1][0].couleur, recu[-1][0].cellules[4]))

    maintenant[0] = INSTANT + timedelta(hours=2)
    appels = len(recu)
    presentateur.rafraichir()
    verifier("le temps qui passe : sans changement du registre, un "
             "rafraîchissement ajoute « (ancien) »",
             (appels + 1, "17/10/2026 14:30:00 (ancien)"),
             (len(recu), recu[-1][0].cellules[4]))

    presentateur.tester_site(None)
    verifier("tester sans sélection : un message, aucun test",
             ["Sélectionnez d'abord un site."], messages)

    messages.clear()
    presentateur.tester_site("Alpha")
    verifier("tester un site (EF-03.1) : la ligne indique « test en "
             "cours » pendant le test, et le message précédent est effacé",
             ("17/10/2026 14:30:00 (ancien) (test en cours)", [""]),
             (recu[-1][0].cellules[4], messages))
    messages.clear()

    presentateur.tester_site("Alpha")
    verifier("redemander le test d'un site déjà en cours : un message, "
             "pas de second test",
             ["Test déjà en cours."], messages)

    barriere.set()
    attendre(lambda: "test en cours" not in recu[-1][0].cellules[4])
    verifier("fin du test : site disponible, en vert, daté de l'horloge, "
             "marque « en cours » retirée",
             (VERT, "DISPONIBLE", "17/10/2026 16:30:00"),
             (recu[-1][0].couleur, recu[-1][0].cellules[1],
              recu[-1][0].cellules[4]))

    registre.ajouter_site("Beta", "beta.be")
    presentateur.tester_tous()
    attendre(lambda: all(
        site.derniere_batterie is not None
        and site.derniere_batterie.declenchement == Declenchement.MANUEL
        for site in registre.sites
    ) and "test en cours" not in recu[-1][1].cellules[4])
    verifier("tester tous les sites (EF-03.4) : chaque site reçoit une "
             "batterie manuelle",
             [Declenchement.MANUEL, Declenchement.MANUEL],
             [site.derniere_batterie.declenchement
              for site in registre.sites])
