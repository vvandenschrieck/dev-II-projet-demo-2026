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
from moniteur.domaine.mesure import Mesure
from moniteur.domaine.page import SCHEMA_PAR_DEFAUT, Page
from moniteur.domaine.testeur import Testeur

NOM_PAGE_PRINCIPALE = "Page d'accueil"


class Site:
    """Site web de la cliente, identifié par son nom.

    Un site est défini par un nom et une URI principale (EF-01.1). Il
    possède des pages (la première est la page principale) et conserve
    l'historique des batteries de tests lancées sur lui.

    INVARIANT :
    - le nom et l'URI principale ne sont jamais vides, sans
    espace au début ni à la fin, et ne changent que par modifier ;
    - l'URI principale porte toujours un schéma ;
    - la première page est la page principale : elle s'appelle
      « Page d'accueil », son URI est l'URI principale (EF-01.1) et
      elle ne peut pas être supprimée (EF-01.5) ;
    - deux pages du site n'ont jamais le même nom (casse ignorée,
      EF-01.4) ni la même URI (EF-01.6) ;
    - l'historique contient les batteries dans l'ordre de
      leur lancement.
    """

    def __init__(self, nom: str, uri_principale: str) -> None:
        """Crée un site à partir de son nom et de son URI principale.

        PRE : aucune.
        POST : le site est créé, sans aucune batterie, avec une seule
               page : la page principale (EF-01.1). Les espaces au
               début et à la fin de nom et de uri_principale sont
               retirés. Une URI sans schéma (« exemple.be ») reçoit
               « https:// » par défaut.
               Exception ValueError : si le nom est vide.
               Exception ValueError : si l'URI principale est vide
               (EF-01.3).
        """
        nom, uri_principale = self.__valider(nom, uri_principale)
        self.__nom = nom
        self.__uri_principale = uri_principale
        self.__pages: list[Page] = [
            Page(NOM_PAGE_PRINCIPALE, uri_principale)
        ]
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

    def modifier(self, nouveau_nom: str, nouvelle_uri: str) -> None:
        """Change le nom et l'URI principale du site (EF-01.2, EF-01.3).

        La page principale reste la même page : son URI suit l'URI
        principale, et ses mesures restent dans l'historique. L'unicité
        du nom parmi les sites est garantie par le registre, qui est le
        point d'entrée de la modification.

        PRE : aucune.
        POST : le site porte le nouveau nom et la nouvelle URI
               principale, et l'URI de la page principale est mise à
               jour. Les espaces au début et à la fin sont retirés, et
               une URI sans schéma reçoit « https:// ». Les autres
               pages et les batteries ne changent pas.
               Exception ValueError : si le nom est vide.
               Exception ValueError : si l'URI principale est vide
               (EF-01.3).
               Exception ValueError : si une autre page du site a déjà
               cette URI (EF-01.6).
               Si une exception est levée, le site n'est pas modifié.
        """
        nom, uri = self.__valider(nouveau_nom, nouvelle_uri)
        for page in self.__pages[1:]:
            if page.uri == uri:
                raise ValueError(
                    f"La page « {page.nom} » a déjà l'URI {page.uri}."
                )
        self.__nom = nom
        self.__uri_principale = uri
        self.__pages[0]._changer_uri(uri)

    def __valider(self, nom: str, uri_principale: str) -> tuple[str, str]:
        """Renvoie le nom et l'URI principale nettoyés, ou refuse.

        Retire les espaces de bord et ajoute « https:// » à une URI sans
        schéma. Lève ValueError si le nom ou l'URI est vide.
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
        return nom, uri_principale

    @property
    def pages(self) -> tuple[Page, ...]:
        """Donne les pages du site, la page principale en premier.

        PRE : aucune.
        POST : renvoie un tuple des pages, dans l'ordre de leur ajout
               (copie : le code extérieur ne peut pas modifier la liste
               interne). Ne modifie rien.
        """
        return tuple(self.__pages)

    def ajouter_page(self, nom: str, uri: str) -> Page:
        """Crée une page, l'ajoute au site et la renvoie (EF-01.4).

        La comparaison des noms ne tient pas compte de la casse.

        PRE : aucune.
        POST : renvoie la page créée, qui est ajoutée à la fin des
               pages du site. Une URI sans schéma reçoit « https:// ».
               Exception ValueError : si le nom est vide.
               Exception ValueError : si l'URI est vide.
               Exception ValueError : si une page du site porte déjà ce
               nom (EF-01.4).
               Exception ValueError : si une page du site a déjà cette
               URI (EF-01.6).
               Si une exception est levée, le site n'est pas modifié.
        """
        page = Page(nom, uri)
        for existante in self.__pages:
            if existante.nom.lower() == page.nom.lower():
                raise ValueError(
                    f"Une page nommée « {existante.nom} » existe déjà."
                )
            if existante.uri == page.uri:
                raise ValueError(
                    f"La page « {existante.nom} » a déjà l'URI "
                    f"{existante.uri}."
                )
        self.__pages.append(page)
        return page

    def supprimer_page(self, nom: str) -> None:
        """Retire du site la page qui porte ce nom (EF-01.5).

        La comparaison des noms ne tient pas compte de la casse. Les
        mesures déjà enregistrées dans les batteries sont conservées.

        PRE : aucune.
        POST : la page de ce nom n'est plus dans les pages du site (les
               espaces de début et de fin de nom sont ignorés).
               Exception ValueError : si aucune page du site ne porte ce
               nom.
               Exception ValueError : si c'est la page principale.
               Si une exception est levée, le site n'est pas modifié.
        """
        page = self.__chercher_page(nom)
        if page is None:
            raise ValueError(f"Aucune page nommée « {nom.strip()} ».")
        if page is self.__pages[0]:
            raise ValueError(
                "La page principale ne peut pas être supprimée."
            )
        self.__pages.remove(page)

    def __chercher_page(self, nom: str) -> Page | None:
        """Renvoie la page qui porte ce nom, ou None si elle n'existe pas."""
        nom_cherche = nom.strip().lower()
        for page in self.__pages:
            if page.nom.lower() == nom_cherche:
                return page
        return None

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

    def historique_page(self, page: Page) -> tuple[Mesure, ...]:
        """Donne les mesures de toutes les batteries qui portent sur une page.

        Les mesures d'une page supprimée restent dans l'historique
        (EF-01.5).

        PRE : aucune.
        POST : renvoie un tuple des mesures dont la page est celle donnée,
               de la plus ancienne batterie à la plus récente. Le tuple
               est vide si aucune mesure ne porte sur cette page. Ne
               modifie rien.
        """
        return tuple(
            mesure
            for batterie in self.__historique
            for mesure in batterie.mesures
            if mesure.page is page
        )

    @property
    def statut_disponibilite(self) -> StatutDisponibilite:
        """Calcule le statut de disponibilité sur la dernière batterie.

        Le statut n'est pas enregistré : il est recalculé à chaque
        lecture (RM-03, RM-04, RM-06).

        PRE : aucune.
        POST : renvoie INCONNU si le site n'a jamais été testé ou si sa
               dernière batterie n'a aucune mesure. Renvoie
               INDISPONIBLE si une mesure L4 est KO, si toutes les
               mesures L7 sont KO, ou si une mesure L3 est KO sans
               qu'aucune mesure L4 ou L7 ne soit OK. Renvoie
               PARTIELLEMENT_INDISPONIBLE si certaines mesures L7
               seulement sont KO. Renvoie DISPONIBLE sinon. Une mesure
               L4 ou L7 OK compense une mesure L3 KO, l'ICMP étant
               souvent bloqué (RM-06, Q-02). Ne modifie rien.
        """
        batterie = self.derniere_batterie
        if batterie is None or len(batterie.mesures) == 0:
            return StatutDisponibilite.INCONNU
        mesures = batterie.mesures
        if self.__a_un_echec(mesures, Couche.L4):
            return StatutDisponibilite.INDISPONIBLE
        l7 = [m for m in mesures if m.couche == Couche.L7]
        if len(l7) > 0 and all(m.verdict == Verdict.KO for m in l7):
            return StatutDisponibilite.INDISPONIBLE
        if (self.__a_un_echec(mesures, Couche.L3)
                and not self.__a_une_reussite_l4_ou_l7(mesures)):
            return StatutDisponibilite.INDISPONIBLE
        if self.__a_un_echec(mesures, Couche.L7):
            return StatutDisponibilite.PARTIELLEMENT_INDISPONIBLE
        return StatutDisponibilite.DISPONIBLE

    def statut_performance(
        self, config: ConfigurationTests
    ) -> StatutPerformance:
        """Calcule le statut de performance sur les dernières batteries.

        Les batteries prises en compte sont celles des
        config.fenetre_performance_min minutes qui précèdent la
        dernière batterie (celle-ci comprise). Le RTT d'une batterie est
        la durée de sa mesure L3 ou, à défaut, de sa mesure L4. Le temps
        de chargement est calculé page par page (RM-08).

        PRE : aucune.
        POST : renvoie DEGRADEES si le RTT moyen dépasse config.seuil_l3_s
               ou si le temps de chargement moyen d'une page du site
               (mesures L7 de cette page) dépasse config.seuil_l7_s.
               Sinon renvoie NORMALES si l'une de ces moyennes a pu être
               calculée, et INCONNU si aucune mesure n'a de durée. Ne
               modifie rien.
        """
        rtt_moyen_s = self.rtt_moyen(config)
        chargements_s = [
            self.chargement_moyen(config, page) for page in self.__pages
        ]
        connus_s = [duree_s for duree_s in chargements_s
                    if duree_s is not None]
        if rtt_moyen_s is None and len(connus_s) == 0:
            return StatutPerformance.INCONNU
        if rtt_moyen_s is not None and rtt_moyen_s > config.seuil_l3_s:
            return StatutPerformance.DEGRADEES
        if any(duree_s > config.seuil_l7_s for duree_s in connus_s):
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

    def chargement_moyen(
        self, config: ConfigurationTests, page: Page
    ) -> float | None:
        """Donne le temps de chargement moyen d'une page sur la fenêtre.

        Il s'agit des mesures L7 de cette page dans les batteries de la
        fenêtre de statut_performance.

        PRE : aucune.
        POST : renvoie le temps de chargement moyen de la page, en
               secondes, ou None si aucune mesure L7 de cette page n'a de
               durée dans la fenêtre. Ne modifie rien.
        """
        batteries = self.__batteries_recentes(config.fenetre_performance_min)
        return self.__moyenne(
            [self.__chargement(b, page) for b in batteries]
        )

    def ecart_chargement(
        self, config: ConfigurationTests, page: Page
    ) -> float | None:
        """Compare le chargement moyen d'une page à sa moyenne globale.

        La moyenne globale porte sur toutes les batteries du site. La
        comparaison n'a de sens que s'il existe des batteries plus
        anciennes que la fenêtre.

        PRE : aucune.
        POST : renvoie l'écart relatif (chargement de la page sur la
               fenêtre - moyenne globale de la page) / moyenne globale.
               Renvoie None si toutes les batteries du site sont dans la
               fenêtre, si l'une des moyennes est inconnue ou si la
               moyenne globale est nulle. Ne modifie rien.
        """
        if not self.__a_des_batteries_hors_fenetre(config):
            return None
        globale = self.__moyenne(
            [self.__chargement(b, page) for b in self.__historique]
        )
        return self.__ecart(self.chargement_moyen(config, page), globale)

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

    def est_a_tester(
        self, frequence_min: int, horloge: Callable[[], datetime]
    ) -> bool:
        """Dit si le site doit être testé par le lancement automatique.

        Un test lancé à la main repousse l'échéance, comme un test
        automatique : seule compte la dernière batterie (EF-03.7).

        PRE : aucune.
        POST : renvoie True si le site n'a jamais été testé ou si sa
               dernière batterie date d'au moins frequence_min minutes
               avant l'instant donné par horloge (appelée une fois).
               Renvoie False sinon. Ne modifie rien.
        """
        derniere = self.derniere_batterie
        if derniere is None:
            return True
        age = horloge() - derniere.horodatage
        return age >= timedelta(minutes=frequence_min)

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

    def __a_un_echec(
        self, mesures: tuple[Mesure, ...], couche: Couche
    ) -> bool:
        """Dit si une mesure de cette couche a un verdict KO."""
        return any(
            m.couche == couche and m.verdict == Verdict.KO for m in mesures
        )

    def __a_une_reussite_l4_ou_l7(self, mesures: tuple[Mesure, ...]) -> bool:
        """Dit si une mesure L4 ou L7 a un verdict OK."""
        return any(
            m.couche != Couche.L3 and m.verdict == Verdict.OK
            for m in mesures
        )

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

    def __chargement(
        self, batterie: BatterieTests, page: Page
    ) -> float | None:
        """Renvoie le temps de chargement d'une page dans une batterie.

        C'est la moyenne des durées des mesures L7 de cette page dans la
        batterie ; None si aucune n'a de durée.
        """
        return self.__moyenne([
            mesure.duree_s for mesure in batterie.mesures
            if mesure.couche == Couche.L7 and mesure.page is page
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
            """Renvoie une seule mesure, datée de l'horodatage reçu.

            Une mesure L7 porte sur la page principale du site.
            """
            self.delais_recus.append(timeout_s)
            page = site.pages[0] if self.couche == Couche.L7 else None
            return [Mesure(horodatage, self.couche, self.__verdict,
                           self.__duree_s, self.__diagnostic, page)]

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

    print("Scénario : une mesure L7 OK et une mesure L7 KO : "
          "PARTIELLEMENT_INDISPONIBLE (RM-04)")
    site_mixte = Site("ClientABC", "clientabc.be")
    site_mixte.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200"), FauxTesteur(Verdict.KO, "500")],
        CONFIG,
        MANUEL,
        fausse_horloge,
    )
    attendu = StatutDisponibilite.PARTIELLEMENT_INDISPONIBLE
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
    accueil = neuf.pages[0]
    attendu = (None, None, None, None)
    obtenu = (neuf.rtt_moyen(CONFIG), neuf.ecart_rtt(CONFIG),
              neuf.chargement_moyen(CONFIG, accueil),
              neuf.ecart_chargement(CONFIG, accueil))
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
    accueil_ecart = site_ecart.pages[0]
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
              round(site_ecart.chargement_moyen(CONFIG, accueil_ecart), 6))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : écart par rapport à la moyenne globale : +50 % "
          "(0,3 contre 0,2 ; 0,6 contre 0,4)")
    attendu = (0.5, 0.5)
    obtenu = (round(site_ecart.ecart_rtt(CONFIG), 6),
              round(site_ecart.ecart_chargement(CONFIG, accueil_ecart), 6))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    site_echeance = Site("ClientABC", "clientabc.be")

    print("Scénario : site jamais testé : à tester (EF-03.7)")
    attendu = True
    obtenu = site_echeance.est_a_tester(15, fausse_horloge)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    site_echeance.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200")],
        CONFIG,
        MANUEL,
        horloge_fixee(INSTANT - timedelta(minutes=14)),
    )
    print("Scénario : dernier test (manuel) il y a 14 minutes : pas encore "
          "à tester")
    attendu = False
    obtenu = site_echeance.est_a_tester(15, fausse_horloge)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    site_echeance.lancer_batterie(
        [FauxTesteur(Verdict.OK, "200")],
        CONFIG,
        MANUEL,
        horloge_fixee(INSTANT - timedelta(minutes=15)),
    )
    print("Scénario : dernier test il y a exactement 15 minutes : à tester")
    attendu = True
    obtenu = site_echeance.est_a_tester(15, fausse_horloge)
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

    def noms_des_pages(site: Site) -> list[str]:
        """Renvoie les noms des pages du site, dans l'ordre."""
        return [page.nom for page in site.pages]

    def resultat_ajout(site: Site, nom: str, uri: str) -> str:
        """Tente d'ajouter une page et renvoie « ok » ou « ValueError »."""
        try:
            site.ajouter_page(nom, uri)
            return "ok"
        except ValueError:
            return "ValueError"

    print("Scénario : un nouveau site a une page principale « Page "
          "d'accueil » (EF-01.1)")
    site_pages = Site("ClientABC", "clientabc.be")
    attendu = [("Page d'accueil", "https://clientabc.be")]
    obtenu = [(page.nom, page.uri) for page in site_pages.pages]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : ajout de « PageA » puis « PageB » (EF-01.4)")
    site_pages.ajouter_page("PageA", "clientabc.be/a")
    site_pages.ajouter_page("PageB", "clientabc.be/b")
    attendu = ["Page d'accueil", "PageA", "PageB"]
    obtenu = noms_des_pages(site_pages)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : ajout d'un second « PageA », même à la casse près "
          "(EF-01.4)")
    attendu = "ValueError"
    obtenu = resultat_ajout(site_pages, "pagea", "clientabc.be/autre")
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : nouvelle page avec l'URI de la page principale, "
          "sous un autre nom (EF-01.6)")
    attendu = "ValueError"
    obtenu = resultat_ajout(site_pages, "Copie", "https://clientabc.be")
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : après les deux refus, le site a toujours 3 pages")
    attendu = ["Page d'accueil", "PageA", "PageB"]
    obtenu = noms_des_pages(site_pages)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    def resultat_suppression(site: Site, nom: str) -> str:
        """Tente de supprimer une page et renvoie « ok » ou « ValueError »."""
        try:
            site.supprimer_page(nom)
            return "ok"
        except ValueError:
            return "ValueError"

    print("Scénario : suppression de « PageA », qui existe (EF-01.5)")
    attendu = ("ok", ["Page d'accueil", "PageB"])
    resultat = resultat_suppression(site_pages, "PageA")
    obtenu = (resultat, noms_des_pages(site_pages))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : suppression de « PageA », qui n'existe plus "
          "(EF-01.5)")
    attendu = "ValueError"
    obtenu = resultat_suppression(site_pages, "PageA")
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : suppression de la page principale (EF-01.5)")
    attendu = ("ValueError", ["Page d'accueil", "PageB"])
    resultat = resultat_suppression(site_pages, "Page d'accueil")
    obtenu = (resultat, noms_des_pages(site_pages))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    class FauxTesteurParPage(Testeur):
        """Testeur de test : une mesure L7 OK par page du site, sans réseau."""

        @property
        def couche(self) -> Couche:
            """Donne la couche testée : L7."""
            return Couche.L7

        def executer(
            self, site: Site, timeout_s: float, horodatage: datetime
        ) -> list[Mesure]:
            """Renvoie une mesure OK pour chaque page du site."""
            return [
                Mesure(horodatage, Couche.L7, Verdict.OK, 0.1, "200", page)
                for page in site.pages
            ]

    site_historique = Site("ClientABC", "clientabc.be")
    page_a = site_historique.ajouter_page("PageA", "clientabc.be/a")
    for _ in range(2):
        site_historique.lancer_batterie(
            [FauxTesteurParPage()], CONFIG, MANUEL, fausse_horloge
        )

    print("Scénario : l'historique d'une page rassemble ses mesures de "
          "toutes les batteries")
    attendu = (2, {"PageA"})
    mesures_a = site_historique.historique_page(page_a)
    obtenu = (len(mesures_a), {mesure.page.nom for mesure in mesures_a})
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : les mesures d'une page supprimée sont conservées "
          "(EF-01.5)")
    site_historique.supprimer_page("PageA")
    attendu = 2
    obtenu = len(site_historique.historique_page(page_a))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    class FauxTesteurPages(Testeur):
        """Testeur de test : une mesure L7 par page, résultats fixés.

        resultats donne le verdict et la durée de chaque page, dans
        l'ordre des pages du site.
        """

        def __init__(self, resultats: list[tuple[Verdict, float]]) -> None:
            """Mémorise le verdict et la durée de chaque page."""
            self.__resultats = resultats

        @property
        def couche(self) -> Couche:
            """Donne la couche testée : L7."""
            return Couche.L7

        def executer(
            self, site: Site, timeout_s: float, horodatage: datetime
        ) -> list[Mesure]:
            """Renvoie une mesure par page, selon les résultats fixés."""
            return [
                Mesure(horodatage, Couche.L7, verdict, duree_s, "x", page)
                for page, (verdict, duree_s)
                in zip(site.pages, self.__resultats)
            ]

    def site_a_trois_pages() -> Site:
        """Crée un site avec sa page principale et deux autres pages."""
        site = Site("ClientABC", "clientabc.be")
        site.ajouter_page("PageA", "clientabc.be/a")
        site.ajouter_page("PageB", "clientabc.be/b")
        return site

    def statut_trois_pages(
        *resultats: tuple[Verdict, float], l3: Verdict | None = None
    ) -> StatutDisponibilite:
        """Teste un site à trois pages et renvoie son statut."""
        site = site_a_trois_pages()
        testeurs: list[Testeur] = [FauxTesteurPages(list(resultats))]
        if l3 is not None:
            testeurs.append(FauxTesteur(l3, "0/6", Couche.L3))
            testeurs.append(FauxTesteur(Verdict.OK, "443", Couche.L4))
        site.lancer_batterie(testeurs, CONFIG, MANUEL, fausse_horloge)
        return site.statut_disponibilite

    OK_RAPIDE = (Verdict.OK, 0.1)
    KO_RAPIDE = (Verdict.KO, 0.1)

    print("Scénario : une page sur trois en erreur : "
          "PARTIELLEMENT_INDISPONIBLE (RM-04)")
    attendu = StatutDisponibilite.PARTIELLEMENT_INDISPONIBLE
    obtenu = statut_trois_pages(OK_RAPIDE, KO_RAPIDE, OK_RAPIDE)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : toutes les pages en erreur : INDISPONIBLE (RM-03)")
    attendu = StatutDisponibilite.INDISPONIBLE
    obtenu = statut_trois_pages(KO_RAPIDE, KO_RAPIDE, KO_RAPIDE)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : L3 KO compensé par L4, une page en erreur : "
          "PARTIELLEMENT_INDISPONIBLE (RM-06)")
    attendu = StatutDisponibilite.PARTIELLEMENT_INDISPONIBLE
    obtenu = statut_trois_pages(
        OK_RAPIDE, KO_RAPIDE, OK_RAPIDE, l3=Verdict.KO
    )
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    site_lent = site_a_trois_pages()
    site_lent.lancer_batterie(
        [FauxTesteurPages([(Verdict.OK, 0.9), (Verdict.OK, 0.1),
                           (Verdict.OK, 0.1)])],
        CONFIG,
        MANUEL,
        fausse_horloge,
    )
    accueil, page_a, _ = site_lent.pages

    print("Scénario : une page lente suffit à dégrader le site, même si "
          "la moyenne de toutes les pages est sous le seuil (RM-08)")
    attendu = (StatutPerformance.DEGRADEES, True)
    moyenne_toutes_pages = (0.9 + 0.1 + 0.1) / 3
    obtenu = (site_lent.statut_performance(CONFIG),
              moyenne_toutes_pages < CONFIG.seuil_l7_s)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : le chargement moyen se calcule page par page")
    attendu = (0.9, 0.1)
    obtenu = (round(site_lent.chargement_moyen(CONFIG, accueil), 6),
              round(site_lent.chargement_moyen(CONFIG, page_a), 6))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : une page lente supprimée ne dégrade plus le site "
          "(RM-08)")
    site_suppression = site_a_trois_pages()
    site_suppression.lancer_batterie(
        [FauxTesteurPages([(Verdict.OK, 0.1), (Verdict.OK, 0.1),
                           (Verdict.OK, 0.9)])],
        CONFIG,
        MANUEL,
        fausse_horloge,
    )
    site_suppression.supprimer_page("PageB")
    attendu = StatutPerformance.NORMALES
    obtenu = site_suppression.statut_performance(CONFIG)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    site_modif = Site("ClientABC", "clientabc.be")
    site_modif.ajouter_page("PageA", "clientabc.be/a")
    site_modif.lancer_batterie(
        [FauxTesteurParPage()], CONFIG, MANUEL, fausse_horloge
    )
    accueil_modif = site_modif.pages[0]
    site_modif.modifier("ClientXYZ", "clientxyz.be")

    print("Scénario : modification du nom et de l'URI principale : la "
          "page principale suit (EF-01.2)")
    attendu = ("ClientXYZ", "https://clientxyz.be", "https://clientxyz.be")
    obtenu = (site_modif.nom, site_modif.uri_principale,
              site_modif.pages[0].uri)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : après la modification, la page principale est "
          "la même et son historique est conservé")
    attendu = (True, 1)
    obtenu = (site_modif.pages[0] is accueil_modif,
              len(site_modif.historique_page(accueil_modif)))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : modification avec l'URI d'une autre page : refusée, "
          "site inchangé (EF-01.6)")
    try:
        site_modif.modifier("ClientABC", "clientabc.be/a")
        refus = "aucune erreur"
    except ValueError:
        refus = "ValueError"
    attendu = ("ValueError", "ClientXYZ", "https://clientxyz.be")
    obtenu = (refus, site_modif.nom, site_modif.pages[0].uri)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : modification avec une URI vide : refusée, site "
          "inchangé (EF-01.3)")
    try:
        site_modif.modifier("ClientABC", "   ")
        refus = "aucune erreur"
    except ValueError:
        refus = "ValueError"
    attendu = ("ValueError", "ClientXYZ", "https://clientxyz.be")
    obtenu = (refus, site_modif.nom, site_modif.uri_principale)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
