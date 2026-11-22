"""Présentateur de l'interface simple : prépare l'affichage et agit.

Le présentateur s'abonne au registre (patron Observer). À chaque
changement, il relit les sites et donne à la vue un bloc par site : une
ligne pour le site et une ligne par page, avec les textes de chaque
colonne et une couleur (EF-02.1, EF-02.4). Il reçoit aussi les demandes
de la vue (ajouter ou modifier un site, ajouter ou supprimer une page,
lancer des tests), les exécute sur le domaine et explique à la vue ce
qui s'est passé par un message. La vue ne contient donc aucune règle
d'affichage ni aucun appel au domaine : elle lit les saisies, montre ce
que le présentateur lui donne et ne connaît ni le registre ni les
règles de couleur. Ce module n'importe ni print ni input, ce qui permet
de le vérifier sans terminal.
"""

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
# Couleur d'une page qui n'a jamais été testée.
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
class LigneSimple:
    """Ligne de l'écran : un site ou une page, prêt à être affiché.

    cellules contient un texte par colonne ; couleur vaut VERT, ORANGE,
    ROUGE, JAUNE ou AUCUNE (EF-02.4).

    INVARIANT : les deux champs ne changent jamais après la création
    (classe figée).
    """

    cellules: tuple[str, ...]
    couleur: str


@dataclass(frozen=True)
class BlocSite:
    """Bloc de l'écran : la ligne d'un site, puis celles de ses pages.

    site a six cellules (nom, disponibilité, performance, RTT, dernier
    test, diagnostics L3 et L4) ; chaque ligne de pages a cinq cellules
    (nom, verdict, chargement, diagnostic, URI), la page principale en
    premier.

    INVARIANT : les deux champs ne changent jamais après la création
    (classe figée).
    """

    site: LigneSimple
    pages: tuple[LigneSimple, ...]


class PresentateurSimple:
    """Présentateur de l'interface simple (EF-02.1, EF-02.3, EF-03.1).

    INVARIANT : le registre, les testeurs, la configuration, l'horloge
    et les fonctions d'affichage reçus à la création ne sont jamais
    remplacés ; les testeurs sont lancés dans le fil d'exécution de
    l'appelant, l'un après l'autre.
    """

    def __init__(
        self,
        registre: RegistreSites,
        testeurs: list[Testeur],
        config: ConfigurationTests,
        horloge: Callable[[], datetime],
        afficher: Callable[[tuple[BlocSite, ...]], None],
        afficher_message: Callable[[str], None],
    ) -> None:
        """Crée le présentateur et l'abonne au registre.

        afficher et afficher_message sont les fonctions de la vue qui
        reçoivent les blocs et les messages à montrer. Elles peuvent
        être appelées depuis n'importe quel fil d'exécution : c'est à
        la vue de s'en protéger.

        PRE : aucune.
        POST : le présentateur est abonné au registre : afficher est
               appelée à chaque changement d'état (EF-02.3). Rien n'est
               affiché à la création : la vue demande l'état avec blocs.
        """
        self.__registre = registre
        self.__testeurs = testeurs
        self.__config = config
        self.__horloge = horloge
        self.__afficher = afficher
        self.__afficher_message = afficher_message
        registre.abonner(self.rafraichir)

    def blocs(self) -> tuple[BlocSite, ...]:
        """Prépare un bloc par site, dans l'ordre du registre (EF-02.1).

        PRE : aucune.
        POST : renvoie un tuple d'un bloc par site du registre. La
               couleur de chaque ligne met en évidence les sites
               indisponibles, jamais testés ou aux performances
               dégradées, et les pages en erreur ou lentes (EF-02.4).
               Ne modifie rien.
        """
        return tuple(
            BlocSite(
                self.__ligne_site(site),
                tuple(self.__ligne_page(site, p) for p in site.pages),
            )
            for site in self.__registre.sites
        )

    def rafraichir(self) -> None:
        """Donne l'état actuel des sites à la vue (EF-02.3).

        Appelée par le registre à chaque changement.

        PRE : aucune.
        POST : afficher est appelée une fois, avec le résultat de blocs.
               Ne modifie ni le registre ni ses sites.
        """
        self.__afficher(self.blocs())

    def verifier_site(self, nom: str) -> bool:
        """Dit si un site porte ce nom, et le refuse à la vue sinon.

        PRE : aucune.
        POST : renvoie True si un site porte ce nom (casse et espaces de
               bord ignorés). Sinon envoie à la vue « Refus : » suivi du
               motif et renvoie False. Ne modifie ni le registre ni ses
               sites.
        """
        try:
            self.__registre.trouver_site(nom)
        except ValueError as erreur:
            self.__afficher_message(f"Refus : {erreur}")
            return False
        return True

    def decrire_site(self, nom: str) -> str:
        """Décrit le nom et l'URI principale actuels d'un site.

        PRE : aucune.
        POST : renvoie une phrase qui donne le nom et l'URI principale
               du site qui porte ce nom. Ne modifie rien.
               Exception ValueError : si aucun site ne porte ce nom.
        """
        site = self.__registre.trouver_site(nom)
        return (f"Nom actuel : {site.nom} — "
                f"URI principale actuelle : {site.uri_principale}")

    def ajouter_site(self, nom: str, uri_principale: str) -> None:
        """Ajoute un site au registre (EF-01.1).

        PRE : aucune.
        POST : si le domaine accepte le nom et l'URI, le site est ajouté
               au registre et une confirmation est envoyée à la vue.
               Sinon (nom déjà utilisé, nom ou URI vide, EF-01.2 et
               EF-01.3), « Refus : » suivi du motif est envoyé à la vue
               et le registre n'est pas modifié.
        """
        try:
            site = self.__registre.ajouter_site(nom, uri_principale)
        except ValueError as erreur:
            self.__afficher_message(f"Refus : {erreur}")
            return
        self.__afficher_message(f"Site « {site.nom} » ajouté.")

    def modifier_site(
        self, nom: str, nouveau_nom: str, nouvelle_uri: str
    ) -> None:
        """Change le nom et l'URI principale d'un site (EF-01.2).

        PRE : aucune.
        POST : si le domaine accepte la modification, le site a son
               nouveau nom et sa nouvelle URI et une confirmation est
               envoyée à la vue. Sinon (site inconnu, nom déjà utilisé,
               nom ou URI vide, EF-01.2 et EF-01.3, URI déjà portée par
               une autre page du site, EF-01.6), « Refus : » suivi du
               motif est envoyé à la vue et le site n'est pas modifié.
        """
        try:
            self.__registre.modifier_site(nom, nouveau_nom, nouvelle_uri)
            site = self.__registre.trouver_site(nouveau_nom)
        except ValueError as erreur:
            self.__afficher_message(f"Refus : {erreur}")
            return
        self.__afficher_message(f"Site « {site.nom} » modifié.")

    def ajouter_page(self, nom_site: str, nom: str, uri: str) -> None:
        """Ajoute une page à un site (EF-01.4).

        PRE : aucune.
        POST : si le domaine l'accepte, la page est ajoutée au site et
               une confirmation est envoyée à la vue. Sinon (site
               inconnu, nom de page déjà utilisé, EF-01.4, URI déjà
               utilisée, EF-01.6, nom ou URI vide), « Refus : » suivi du
               motif est envoyé à la vue et le site n'est pas modifié.
        """
        try:
            site = self.__registre.trouver_site(nom_site)
            page = site.ajouter_page(nom, uri)
        except ValueError as erreur:
            self.__afficher_message(f"Refus : {erreur}")
            return
        self.__afficher_message(f"Page « {page.nom} » ajoutée.")

    def supprimer_page(self, nom_site: str, nom: str) -> None:
        """Retire une page d'un site (EF-01.5).

        PRE : aucune.
        POST : si le domaine l'accepte, la page est retirée du site (ses
               mesures restent dans l'historique) et une confirmation
               est envoyée à la vue. Sinon (site inconnu, page
               inexistante, page principale), « Refus : » suivi du
               motif est envoyé à la vue et le site n'est pas modifié.
        """
        try:
            site = self.__registre.trouver_site(nom_site)
            site.supprimer_page(nom)
        except ValueError as erreur:
            self.__afficher_message(f"Refus : {erreur}")
            return
        self.__afficher_message(
            f"Page « {nom.strip()} » supprimée "
            "(ses mesures restent dans l'historique)."
        )

    def tester_site(self, nom: str) -> None:
        """Lance une batterie de tests sur un site (EF-03.1).

        PRE : aucune.
        POST : si un site porte ce nom, envoie un message à la vue puis
               lance sur lui une batterie manuelle, qui rejoint son
               historique. Sinon envoie « Refus : » suivi du motif à la
               vue et ne teste rien.
               Exception ValueError : si testeurs est vide et que le
               site existe.
        """
        try:
            site = self.__registre.trouver_site(nom)
        except ValueError as erreur:
            self.__afficher_message(f"Refus : {erreur}")
            return
        self.__tester(site, Declenchement.MANUEL, "Test")

    def tester_tous(self) -> None:
        """Lance une batterie de tests sur chaque site (EF-03.4).

        PRE : aucune.
        POST : pour chaque site du registre, dans l'ordre, envoie un
               message à la vue puis lance une batterie manuelle, qui
               rejoint l'historique du site. Ne fait rien si le registre
               est vide.
               Exception ValueError : si testeurs est vide et que le
               registre contient au moins un site.
        """
        for site in self.__registre.sites:
            self.__tester(site, Declenchement.MANUEL, "Test")

    def tester_echeances(self, frequence_min: int) -> int:
        """Teste les sites dont l'échéance est atteinte (EF-03.7).

        PRE : aucune.
        POST : pour chaque site du registre qui n'a jamais été testé ou
               dont le dernier test date d'au moins frequence_min
               minutes, envoie un message à la vue puis lance une
               batterie périodique, qui rejoint l'historique du site.
               Renvoie le nombre de sites testés.
               Exception ValueError : si testeurs est vide et qu'un site
               est testé.
        """
        nombre = 0
        for site in self.__registre.sites:
            if site.est_a_tester(frequence_min, self.__horloge):
                self.__tester(site, Declenchement.PERIODIQUE,
                              "Test automatique")
                nombre += 1
        return nombre

    def __tester(
        self, site: Site, declenchement: Declenchement, debut: str
    ) -> None:
        """Annonce le test d'un site à la vue, puis lance sa batterie."""
        self.__afficher_message(f"{debut} de « {site.nom} » en cours...")
        site.lancer_batterie(
            self.__testeurs, self.__config, declenchement, self.__horloge
        )

    def __ligne_site(self, site: Site) -> LigneSimple:
        """Prépare la ligne d'un site : textes et couleur (EF-02.4).

        La couleur suit le statut de disponibilité, mais passe au jaune
        pour un site disponible aux performances dégradées. L'horodatage
        est suivi de « (ancien) » si les statuts datent de trop
        longtemps. Horodatage et diagnostic valent « - » si le site n'a
        jamais été testé. Les diagnostics sont ceux des mesures L3 et
        L4, précédés de leur couche (« L3: 6/6 sondes »).
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
            site.nom, statut.name, performance.name, rtt, horodatage,
            diagnostic,
        )
        return LigneSimple(cellules, couleur)

    def __ligne_page(self, site: Site, page: Page) -> LigneSimple:
        """Prépare la ligne d'une page : textes et couleur (EF-02.1).

        Le verdict et le diagnostic sont ceux de la dernière mesure de
        la page, « - » si elle n'a jamais été testée. Le chargement est
        la moyenne de la page avec son écart par rapport à sa moyenne
        globale.
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
        cellules = (page.nom, verdict, chargement, diagnostic, page.uri)
        return LigneSimple(
            cellules, self.__couleur_page(derniere, chargement_s)
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
    INSTANT = datetime(2026, 10, 17, 14, 30)
    CONFIG = ConfigurationTests(5.0)

    class FauxTesteur(Testeur):
        """Testeur de test : une mesure L7 au verdict fixé, sans réseau."""

        def __init__(self, verdict: Verdict, duree_s: float = 0.05) -> None:
            """Mémorise le verdict et la durée renvoyés."""
            self.__verdict = verdict
            self.__duree_s = duree_s

        @property
        def couche(self) -> Couche:
            """Donne la couche simulée (L7)."""
            return Couche.L7

        def executer(
            self, site: Site, timeout_s: float, horodatage: datetime
        ) -> list[Mesure]:
            """Renvoie une mesure par page du site."""
            return [
                Mesure(horodatage, Couche.L7, self.__verdict,
                       self.__duree_s, "200", page)
                for page in site.pages
            ]

    maintenant = [INSTANT]
    recu: list[tuple[BlocSite, ...]] = []
    messages: list[str] = []
    registre = RegistreSites()
    presentateur = PresentateurSimple(
        registre, [FauxTesteur(Verdict.OK)], CONFIG,
        lambda: maintenant[0], recu.append, messages.append,
    )

    def verifier(description: str, attendu: object, obtenu: object) -> None:
        """Affiche un scénario au format du cours."""
        print(f"Scénario : {description}")
        print(f"  attendu : {attendu}")
        print(f"  obtenu  : {obtenu}")
        print("  → OK" if obtenu == attendu else "  → ÉCHEC")
        print("-" * 40)

    presentateur.ajouter_site("Alpha", "alpha.be")
    bloc = recu[-1][0]
    verifier("l'ajout d'un site (EF-01.1) rafraîchit la vue sans action "
             "de l'utilisatrice (EF-02.3) : site jamais testé, en jaune, "
             "avec sa page principale sans couleur (EF-02.4)",
             (JAUNE, ("Alpha", "INCONNU", "INCONNU", "-", "-", "-"),
              AUCUNE, ["Site « Alpha » ajouté."]),
             (bloc.site.couleur, bloc.site.cellules,
              bloc.pages[0].couleur, messages))

    messages.clear()
    appels = len(recu)
    presentateur.ajouter_site("alpha", "autre.be")
    verifier("ajout d'un site au nom déjà utilisé (EF-01.2) : un refus "
             "pour la vue, et le registre n'est pas modifié",
             ([("Refus : Un site nommé « Alpha » existe déjà.")],
              appels, 1),
             (messages, len(recu), len(registre.sites)))

    messages.clear()
    presentateur.tester_site("Alpha")
    bloc = recu[-1][0]
    verifier("tester un site (EF-03.1) : message d'annonce, puis site "
             "disponible en vert, daté de l'horloge, page OK en vert",
             (["Test de « Alpha » en cours..."], VERT, "DISPONIBLE",
              "17/10/2026 14:30:00", VERT),
             (messages, bloc.site.couleur, bloc.site.cellules[1],
              bloc.site.cellules[4], bloc.pages[0].couleur))

    messages.clear()
    presentateur.tester_site("Inconnu")
    verifier("tester un site inconnu : un refus, aucun test",
             ["Refus : Aucun site nommé « Inconnu »."], messages)

    registre.ajouter_site("Beta", "beta.be")
    maintenant[0] = INSTANT.replace(minute=40)
    messages.clear()
    nombre = presentateur.tester_echeances(15)
    verifier("tests automatiques (EF-03.7) : seul Beta, jamais testé, est "
             "testé ; Alpha date de 10 minutes, sous la fréquence de 15",
             (1, ["Test automatique de « Beta » en cours..."]),
             (nombre, messages))

    maintenant[0] = INSTANT.replace(hour=18)
    verifier("le temps qui passe : la ligne d'un site dont le test est "
             "trop ancien porte « (ancien) » (EF-02.2)",
             "17/10/2026 14:30:00 (ancien)",
             presentateur.blocs()[0].site.cellules[4])

    presentateur_ko = PresentateurSimple(
        registre, [FauxTesteur(Verdict.KO)], CONFIG,
        lambda: INSTANT, recu.append, messages.append,
    )
    presentateur_ko.tester_site("Beta")
    bloc = presentateur.blocs()[1]
    verifier("site dont la page répond en erreur : site indisponible en "
             "rouge, page KO en rouge (EF-02.4)",
             (ROUGE, "INDISPONIBLE", ROUGE),
             (bloc.site.couleur, bloc.site.cellules[1],
              bloc.pages[0].couleur))

    presentateur.ajouter_page("Beta", "Contact", "beta.be/contact")
    presentateur.supprimer_page("Beta", "Page d'accueil")
    verifier("la page principale ne peut pas être supprimée (EF-01.5) : "
             "un refus, et la page ajoutée (EF-01.4) est conservée",
             ("Refus : La page principale ne peut pas être supprimée.", 2),
             (messages[-1], len(presentateur.blocs()[1].pages)))
