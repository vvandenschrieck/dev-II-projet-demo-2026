"""Site : site web surveillé, avec l'historique de ses batteries."""

from moniteur.domaine.batterie_tests import BatterieTests

SCHEMA_PAR_DEFAUT = "https://"


class Site:
    """Site web de la cliente, identifié par son nom.

    Un site est défini par un nom et une URI principale (EF-01.1). Il
    conserve l'historique des batteries de tests lancées sur lui.
    """

    def __init__(self, nom: str, uri_principale: str) -> None:
        """Crée un site à partir de son nom et de son URI principale.

        Les espaces au début et à la fin sont retirés. Une URI sans
        schéma (« exemple.be ») reçoit « https:// » par défaut.
        Lève ValueError si le nom ou l'URI principale est vide
        (EF-01.3).
        """
        nom = nom.strip()
        uri_principale = uri_principale.strip()
        if nom == "":
            raise ValueError("Le nom du site ne peut pas être vide.")
        if uri_principale == "":
            raise ValueError(
                "L'URI principale du site ne peut pas être vide (EF-01.3)."
            )
        if "://" not in uri_principale:
            uri_principale = SCHEMA_PAR_DEFAUT + uri_principale
        self.__nom = nom
        self.__uri_principale = uri_principale
        self.__historique: list[BatterieTests] = []

    @property
    def nom(self) -> str:
        """Nom du site, tel qu'il a été saisi."""
        return self.__nom

    @property
    def uri_principale(self) -> str:
        """URI principale du site, avec son schéma (http:// ou https://)."""
        return self.__uri_principale

    @property
    def derniere_batterie(self) -> BatterieTests | None:
        """Dernière batterie lancée sur le site, ou None s'il n'a
        jamais été testé (EF-02.2).
        """
        if len(self.__historique) == 0:
            return None
        return self.__historique[-1]


if __name__ == "__main__":
    site = Site("ClientABC", "https://clientabc.be")

    print("Scénario : création d'un site : nom conservé (critère 1)")
    attendu = "ClientABC"
    obtenu = site.nom
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : création d'un site : URI principale conservée")
    attendu = "https://clientabc.be"
    obtenu = site.uri_principale
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : site neuf : aucune batterie, donc pas d'horodatage "
          "(critère 1)")
    attendu = None
    obtenu = site.derniere_batterie
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : URI sans schéma : « https:// » ajouté par défaut")
    attendu = "https://clientabc.be"
    obtenu = Site("ClientABC", "clientabc.be").uri_principale
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : URI en http:// : schéma conservé")
    attendu = "http://clientabc.be"
    obtenu = Site("ClientABC", "http://clientabc.be").uri_principale
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    site_espaces = Site("  ClientABC ", " https://clientabc.be  ")

    print("Scénario : espaces autour du nom retirés")
    attendu = "ClientABC"
    obtenu = site_espaces.nom
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : espaces autour de l'URI principale retirés")
    attendu = "https://clientabc.be"
    obtenu = site_espaces.uri_principale
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

    print("Scénario : nom composé uniquement d'espaces")
    attendu = "ValueError"
    try:
        Site("   ", "https://clientabc.be")
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

    print("Scénario : URI principale composée uniquement d'espaces "
          "(EF-01.3)")
    attendu = "ValueError"
    try:
        Site("ClientABC", "   ")
        obtenu = "aucune erreur"
    except ValueError:
        obtenu = "ValueError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
