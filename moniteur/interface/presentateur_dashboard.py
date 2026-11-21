"""Présentateur du dashboard : prépare l'affichage de la vue passive.

Le présentateur s'abonne au registre (patron Observer). À chaque
changement, il relit les sites, prépare un texte et une couleur par
site, et les donne à la vue. La vue n'a donc aucune logique : elle ne
connaît ni le registre ni les règles de couleur. Ce module n'importe
aucune bibliothèque graphique, ce qui permet de le vérifier sans
fenêtre.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.enumerations import (
    StatutDisponibilite,
    StatutPerformance,
)
from moniteur.domaine.formatage import formater_duree
from moniteur.domaine.registre_sites import RegistreSites
from moniteur.domaine.site import Site

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
    """Présentateur du dashboard passif (ENF-05, EF-02.1, EF-02.3).

    INVARIANT : le registre, la configuration, l'horloge et la fonction
    d'affichage reçus à la création ne sont jamais remplacés ; le
    présentateur ne modifie jamais le registre (vue passive).
    """

    def __init__(
        self,
        registre: RegistreSites,
        afficher: Callable[[tuple[LigneDashboard, ...]], None],
        config: ConfigurationTests,
        horloge: Callable[[], datetime],
    ) -> None:
        """Crée le présentateur, s'abonne au registre et affiche l'état.

        afficher est la méthode de la vue qui reçoit les lignes à
        montrer. Elle peut être appelée depuis n'importe quel fil
        d'exécution : c'est à la vue de s'en protéger.

        PRE : aucune.
        POST : le présentateur est abonné au registre : afficher est
               appelée à chaque changement d'état (EF-02.3). Elle est
               aussi appelée une première fois, avec l'état actuel.
        """
        self.__registre = registre
        self.__afficher = afficher
        self.__config = config
        self.__horloge = horloge
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
            return "-"
        texte = batterie.horodatage.strftime(FORMAT_HORODATAGE)
        if site.statut_est_ancien(self.__config, self.__horloge):
            texte += MARQUE_ANCIEN
        return texte


if __name__ == "__main__":
    from datetime import timedelta

    from moniteur.domaine.enumerations import Couche, Declenchement, Verdict
    from moniteur.domaine.mesure import Mesure
    from moniteur.domaine.testeur import Testeur

    INSTANT = datetime(2026, 10, 17, 14, 30)
    CONFIG = ConfigurationTests(5.0)

    class FauxTesteur(Testeur):
        """Testeur de test : renvoie une mesure L7 au verdict fixé."""

        def __init__(self, verdict: Verdict) -> None:
            """Mémorise le verdict que renverront toutes les mesures."""
            self.__verdict = verdict

        @property
        def couche(self) -> Couche:
            """Donne la couche simulée (L7)."""
            return Couche.L7

        def executer(
            self, site: Site, timeout_s: float, horodatage: datetime
        ) -> list[Mesure]:
            """Renvoie une mesure par page du site, sans réseau."""
            return [
                Mesure(horodatage, Couche.L7, self.__verdict, 0.05, "200",
                       page)
                for page in site.pages
            ]

    maintenant = [INSTANT]
    recu: list[tuple[LigneDashboard, ...]] = []
    registre = RegistreSites()
    presentateur = PresentateurDashboard(
        registre, recu.append, CONFIG, lambda: maintenant[0]
    )

    def tester(nom: str, verdict: Verdict) -> None:
        """Lance sur le site une batterie au verdict choisi."""
        registre.trouver_site(nom).lancer_batterie(
            [FauxTesteur(verdict)], CONFIG, Declenchement.PERIODIQUE,
            lambda: INSTANT,
        )

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

    tester("Alpha", Verdict.OK)
    verifier("un site disponible est en vert",
             (VERT, "DISPONIBLE"),
             (recu[-1][0].couleur, recu[-1][0].cellules[1]))

    maintenant[0] = INSTANT + timedelta(hours=2)
    appels = len(recu)
    presentateur.rafraichir()
    verifier("le temps qui passe : sans changement du registre, un "
             "rafraîchissement ajoute « (ancien) »",
             (appels + 1, "17/10/2026 14:30:00 (ancien)"),
             (len(recu), recu[-1][0].cellules[4]))
