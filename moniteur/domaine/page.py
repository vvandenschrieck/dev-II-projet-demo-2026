"""Page : page web d'un site, identifiée par un nom et une URI."""

SCHEMA_PAR_DEFAUT = "https://"


class Page:
    """Page web d'un site, définie par un nom et une URI (EF-01.4).

    La page principale d'un site porte le nom « Page d'accueil » et
    l'URI principale du site (EF-01.1). L'unicité des noms et des URI
    au sein d'un site est garantie par le site (EF-01.4, EF-01.6).

    INVARIANT :
    - le nom et l'URI ne sont jamais vides, sans espace au début ni à
      la fin, et ne changent jamais ;
    - l'URI porte toujours un schéma.
    """

    def __init__(self, nom: str, uri: str) -> None:
        """Crée une page à partir de son nom et de son URI.

        PRE : aucune.
        POST : la page est créée. Les espaces au début et à la fin de
               nom et de uri sont retirés. Une URI sans schéma
               (« exemple.be/contact ») reçoit « https:// » par défaut.
               Exception ValueError : si le nom est vide.
               Exception ValueError : si l'URI est vide.
        """
        nom = nom.strip()
        uri = uri.strip()
        if nom == "":
            raise ValueError("Le nom de la page ne peut pas être vide.")
        if uri == "":
            raise ValueError("L'URI de la page ne peut pas être vide.")
        if "://" not in uri:
            uri = SCHEMA_PAR_DEFAUT + uri
        self.__nom = nom
        self.__uri = uri

    @property
    def nom(self) -> str:
        """Donne le nom de la page.

        PRE : aucune.
        POST : renvoie le nom de la page, tel qu'il a été saisi (sans
               les espaces de début et de fin). Ne modifie rien.
        """
        return self.__nom

    @property
    def uri(self) -> str:
        """Donne l'URI de la page.

        PRE : aucune.
        POST : renvoie l'URI de la page, avec son schéma. Ne modifie
               rien.
        """
        return self.__uri


if __name__ == "__main__":
    def verifier(attendu: object, obtenu: object) -> None:
        """Affiche attendu et obtenu, puis le verdict du scénario."""
        print(f"  attendu : {attendu}")
        print(f"  obtenu  : {obtenu}")
        print("  → OK" if obtenu == attendu else "  → ÉCHEC")
        print("-" * 40)

    print("Scénario : une URI sans schéma reçoit « https:// »")
    verifier("https://exemple.be/contact",
             Page("Contact", "exemple.be/contact").uri)

    print("Scénario : les espaces de début et de fin sont retirés")
    page = Page("  Contact ", " https://exemple.be ")
    verifier(("Contact", "https://exemple.be"), (page.nom, page.uri))

    print("Scénario : création d'une page avec une URI vide (EF-01.3)")
    try:
        Page("Contact", "   ")
        obtenu = "aucune exception"
    except ValueError:
        obtenu = "ValueError"
    verifier("ValueError", obtenu)
