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

    instant = datetime(2026, 10, 17, 14, 30)
    mesure = Mesure(instant, Verdict.OK, 0.12, "200")

    print("Scénario : modification d'une mesure existante")
    attendu = "FrozenInstanceError"
    try:
        mesure.verdict = Verdict.KO
        obtenu = "aucune erreur"
    except FrozenInstanceError:
        obtenu = "FrozenInstanceError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
