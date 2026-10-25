"""Interface Textual : tableau des sites, formulaire et raccourcis clavier.

L'écran affiche en permanence la liste des sites. Un formulaire permet
d'en ajouter, et des raccourcis lancent les tests. Les tests tournent
dans un fil d'exécution séparé pour que l'écran reste utilisable.
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
    StatutDisponibilite,
    StatutPerformance,
)
from moniteur.domaine.registre_sites import RegistreSites
from moniteur.domaine.site import Site
from moniteur.domaine.testeur import Testeur

COULEURS = {
    StatutDisponibilite.DISPONIBLE: "green",
    StatutDisponibilite.INDISPONIBLE: "red",
    StatutDisponibilite.INCONNU: "yellow",
}

FORMAT_HORODATAGE = "%d/%m/%Y %H:%M:%S"

# Ajouté à l'horodatage d'un site dont les statuts datent de trop longtemps.
MARQUE_ANCIEN = " (ancien)"


def formater_duree(duree_s: float | None, ecart: float | None) -> str:
    """Formate une durée en millisecondes, suivie de son écart en %.

    PRE : aucune.
    POST : renvoie « - » si duree_s est None. Sinon renvoie la durée en
           millisecondes (deux décimales sous 1 ms, une sous 10 ms,
           aucune au-delà), suivie de l'écart entre parenthèses
           (« 85 ms (+37 %) »), ou de « (-) » si ecart est None. Ne
           modifie rien.
    """
    if duree_s is None:
        return "-"
    ms = duree_s * 1000
    if ms < 1:
        texte = f"{ms:.2f} ms"
    elif ms < 10:
        texte = f"{ms:.1f} ms"
    else:
        texte = f"{ms:.0f} ms"
    if ecart is None:
        return f"{texte} (-)"
    return f"{texte} ({ecart * 100:+.0f} %)"


class MoniteurApp(App):
    """Application Textual de surveillance des sites.

    INVARIANT : le registre, les testeurs, la configuration et l'horloge
    reçus à la création ne sont jamais remplacés.
    """

    TITLE = "Surveillance des sites"
    CSS = """
    #sites { height: 1fr; }
    #formulaire { height: auto; }
    #formulaire Input { width: 1fr; }
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
    ) -> None:
        """Mémorise les objets créés par main.py, transmis au domaine.

        PRE : aucune.
        POST : l'application est créée, sans rien afficher.
        """
        super().__init__()
        self.__registre = registre
        self.__testeurs = testeurs
        self.__config = config
        self.__horloge = horloge

    def compose(self) -> ComposeResult:
        """Construit l'écran : tableau, formulaire, message et raccourcis.

        PRE : aucune.
        POST : produit les éléments de l'écran, dans l'ordre. Ne
               modifie rien.
        """
        yield Header()
        yield DataTable(id="sites", cursor_type="row")
        with Horizontal(id="formulaire"):
            yield Input(placeholder="Nom du site", id="nom")
            yield Input(placeholder="URI principale", id="uri")
            yield Button("Ajouter", id="ajouter")
        yield Static(id="message")
        yield Footer()

    def on_mount(self) -> None:
        """Crée les colonnes du tableau et l'affiche une première fois.

        PRE : l'écran a été construit (compose).
        POST : le tableau a ses huit colonnes et affiche les sites du
               registre (EF-02.1). Ne modifie ni le registre ni les
               sites.
        """
        tableau = self.query_one(DataTable)
        tableau.add_columns(
            "Nom", "Statut", "Performance", "RTT L3/L4", "Chargement L7",
            "Dernier test", "Diagnostic", "URI",
        )
        self.__rafraichir()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Ajoute le site saisi lorsque le bouton est pressé.

        PRE : aucune.
        POST : même effet que l'envoi du formulaire (voir
               on_input_submitted).
        """
        self.__ajouter_site()

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
               Sinon lance, en arrière-plan, une batterie sur le site
               sélectionné : elle rejoint son historique et le tableau
               est rafraîchi à la fin du test.
        """
        tableau = self.query_one(DataTable)
        if tableau.row_count == 0:
            self.__afficher_message("Aucun site à tester.")
            return
        cle = tableau.coordinate_to_cell_key(tableau.cursor_coordinate)
        site = self.__registre.trouver_site(cle.row_key.value)
        self.__lancer_tests([site])

    def action_tester_tous(self) -> None:
        """Lance une batterie sur chaque site du registre (EF-03.4).

        PRE : aucune.
        POST : lance, en arrière-plan, une batterie sur chaque site du
               registre, dans l'ordre : elle rejoint l'historique du
               site et le tableau est rafraîchi après chaque site.
        """
        self.__lancer_tests(list(self.__registre.sites))

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

    @work(thread=True)
    def __lancer_tests(self, sites: list[Site]) -> None:
        """Teste les sites un par un, dans un fil d'exécution séparé.

        Le tableau est mis à jour après chaque site. Les appels à
        l'écran passent par call_from_thread, seul moyen sûr de
        modifier l'interface depuis un autre fil.
        """
        for site in sites:
            message = f"Test de « {site.nom} » en cours..."
            self.call_from_thread(self.__afficher_message, message)
            site.lancer_batterie(
                self.__testeurs, self.__config, self.__horloge
            )
            self.call_from_thread(self.__rafraichir)
        self.call_from_thread(self.__afficher_message, "Tests terminés.")

    def __rafraichir(self) -> None:
        """Réaffiche toutes les lignes du tableau (EF-02.1).

        La couleur de chaque ligne met en évidence les sites
        indisponibles, jamais testés ou aux performances dégradées
        (EF-02.4).
        """
        tableau = self.query_one(DataTable)
        ligne_selectionnee = tableau.cursor_row
        tableau.clear()
        for site in self.__registre.sites:
            couleur = self.__couleur(site)
            cellules = [
                f"[{couleur}]{escape(texte)}[/]"
                for texte in self.__decrire(site)
            ]
            tableau.add_row(*cellules, key=site.nom)
        tableau.move_cursor(row=ligne_selectionnee)

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

    def __decrire(self, site: Site) -> list[str]:
        """Renvoie les textes des colonnes du tableau pour un site.

        Les colonnes sont le nom, les statuts de disponibilité et de
        performance (EF-02.1), le RTT et le temps de chargement moyens de
        la dernière fenêtre avec leur écart par rapport à la moyenne
        globale (« 85 ms (+37 %) »), l'horodatage du dernier test (EF-02.2),
        suivi de « (ancien) » si les statuts datent de trop longtemps,
        les diagnostics des mesures, précédés de leur couche
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
                if mesure.diagnostic is not None
            )
        return [
            site.nom,
            site.statut_disponibilite.name,
            site.statut_performance(self.__config).name,
            formater_duree(
                site.rtt_moyen(self.__config), site.ecart_rtt(self.__config)
            ),
            formater_duree(
                site.chargement_moyen(self.__config),
                site.ecart_chargement(self.__config),
            ),
            horodatage,
            diagnostic,
            site.uri_principale,
        ]

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
) -> None:
    """Lance l'application Textual jusqu'à ce que l'utilisatrice quitte.

    registre, testeurs, config et horloge sont créés par main.py et
    transmis tels quels au domaine.

    PRE : config.timeout_s > 0.
    POST : affiche l'application et ne rend la main que lorsque
           l'utilisatrice quitte. Modifie registre (sites ajoutés) et
           les sites testés (nouvelles batteries).
    """
    MoniteurApp(registre, testeurs, config, horloge).run()
