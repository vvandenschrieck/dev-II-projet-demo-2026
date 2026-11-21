"""Registre des sites : point d'entrée unique du domaine."""

from collections.abc import Callable

from moniteur.domaine.site import Site


class RegistreSites:
    """Ensemble des sites surveillés, identifiés par leur nom.

    Le registre crée et modifie les sites, et garantit l'unicité de leur
    nom (EF-01.1, EF-01.2). La comparaison des noms ne tient pas compte de
    la casse : « ClientABC » et « clientabc » désignent le même site.

    INVARIANT : deux sites du registre ne portent jamais le même nom,
    à la casse près ; les sites sont conservés dans l'ordre de leur
    ajout ;
    les rappels abonnés sont appelés après chaque changement d'état du
    registre ou de l'un de ses sites (patron Observer).
    """

    def __init__(self) -> None:
        """Crée un registre vide.

        PRE : aucune.
        POST : le registre est créé, sans aucun site.
        """
        self.__sites: list[Site] = []
        self.__observateurs: list[Callable[[], None]] = []

    def abonner(self, rappel: Callable[[], None]) -> None:
        """Abonne un rappel aux changements d'état du registre (EF-02.3).

        Le registre relaie ses propres changements (ajout d'un site) et
        ceux de ses sites (modification, pages, batteries de tests).

        PRE : aucune.
        POST : rappel est ajouté à la fin des abonnés ; il sera appelé,
               sans argument, dans le fil d'exécution de l'appelant,
               après chaque changement. Un refus métier (ValueError) ne
               déclenche aucun appel. Rien d'autre n'est modifié.
        """
        self.__observateurs.append(rappel)

    def __notifier(self) -> None:
        """Appelle chaque rappel abonné, une fois l'état cohérent."""
        for rappel in tuple(self.__observateurs):
            rappel()

    @property
    def sites(self) -> tuple[Site, ...]:
        """Donne les sites du registre, dans l'ordre de leur ajout (EF-02.1).

        PRE : aucune.
        POST : renvoie un tuple des sites (copie : le code extérieur ne
               peut pas modifier la liste interne). Ne modifie rien.
        """
        return tuple(self.__sites)

    def ajouter_site(self, nom: str, uri_principale: str) -> Site:
        """Crée un site, l'ajoute au registre et le renvoie (EF-01.1).

        PRE : aucune.
        POST : renvoie le site créé, qui est ajouté à la fin du
               registre. Une URI sans schéma reçoit « https:// ».
               Exception ValueError : si un site du même nom existe déjà,
               sans tenir compte de la casse (EF-01.2).
               Exception ValueError : si le nom est vide.
               Exception ValueError : si l'URI principale est vide
               (EF-01.3).
               Si une exception est levée, le registre n'est pas modifié.
        """
        site = Site(nom, uri_principale)
        existant = self.__chercher(site.nom)
        if existant is not None:
            raise ValueError(
                f"Un site nommé « {existant.nom} » existe déjà."
            )
        site.abonner(self.__notifier)
        self.__sites.append(site)
        self.__notifier()
        return site

    def modifier_site(
        self, nom: str, nouveau_nom: str, nouvelle_uri: str
    ) -> None:
        """Change le nom et l'URI principale d'un site (EF-01.2, EF-01.3).

        Un site peut garder son propre nom, avec une autre casse par
        exemple : il n'est pas en conflit avec lui-même.

        PRE : aucune.
        POST : le site qui porte le nom donné a le nouveau nom et la
               nouvelle URI principale, et l'URI de sa page principale
               suit (les espaces de bord sont retirés, une URI sans
               schéma reçoit « https:// »). Sa position dans le registre,
               ses pages et ses batteries ne changent pas.
               Exception ValueError : si aucun site ne porte le nom
               donné.
               Exception ValueError : si un autre site porte déjà le
               nouveau nom, sans tenir compte de la casse (EF-01.2).
               Exception ValueError : si le nouveau nom est vide.
               Exception ValueError : si la nouvelle URI est vide
               (EF-01.3).
               Exception ValueError : si une autre page du site a déjà
               cette URI (EF-01.6).
               Si une exception est levée, aucun site n'est modifié.
        """
        site = self.trouver_site(nom)
        existant = self.__chercher(nouveau_nom)
        if existant is not None and existant is not site:
            raise ValueError(
                f"Un site nommé « {existant.nom} » existe déjà."
            )
        site.modifier(nouveau_nom, nouvelle_uri)

    def trouver_site(self, nom: str) -> Site:
        """Trouve le site qui porte ce nom, sans tenir compte de la casse.

        PRE : aucune.
        POST : renvoie le site du registre dont le nom correspond à nom
               (casse et espaces de début et de fin ignorés). Ne modifie
               rien.
               Exception ValueError : si aucun site ne porte ce nom.
        """
        site = self.__chercher(nom)
        if site is None:
            raise ValueError(f"Aucun site nommé « {nom.strip()} ».")
        return site

    def __chercher(self, nom: str) -> Site | None:
        """Renvoie le site qui porte ce nom, ou None s'il n'existe pas."""
        nom_cherche = nom.strip().lower()
        for site in self.__sites:
            if site.nom.lower() == nom_cherche:
                return site
        return None


if __name__ == "__main__":
    from datetime import datetime

    from moniteur.domaine.configuration_tests import ConfigurationTests
    from moniteur.domaine.enumerations import (
        Couche,
        Declenchement,
        StatutDisponibilite,
        Verdict,
    )
    from moniteur.domaine.mesure import Mesure
    from moniteur.domaine.testeur import Testeur

    INSTANT = datetime(2026, 10, 17, 14, 30)

    def fausse_horloge() -> datetime:
        """Horloge de test : renvoie toujours le même instant."""
        return INSTANT

    class FauxTesteur(Testeur):
        """Testeur de test : renvoie toujours une mesure OK, sans réseau."""

        @property
        def couche(self) -> Couche:
            """Donne la couche simulée (L7)."""
            return Couche.L7

        def executer(
            self, site: Site, timeout_s: float, horodatage: datetime
        ) -> list[Mesure]:
            """Renvoie une seule mesure OK, datée de l'horodatage reçu."""
            return [Mesure(horodatage, self.couche, Verdict.OK, 0.1, "200")]

    registre = RegistreSites()
    registre.ajouter_site("ClientABC", "clientabc.be")

    print("Scénario : ajout du site « ClientABC » : il apparaît dans la "
          "liste (critère 1)")
    attendu = ["ClientABC"]
    obtenu = [site.nom for site in registre.sites]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : ajout d'un second site nommé « ClientABC » "
          "(critère 2, EF-01.2)")
    attendu = "ValueError"
    try:
        registre.ajouter_site("ClientABC", "autre-site.be")
        obtenu = "aucune erreur"
    except ValueError:
        obtenu = "ValueError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : ajout de « clientabc » : même nom à la casse près "
          "(EF-01.2)")
    attendu = "ValueError"
    try:
        registre.ajouter_site("clientabc", "autre-site.be")
        obtenu = "aucune erreur"
    except ValueError:
        obtenu = "ValueError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : après ces refus, le registre contient toujours un "
          "seul site")
    attendu = 1
    obtenu = len(registre.sites)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : trouver_site(\"clientabc\") retrouve « ClientABC »")
    attendu = "ClientABC"
    obtenu = registre.trouver_site("clientabc").nom
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : recherche d'un site inconnu")
    attendu = "ValueError"
    try:
        registre.trouver_site("Inconnu")
        obtenu = "aucune erreur"
    except ValueError:
        obtenu = "ValueError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    # Le test de tous les sites (EF-03.4) est une boucle écrite dans
    # chaque interface : ce scénario montre cette boucle.
    print("Scénario : test de l'ensemble des sites : chaque statut est "
          "mis à jour (critère 9, EF-03.4)")
    registre.ajouter_site("ClientXYZ", "clientxyz.be")
    for site in registre.sites:
        site.lancer_batterie(
            [FauxTesteur()],
            ConfigurationTests(5.0),
            Declenchement.MANUEL,
            fausse_horloge,
        )
    attendu = [StatutDisponibilite.DISPONIBLE, StatutDisponibilite.DISPONIBLE]
    obtenu = [site.statut_disponibilite for site in registre.sites]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    registre_modif = RegistreSites()
    registre_modif.ajouter_site("ClientABC", "clientabc.be")
    registre_modif.ajouter_site("ClientXYZ", "clientxyz.be")

    def essayer_modification(nom: str, nouveau: str, uri: str) -> str:
        """Tente de modifier un site : renvoie « ok » ou « ValueError »."""
        try:
            registre_modif.modifier_site(nom, nouveau, uri)
            return "ok"
        except ValueError:
            return "ValueError"

    def noms_et_uri() -> list[tuple[str, str]]:
        """Renvoie le nom et l'URI principale de chaque site."""
        return [(s.nom, s.uri_principale) for s in registre_modif.sites]

    print("Scénario : modification du nom et de l'URI d'un site "
          "(EF-01.2, EF-01.3)")
    resultat = essayer_modification("ClientABC", "ClientDEF", "clientdef.be")
    attendu = ("ok", [("ClientDEF", "https://clientdef.be"),
                      ("ClientXYZ", "https://clientxyz.be")])
    obtenu = (resultat, noms_et_uri())
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : renommer un site avec le nom d'un autre, à la casse "
          "près : refusé, rien ne change (EF-01.2)")
    resultat = essayer_modification("ClientDEF", "clientxyz", "autre.be")
    attendu = ("ValueError", [("ClientDEF", "https://clientdef.be"),
                              ("ClientXYZ", "https://clientxyz.be")])
    obtenu = (resultat, noms_et_uri())
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : un site garde son propre nom, avec une autre casse "
          "(pas de conflit avec lui-même)")
    resultat = essayer_modification("ClientDEF", "CLIENTDEF", "clientdef.be")
    attendu = ("ok", "CLIENTDEF")
    obtenu = (resultat, registre_modif.sites[0].nom)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : modification d'un site inconnu")
    attendu = "ValueError"
    obtenu = essayer_modification("Inconnu", "Nouveau", "nouveau.be")
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    # Patron Observer : un simple compteur tient lieu de vue (EF-02.3).
    registre_obs = RegistreSites()
    notifications: list[int] = []
    registre_obs.abonner(lambda: notifications.append(1))

    print("Scénario : l'ajout d'un site notifie l'observateur une fois "
          "(EF-02.3)")
    site_obs = registre_obs.ajouter_site("ClientABC", "clientabc.be")
    attendu = 1
    obtenu = len(notifications)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : un refus métier ne notifie personne : l'état n'a "
          "pas changé")
    try:
        registre_obs.ajouter_site("clientabc", "autre.be")
    except ValueError:
        pass
    attendu = 1
    obtenu = len(notifications)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : un test lancé directement sur le site notifie le "
          "registre (test périodique ou manuel)")
    site_obs.lancer_batterie(
        [FauxTesteur()],
        ConfigurationTests(5.0),
        Declenchement.PERIODIQUE,
        fausse_horloge,
    )
    attendu = 2
    obtenu = len(notifications)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : la modification d'un site notifie une seule fois")
    registre_obs.modifier_site("ClientABC", "ClientDEF", "clientdef.be")
    attendu = 3
    obtenu = len(notifications)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
