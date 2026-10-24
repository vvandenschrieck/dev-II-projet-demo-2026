"""Site : site web surveillé, avec l'historique de ses batteries."""

from collections.abc import Callable
from datetime import datetime

from moniteur.domaine.batterie_tests import BatterieTests
from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.enumerations import StatutDisponibilite, Verdict
from moniteur.domaine.testeur import Testeur

SCHEMA_PAR_DEFAUT = "https://"


class Site:
    """Site web de la cliente, identifié par son nom.

    Un site est défini par un nom et une URI principale (EF-01.1). Il
    conserve l'historique des batteries de tests lancées sur lui.

    INVARIANT :
    - le nom et l'URI principale ne sont jamais vides, sans
    espace au début ni à la fin, et ne changent jamais ;
    - l'URI principale porte toujours un schéma ;
    - l'historique contient les batteries dans l'ordre de
      leur lancement.
    """

    def __init__(self, nom: str, uri_principale: str) -> None:
        """Crée un site à partir de son nom et de son URI principale.

        PRE : aucune.
        POST : le site est créé, sans aucune batterie. Les espaces au
               début et à la fin de nom et de uri_principale sont
               retirés. Une URI sans schéma (« exemple.be ») reçoit
               « https:// » par défaut.
               Exception ValueError : si le nom est vide.
               Exception ValueError : si l'URI principale est vide
               (EF-01.3).
        """
        nom = nom.strip()
        uri_principale = uri_principale.strip()
        if nom == "":
            raise ValueError("Le nom du site ne peut pas être vide.")
        if uri_principale == "":
            raise ValueError(
                "L'URI principale du site ne peut pas être vide (EF-01.3)."
            )
        if "://" not in uri_principale:
            uri_principale = SCHEMA_PAR_DEFAUT + uri_principale
        self.__nom = nom
        self.__uri_principale = uri_principale
        self.__historique: list[BatterieTests] = []

    @property
    def nom(self) -> str:
        """Donne le nom du site.

        PRE : aucune.
        POST : renvoie le nom du site, tel qu'il a été saisi (sans les
               espaces de début et de fin). Ne modifie rien.
        """
        return self.__nom

    @property
    def uri_principale(self) -> str:
        """Donne l'URI principale du site.

        PRE : aucune.
        POST : renvoie l'URI principale, avec son schéma. Ne modifie
               rien.
        """
        return self.__uri_principale

    @property
    def derniere_batterie(self) -> BatterieTests | None:
        """Donne la dernière batterie lancée sur le site (EF-02.2).

        PRE : aucune.
        POST : renvoie la dernière batterie lancée, ou None si le site
               n'a jamais été testé. Ne modifie rien.
        """
        if len(self.__historique) == 0:
            return None
        return self.__historique[-1]

    @property
    def statut_disponibilite(self) -> StatutDisponibilite:
        """Calcule le statut de disponibilité sur la dernière batterie.

        Le statut n'est pas enregistré : il est recalculé à chaque
        lecture (RM-03, page MVP section 3.2).

        PRE : aucune.
        POST : renvoie INCONNU si le site n'a jamais été testé ou si sa
               dernière batterie n'a aucune mesure, DISPONIBLE si toutes
               les mesures de la dernière batterie sont OK,
               INDISPONIBLE si l'une d'elles est KO. Ne modifie rien.
        """
        batterie = self.derniere_batterie
        if batterie is None or len(batterie.mesures) == 0:
            return StatutDisponibilite.INCONNU
        for mesure in batterie.mesures:
            if mesure.verdict == Verdict.KO:
                return StatutDisponibilite.INDISPONIBLE
        return StatutDisponibilite.DISPONIBLE

    def lancer_batterie(
        self,
        testeurs: list[Testeur],
        config: ConfigurationTests,
        horloge: Callable[[], datetime],
    ) -> BatterieTests:
        """Lance une batterie de tests sur le site et la renvoie (EF-03.1).

        config donne le délai maximal d'attente (EF-03.5) ; horloge
        fournit l'horodatage de la batterie.

        PRE : config.timeout_s > 0 (précondition de Testeur.executer).
        POST : renvoie la nouvelle batterie, datée de l'instant donné
               par horloge (appelée une fois). Chaque testeur est
               exécuté à son tour, et ses mesures sont ajoutées à la
               batterie dans cet ordre. La batterie est ajoutée à la
               fin de l'historique du site : elle devient sa dernière
               batterie. Ne modifie ni testeurs ni config.
               Exception ValueError : si testeurs est vide.
               Si une exception est levée, l'historique n'est pas
               modifié.
        """
        if len(testeurs) == 0:
            raise ValueError(
                "Une batterie de tests demande au moins un testeur."
            )
        batterie = BatterieTests(horloge())
        for testeur in testeurs:
            mesures = testeur.executer(
                self, config.timeout_s, batterie.horodatage
            )
            batterie.ajouter(mesures)
        self.__historique.append(batterie)
        return batterie


if __name__ == "__main__":
    from moniteur.domaine.mesure import Mesure

    INSTANT = datetime(2026, 10, 17, 14, 30)
    CONFIG = ConfigurationTests(5.0)

    def fausse_horloge() -> datetime:
        """Horloge de test : renvoie toujours le même instant."""
        return INSTANT

    class FauxTesteur(Testeur):
        """Testeur de test : renvoie une mesure fixée, sans réseau.

        L'attribut public delais_recus garde le délai reçu à chaque
        appel, pour vérifier ce que le site transmet au testeur.
        """

        def __init__(self, verdict: Verdict, diagnostic: str) -> None:
            """Mémorise le verdict et le diagnostic à renvoyer."""
            self.__verdict = verdict
            self.__diagnostic = diagnostic
            self.delais_recus: list[float] = []

        def executer(
            self, site: Site, timeout_s: float, horodatage: datetime
        ) -> list[Mesure]:
            """Renvoie une seule mesure, datée de l'horodatage reçu."""
            self.delais_recus.append(timeout_s)
            return [Mesure(horodatage, self.__verdict, 0.1,
                           self.__diagnostic)]

    print("Scénario : URI sans schéma : « https:// » ajouté par défaut")
    attendu = "https://clientabc.be"
    obtenu = Site("ClientABC", "clientabc.be").uri_principale
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : nom vide")
    attendu = "ValueError"
    try:
        Site("", "https://clientabc.be")
        obtenu = "aucune erreur"
    except ValueError:
        obtenu = "ValueError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : URI principale vide (critère 3, EF-01.3)")
    attendu = "ValueError"
    try:
        Site("ClientABC", "")
        obtenu = "aucune erreur"
    except ValueError:
        obtenu = "ValueError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : site neuf : statut INCONNU (critère 1)")
    attendu = StatutDisponibilite.INCONNU
    obtenu = Site("ClientABC", "clientabc.be").statut_disponibilite
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    class TesteurVide(Testeur):
        """Testeur de test : ne renvoie aucune mesure, sans réseau."""

        def executer(
            self, site: Site, timeout_s: float, horodatage: datetime
        ) -> list[Mesure]:
            """Renvoie une liste vide."""
            return []

    print("Scénario : batterie sans aucune mesure : statut INCONNU")
    site_vide = Site("ClientABC", "clientabc.be")
    site_vide.lancer_batterie([TesteurVide()], CONFIG, fausse_horloge)
    attendu = StatutDisponibilite.INCONNU
    obtenu = site_vide.statut_disponibilite
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : test d'un site qui répond 200 : DISPONIBLE "
          "(critère 4)")
    site_200 = Site("ClientABC", "clientabc.be")
    site_200.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200")], CONFIG, fausse_horloge
    )
    attendu = StatutDisponibilite.DISPONIBLE
    obtenu = site_200.statut_disponibilite
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : la batterie porte l'horodatage de l'horloge "
          "(critère 4)")
    attendu = INSTANT
    obtenu = site_200.derniere_batterie.horodatage
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : test d'un site qui répond 404 : INDISPONIBLE "
          "(critère 6)")
    site_404 = Site("ClientABC", "clientabc.be")
    site_404.lancer_batterie(
        [FauxTesteur(Verdict.KO, "404")], CONFIG, fausse_horloge
    )
    attendu = StatutDisponibilite.INDISPONIBLE
    obtenu = site_404.statut_disponibilite
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : batterie KO puis batterie OK : le statut suit la "
          "dernière batterie")
    site_retabli = Site("ClientABC", "clientabc.be")
    site_retabli.lancer_batterie(
        [FauxTesteur(Verdict.KO, "500")], CONFIG, fausse_horloge
    )
    site_retabli.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200")], CONFIG, fausse_horloge
    )
    attendu = StatutDisponibilite.DISPONIBLE
    obtenu = site_retabli.statut_disponibilite
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : une mesure OK et une mesure KO : INDISPONIBLE "
          "(page MVP, section 3.2)")
    site_mixte = Site("ClientABC", "clientabc.be")
    site_mixte.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200"), FauxTesteur(Verdict.KO, "500")],
        CONFIG,
        fausse_horloge,
    )
    attendu = StatutDisponibilite.INDISPONIBLE
    obtenu = site_mixte.statut_disponibilite
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : le testeur reçoit le délai de la configuration "
          "(EF-03.5)")
    testeur_espion = FauxTesteur(Verdict.OK, "200")
    site_espion = Site("ClientABC", "clientabc.be")
    site_espion.lancer_batterie([testeur_espion], CONFIG, fausse_horloge)
    attendu = [5.0]
    obtenu = testeur_espion.delais_recus
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : lancer une batterie sans testeur")
    attendu = "ValueError"
    try:
        Site("ClientABC", "clientabc.be").lancer_batterie(
            [], CONFIG, fausse_horloge
        )
        obtenu = "aucune erreur"
    except ValueError:
        obtenu = "ValueError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
