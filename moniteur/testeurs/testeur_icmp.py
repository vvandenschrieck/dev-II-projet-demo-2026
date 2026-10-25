"""Testeur ICMP : vérifie qu'un site répond aux sondes ping."""

import platform
import socket
import subprocess
from datetime import datetime
from math import ceil
from urllib.parse import urlsplit

from moniteur.domaine.enumerations import Couche, Verdict
from moniteur.domaine.mesure import Mesure
from moniteur.domaine.site import Site
from moniteur.domaine.testeur import Testeur

# Nombre de sondes envoyées par défaut (Q-04).
NB_SONDES_PAR_DEFAUT = 6

# Marge, en secondes, laissée au système pour lancer et terminer un ping.
MARGE_S = 2.0


def calculer_verdict(reussies: int, nb_sondes: int) -> Verdict:
    """Décide du verdict d'après le nombre de sondes réussies (RM-01).

    PRE : nb_sondes > 0.
    POST : renvoie KO si moins de la moitié des sondes ont abouti
           (taux de succès < 50 %), OK sinon. Ne modifie rien.
    """
    if reussies * 2 < nb_sondes:
        return Verdict.KO
    return Verdict.OK


class TesteurIcmp(Testeur):
    """Testeur de la couche 3 : envoie des sondes ping vers le site.

    Le nom d'hôte de l'URI principale est résolu en adresse IPv4 et la
    première adresse reçue est utilisée (Q-05). Les sondes sont envoyées
    par la commande ping du système, qui n'exige pas de droits
    particuliers. Les options de cette commande dépendent du système
    (Windows, macOS, Linux). Les sondes partent en même temps, pour que
    le test ne dure pas plusieurs délais maximaux.

    INVARIANT : la couche testée est toujours L3 ; le nombre de sondes
    est au moins 1 et ne change jamais.
    """

    def __init__(self, nb_sondes: int = NB_SONDES_PAR_DEFAUT) -> None:
        """Crée un testeur qui envoie nb_sondes sondes (Q-04).

        PRE : aucune.
        POST : le testeur est créé pour nb_sondes sondes.
               Exception ValueError : si nb_sondes est inférieur à 1.
        """
        if nb_sondes < 1:
            raise ValueError("Le nombre de sondes doit être au moins 1.")
        self.__nb_sondes = nb_sondes

    @property
    def couche(self) -> Couche:
        """Donne la couche testée.

        PRE : aucune.
        POST : renvoie Couche.L3. Ne modifie rien.
        """
        return Couche.L3

    def executer(
        self, site: Site, timeout_s: float, horodatage: datetime
    ) -> list[Mesure]:
        """Envoie des sondes ping vers le site et décide du verdict.

        Un site injoignable n'est pas une erreur du programme : il donne
        une mesure KO (RM-01, EF-03.5).

        PRE : timeout_s > 0.
        POST : envoie nb_sondes sondes ping vers l'adresse IPv4 du site
               et renvoie une liste d'une seule mesure, de couche L3 et
               datée de horodatage :
               - sondes envoyées : verdict OK si au moins la moitié ont
                 abouti, KO sinon (RM-01), diagnostic « N/M sondes ».
                 La durée est None : elle n'est pas mesurée, la sortie
                 de ping dépendant du système ;
               - sondes impossibles à envoyer (nom introuvable, URI mal
                 formée, commande ping absente, système non pris en
                 charge) : verdict KO, durée None, diagnostic donnant
                 la nature de l'erreur.
               Ne modifie ni site ni les autres paramètres.
        """
        try:
            hote = self.__lire_hote(site.uri_principale)
        except ValueError as erreur:
            return [self.__mesure_ko(horodatage, f"URI invalide ({erreur})")]
        try:
            adresse = socket.getaddrinfo(
                hote, None, socket.AF_INET, socket.SOCK_STREAM
            )[0][4][0]
            reussies = self.__envoyer_sondes(adresse, timeout_s)
        except socket.gaierror:
            return [self.__mesure_ko(horodatage, "nom de domaine introuvable")]
        except FileNotFoundError:
            return [self.__mesure_ko(horodatage, "commande ping introuvable")]
        except NotImplementedError as erreur:
            return [self.__mesure_ko(horodatage, str(erreur))]
        verdict = calculer_verdict(reussies, self.__nb_sondes)
        diagnostic = f"{reussies}/{self.__nb_sondes} sondes"
        return [Mesure(horodatage, self.couche, verdict, None, diagnostic)]

    def __mesure_ko(self, horodatage: datetime, diagnostic: str) -> Mesure:
        """Renvoie une mesure KO, sans durée, avec ce diagnostic."""
        return Mesure(horodatage, self.couche, Verdict.KO, None, diagnostic)

    def __lire_hote(self, uri: str) -> str:
        """Renvoie le nom d'hôte de l'URI.

        Lève ValueError si l'URI est mal formée ou sans hôte.
        """
        hote = urlsplit(uri).hostname
        if hote is None:
            raise ValueError("hôte manquant")
        return hote

    def __commande_ping(self, adresse: str, timeout_s: float) -> list[str]:
        """Renvoie la commande qui envoie une sonde, selon le système.

        Le délai s'exprime en millisecondes sous Windows et macOS, en
        secondes sous Linux. Lève NotImplementedError pour un autre
        système.
        """
        systeme = platform.system()
        if systeme == "Windows":
            return ["ping", "-n", "1", "-w", str(ceil(timeout_s * 1000)),
                    adresse]
        if systeme == "Darwin":
            return ["ping", "-c", "1", "-W", str(ceil(timeout_s * 1000)),
                    adresse]
        if systeme == "Linux":
            return ["ping", "-c", "1", "-W", str(ceil(timeout_s)), adresse]
        raise NotImplementedError(f"ping non pris en charge sur {systeme}")

    def __envoyer_sondes(self, adresse: str, timeout_s: float) -> int:
        """Envoie les sondes en même temps et renvoie le nombre réussi.

        Une sonde réussit si la commande ping se termine avec le code 0
        (réponse reçue). Lève FileNotFoundError si la commande ping est
        absente et NotImplementedError si le système n'est pas pris en
        charge.
        """
        commande = self.__commande_ping(adresse, timeout_s)
        sondes = [
            subprocess.Popen(
                commande, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            for _ in range(self.__nb_sondes)
        ]
        reussies = 0
        for sonde in sondes:
            try:
                if sonde.wait(timeout=timeout_s + MARGE_S) == 0:
                    reussies += 1
            except subprocess.TimeoutExpired:
                sonde.kill()
                sonde.wait()
        return reussies


if __name__ == "__main__":
    # Ces scénarios envoient de vrais pings, mais seulement vers
    # 127.0.0.1 et vers une adresse réservée à la documentation
    # (192.0.2.1), qui ne désigne aucun site réel.
    testeur = TesteurIcmp()
    instant = datetime(2026, 10, 17, 14, 30)

    def tester(uri: str, timeout_s: float = 1.0) -> Mesure:
        """Teste un site fictif d'URI donnée et renvoie sa mesure."""
        return testeur.executer(Site("Test", uri), timeout_s, instant)[0]

    print("Scénario : machine locale : 6 sondes sur 6, verdict OK "
          "(RM-01)")
    attendu = (Verdict.OK, "6/6 sondes")
    mesure = tester("http://127.0.0.1")
    obtenu = (mesure.verdict, mesure.diagnostic)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : adresse sans réponse : 0 sonde sur 6, verdict KO "
          "(RM-01)")
    attendu = (Verdict.KO, "0/6 sondes")
    mesure = tester("http://192.0.2.1")
    obtenu = (mesure.verdict, mesure.diagnostic)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : seuil de 50 % : 3 sondes sur 6 donnent OK, 2 sur 6 "
          "donnent KO (RM-01)")
    attendu = (Verdict.OK, Verdict.KO)
    obtenu = (calculer_verdict(3, 6), calculer_verdict(2, 6))
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : nom de domaine inexistant : verdict KO "
          "(décision e)")
    attendu = (Verdict.KO, "nom de domaine introuvable")
    mesure = tester("https://site-inexistant.invalid")
    obtenu = (mesure.verdict, mesure.diagnostic)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : zéro sonde demandée")
    attendu = "ValueError"
    try:
        TesteurIcmp(0)
        obtenu = "aucune erreur"
    except ValueError:
        obtenu = "ValueError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
