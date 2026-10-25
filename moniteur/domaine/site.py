"""Site : site web surveillé, avec l'historique de ses batteries."""

from collections.abc import Callable
from datetime import datetime

from moniteur.domaine.batterie_tests import BatterieTests
from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.enumerations import (
    Couche,
    StatutDisponibilite,
    Verdict,
)
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
                "L'URI principale du site ne peut pas être vide."
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
               dernière batterie n'a aucune mesure, INDISPONIBLE si une
               mesure L4 ou L7 de la dernière batterie est KO, et
               DISPONIBLE sinon. Une mesure L3 KO ne rend le site
               indisponible que si la batterie n'a aucune mesure L4 ou
               L7 : une mesure d'une de ces couches (forcément OK à ce
               stade) la compense, l'ICMP étant souvent bloqué (RM-06,
               Q-02). Ne modifie rien.
        """
        batterie = self.derniere_batterie
        if batterie is None or len(batterie.mesures) == 0:
            return StatutDisponibilite.INCONNU
        echec_l3 = False
        mesure_l4_ou_l7 = False
        for mesure in batterie.mesures:
            if mesure.couche == Couche.L3:
                echec_l3 = echec_l3 or mesure.verdict == Verdict.KO
            elif mesure.verdict == Verdict.KO:
                return StatutDisponibilite.INDISPONIBLE
            else:
                mesure_l4_ou_l7 = True
        if echec_l3 and not mesure_l4_ou_l7:
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
               par horloge (appelée une fois). Les testeurs sont
               exécutés dans l'ordre des couches L3, L4, L7 (à couche
               égale, dans l'ordre reçu) et leurs mesures sont ajoutées
               à la batterie dans cet ordre. Dès que la batterie est
               interrompue (mesure KO en L4, EF-03.2), les testeurs
               restants ne sont pas exécutés. La batterie est ajoutée à
               la fin de l'historique du site : elle devient sa
               dernière batterie. Ne modifie ni testeurs ni config.
               Exception ValueError : si testeurs est vide.
               Si une exception est levée, l'historique n'est pas
               modifié.
        """
        if len(testeurs) == 0:
            raise ValueError(
                "Une batterie de tests demande au moins un testeur."
            )
        batterie = BatterieTests(horloge())
        for testeur in self.__trier_par_couche(testeurs):
            if batterie.interrompue:
                break
            mesures = testeur.executer(
                self, config.timeout_s, batterie.horodatage
            )
            batterie.ajouter(mesures)
        self.__historique.append(batterie)
        return batterie

    def __trier_par_couche(self, testeurs: list[Testeur]) -> list[Testeur]:
        """Renvoie les testeurs dans l'ordre des couches L3, L4, L7.

        À couche égale, l'ordre reçu est conservé.
        """
        tries: list[Testeur] = []
        for couche in Couche:
            for testeur in testeurs:
                if testeur.couche == couche:
                    tries.append(testeur)
        return tries


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

        def __init__(
            self,
            verdict: Verdict,
            diagnostic: str,
            couche: Couche = Couche.L7,
        ) -> None:
            """Mémorise le verdict, le diagnostic et la couche simulée."""
            self.__verdict = verdict
            self.__diagnostic = diagnostic
            self.__couche = couche
            self.delais_recus: list[float] = []

        @property
        def couche(self) -> Couche:
            """Donne la couche simulée."""
            return self.__couche

        def executer(
            self, site: Site, timeout_s: float, horodatage: datetime
        ) -> list[Mesure]:
            """Renvoie une seule mesure, datée de l'horodatage reçu."""
            self.delais_recus.append(timeout_s)
            return [Mesure(horodatage, self.couche, self.__verdict, 0.1,
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

        @property
        def couche(self) -> Couche:
            """Donne la couche simulée (L7)."""
            return Couche.L7

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

    print("Scénario : les testeurs sont exécutés dans l'ordre L3, L4, L7 "
          "(EF-03.2)")
    site_ordre = Site("ClientABC", "clientabc.be")
    batterie_ordre = site_ordre.lancer_batterie(
        [
            FauxTesteur(Verdict.OK, "200", Couche.L7),
            FauxTesteur(Verdict.OK, "6/6", Couche.L3),
            FauxTesteur(Verdict.OK, "443", Couche.L4),
        ],
        CONFIG,
        fausse_horloge,
    )
    attendu = [Couche.L3, Couche.L4, Couche.L7]
    obtenu = [mesure.couche for mesure in batterie_ordre.mesures]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : un échec en L4 arrête la batterie : pas de mesure "
          "L7 (EF-03.2)")
    site_l4 = Site("ClientABC", "clientabc.be")
    batterie_l4 = site_l4.lancer_batterie(
        [
            FauxTesteur(Verdict.OK, "6/6", Couche.L3),
            FauxTesteur(Verdict.KO, "port fermé", Couche.L4),
            FauxTesteur(Verdict.OK, "200", Couche.L7),
        ],
        CONFIG,
        fausse_horloge,
    )
    attendu = [Couche.L3, Couche.L4]
    obtenu = [mesure.couche for mesure in batterie_l4.mesures]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : échec en L4 : statut INDISPONIBLE (RM-06)")
    attendu = StatutDisponibilite.INDISPONIBLE
    obtenu = site_l4.statut_disponibilite
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : échec en L3 compensé par L4 et L7 : DISPONIBLE "
          "(Q-02, RM-06)")
    site_icmp_bloque = Site("ClientABC", "clientabc.be")
    site_icmp_bloque.lancer_batterie(
        [
            FauxTesteur(Verdict.KO, "0/6", Couche.L3),
            FauxTesteur(Verdict.OK, "443", Couche.L4),
            FauxTesteur(Verdict.OK, "200", Couche.L7),
        ],
        CONFIG,
        fausse_horloge,
    )
    attendu = StatutDisponibilite.DISPONIBLE
    obtenu = site_icmp_bloque.statut_disponibilite
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : échec en L3 sans aucune mesure L4 ou L7 : "
          "INDISPONIBLE (RM-06)")
    site_l3_seul = Site("ClientABC", "clientabc.be")
    site_l3_seul.lancer_batterie(
        [FauxTesteur(Verdict.KO, "0/6", Couche.L3)], CONFIG, fausse_horloge
    )
    attendu = StatutDisponibilite.INDISPONIBLE
    obtenu = site_l3_seul.statut_disponibilite
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
