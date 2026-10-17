"""Mesure : résultat immuable d'un test réalisé par un testeur."""

from dataclasses import dataclass
from datetime import datetime

from moniteur.domaine.enumerations import Verdict


@dataclass(frozen=True)
class Mesure:
    """Résultat d'un test sur un site, à un instant donné.

    Une mesure contient l'horodatage de la batterie, le verdict (OK ou
    KO), la durée jusqu'à la première réponse en secondes et un
    diagnostic (code HTTP ou nature de l'erreur). La durée vaut None
    lorsqu'aucune réponse n'a été reçue : ce n'est pas une durée nulle
    (page MVP, section 2.1, et EF-03.5).

    La classe est figée : une mesure ne change plus après sa création.
    """

    horodatage: datetime
    verdict: Verdict
    duree_s: float | None
    diagnostic: str | None


if __name__ == "__main__":
    from dataclasses import FrozenInstanceError

    def afficher(scenario: str, attendu: object, obtenu: object) -> None:
        """Affiche un scénario de test manuel et son verdict."""
        print(f"Scénario : {scenario}")
        print(f"  attendu : {attendu}")
        print(f"  obtenu  : {obtenu}")
        print("  → OK" if attendu == obtenu else "  → ÉCHEC")

    instant = datetime(2026, 10, 17, 14, 30)

    mesure_ok = Mesure(instant, Verdict.OK, 0.12, "200")
    afficher(
        "mesure OK avec durée et code HTTP (critère 4)",
        (instant, Verdict.OK, 0.12, "200"),
        (mesure_ok.horodatage, mesure_ok.verdict,
         mesure_ok.duree_s, mesure_ok.diagnostic),
    )

    mesure_ko = Mesure(instant, Verdict.KO, None, "délai dépassé")
    afficher(
        "mesure KO sans réponse : durée None et non 0 (EF-03.5)",
        (Verdict.KO, None, "délai dépassé"),
        (mesure_ko.verdict, mesure_ko.duree_s, mesure_ko.diagnostic),
    )

    try:
        mesure_ok.verdict = Verdict.KO
        obtenu = "aucune erreur"
    except FrozenInstanceError:
        obtenu = "FrozenInstanceError"
    afficher(
        "modification d'une mesure existante",
        "FrozenInstanceError",
        obtenu,
    )

    afficher(
        "deux mesures aux valeurs identiques sont égales",
        True,
        mesure_ok == Mesure(instant, Verdict.OK, 0.12, "200"),
    )
