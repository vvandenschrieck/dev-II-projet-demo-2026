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
    mesure_ok = Mesure(instant, Verdict.OK, 0.12, "200")
    mesure_ko = Mesure(instant, Verdict.KO, None, "délai dépassé")

    print("Scénario : mesure OK : horodatage conservé")
    attendu = instant
    obtenu = mesure_ok.horodatage
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print()

    print("Scénario : mesure OK : verdict OK (critère 4)")
    attendu = Verdict.OK
    obtenu = mesure_ok.verdict
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print()

    print("Scénario : mesure OK : durée conservée")
    attendu = 0.12
    obtenu = mesure_ok.duree_s
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print()

    print("Scénario : mesure OK : code HTTP en diagnostic")
    attendu = "200"
    obtenu = mesure_ok.diagnostic
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print()

    print("Scénario : mesure KO : verdict KO")
    attendu = Verdict.KO
    obtenu = mesure_ko.verdict
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print()

    print("Scénario : mesure KO sans réponse : durée None et non 0 "
          "(EF-03.5)")
    attendu = None
    obtenu = mesure_ko.duree_s
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print()

    print("Scénario : mesure KO sans réponse : diagnostic "
          "« délai dépassé »")
    attendu = "délai dépassé"
    obtenu = mesure_ko.diagnostic
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print()

    print("Scénario : modification d'une mesure existante")
    attendu = "FrozenInstanceError"
    try:
        mesure_ok.verdict = Verdict.KO
        obtenu = "aucune erreur"
    except FrozenInstanceError:
        obtenu = "FrozenInstanceError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print()

    print("Scénario : deux mesures aux valeurs identiques sont égales")
    attendu = True
    obtenu = mesure_ok == Mesure(instant, Verdict.OK, 0.12, "200")
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print()
