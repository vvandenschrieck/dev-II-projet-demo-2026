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
from moniteur.domaine.site import Site
from moniteur.domaine.testeur import Testeur

DELAI_DEPASSE = "délai dépassé"


class TesteurHttp(Testeur):
    """Testeur applicatif : envoie une requête GET sur l'URI principale.

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
        """Teste l'URI principale du site et renvoie une seule mesure.

        Un site injoignable n'est pas une erreur du programme : il donne
        une mesure KO (EF-03.1, EF-03.5).

        PRE : timeout_s > 0.
        POST : envoie une requête GET à l'URI principale du site et
               renvoie une liste d'une seule mesure, de couche L7 et
               datée de horodatage :
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
        try:
            code, duree_s = self.__envoyer_get(
                site.uri_principale, timeout_s
            )
            if code < 400:
                verdict = Verdict.OK
            else:
                verdict = Verdict.KO
            return [
                Mesure(horodatage, self.couche, verdict, duree_s, str(code))
            ]
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
        return [
            Mesure(horodatage, self.couche, Verdict.KO, None, diagnostic)
        ]

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
