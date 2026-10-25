"""Testeur TCP : vérifie qu'un port du site accepte une connexion."""

import socket
import time
from datetime import datetime
from urllib.parse import urlsplit

from moniteur.domaine.enumerations import Couche, Verdict
from moniteur.domaine.mesure import Mesure
from moniteur.domaine.site import Site
from moniteur.domaine.testeur import Testeur

# Port testé quand l'URI n'en indique pas, selon son schéma.
PORTS_PAR_SCHEMA = {"http": 80, "https": 443}


class TesteurTcp(Testeur):
    """Testeur de la couche 4 : ouvre une connexion TCP vers le site.

    Le nom d'hôte de l'URI principale est résolu en adresse IPv4 et la
    première adresse reçue est utilisée (Q-05). Le port testé est celui
    de l'URI, ou à défaut celui de son schéma : 80 pour http, 443 pour
    https. La connexion est fermée dès qu'elle est établie.

    INVARIANT : la couche testée est toujours L4.
    """

    @property
    def couche(self) -> Couche:
        """Donne la couche testée.

        PRE : aucune.
        POST : renvoie Couche.L4. Ne modifie rien.
        """
        return Couche.L4

    def executer(
        self, site: Site, timeout_s: float, horodatage: datetime
    ) -> list[Mesure]:
        """Teste la connexion TCP vers l'URI principale du site.

        Un site injoignable n'est pas une erreur du programme : il donne
        une mesure KO (EF-03.2, EF-03.5).

        PRE : timeout_s > 0.
        POST : ouvre puis ferme une connexion TCP vers le site et
               renvoie une liste d'une seule mesure, de couche L4 et
               datée de horodatage :
               - connexion établie : verdict OK, durée de l'ouverture de
                 la connexion (hors résolution du nom), diagnostic
                 « port N ouvert » ;
               - échec (nom introuvable, connexion refusée, délai
                 dépassé, URI mal formée ou de schéma non pris en
                 charge) : verdict KO, durée None, diagnostic donnant
                 la nature de l'erreur.
               Ne modifie ni site ni les autres paramètres.
        """
        try:
            hote, port = self.__lire_hote_et_port(site.uri_principale)
        except ValueError as erreur:
            diagnostic = f"URI invalide ({erreur})"
            return [Mesure(horodatage, self.couche, Verdict.KO, None,
                           diagnostic)]
        try:
            duree_s = self.__ouvrir_connexion(hote, port, timeout_s)
            return [Mesure(horodatage, self.couche, Verdict.OK, duree_s,
                           f"port {port} ouvert")]
        except socket.gaierror:
            diagnostic = "nom de domaine introuvable"
        except TimeoutError:
            diagnostic = f"délai dépassé (port {port})"
        except ConnectionRefusedError:
            diagnostic = f"connexion refusée (port {port})"
        except OSError as erreur:
            diagnostic = f"connexion impossible : {erreur}"
        return [Mesure(horodatage, self.couche, Verdict.KO, None,
                       diagnostic)]

    def __lire_hote_et_port(self, uri: str) -> tuple[str, int]:
        """Renvoie le nom d'hôte et le port à tester pour cette URI.

        Le port est celui de l'URI, ou à défaut celui de son schéma.
        Lève ValueError si l'URI est mal formée, sans hôte ou de schéma
        non pris en charge.
        """
        parties = urlsplit(uri)
        if parties.scheme not in PORTS_PAR_SCHEMA:
            raise ValueError(f"schéma non pris en charge : {parties.scheme}")
        if parties.hostname is None:
            raise ValueError("hôte manquant")
        port = parties.port or PORTS_PAR_SCHEMA[parties.scheme]
        return parties.hostname, port

    def __ouvrir_connexion(
        self, hote: str, port: int, timeout_s: float
    ) -> float:
        """Ouvre une connexion TCP puis la ferme, et renvoie sa durée.

        La durée, en secondes, ne compte que l'ouverture de la connexion
        vers la première adresse IPv4 de l'hôte. Les erreurs réseau sont
        propagées sous forme d'exceptions.
        """
        adresse = socket.getaddrinfo(
            hote, port, socket.AF_INET, socket.SOCK_STREAM
        )[0][4]
        debut = time.perf_counter()
        with socket.create_connection(adresse, timeout=timeout_s):
            return time.perf_counter() - debut


if __name__ == "__main__":
    # Les scénarios utilisent des sockets locaux : un port qui écoute et
    # un port fermé, sur 127.0.0.1.
    testeur = TesteurTcp()
    instant = datetime(2026, 10, 17, 14, 30)

    def tester(uri: str) -> Mesure:
        """Teste un site fictif d'URI donnée et renvoie sa mesure."""
        return testeur.executer(Site("Test", uri), 2.0, instant)[0]

    serveur = socket.socket()
    serveur.bind(("127.0.0.1", 0))
    serveur.listen()
    port_ouvert = serveur.getsockname()[1]
    with socket.socket() as socket_temporaire:
        socket_temporaire.bind(("127.0.0.1", 0))
        port_ferme = socket_temporaire.getsockname()[1]

    print("Scénario : port qui écoute : verdict OK, port en diagnostic "
          "(EF-03.2)")
    attendu = (Verdict.OK, f"port {port_ouvert} ouvert")
    mesure = tester(f"http://127.0.0.1:{port_ouvert}")
    obtenu = (mesure.verdict, mesure.diagnostic)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : port qui écoute : durée de connexion enregistrée")
    attendu = True
    obtenu = mesure.duree_s is not None
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : port fermé : verdict KO, connexion refusée "
          "(EF-03.2)")
    attendu = (Verdict.KO, f"connexion refusée (port {port_ferme})")
    mesure = tester(f"http://127.0.0.1:{port_ferme}")
    obtenu = (mesure.verdict, mesure.diagnostic)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    # Que le port 443 soit ouvert ou fermé sur cette machine, le
    # diagnostic le mentionne : le test ne dépend pas de la machine.
    print("Scénario : URI https sans port : le port 443 est testé")
    attendu = True
    obtenu = "443" in (tester("https://127.0.0.1").diagnostic or "")
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : nom de domaine inexistant : verdict KO (décision e)")
    attendu = (Verdict.KO, "nom de domaine introuvable")
    mesure = tester("https://site-inexistant.invalid")
    obtenu = (mesure.verdict, mesure.diagnostic)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : schéma non pris en charge : mesure KO, pas "
          "d'exception")
    attendu = (Verdict.KO, "URI invalide (schéma non pris en charge : ftp)")
    mesure = tester("ftp://exemple.be")
    obtenu = (mesure.verdict, mesure.diagnostic)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    serveur.close()
