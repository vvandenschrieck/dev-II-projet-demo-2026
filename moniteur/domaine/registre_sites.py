"""Registre des sites : point d'entrée unique du domaine."""

from moniteur.domaine.site import Site


class RegistreSites:
    """Ensemble des sites surveillés, identifiés par leur nom.

    Le registre crée les sites et garantit l'unicité de leur nom
    (EF-01.1, EF-01.2). La comparaison des noms ne tient pas compte de
    la casse : « ClientABC » et « clientabc » désignent le même site.
    """

    def __init__(self) -> None:
        """Crée un registre vide."""
        self.__sites: list[Site] = []

    @property
    def sites(self) -> tuple[Site, ...]:
        """Sites du registre, dans l'ordre de leur ajout (EF-02.1)."""
        return tuple(self.__sites)

    def ajouter_site(self, nom: str, uri_principale: str) -> Site:
        """Crée un site, l'ajoute au registre et le renvoie (EF-01.1).

        Lève ValueError si un site du même nom existe déjà, sans tenir
        compte de la casse (EF-01.2), ou si le nom ou l'URI principale
        est vide (EF-01.3).
        """
        site = Site(nom, uri_principale)
        existant = self.__chercher(site.nom)
        if existant is not None:
            raise ValueError(
                f"Un site nommé « {existant.nom} » existe déjà (EF-01.2)."
            )
        self.__sites.append(site)
        return site

    def site(self, nom: str) -> Site:
        """Renvoie le site qui porte ce nom, sans tenir compte de la casse.

        Lève ValueError si aucun site ne porte ce nom.
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
    from moniteur.domaine.enumerations import StatutDisponibilite, Verdict
    from moniteur.domaine.mesure import Mesure
    from moniteur.domaine.testeur import Testeur

    INSTANT = datetime(2026, 10, 17, 14, 30)

    def fausse_horloge() -> datetime:
        """Horloge de test : renvoie toujours le même instant."""
        return INSTANT

    class FauxTesteur(Testeur):
        """Testeur de test : renvoie toujours une mesure OK, sans réseau."""

        def executer(
            self, site: Site, timeout_s: float, horodatage: datetime
        ) -> list[Mesure]:
            """Renvoie une seule mesure OK, datée de l'horodatage reçu."""
            return [Mesure(horodatage, Verdict.OK, 0.1, "200")]

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

    print("Scénario : site(\"clientabc\") retrouve « ClientABC »")
    attendu = "ClientABC"
    obtenu = registre.site("clientabc").nom
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : recherche d'un site inconnu")
    attendu = "ValueError"
    try:
        registre.site("Inconnu")
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
            [FauxTesteur()], ConfigurationTests(5.0), fausse_horloge
        )
    attendu = [StatutDisponibilite.DISPONIBLE, StatutDisponibilite.DISPONIBLE]
    obtenu = [site.statut_disponibilite for site in registre.sites]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
