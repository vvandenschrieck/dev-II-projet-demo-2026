"""Mesure : résultat immuable d'un test réalisé par un testeur."""

from dataclasses import dataclass
from datetime import datetime

from moniteur.domaine.enumerations import Couche, Verdict


@dataclass(frozen=True)
class Mesure:
    """Résultat d'un test sur un site, à un instant donné.

    Une mesure contient l'horodatage de la batterie, la couche testée
    (L3, L4 ou L7), le verdict (OK ou KO), la durée jusqu'à la première
    réponse en secondes et un diagnostic (code HTTP ou nature de
    l'erreur). La durée vaut None lorsqu'aucune réponse n'a été reçue :
    ce n'est pas une durée nulle (page MVP, section 2.1, et EF-03.5).

    INVARIANT : les cinq champs ne changent jamais après la création
    (classe figée). Le constructeur, généré par la dataclass, ne
    contrôle pas les valeurs reçues.
    """

    horodatage: datetime
    couche: Couche
    verdict: Verdict
    duree_s: float | None
    diagnostic: str | None


if __name__ == "__main__":
    from dataclasses import FrozenInstanceError

    instant = datetime(2026, 10, 17, 14, 30)
    mesure = Mesure(instant, Couche.L7, Verdict.OK, 0.12, "200")

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
