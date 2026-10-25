"""Essais sur des sites réels : série de tests manuels à lancer à la main.

Cette série teste les trois testeurs et le statut de disponibilité sur
quelques sites publics aux comportements connus. Elle n'est jamais
lancée par un autre module. Elle vérifie d'abord que le réseau a l'air
correct et s'arrête sinon. Les sites tiers (httpbin.org, badssl.com)
peuvent changer : un échec n'est pas forcément un défaut du programme.

Lancement depuis la racine du projet : python essais_reels.py
(compter une trentaine de secondes).
"""

import socket
import sys
from datetime import datetime

from moniteur.domaine.configuration_tests import ConfigurationTests
from moniteur.domaine.enumerations import Couche, Declenchement
from moniteur.domaine.site import Site
from moniteur.testeurs.testeur_http import TesteurHttp
from moniteur.testeurs.testeur_icmp import TesteurIcmp
from moniteur.testeurs.testeur_tcp import TesteurTcp

TIMEOUT_S = 3.0

# Site utilisé pour vérifier que le réseau fonctionne.
SITE_REFERENCE = "www.google.com"

# Chaque essai donne un titre, l'URI du site et le résultat attendu :
# le verdict de chaque couche citée (« absente » si la batterie s'est
# arrêtée avant) et le statut de disponibilité.
ESSAIS = [
    ("site qui fonctionne (critère 4)",
     "https://www.google.com",
     {"L3": "OK", "L4": "OK", "L7": "OK", "statut": "DISPONIBLE"}),
    ("redirection 301 non suivie (critère 5, Q-03)",
     "http://google.com",
     {"L3": "OK", "L4": "OK", "L7": "OK", "statut": "DISPONIBLE"}),
    ("page absente : 404 (critère 6)",
     "https://www.google.com/page-inexistante-ephec",
     {"L4": "OK", "L7": "KO", "statut": "INDISPONIBLE"}),
    ("ICMP bloqué, web en ordre : la couche 4 compense (Q-02, RM-06)",
     "https://httpbin.org/get",
     {"L3": "KO", "L4": "OK", "L7": "OK", "statut": "DISPONIBLE"}),
    ("ICMP bloqué, erreur 500 (critère 6)",
     "https://httpbin.org/status/500",
     {"L3": "KO", "L4": "OK", "L7": "KO", "statut": "INDISPONIBLE"}),
    ("aucun serveur sur le port prévu : la batterie s'arrête (EF-03.2)",
     "http://www.google.com:81",
     {"L3": "OK", "L4": "KO", "L7": "absente", "statut": "INDISPONIBLE"}),
    ("certificat expiré : erreur TLS en L7",
     "https://expired.badssl.com",
     {"L4": "OK", "L7": "KO", "statut": "INDISPONIBLE"}),
    ("serveur trop lent : délai dépassé (critère 8, EF-03.5)",
     "https://httpbin.org/delay/10",
     {"L4": "OK", "L7": "KO", "statut": "INDISPONIBLE"}),
    ("nom de domaine inexistant (critère 7)",
     "https://site-inexistant.invalid",
     {"L3": "KO", "L4": "KO", "L7": "absente", "statut": "INDISPONIBLE"}),
]


def reseau_correct() -> bool:
    """Vérifie que le réseau permet de lancer les essais.

    PRE : aucune.
    POST : renvoie True si une connexion TCP vers le port 443 de
           SITE_REFERENCE s'établit dans le délai (le nom est donc
           résolu), False sinon. Ne modifie rien.
    """
    try:
        with socket.create_connection((SITE_REFERENCE, 443), TIMEOUT_S):
            return True
    except OSError:
        return False


def tester(uri: str) -> Site:
    """Lance une batterie complète sur un site fictif d'URI donnée.

    PRE : aucune.
    POST : renvoie un nouveau site, testé une fois par les testeurs ICMP,
           TCP et HTTP. Envoie des paquets vers l'hôte de l'URI.
    """
    site = Site("Essai", uri)
    site.lancer_batterie(
        [TesteurIcmp(), TesteurTcp(), TesteurHttp()],
        ConfigurationTests(TIMEOUT_S),
        Declenchement.MANUEL,
        datetime.now,
    )
    return site


def resumer(site: Site, cles: list[str]) -> dict[str, str]:
    """Résume le résultat d'un site pour les clés demandées.

    PRE : site a été testé ; les clés sont des noms de couche ou
          « statut ».
    POST : renvoie, pour chaque clé, le verdict de la couche (« absente »
           sans mesure de cette couche) ou le statut du site. Ne modifie
           rien.
    """
    resume = {}
    for cle in cles:
        if cle == "statut":
            resume[cle] = site.statut_disponibilite.name
            continue
        resume[cle] = "absente"
        for mesure in site.derniere_batterie.mesures:
            if mesure.couche == Couche[cle]:
                resume[cle] = mesure.verdict.name
    return resume


def lancer_essai(titre: str, uri: str, attendu: dict[str, str]) -> bool:
    """Lance un essai, affiche son résultat et dit s'il est conforme.

    PRE : aucune.
    POST : teste le site d'URI uri, affiche le scénario, le détail des
           diagnostics, le résultat attendu et le résultat obtenu, puis
           renvoie True si les deux sont identiques.
    """
    site = tester(uri)
    obtenu = resumer(site, list(attendu))
    detail = ", ".join(
        f"{mesure.couche.name}: {mesure.diagnostic}"
        for mesure in site.derniere_batterie.mesures
    )
    print(f"Scénario : {titre}")
    print(f"  site    : {uri}")
    print(f"  détail  : {detail}")
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
    return obtenu == attendu


def main() -> int:
    """Lance tous les essais si le réseau a l'air correct.

    PRE : aucune.
    POST : si le réseau n'a pas l'air correct, affiche un message et ne
           teste rien. Sinon lance chaque essai et affiche le nombre de
           scénarios conformes. Renvoie 0 si tout est conforme, 1 sinon.
    """
    if not reseau_correct():
        print(f"Réseau indisponible ou filtré ({SITE_REFERENCE}, port "
              "443) : essais non exécutés.")
        return 1
    resultats = [lancer_essai(*essai) for essai in ESSAIS]
    print(f"{sum(resultats)} scénarios conformes sur {len(resultats)}.")
    return 0 if all(resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
