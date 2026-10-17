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

from moniteur.domaine.enumerations import Verdict
from moniteur.domaine.mesure import Mesure
from moniteur.domaine.site import Site
from moniteur.domaine.testeur import Testeur

DELAI_DEPASSE = "délai dépassé"


class TesteurHttp(Testeur):
    """Testeur applicatif : envoie une requête GET sur l'URI principale.

    Les redirections ne sont pas suivies et une réponse 3xx compte comme
    un succès (Q-03). La durée mesurée s'arrête à la première réponse du
    serveur. Le code HTTP est conservé en diagnostic (page MVP,
    section 2.1).
    """

    def executer(
        self, site: Site, timeout_s: float, horodatage: datetime
    ) -> list[Mesure]:
        """Teste l'URI principale du site et renvoie une seule mesure.

        Réponse 2xx ou 3xx : verdict OK. Réponse 4xx ou 5xx : verdict KO
        (RM-03). Dans ces deux cas, la mesure contient la durée et le
        code HTTP. Si aucune réponse n'est reçue (nom introuvable,
        connexion refusée, erreur TLS, délai dépassé, EF-03.5), la
        mesure est KO, sans durée, avec la nature de l'erreur. Aucune
        exception n'est propagée : un site injoignable n'est pas une
        erreur du programme.
        """
        try:
            code, duree_s = self.__envoyer_get(
                site.uri_principale, timeout_s
            )
            if code < 400:
                verdict = Verdict.OK
            else:
                verdict = Verdict.KO
            return [Mesure(horodatage, verdict, duree_s, str(code))]
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
        return [Mesure(horodatage, Verdict.KO, None, diagnostic)]

    def __envoyer_get(self, uri: str, timeout_s: float) -> tuple[int, float]:
        """Envoie une requête GET et renvoie le code HTTP et la durée.

        La durée, en secondes, va de l'envoi de la requête à la
        réception de la première réponse (Q-03). Les erreurs réseau
        sont propagées sous forme d'exceptions.
        """
        parties = urlsplit(uri)
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
    # Ces scénarios interrogent de vrais sites : ils demandent une
    # connexion à Internet et leurs résultats peuvent varier si un site
    # change de comportement.
    testeur = TesteurHttp()
    instant = datetime(2026, 10, 17, 14, 30)

    def tester(uri: str, timeout_s: float = 5.0) -> Mesure:
        """Teste un site fictif d'URI donnée et renvoie sa mesure."""
        return testeur.executer(Site("Test", uri), timeout_s, instant)[0]

    print("Scénario : site qui répond 200 : verdict OK (critère 4)")
    attendu = Verdict.OK
    obtenu = tester("https://www.google.com").verdict
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : site qui répond : durée jusqu'à la première réponse "
          "enregistrée (Q-03)")
    attendu = True
    obtenu = tester("https://www.google.com").duree_s is not None
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : redirection 301 non suivie : verdict OK "
          "(critère 5, Q-03)")
    attendu = Verdict.OK
    obtenu = tester("http://google.com").verdict
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : redirection 301 : code 301 en diagnostic "
          "(critère 5)")
    attendu = "301"
    obtenu = tester("http://google.com").diagnostic
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : page qui répond 404 : verdict KO (critère 6)")
    attendu = Verdict.KO
    uri_404 = "https://www.google.com/page-inexistante-ephec"
    obtenu = tester(uri_404).verdict
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : nom de domaine inexistant (critère 7)")
    attendu = "nom de domaine introuvable"
    obtenu = tester("https://site-inexistant.invalid").diagnostic
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    # httpbin.org/delay/10 attend 10 secondes avant de répondre : avec
    # un délai maximal de 2 secondes, la réponse arrive trop tard.
    print("Scénario : serveur trop lent : diagnostic « délai dépassé » "
          "(critère 8, EF-03.5)")
    attendu = DELAI_DEPASSE
    obtenu = tester("https://httpbin.org/delay/10", timeout_s=2.0).diagnostic
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : certificat expiré : diagnostic « erreur TLS »")
    attendu = "erreur TLS"
    obtenu = tester("https://expired.badssl.com").diagnostic
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
