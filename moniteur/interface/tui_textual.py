"""Interface Textual : tableau des sites, formulaire et raccourcis clavier.

Cette interface est la vue d'un présentateur (voir presentateur_textual).
L'écran affiche en permanence la liste des sites, avec une ligne par page
sous chaque site. Un formulaire et quatre boutons permettent d'ajouter ou
de modifier un site, d'ajouter ou de supprimer une page, et des
raccourcis lancent les tests. Un minuteur demande aussi au présentateur
de tester les sites dont l'échéance est atteinte (EF-03.7). La vue ne
connaît ni le registre ni les règles de couleur : elle montre ce que le
présentateur lui donne et lui transmet les actions. Les tests tournent
dans un fil de travail du présentateur, pour que l'écran reste utilisable.
"""

import threading
from collections.abc import Callable
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.markup import escape
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.registre_sites import RegistreSites
from moniteur.domaine.testeur import Testeur
from moniteur.interface.presentateur_textual import (
    AUCUNE,
    JAUNE,
    ORANGE,
    ROUGE,
    VERT,
    LigneTextual,
    PresentateurTextual,
)

# Couleurs Textual des couleurs du présentateur.
COULEURS = {
    VERT: "green",
    ORANGE: "dark_orange",
    ROUGE: "red",
    JAUNE: "yellow",
    AUCUNE: "",
}

# Délai, en secondes, entre deux vérifications des échéances de test.
INTERVALLE_REVEIL_S = 60


class MoniteurApp(App):
    """Application Textual : la vue du présentateur.

    INVARIANT : le présentateur créé avec l'application n'est jamais
    remplacé ; la liste des lignes décrit, dans l'ordre, les lignes du
    tableau ; seul le fil d'exécution de l'application touche à l'écran
    (les autres fils passent par __dans_ecran).
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
        """Crée l'application et son présentateur.

        registre, testeurs, config, horloge et frequence_min sont créés
        par main.py et transmis tels quels au présentateur.

        PRE : aucune.
        POST : l'application est créée, sans rien afficher. Le
               présentateur est abonné au registre.
        """
        super().__init__()
        self.__fil_ecran: int | None = None
        self.__lignes: tuple[LigneTextual, ...] = ()
        self.__presentateur = PresentateurTextual(
            registre, testeurs, config, horloge, frequence_min,
            self.__recevoir_lignes, self.__recevoir_message,
            self.__recevoir_vidage,
        )

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
               registre (EF-02.1). Un minuteur demande ensuite au
               présentateur, toutes les INTERVALLE_REVEIL_S secondes, de
               tester les sites à tester (EF-03.7). Ne modifie ni le
               registre ni les sites.
        """
        self.__fil_ecran = threading.get_ident()
        tableau = self.query_one(DataTable)
        tableau.add_columns(
            "Nom / Page", "Statut / Verdict", "Performance", "RTT L3/L4",
            "Chargement L7", "Dernier test", "Diagnostic", "URI",
        )
        self.__presentateur.rafraichir()
        self.set_interval(
            INTERVALLE_REVEIL_S, self.__presentateur.tester_echeances
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Exécute l'action du bouton pressé.

        PRE : aucune.
        POST : « Ajouter un site » a le même effet que l'envoi du
               formulaire (voir on_input_submitted). « Modifier le site »,
               « Ajouter une page » et « Supprimer la page » agissent sur
               la ligne sélectionnée du tableau. Le présentateur effectue
               l'action ou la refuse.
        """
        actions = {
            "ajouter_site": self.__ajouter_site,
            "modifier_site": self.__modifier_site,
            "ajouter_page": self.__ajouter_page,
            "supprimer_page": self.__supprimer_page,
        }
        actions[str(event.button.id)]()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Transmet le formulaire au présentateur quand Entrée est pressée.

        PRE : aucune.
        POST : le nom et l'URI du formulaire sont transmis au
               présentateur, qui ajoute le site ou le refuse (EF-01.1,
               EF-01.2 et EF-01.3).
        """
        self.__ajouter_site()

    def action_tester_site(self) -> None:
        """Demande le test du site de la ligne sélectionnée (EF-03.1).

        PRE : aucune.
        POST : le site de la ligne sélectionnée (site ou page), ou aucun
               site si le tableau est vide, est transmis au
               présentateur, qui lance le test ou explique pourquoi il
               ne le lance pas.
        """
        ligne = self.__ligne_selectionnee()
        self.__presentateur.tester_site(
            None if ligne is None else ligne.nom_site
        )

    def action_tester_tous(self) -> None:
        """Demande le test de tous les sites (EF-03.4).

        PRE : aucune.
        POST : le présentateur lance les tests ou explique pourquoi il ne
               les lance pas.
        """
        self.__presentateur.tester_tous()

    def __ajouter_site(self) -> None:
        """Transmet le formulaire pour ajouter un site."""
        self.__presentateur.ajouter_site(
            self.query_one("#nom", Input).value,
            self.query_one("#uri", Input).value,
        )

    def __modifier_site(self) -> None:
        """Transmet le formulaire pour modifier le site sélectionné."""
        ligne = self.__ligne_selectionnee()
        self.__presentateur.modifier_site(
            None if ligne is None else ligne.nom_site,
            self.query_one("#nom", Input).value,
            self.query_one("#uri", Input).value,
        )

    def __ajouter_page(self) -> None:
        """Transmet le formulaire pour ajouter une page au site choisi."""
        ligne = self.__ligne_selectionnee()
        self.__presentateur.ajouter_page(
            None if ligne is None else ligne.nom_site,
            self.query_one("#nom", Input).value,
            self.query_one("#uri", Input).value,
        )

    def __supprimer_page(self) -> None:
        """Transmet la ligne sélectionnée pour supprimer sa page."""
        ligne = self.__ligne_selectionnee()
        if ligne is None:
            self.__presentateur.supprimer_page(None, None)
        else:
            self.__presentateur.supprimer_page(
                ligne.nom_site, ligne.nom_page
            )

    def __ligne_selectionnee(self) -> LigneTextual | None:
        """Renvoie la ligne sélectionnée, ou None si le tableau est vide."""
        if len(self.__lignes) == 0:
            return None
        return self.__lignes[self.query_one(DataTable).cursor_row]

    def __recevoir_lignes(self, lignes: tuple[LigneTextual, ...]) -> None:
        """Reçoit les lignes du présentateur, depuis n'importe quel fil."""
        self.__dans_ecran(self.__dessiner, lignes)

    def __recevoir_message(self, texte: str, couleur: str) -> None:
        """Reçoit un message du présentateur, depuis n'importe quel fil."""
        self.__dans_ecran(self.__afficher_message, texte, couleur)

    def __recevoir_vidage(self) -> None:
        """Reçoit la demande de vider le formulaire (n'importe quel fil)."""
        self.__dans_ecran(self.__vider_formulaire)

    def __dans_ecran(
        self, fonction: Callable[..., None], *arguments: object
    ) -> None:
        """Exécute fonction dans le fil de l'application.

        Textual n'est sûr que dans son propre fil : un autre fil doit
        passer par call_from_thread. Si l'application est déjà fermée,
        l'affichage n'a plus lieu d'être et l'appel est ignoré.
        """
        if threading.get_ident() == self.__fil_ecran:
            fonction(*arguments)
            return
        try:
            self.call_from_thread(fonction, *arguments)
        except RuntimeError:
            pass

    def __dessiner(self, lignes: tuple[LigneTextual, ...]) -> None:
        """Remplace le contenu du tableau par ces lignes (EF-02.1).

        La ligne sélectionnée est conservée. Le texte de chaque cellule
        est protégé : un nom entre crochets ne devient pas une couleur.
        """
        tableau = self.query_one(DataTable)
        ligne_selectionnee = tableau.cursor_row
        tableau.clear()
        for ligne in lignes:
            couleur = COULEURS[ligne.couleur]
            if couleur == "":
                cellules = [escape(texte) for texte in ligne.cellules]
            else:
                cellules = [
                    f"[{couleur}]{escape(texte)}[/]"
                    for texte in ligne.cellules
                ]
            tableau.add_row(*cellules)
        self.__lignes = lignes
        tableau.move_cursor(row=ligne_selectionnee)

    def __afficher_message(self, texte: str, couleur: str) -> None:
        """Affiche un message sous le formulaire, en couleur si demandé."""
        if COULEURS[couleur] == "":
            contenu = escape(texte)
        else:
            contenu = f"[{COULEURS[couleur]}]{escape(texte)}[/]"
        self.query_one("#message", Static).update(contenu)

    def __vider_formulaire(self) -> None:
        """Vide les deux champs du formulaire et se place sur le nom."""
        champ_nom = self.query_one("#nom", Input)
        self.query_one("#uri", Input).clear()
        champ_nom.clear()
        champ_nom.focus()


def lancer(
    registre: RegistreSites,
    testeurs: list[Testeur],
    config: ConfigurationTests,
    horloge: Callable[[], datetime],
    frequence_min: int,
) -> None:
    """Lance l'application Textual jusqu'à ce que l'utilisatrice quitte.

    registre, testeurs, config, horloge et frequence_min sont créés par
    main.py et transmis tels quels au présentateur.

    PRE : config.timeout_s > 0.
    POST : affiche l'application et ne rend la main que lorsque
           l'utilisatrice quitte. Teste automatiquement chaque site
           dont le dernier test date d'au moins frequence_min minutes
           (EF-03.7). Modifie registre (sites ajoutés ou modifiés), les
           pages des sites (ajoutées ou supprimées) et les sites testés
           (nouvelles batteries).
    """
    MoniteurApp(registre, testeurs, config, horloge, frequence_min).run()
