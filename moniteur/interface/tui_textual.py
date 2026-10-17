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
from moniteur.domaine.enumerations import StatutDisponibilite
from moniteur.domaine.registre_sites import RegistreSites
from moniteur.domaine.site import Site
from moniteur.domaine.testeur import Testeur

COULEURS = {
    StatutDisponibilite.DISPONIBLE: "green",
    StatutDisponibilite.INDISPONIBLE: "red",
    StatutDisponibilite.INCONNU: "yellow",
}

FORMAT_HORODATAGE = "%d/%m/%Y %H:%M:%S"


class MoniteurApp(App):
    """Application Textual de surveillance des sites."""

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
        """Mémorise les objets créés par main.py, transmis au domaine."""
        super().__init__()
        self.__registre = registre
        self.__testeurs = testeurs
        self.__config = config
        self.__horloge = horloge

    def compose(self) -> ComposeResult:
        """Construit l'écran : tableau, formulaire, message et raccourcis."""
        yield Header()
        yield DataTable(id="sites", cursor_type="row")
        with Horizontal(id="formulaire"):
            yield Input(placeholder="Nom du site", id="nom")
            yield Input(placeholder="URI principale", id="uri")
            yield Button("Ajouter", id="ajouter")
        yield Static(id="message")
        yield Footer()

    def on_mount(self) -> None:
        """Crée les colonnes du tableau et l'affiche une première fois."""
        tableau = self.query_one(DataTable)
        tableau.add_columns(
            "Nom", "Statut", "Dernier test", "Diagnostic", "URI"
        )
        self.__rafraichir()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Ajoute le site saisi lorsque le bouton est pressé."""
        self.__ajouter_site()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Ajoute le site saisi lorsque Entrée est pressée dans le
        formulaire."""
        self.__ajouter_site()

    def action_tester_site(self) -> None:
        """Lance une batterie sur le site sélectionné (EF-03.1)."""
        tableau = self.query_one(DataTable)
        if tableau.row_count == 0:
            self.__afficher_message("Aucun site à tester.")
            return
        cle = tableau.coordinate_to_cell_key(tableau.cursor_coordinate)
        site = self.__registre.site(cle.row_key.value)
        self.__lancer_tests([site])

    def action_tester_tous(self) -> None:
        """Lance une batterie sur chaque site du registre (EF-03.4)."""
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
        indisponibles ou jamais testés (EF-02.4).
        """
        tableau = self.query_one(DataTable)
        ligne_selectionnee = tableau.cursor_row
        tableau.clear()
        for site in self.__registre.sites:
            couleur = COULEURS[site.statut_disponibilite]
            cellules = [
                f"[{couleur}]{escape(texte)}[/]"
                for texte in self.__decrire(site)
            ]
            tableau.add_row(*cellules, key=site.nom)
        tableau.move_cursor(row=ligne_selectionnee)

    def __decrire(self, site: Site) -> list[str]:
        """Renvoie les textes des colonnes du tableau pour un site.

        Les colonnes sont le nom, le statut, l'horodatage du dernier
        test (EF-02.2), le diagnostic et l'URI principale.
        """
        batterie = site.derniere_batterie
        if batterie is None:
            horodatage = "-"
            diagnostic = "-"
        else:
            horodatage = batterie.horodatage.strftime(FORMAT_HORODATAGE)
            diagnostic = ", ".join(
                mesure.diagnostic for mesure in batterie.mesures
                if mesure.diagnostic is not None
            )
        return [
            site.nom,
            site.statut_disponibilite.name,
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

    Reçoit le registre, les testeurs, la configuration et l'horloge,
    créés par main.py et transmis tels quels au domaine.
    """
    MoniteurApp(registre, testeurs, config, horloge).run()
