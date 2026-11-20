"""Testeur HTTP : vérifie qu'un site répond à une requête GET."""

import socket
import ssl
import time
from datetime import datetime
from http.client import (
    HTTPConnection,
    HTTPException,
    HTTPSConnection,
    InvalidURL,
)
from urllib.parse import urlsplit

from moniteur.domaine.enumerations import Couche, Verdict
from moniteur.domaine.mesure import Mesure
from moniteur.domaine.page import Page
from moniteur.domaine.site import Site
from moniteur.domaine.testeur import Testeur

DELAI_DEPASSE = "délai dépassé"


class TesteurHttp(Testeur):
    """Testeur applicatif : envoie une requête GET sur chaque page du site.

    Les redirections ne sont pas suivies et une réponse 3xx compte comme
    un succès (Q-03). La durée mesurée s'arrête à la première réponse du
    serveur. Le code HTTP est conservé en diagnostic (page MVP,
    section 2.1).

    INVARIANT : la couche testée est toujours L7.
    """

    @property
    def couche(self) -> Couche:
        """Donne la couche testée.

        PRE : aucune.
        POST : renvoie Couche.L7. Ne modifie rien.
        """
        return Couche.L7

    def executer(
        self, site: Site, timeout_s: float, horodatage: datetime
    ) -> list[Mesure]:
        """Teste chaque page du site et renvoie une mesure par page.

        Un site injoignable n'est pas une erreur du programme : il donne
        une mesure KO (EF-03.1, EF-03.5). Une page en erreur
        n'empêche pas de tester les suivantes (RM-04).

        PRE : timeout_s > 0.
        POST : envoie une requête GET à l'URI de chaque page du site, la
               page principale en premier, et renvoie une liste d'une
               mesure par page, dans l'ordre des pages. Chaque mesure
               est de couche L7, datée de horodatage et porte sa page :
               - réponse 2xx ou 3xx : verdict OK ; réponse 4xx ou 5xx :
                 verdict KO (RM-03). Dans les deux cas, la mesure
                 contient la durée jusqu'à la première réponse et le
                 code HTTP en diagnostic ;
               - aucune réponse (nom introuvable, connexion refusée,
                 erreur TLS, délai dépassé, schéma non pris en charge,
                 URI mal formée) : verdict KO, durée None, diagnostic
                 donnant la nature de l'erreur.
               Ne modifie ni site ni les autres paramètres.
        """
        return [
            self.__mesurer_page(page, timeout_s, horodatage)
            for page in site.pages
        ]

    def __mesurer_page(
        self, page: Page, timeout_s: float, horodatage: datetime
    ) -> Mesure:
        """Envoie une requête GET à une page et renvoie sa mesure."""
        try:
            code, duree_s = self.__envoyer_get(page.uri, timeout_s)
            if code < 400:
                verdict = Verdict.OK
            else:
                verdict = Verdict.KO
            return Mesure(
                horodatage, self.couche, verdict, duree_s, str(code), page
            )
        except TimeoutError:
            diagnostic = DELAI_DEPASSE
        except socket.gaierror:
            diagnostic = "nom de domaine introuvable"
        except ConnectionRefusedError:
            diagnostic = "connexion refusée"
        except ssl.SSLError:
            diagnostic = "erreur TLS"
        except (OSError, HTTPException) as erreur:
            diagnostic = f"connexion impossible : {erreur}"
        return Mesure(
            horodatage, self.couche, Verdict.KO, None, diagnostic, page
        )

    def __envoyer_get(self, uri: str, timeout_s: float) -> tuple[int, float]:
        """Envoie une requête GET et renvoie le code HTTP et la durée.

        La durée, en secondes, va de l'envoi de la requête à la
        réception de la première réponse (Q-03). Les erreurs réseau
        sont propagées sous forme d'exceptions.
        """
        try:
            parties = urlsplit(uri)
        except ValueError as erreur:
            raise InvalidURL(f"URI invalide ({erreur})") from erreur
        chemin = parties.path or "/"
        if parties.query:
            chemin = chemin + "?" + parties.query
        if parties.scheme == "https":
            connexion = HTTPSConnection(parties.netloc, timeout=timeout_s)
        elif parties.scheme == "http":
            connexion = HTTPConnection(parties.netloc, timeout=timeout_s)
        else:
            raise InvalidURL(f"schéma non pris en charge ({parties.scheme})")
        try:
            debut = time.perf_counter()
            connexion.request("GET", chemin)
            reponse = connexion.getresponse()
            return reponse.status, time.perf_counter() - debut
        finally:
            connexion.close()


if __name__ == "__main__":
    # Les scénarios utilisent un serveur HTTP local (127.0.0.1) : la page
    # « /absente » répond 404, toutes les autres répondent 200.
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        """Serveur de test : 404 pour « /absente », 200 pour le reste."""

        def do_GET(self) -> None:
            """Répond à une requête GET, sans corps de réponse."""
            self.send_response(404 if self.path == "/absente" else 200)
            self.end_headers()

        def log_message(self, *arguments: object) -> None:
            """Ne rien écrire dans la console."""

    serveur = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{serveur.server_port}"

    site = Site("Test", base + "/")
    site.ajouter_page("Absente", base + "/absente")
    site.ajouter_page("Contact", base + "/contact")
    mesures = TesteurHttp().executer(site, 2.0, datetime(2026, 11, 20, 10, 0))

    print("Scénario : une mesure par page, dans l'ordre, avec sa page "
          "(RM-07)")
    attendu = ["Page d'accueil", "Absente", "Contact"]
    obtenu = [mesure.page.nom for mesure in mesures]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : une page en 404 n'empêche pas de tester la "
          "suivante (RM-04)")
    attendu = [(Verdict.OK, "200"), (Verdict.KO, "404"),
               (Verdict.OK, "200")]
    obtenu = [(mesure.verdict, mesure.diagnostic) for mesure in mesures]
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    serveur.shutdown()
