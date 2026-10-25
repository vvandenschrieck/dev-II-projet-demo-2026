"""Site : site web surveillé, avec l'historique de ses batteries."""

from collections.abc import Callable
from datetime import datetime, timedelta

from moniteur.domaine.batterie_tests import BatterieTests
from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.enumerations import (
    Couche,
    Declenchement,
    StatutDisponibilite,
    StatutPerformance,
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

    def statut_performance(
        self, config: ConfigurationTests
    ) -> StatutPerformance:
        """Calcule le statut de performance sur les dernières batteries.

        Les batteries prises en compte sont celles des
        config.fenetre_performance_min minutes qui précèdent la
        dernière batterie (celle-ci comprise). Le RTT d'une batterie est
        la durée de sa mesure L3 ou, à défaut, de sa mesure L4. Le site
        n'a pour l'instant qu'une page, l'URI principale (RM-08).

        PRE : aucune.
        POST : renvoie DEGRADEES si le RTT moyen dépasse config.seuil_l3_s
               ou si le temps de chargement moyen (mesures L7) dépasse
               config.seuil_l7_s. Sinon renvoie NORMALES si l'une de ces
               deux moyennes a pu être calculée, et INCONNU si aucune
               mesure n'a de durée. Ne modifie rien.
        """
        rtt_moyen_s = self.rtt_moyen(config)
        chargement_moyen_s = self.chargement_moyen(config)
        if rtt_moyen_s is None and chargement_moyen_s is None:
            return StatutPerformance.INCONNU
        if rtt_moyen_s is not None and rtt_moyen_s > config.seuil_l3_s:
            return StatutPerformance.DEGRADEES
        if (chargement_moyen_s is not None
                and chargement_moyen_s > config.seuil_l7_s):
            return StatutPerformance.DEGRADEES
        return StatutPerformance.NORMALES

    def rtt_moyen(self, config: ConfigurationTests) -> float | None:
        """Donne le RTT moyen des batteries de la dernière fenêtre.

        Le RTT d'une batterie est la durée de sa mesure L3 ou, à défaut,
        de sa mesure L4. La fenêtre est celle de statut_performance.

        PRE : aucune.
        POST : renvoie le RTT moyen, en secondes, ou None si aucune
               batterie de la fenêtre n'a de RTT. Ne modifie rien.
        """
        batteries = self.__batteries_recentes(config.fenetre_performance_min)
        return self.__moyenne([self.__rtt(b) for b in batteries])

    def ecart_rtt(self, config: ConfigurationTests) -> float | None:
        """Compare le RTT moyen de la fenêtre à la moyenne globale.

        La moyenne globale porte sur toutes les batteries du site. La
        comparaison n'a de sens que s'il existe des batteries plus
        anciennes que la fenêtre.

        PRE : aucune.
        POST : renvoie l'écart relatif (RTT de la fenêtre - moyenne
               globale) / moyenne globale, par exemple 0.5 pour 50 %
               plus lent. Renvoie None si toutes les batteries du site
               sont dans la fenêtre, si l'une des moyennes est inconnue
               ou si la moyenne globale est nulle. Ne modifie rien.
        """
        if not self.__a_des_batteries_hors_fenetre(config):
            return None
        globale = self.__moyenne([self.__rtt(b) for b in self.__historique])
        return self.__ecart(self.rtt_moyen(config), globale)

    def chargement_moyen(self, config: ConfigurationTests) -> float | None:
        """Donne le temps de chargement moyen de la dernière fenêtre.

        Il s'agit des mesures L7 des batteries de la fenêtre de
        statut_performance.

        PRE : aucune.
        POST : renvoie le temps de chargement moyen, en secondes, ou
               None si aucune mesure L7 de la fenêtre n'a de durée. Ne
               modifie rien.
        """
        batteries = self.__batteries_recentes(config.fenetre_performance_min)
        return self.__moyenne([self.__chargement(b) for b in batteries])

    def ecart_chargement(self, config: ConfigurationTests) -> float | None:
        """Compare le chargement moyen de la fenêtre à la moyenne globale.

        La moyenne globale porte sur toutes les batteries du site. La
        comparaison n'a de sens que s'il existe des batteries plus
        anciennes que la fenêtre.

        PRE : aucune.
        POST : renvoie l'écart relatif (chargement de la fenêtre -
               moyenne globale) / moyenne globale. Renvoie None si
               toutes les batteries du site sont dans la fenêtre, si
               l'une des moyennes est inconnue ou si la moyenne globale
               est nulle. Ne modifie rien.
        """
        if not self.__a_des_batteries_hors_fenetre(config):
            return None
        globale = self.__moyenne(
            [self.__chargement(b) for b in self.__historique]
        )
        return self.__ecart(self.chargement_moyen(config), globale)

    def statut_est_ancien(
        self, config: ConfigurationTests, horloge: Callable[[], datetime]
    ) -> bool:
        """Dit si les statuts du site datent de trop longtemps.

        Les statuts de disponibilité et de performance reposent sur la
        dernière batterie : ils vieillissent avec elle. Le seuil est
        config.age_max_statut_min.

        PRE : aucune.
        POST : renvoie True si la dernière batterie date de strictement
               plus de config.age_max_statut_min minutes avant l'instant
               donné par horloge (appelée une fois). Renvoie False si
               elle est plus récente, ou si le site n'a jamais été testé
               (son statut est alors INCONNU). Ne modifie rien.
        """
        derniere = self.derniere_batterie
        if derniere is None:
            return False
        age = horloge() - derniere.horodatage
        return age > timedelta(minutes=config.age_max_statut_min)

    def lancer_batterie(
        self,
        testeurs: list[Testeur],
        config: ConfigurationTests,
        declenchement: Declenchement,
        horloge: Callable[[], datetime],
    ) -> BatterieTests:
        """Lance une batterie de tests sur le site et la renvoie (EF-03.1).

        config donne le délai maximal d'attente (EF-03.5) ;
        declenchement dit si la batterie est lancée à la demande ou
        automatiquement (EF-03.7) ; horloge fournit l'horodatage de la
        batterie.

        PRE : config.timeout_s > 0 (précondition de Testeur.executer).
        POST : renvoie la nouvelle batterie, datée de l'instant donné
               par horloge (appelée une fois) et portant le
               déclenchement donné. Les testeurs sont
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
        batterie = BatterieTests(horloge(), declenchement)
        for testeur in self.__trier_par_couche(testeurs):
            if batterie.interrompue:
                break
            mesures = testeur.executer(
                self, config.timeout_s, batterie.horodatage
            )
            batterie.ajouter(mesures)
        self.__historique.append(batterie)
        return batterie

    def __batteries_recentes(self, minutes: int) -> list[BatterieTests]:
        """Renvoie les batteries de la fenêtre qui précède la dernière.

        La fenêtre dure minutes minutes et se termine à l'horodatage de
        la dernière batterie, comprise. Renvoie une liste vide si le site
        n'a jamais été testé.
        """
        derniere = self.derniere_batterie
        if derniere is None:
            return []
        debut = derniere.horodatage - timedelta(minutes=minutes)
        return [b for b in self.__historique if b.horodatage >= debut]

    def __rtt(self, batterie: BatterieTests) -> float | None:
        """Renvoie le RTT d'une batterie, ou None s'il est inconnu.

        C'est la durée de la mesure L3 ; à défaut, celle de la mesure L4.
        """
        for couche in (Couche.L3, Couche.L4):
            for mesure in batterie.mesures:
                if mesure.couche == couche and mesure.duree_s is not None:
                    return mesure.duree_s
        return None

    def __chargement(self, batterie: BatterieTests) -> float | None:
        """Renvoie le temps de chargement d'une batterie, ou None.

        C'est la moyenne des durées des mesures L7 de la batterie.
        """
        return self.__moyenne([
            mesure.duree_s for mesure in batterie.mesures
            if mesure.couche == Couche.L7
        ])

    def __a_des_batteries_hors_fenetre(
        self, config: ConfigurationTests
    ) -> bool:
        """Dit si le site a des batteries plus anciennes que la fenêtre."""
        recentes = self.__batteries_recentes(config.fenetre_performance_min)
        return len(recentes) < len(self.__historique)

    def __ecart(
        self, valeur: float | None, reference: float | None
    ) -> float | None:
        """Renvoie l'écart relatif de valeur par rapport à reference.

        Renvoie None si l'une des deux est inconnue ou si reference est
        nulle.
        """
        if valeur is None or reference is None or reference == 0:
            return None
        return (valeur - reference) / reference

    def __moyenne(self, valeurs: list[float | None]) -> float | None:
        """Renvoie la moyenne des valeurs connues, ou None s'il n'y en a."""
        connues = [valeur for valeur in valeurs if valeur is not None]
        if len(connues) == 0:
            return None
        return sum(connues) / len(connues)

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
    MANUEL = Declenchement.MANUEL

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
            duree_s: float | None = 0.1,
        ) -> None:
            """Mémorise le verdict, le diagnostic, la couche et la durée."""
            self.__verdict = verdict
            self.__diagnostic = diagnostic
            self.__couche = couche
            self.__duree_s = duree_s
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
            return [Mesure(horodatage, self.couche, self.__verdict,
                           self.__duree_s, self.__diagnostic)]

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
    site_vide.lancer_batterie([TesteurVide()], CONFIG, MANUEL, fausse_horloge)
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
        [FauxTesteur(Verdict.OK, "200")], CONFIG, MANUEL, fausse_horloge
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
        [FauxTesteur(Verdict.KO, "404")], CONFIG, MANUEL, fausse_horloge
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
        [FauxTesteur(Verdict.KO, "500")], CONFIG, MANUEL, fausse_horloge
    )
    site_retabli.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200")], CONFIG, MANUEL, fausse_horloge
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
        MANUEL,
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
    site_espion.lancer_batterie(
        [testeur_espion], CONFIG, MANUEL, fausse_horloge
    )
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
        MANUEL,
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
        MANUEL,
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
        MANUEL,
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
        [FauxTesteur(Verdict.KO, "0/6", Couche.L3)],
        CONFIG,
        MANUEL,
        fausse_horloge,
    )
    attendu = StatutDisponibilite.INDISPONIBLE
    obtenu = site_l3_seul.statut_disponibilite
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    def horloge_fixee(instant_donne: datetime) -> Callable[[], datetime]:
        """Fabrique une horloge de test qui renvoie toujours cet instant."""
        return lambda: instant_donne

    def statut_perf(*testeurs: Testeur) -> StatutPerformance:
        """Teste un site neuf avec ces testeurs et renvoie sa performance."""
        site = Site("ClientABC", "clientabc.be")
        site.lancer_batterie(list(testeurs), CONFIG, MANUEL, fausse_horloge)
        return site.statut_performance(CONFIG)

    print("Scénario : RTT L3 supérieur au seuil : DEGRADEES (RM-08)")
    attendu = StatutPerformance.DEGRADEES
    obtenu = statut_perf(FauxTesteur(Verdict.OK, "6/6", Couche.L3, 0.2))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : pas de durée L3 : la durée L4 sert de RTT (RM-08)")
    attendu = StatutPerformance.DEGRADEES
    obtenu = statut_perf(
        FauxTesteur(Verdict.KO, "0/6", Couche.L3, None),
        FauxTesteur(Verdict.OK, "443", Couche.L4, 0.3),
    )
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : chargement L7 supérieur au seuil : DEGRADEES "
          "(RM-08)")
    attendu = StatutPerformance.DEGRADEES
    obtenu = statut_perf(FauxTesteur(Verdict.OK, "200", Couche.L7, 0.8))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : RTT et chargement sous les seuils : NORMALES")
    attendu = StatutPerformance.NORMALES
    obtenu = statut_perf(
        FauxTesteur(Verdict.OK, "6/6", Couche.L3, 0.05),
        FauxTesteur(Verdict.OK, "200", Couche.L7, 0.2),
    )
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : aucune mesure n'a de durée : INCONNU")
    attendu = StatutPerformance.INCONNU
    obtenu = statut_perf(FauxTesteur(Verdict.KO, "0/6", Couche.L3, None))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : une batterie lente de plus de 30 minutes avant la "
          "dernière est ignorée")
    site_fenetre = Site("ClientABC", "clientabc.be")
    site_fenetre.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200", Couche.L7, 0.9)],
        CONFIG,
        MANUEL,
        horloge_fixee(INSTANT - timedelta(minutes=45)),
    )
    site_fenetre.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200", Couche.L7, 0.1)],
        CONFIG,
        MANUEL,
        fausse_horloge,
    )
    attendu = StatutPerformance.NORMALES
    obtenu = site_fenetre.statut_performance(CONFIG)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    site_age = Site("ClientABC", "clientabc.be")

    print("Scénario : site jamais testé : le statut n'est pas ancien")
    attendu = False
    obtenu = site_age.statut_est_ancien(CONFIG, fausse_horloge)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    site_age.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200")],
        CONFIG,
        MANUEL,
        horloge_fixee(INSTANT - timedelta(minutes=30)),
    )
    print("Scénario : dernier test il y a exactement 30 minutes : pas "
          "ancien")
    attendu = False
    obtenu = site_age.statut_est_ancien(CONFIG, fausse_horloge)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    site_age.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200")],
        CONFIG,
        MANUEL,
        horloge_fixee(INSTANT - timedelta(minutes=31)),
    )
    print("Scénario : dernier test il y a 31 minutes : statut ancien")
    attendu = True
    obtenu = site_age.statut_est_ancien(CONFIG, fausse_horloge)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : site jamais testé : ni moyenne ni écart")
    neuf = Site("ClientABC", "clientabc.be")
    attendu = (None, None, None, None)
    obtenu = (neuf.rtt_moyen(CONFIG), neuf.ecart_rtt(CONFIG),
              neuf.chargement_moyen(CONFIG), neuf.ecart_chargement(CONFIG))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    site_ecart = Site("ClientABC", "clientabc.be")
    site_ecart.lancer_batterie(
        [FauxTesteur(Verdict.OK, "6/6", Couche.L3, 0.1),
         FauxTesteur(Verdict.OK, "200", Couche.L7, 0.2)],
        CONFIG,
        MANUEL,
        horloge_fixee(INSTANT - timedelta(minutes=45)),
    )
    site_ecart.lancer_batterie(
        [FauxTesteur(Verdict.OK, "6/6", Couche.L3, 0.3),
         FauxTesteur(Verdict.OK, "200", Couche.L7, 0.6)],
        CONFIG,
        MANUEL,
        fausse_horloge,
    )
    site_recent = Site("ClientABC", "clientabc.be")
    for _ in range(2):
        site_recent.lancer_batterie(
            [FauxTesteur(Verdict.OK, "6/6", Couche.L3, 0.1)],
            CONFIG,
            MANUEL,
            fausse_horloge,
        )
    print("Scénario : toutes les batteries dans la fenêtre : pas "
          "d'écart à comparer")
    attendu = (0.1, None)
    obtenu = (round(site_recent.rtt_moyen(CONFIG), 6),
              site_recent.ecart_rtt(CONFIG))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : les moyennes de la fenêtre ignorent la batterie "
          "vieille de 45 minutes")
    attendu = (0.3, 0.6)
    obtenu = (round(site_ecart.rtt_moyen(CONFIG), 6),
              round(site_ecart.chargement_moyen(CONFIG), 6))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : écart par rapport à la moyenne globale : +50 % "
          "(0,3 contre 0,2 ; 0,6 contre 0,4)")
    attendu = (0.5, 0.5)
    obtenu = (round(site_ecart.ecart_rtt(CONFIG), 6),
              round(site_ecart.ecart_chargement(CONFIG), 6))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : une batterie lancée automatiquement porte le "
          "déclenchement PERIODIQUE (EF-03.7)")
    site_periodique = Site("ClientABC", "clientabc.be")
    batterie_periodique = site_periodique.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200")],
        CONFIG,
        Declenchement.PERIODIQUE,
        fausse_horloge,
    )
    attendu = Declenchement.PERIODIQUE
    obtenu = batterie_periodique.declenchement
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : lancer une batterie sans testeur")
    attendu = "ValueError"
    try:
        Site("ClientABC", "clientabc.be").lancer_batterie(
            [], CONFIG, MANUEL, fausse_horloge
        )
        obtenu = "aucune erreur"
    except ValueError:
        obtenu = "ValueError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
