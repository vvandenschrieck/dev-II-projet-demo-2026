"""Dashboard en Tkinter : un tableau des sites sur une fenêtre.

La fenêtre affiche l'état des sites sur un écran secondaire (ENF-05) et
offre deux boutons pour lancer des tests (EF-03.1, EF-03.4). La vue ne
contient aucune logique : elle montre les lignes que lui donne son
présentateur et lui transmet les clics (voir presentateur_dashboard).
"""

import ctypes
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from tkinter import ttk

from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.registre_sites import RegistreSites
from moniteur.domaine.testeur import Testeur
from moniteur.interface.presentateur_dashboard import (
    COLONNES,
    JAUNE,
    ORANGE,
    PresentateurDashboard,
    ROUGE,
    VERT,
    LigneDashboard,
)

# Fonds pâles et texte noir : lisibles de loin, sans dépendre du thème.
FONDS = {
    VERT: "#c8e6c9",
    ORANGE: "#ffe0b2",
    ROUGE: "#ffcdd2",
    JAUNE: "#fff9c4",
}

# Délai, en millisecondes, entre deux lectures des lignes à afficher.
INTERVALLE_LECTURE_MS = 200

# Délai, en secondes, entre deux rafraîchissements dus au seul passage du
# temps (marqueur « (ancien) »).
INTERVALLE_REVEIL_S = 60


def couper_crochet_saisie() -> None:
    """Empêche input() d'appeler Tkinter depuis un autre fil d'exécution.

    Créer une fenêtre Tk installe un crochet de saisie (PyOS_InputHook)
    que input() appelle dans un terminal pour faire vivre la fenêtre
    pendant l'attente. Appelé depuis le fil de l'interface texte, il
    touche à Tcl hors du fil principal et fait planter le programme
    (« Notifier not initialized »). Ici la fenêtre vit dans sa propre
    boucle (mainloop) : le crochet est inutile.

    PRE : aucune.
    POST : input() n'appelle plus Tkinter. Ne modifie rien d'autre.
    """
    crochet = ctypes.c_void_p.in_dll(ctypes.pythonapi, "PyOS_InputHook")
    crochet.value = None


class VueDashboardTk:
    """Fenêtre Tkinter qui affiche le tableau des sites, sans le calculer.

    INVARIANT : la fenêtre n'a que deux boutons de test et aucun champ de
    saisie ; seul le fil d'exécution qui a créé la vue (celui de
    boucler) touche aux éléments Tkinter. Les autres fils passent par
    afficher et afficher_message.
    """

    def __init__(self, titre: str) -> None:
        """Crée la fenêtre et son tableau vide.

        PRE : le fil d'exécution appelant est celui qui appellera boucler.
        POST : la fenêtre est créée avec le titre donné, mais pas encore
               affichée à l'écran avant boucler.
               Exception tkinter.TclError : si aucun affichage graphique
               n'est disponible.
        """
        self.__racine = tk.Tk()
        couper_crochet_saisie()
        self.__racine.title(titre)
        style = ttk.Style(self.__racine)
        style.configure("Treeview", font=("TkDefaultFont", 16),
                        rowheight=36)
        style.configure("Treeview.Heading", font=("TkDefaultFont", 16, "bold"))
        self.__tableau = ttk.Treeview(
            self.__racine, columns=COLONNES, show="headings",
            selectmode="browse",
        )
        for colonne in COLONNES:
            self.__tableau.heading(colonne, text=colonne)
            self.__tableau.column(colonne, width=200, anchor="w")
        for couleur, fond in FONDS.items():
            self.__tableau.tag_configure(
                couleur, background=fond, foreground="black"
            )
        self.__tableau.pack(fill="both", expand=True)
        self.__bouton_site = ttk.Button(
            self.__racine, text="Tester le site sélectionné"
        )
        self.__bouton_tous = ttk.Button(
            self.__racine, text="Tester tous les sites"
        )
        self.__message = tk.StringVar()
        barre = ttk.Frame(self.__racine)
        self.__bouton_site.pack(in_=barre, side="left", padx=8, pady=8)
        self.__bouton_tous.pack(in_=barre, side="left", pady=8)
        ttk.Label(barre, textvariable=self.__message).pack(
            side="left", padx=16
        )
        barre.pack(fill="x")
        self.__messages: queue.Queue[str] = queue.Queue()
        self.__a_afficher: queue.Queue[tuple[LigneDashboard, ...]] = (
            queue.Queue()
        )
        self.__arret = threading.Event()

    def definir_actions(
        self,
        tester_site: Callable[[str | None], None],
        tester_tous: Callable[[], None],
    ) -> None:
        """Relie les deux boutons aux demandes de test du présentateur.

        PRE : aucune.
        POST : « Tester le site sélectionné » appelle tester_site avec le
               nom du site sélectionné dans le tableau (None si aucun) ;
               « Tester tous les sites » appelle tester_tous. Les deux
               sont appelées dans le fil de la fenêtre et doivent rendre
               la main tout de suite.
        """
        self.__bouton_site.configure(
            command=lambda: tester_site(self.__nom_selectionne())
        )
        self.__bouton_tous.configure(command=tester_tous)

    def afficher_message(self, texte: str) -> None:
        """Demande l'affichage d'un message, depuis n'importe quel fil.

        PRE : aucune.
        POST : texte sera affiché sous le tableau à la prochaine lecture
               (au plus INTERVALLE_LECTURE_MS plus tard), à la place du
               message précédent. Ne touche pas à Tkinter.
        """
        self.__messages.put(texte)

    def afficher(self, lignes: tuple[LigneDashboard, ...]) -> None:
        """Demande l'affichage de ces lignes, depuis n'importe quel fil.

        PRE : aucune.
        POST : lignes remplacera le contenu du tableau à la prochaine
               lecture (au plus INTERVALLE_LECTURE_MS plus tard). Ne
               touche pas à Tkinter : peut être appelée depuis un autre
               fil que celui de la fenêtre.
        """
        self.__a_afficher.put(lignes)

    def boucler(
        self,
        rappel_reveil: Callable[[], None],
        intervalle_s: int,
        arret: threading.Event,
    ) -> None:
        """Affiche la fenêtre et la fait vivre jusqu'à sa fermeture.

        PRE : aucune.
        POST : affiche la fenêtre et ne rend la main que lorsque
               l'utilisatrice la ferme ou que arret est déclenché (par
               n'importe quel fil). Appelle rappel_reveil, dans le fil
               de la fenêtre, toutes les intervalle_s secondes.
        """
        self.__arret = arret
        self.__lire()
        self.__reveiller(rappel_reveil, intervalle_s)
        self.__racine.mainloop()

    def __lire(self) -> None:
        """Affiche les dernières lignes reçues, puis se reprogramme.

        Ferme la fenêtre si l'arrêt a été demandé.
        """
        if self.__arret.is_set():
            # Planifié, pas appelé directement : quit() est sans effet
            # tant que la boucle de la fenêtre n'a pas démarré.
            self.__racine.after(0, self.__racine.quit)
            return
        lignes = None
        while not self.__a_afficher.empty():
            lignes = self.__a_afficher.get()
        if lignes is not None:
            self.__dessiner(lignes)
        while not self.__messages.empty():
            self.__message.set(self.__messages.get())
        self.__racine.after(INTERVALLE_LECTURE_MS, self.__lire)

    def __reveiller(
        self, rappel_reveil: Callable[[], None], intervalle_s: int
    ) -> None:
        """Appelle rappel_reveil, puis se reprogramme."""
        rappel_reveil()
        self.__racine.after(
            intervalle_s * 1000,
            lambda: self.__reveiller(rappel_reveil, intervalle_s),
        )

    def __nom_selectionne(self) -> str | None:
        """Renvoie le nom du site sélectionné, ou None s'il n'y en a pas."""
        selection = self.__tableau.selection()
        if len(selection) == 0:
            return None
        return str(self.__tableau.item(selection[0])["values"][0])

    def __dessiner(self, lignes: tuple[LigneDashboard, ...]) -> None:
        """Remplace le contenu du tableau par ces lignes.

        La sélection est conservée : la ligne du même site est
        sélectionnée de nouveau.
        """
        nom_selectionne = self.__nom_selectionne()
        self.__tableau.delete(*self.__tableau.get_children())
        for ligne in lignes:
            ligne_tableau = self.__tableau.insert(
                "", "end", values=ligne.cellules, tags=(ligne.couleur,)
            )
            if ligne.cellules[0] == nom_selectionne:
                self.__tableau.selection_set(ligne_tableau)


def lancer(
    registre: RegistreSites,
    testeurs: list[Testeur],
    config: ConfigurationTests,
    horloge: Callable[[], datetime],
    arret: threading.Event,
    apres_ouverture: Callable[[], None],
) -> None:
    """Ouvre le dashboard et le garde à jour jusqu'à sa fermeture.

    arret permet à un autre fil d'exécution (l'interface active) de
    fermer la fenêtre en le déclenchant. apres_ouverture est appelée une
    fois la fenêtre créée, juste avant la boucle : c'est là que
    l'appelant démarre son interface active, qui ne doit pas saisir de
    texte avant que la fenêtre existe (voir couper_crochet_saisie).

    PRE : doit être appelée depuis le fil d'exécution principal (exigence
          de Tkinter) ; config.timeout_s > 0.
    POST : affiche une fenêtre qui montre l'état des sites (EF-02.1) et
           se rafraîchit à chaque changement du registre (EF-02.3) ainsi
           que toutes les INTERVALLE_REVEIL_S secondes. Ses boutons
           lancent des batteries de tests manuelles (EF-03.1, EF-03.4)
           avec testeurs. Ne rend la main que lorsque l'utilisatrice
           ferme la fenêtre ou que arret est déclenché. Modifie les
           sites testés (nouvelles batteries).
           Exception tkinter.TclError : si aucun affichage graphique
           n'est disponible.
    """
    vue = VueDashboardTk("Surveillance des sites")
    presentateur = PresentateurDashboard(
        registre, testeurs, vue.afficher, vue.afficher_message, config,
        horloge,
    )
    vue.definir_actions(presentateur.tester_site, presentateur.tester_tous)
    apres_ouverture()
    vue.boucler(presentateur.rafraichir, INTERVALLE_REVEIL_S, arret)
