"""Interface Textual : tableau des sites, formulaire et raccourcis clavier.

L'écran affiche en permanence la liste des sites, avec une ligne par page
sous chaque site. Un formulaire et quatre boutons permettent d'ajouter ou
de modifier un site, d'ajouter ou de supprimer une page, et des
raccourcis lancent les tests. Un minuteur lance aussi automatiquement
les tests des sites dont l'échéance est atteinte (EF-03.7). Les tests
tournent dans un fil d'exécution séparé pour que l'écran reste
utilisable.
"""

from collections.abc import Callable
from datetime import datetime

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.markup import escape
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

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

COULEURS = {
    StatutDisponibilite.DISPONIBLE: "green",
    StatutDisponibilite.PARTIELLEMENT_INDISPONIBLE: "dark_orange",
    StatutDisponibilite.INDISPONIBLE: "red",
    StatutDisponibilite.INCONNU: "yellow",
}

FORMAT_HORODATAGE = "%d/%m/%Y %H:%M:%S"

# Ajouté à l'horodatage d'un site dont les statuts datent de trop longtemps.
MARQUE_ANCIEN = " (ancien)"

# Délai, en secondes, entre deux vérifications des échéances de test.
INTERVALLE_REVEIL_S = 60


class MoniteurApp(App):
    """Application Textual de surveillance des sites.

    INVARIANT : le registre, les testeurs, la configuration, l'horloge
    et la fréquence des tests reçus à la création ne sont jamais
    remplacés ; un site n'est jamais testé deux fois en même temps par
    cette application ; la liste des lignes décrit, dans l'ordre, les
    lignes du tableau (un site, ou une page de ce site).
    """

    TITLE = "Surveillance des sites"
    CSS = """
    #sites { height: 1fr; }
    #formulaire { height: auto; }
    #formulaire Input { width: 1fr; }
    #actions { height: auto; }
    #message { padding: 0 1; }
    """
    BINDINGS = [
        ("t", "tester_site", "Tester le site sélectionné"),
        ("a", "tester_tous", "Tester tous les sites"),
        ("q", "quit", "Quitter"),
    ]

    def __init__(
        self,
        registre: RegistreSites,
        testeurs: list[Testeur],
        config: ConfigurationTests,
        horloge: Callable[[], datetime],
        frequence_min: int,
    ) -> None:
        """Mémorise les objets créés par main.py, transmis au domaine.

        frequence_min est le délai, en minutes, entre deux tests
        automatiques d'un même site (EF-03.7).

        PRE : aucune.
        POST : l'application est créée, sans rien afficher.
        """
        super().__init__()
        self.__registre = registre
        self.__testeurs = testeurs
        self.__config = config
        self.__horloge = horloge
        self.__frequence_min = frequence_min
        self.__en_cours: set[Site] = set()
        self.__lignes: list[tuple[Site, Page | None]] = []

    def compose(self) -> ComposeResult:
        """Construit l'écran : tableau, formulaire, boutons et raccourcis.

        PRE : aucune.
        POST : produit les éléments de l'écran, dans l'ordre. Ne
               modifie rien.
        """
        yield Header()
        yield DataTable(id="sites", cursor_type="row")
        with Horizontal(id="formulaire"):
            yield Input(placeholder="Nom du site ou de la page", id="nom")
            yield Input(placeholder="URI principale ou de la page", id="uri")
        with Horizontal(id="actions"):
            yield Button("Ajouter un site", id="ajouter_site")
            yield Button("Modifier le site", id="modifier_site")
            yield Button("Ajouter une page", id="ajouter_page")
            yield Button("Supprimer la page", id="supprimer_page")
        yield Static(id="message")
        yield Footer()

    def on_mount(self) -> None:
        """Crée les colonnes du tableau, l'affiche et lance le minuteur.

        PRE : l'écran a été construit (compose).
        POST : le tableau a ses huit colonnes et affiche les sites du
               registre (EF-02.1). Un minuteur vérifie ensuite toutes
               les INTERVALLE_REVEIL_S secondes quels sites sont à tester
               et les teste en arrière-plan (EF-03.7). Ne modifie ni le
               registre ni les sites.
        """
        tableau = self.query_one(DataTable)
        tableau.add_columns(
            "Nom / Page", "Statut / Verdict", "Performance", "RTT L3/L4",
            "Chargement L7", "Dernier test", "Diagnostic", "URI",
        )
        self.__rafraichir()
        self.set_interval(INTERVALLE_REVEIL_S, self.__lancer_echeances)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Exécute l'action du bouton pressé.

        PRE : aucune.
        POST : « Ajouter un site » a le même effet que l'envoi du
               formulaire (voir on_input_submitted). « Modifier le site »,
               « Ajouter une page » et « Supprimer la page » agissent sur
               la ligne sélectionnée du tableau (voir __modifier_site,
               __ajouter_page et __supprimer_page).
        """
        actions = {
            "ajouter_site": self.__ajouter_site,
            "modifier_site": self.__modifier_site,
            "ajouter_page": self.__ajouter_page,
            "supprimer_page": self.__supprimer_page,
        }
        actions[str(event.button.id)]()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Ajoute le site saisi lorsque Entrée est pressée (EF-01.1).

        PRE : aucune.
        POST : si le domaine accepte le nom et l'URI du formulaire, le
               site est ajouté au registre, le formulaire est vidé, une
               confirmation est affichée et le tableau est rafraîchi.
               Sinon (nom déjà utilisé, nom ou URI vide, EF-01.2 et
               EF-01.3), le motif du refus est affiché en rouge, le
               formulaire est conservé et le registre n'est pas modifié.
        """
        self.__ajouter_site()

    def action_tester_site(self) -> None:
        """Lance une batterie sur le site sélectionné (EF-03.1).

        PRE : aucune.
        POST : si le tableau est vide, affiche « Aucun site à tester. ».
               Sinon lance, en arrière-plan, une batterie sur le site de
               la ligne sélectionnée (site ou page) : elle rejoint son
               historique et le tableau est rafraîchi à la fin du test.
               Si ce site est déjà en cours de test, affiche « Test déjà
               en cours. ».
        """
        ligne = self.__ligne_selectionnee()
        if ligne is None:
            self.__afficher_message("Aucun site à tester.")
            return
        self.__demarrer_tests([ligne[0]], Declenchement.MANUEL)

    def action_tester_tous(self) -> None:
        """Lance une batterie sur chaque site du registre (EF-03.4).

        PRE : aucune.
        POST : lance, en arrière-plan, une batterie sur chaque site du
               registre, dans l'ordre : elle rejoint l'historique du
               site et le tableau est rafraîchi après chaque site. Les
               sites déjà en cours de test sont ignorés.
        """
        self.__demarrer_tests(
            list(self.__registre.sites), Declenchement.MANUEL
        )

    def __ajouter_site(self) -> None:
        """Ajoute le site décrit dans le formulaire.

        Un refus du domaine (nom déjà utilisé, nom ou URI vide, EF-01.2
        et EF-01.3) est affiché en rouge, et le formulaire est conservé.
        """
        champ_nom = self.query_one("#nom", Input)
        champ_uri = self.query_one("#uri", Input)
        try:
            site = self.__registre.ajouter_site(
                champ_nom.value, champ_uri.value
            )
        except ValueError as erreur:
            self.__afficher_message(f"Refus : {erreur}", "red")
            return
        champ_nom.clear()
        champ_uri.clear()
        champ_nom.focus()
        self.__afficher_message(f"Site « {site.nom} » ajouté.")
        self.__rafraichir()

    def __ligne_selectionnee(self) -> tuple[Site, Page | None] | None:
        """Renvoie le site et la page de la ligne sélectionnée.

        La page vaut None si la ligne est celle d'un site. Renvoie None
        si le tableau est vide.
        """
        if len(self.__lignes) == 0:
            return None
        return self.__lignes[self.query_one(DataTable).cursor_row]

    def __modifier_site(self) -> None:
        """Change le nom et l'URI du site de la ligne sélectionnée.

        Le nom et l'URI viennent du formulaire ; une saisie vide n'est
        pas remplacée par la valeur actuelle (EF-01.3). Un refus du
        domaine (nom déjà utilisé, nom ou URI vide, URI déjà portée par
        une autre page, EF-01.2, EF-01.3 et EF-01.6) est affiché en
        rouge, et le formulaire est conservé.
        """
        ligne = self.__ligne_selectionnee()
        if ligne is None:
            self.__afficher_message("Aucun site sélectionné.", "red")
            return
        site = ligne[0]
        champ_nom = self.query_one("#nom", Input)
        champ_uri = self.query_one("#uri", Input)
        try:
            self.__registre.modifier_site(
                site.nom, champ_nom.value, champ_uri.value
            )
        except ValueError as erreur:
            self.__afficher_message(f"Refus : {erreur}", "red")
            return
        champ_nom.clear()
        champ_uri.clear()
        self.__afficher_message(f"Site « {site.nom} » modifié.")
        self.__rafraichir()

    def __ajouter_page(self) -> None:
        """Ajoute au site de la ligne sélectionnée la page du formulaire.

        Un refus du domaine (nom de page déjà utilisé, URI déjà utilisée,
        nom ou URI vide, EF-01.4 et EF-01.6) est affiché en rouge, et le
        formulaire est conservé.
        """
        ligne = self.__ligne_selectionnee()
        if ligne is None:
            self.__afficher_message("Aucun site sélectionné.", "red")
            return
        site = ligne[0]
        champ_nom = self.query_one("#nom", Input)
        champ_uri = self.query_one("#uri", Input)
        try:
            page = site.ajouter_page(champ_nom.value, champ_uri.value)
        except ValueError as erreur:
            self.__afficher_message(f"Refus : {erreur}", "red")
            return
        champ_nom.clear()
        champ_uri.clear()
        self.__afficher_message(
            f"Page « {page.nom} » ajoutée au site « {site.nom} »."
        )
        self.__rafraichir()

    def __supprimer_page(self) -> None:
        """Supprime la page de la ligne sélectionnée (EF-01.5).

        Ses mesures restent dans l'historique du site. Un refus du
        domaine (page principale) est affiché en rouge.
        """
        ligne = self.__ligne_selectionnee()
        if ligne is None or ligne[1] is None:
            self.__afficher_message(
                "Sélectionnez la ligne de la page à supprimer.", "red"
            )
            return
        site, page = ligne
        try:
            site.supprimer_page(page.nom)
        except ValueError as erreur:
            self.__afficher_message(f"Refus : {erreur}", "red")
            return
        self.__afficher_message(
            f"Page « {page.nom} » supprimée "
            "(ses mesures restent dans l'historique)."
        )
        self.__rafraichir()

    def __lancer_echeances(self) -> None:
        """Lance le test automatique des sites dont l'échéance est atteinte.

        Appelée par le minuteur. Un site est à tester s'il n'a jamais
        été testé ou si son dernier test date d'au moins la fréquence
        choisie (EF-03.7).
        """
        a_tester = [
            site for site in self.__registre.sites
            if site.est_a_tester(self.__frequence_min, self.__horloge)
        ]
        self.__demarrer_tests(a_tester, Declenchement.PERIODIQUE)

    def __demarrer_tests(
        self, sites: list[Site], declenchement: Declenchement
    ) -> None:
        """Lance en arrière-plan les tests des sites qui ne sont pas en cours.

        Affiche « Test déjà en cours. » si un test demandé à la main
        porte sur des sites tous déjà en cours de test.
        """
        libres = [s for s in sites if s not in self.__en_cours]
        if len(libres) == 0:
            if declenchement == Declenchement.MANUEL and len(sites) > 0:
                self.__afficher_message("Test déjà en cours.")
            return
        self.__en_cours.update(libres)
        self.__lancer_tests(libres, declenchement)

    def __liberer(self, site: Site) -> None:
        """Note que ce site n'est plus en cours de test.

        Le suivi se fait par site et non par nom : un site renommé
        pendant son test reste bien identifié.
        """
        self.__en_cours.discard(site)

    @work(thread=True)
    def __lancer_tests(
        self, sites: list[Site], declenchement: Declenchement
    ) -> None:
        """Teste les sites un par un, dans un fil d'exécution séparé.

        Le tableau est mis à jour après chaque site. Les appels à
        l'écran passent par call_from_thread, seul moyen sûr de
        modifier l'interface depuis un autre fil.
        """
        automatique = declenchement == Declenchement.PERIODIQUE
        for site in sites:
            if automatique:
                message = f"Test automatique de « {site.nom} » en cours..."
            else:
                message = f"Test de « {site.nom} » en cours..."
            self.call_from_thread(self.__afficher_message, message)
            try:
                site.lancer_batterie(
                    self.__testeurs,
                    self.__config,
                    declenchement,
                    self.__horloge,
                )
            finally:
                self.call_from_thread(self.__liberer, site)
            self.call_from_thread(self.__rafraichir)
        self.call_from_thread(self.__afficher_message, "Tests terminés.")

    def __rafraichir(self) -> None:
        """Réaffiche toutes les lignes du tableau (EF-02.1).

        Chaque site est suivi d'une ligne par page. La couleur de chaque
        ligne met en évidence les sites indisponibles, jamais testés ou
        aux performances dégradées, et les pages en erreur ou lentes
        (EF-02.4).
        """
        tableau = self.query_one(DataTable)
        ligne_selectionnee = tableau.cursor_row
        tableau.clear()
        self.__lignes = []
        for site in self.__registre.sites:
            self.__ajouter_ligne(
                tableau, site, None, self.__couleur(site),
                self.__decrire(site),
            )
            for page in site.pages:
                self.__ajouter_ligne(
                    tableau, site, page, *self.__decrire_page(site, page)
                )
        tableau.move_cursor(row=ligne_selectionnee)

    def __ajouter_ligne(
        self,
        tableau: DataTable,
        site: Site,
        page: Page | None,
        couleur: str,
        textes: list[str],
    ) -> None:
        """Ajoute une ligne au tableau et la mémorise dans les lignes.

        La ligne est colorée si couleur n'est pas vide.
        """
        if couleur == "":
            cellules = [escape(texte) for texte in textes]
        else:
            cellules = [f"[{couleur}]{escape(texte)}[/]" for texte in textes]
        tableau.add_row(*cellules)
        self.__lignes.append((site, page))

    def __couleur(self, site: Site) -> str:
        """Renvoie la couleur de la ligne d'un site.

        Elle suit le statut de disponibilité, mais passe au jaune pour
        un site disponible aux performances dégradées.
        """
        couleur = COULEURS[site.statut_disponibilite]
        performance = site.statut_performance(self.__config)
        if (site.statut_disponibilite == StatutDisponibilite.DISPONIBLE
                and performance == StatutPerformance.DEGRADEES):
            couleur = "yellow"
        return couleur

    def __couleur_page(
        self, derniere: Mesure | None, chargement_s: float | None
    ) -> str:
        """Renvoie la couleur de la ligne d'une page.

        Rouge si la dernière mesure est KO, jaune si elle est OK mais que
        le chargement moyen dépasse le seuil L7 (RM-08), vert sinon, et
        une chaîne vide (aucune couleur) si la page n'a jamais été
        testée.
        """
        if derniere is None:
            return ""
        if derniere.verdict == Verdict.KO:
            return "red"
        if (chargement_s is not None
                and chargement_s > self.__config.seuil_l7_s):
            return "yellow"
        return "green"

    def __decrire(self, site: Site) -> list[str]:
        """Renvoie les textes des colonnes du tableau pour un site.

        Les colonnes sont le nom, les statuts de disponibilité et de
        performance (EF-02.1), le RTT moyen de la dernière fenêtre avec
        son écart par rapport à la moyenne globale (« 85 ms (+37 %) »),
        une colonne de chargement laissée vide (il se lit sur les lignes
        des pages), l'horodatage du dernier test (EF-02.2), suivi de
        « (ancien) » si les statuts datent de trop longtemps, les
        diagnostics des mesures L3 et L4, précédés de leur couche
        (« L3: 6/6 sondes »), et l'URI principale.
        """
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
        return [
            site.nom,
            site.statut_disponibilite.name,
            site.statut_performance(self.__config).name,
            formater_duree(
                site.rtt_moyen(self.__config), site.ecart_rtt(self.__config)
            ),
            "",
            horodatage,
            diagnostic,
            site.uri_principale,
        ]

    def __decrire_page(self, site: Site, page: Page) -> tuple[str, list[str]]:
        """Renvoie la couleur et les textes des colonnes d'une page.

        Le nom est en retrait. Le verdict et le diagnostic sont ceux de la
        dernière mesure de la page, « - » si elle n'a jamais été testée.
        Le chargement est la moyenne de la page avec son écart par
        rapport à sa moyenne globale.
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
        textes = [
            "  " + page.nom,
            verdict,
            "",
            "",
            formater_duree(
                chargement_s, site.ecart_chargement(self.__config, page)
            ),
            "",
            diagnostic,
            page.uri,
        ]
        return self.__couleur_page(derniere, chargement_s), textes

    def __afficher_message(self, texte: str, couleur: str = "") -> None:
        """Affiche un message sous le formulaire, en couleur si demandé."""
        if couleur == "":
            contenu = escape(texte)
        else:
            contenu = f"[{couleur}]{escape(texte)}[/]"
        self.query_one("#message", Static).update(contenu)


def lancer(
    registre: RegistreSites,
    testeurs: list[Testeur],
    config: ConfigurationTests,
    horloge: Callable[[], datetime],
    frequence_min: int,
) -> None:
    """Lance l'application Textual jusqu'à ce que l'utilisatrice quitte.

    registre, testeurs, config, horloge et frequence_min sont créés par
    main.py et transmis tels quels au domaine.

    PRE : config.timeout_s > 0.
    POST : affiche l'application et ne rend la main que lorsque
           l'utilisatrice quitte. Teste automatiquement chaque site
           dont le dernier test date d'au moins frequence_min minutes
           (EF-03.7). Modifie registre (sites ajoutés ou modifiés), les
           pages des sites (ajoutées ou supprimées) et les sites testés
           (nouvelles batteries).
    """
    MoniteurApp(registre, testeurs, config, horloge, frequence_min).run()
