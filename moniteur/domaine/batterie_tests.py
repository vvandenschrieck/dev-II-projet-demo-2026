"""Batterie de tests : mesures réalisées sur un site au même instant."""

from datetime import datetime

from moniteur.domaine.mesure import Mesure


class BatterieTests:
    """Ensemble des mesures produites lors d'un lancement de tests.

    Une batterie est créée par un site à chaque lancement de tests
    (EF-03.1). Elle porte l'horodatage du lancement, affiché à
    l'utilisatrice (EF-02.2), et regroupe les mesures renvoyées par
    les testeurs.
    """

    def __init__(self, horodatage: datetime) -> None:
        """Crée une batterie vide, datée de l'instant reçu."""
        self.__horodatage = horodatage
        self.__mesures: list[Mesure] = []

    @property
    def horodatage(self) -> datetime:
        """Instant du lancement de la batterie (EF-02.2)."""
        return self.__horodatage

    @property
    def mesures(self) -> tuple[Mesure, ...]:
        """Mesures de la batterie, dans l'ordre de leur ajout.

        Renvoie un tuple : le code extérieur ne peut pas modifier la
        liste interne.
        """
        return tuple(self.__mesures)

    def ajouter(self, mesures: list[Mesure]) -> None:
        """Ajoute à la batterie les mesures renvoyées par un testeur."""
        self.__mesures.extend(mesures)


if __name__ == "__main__":
    from moniteur.domaine.enumerations import Verdict

    def afficher(scenario: str, attendu: object, obtenu: object) -> None:
        """Affiche un scénario de test manuel et son verdict."""
        print(f"Scénario : {scenario}")
        print(f"  attendu : {attendu}")
        print(f"  obtenu  : {obtenu}")
        print("  → OK" if attendu == obtenu else "  → ÉCHEC")

    instant = datetime(2026, 10, 17, 14, 30)
    mesure_ok = Mesure(instant, Verdict.OK, 0.12, "200")
    mesure_ko = Mesure(instant, Verdict.KO, None, "délai dépassé")

    batterie = BatterieTests(instant)
    afficher(
        "batterie neuve : horodatage reçu",
        instant,
        batterie.horodatage,
    )
    afficher(
        "batterie neuve : aucune mesure",
        0,
        len(batterie.mesures),
    )

    batterie.ajouter([mesure_ok])
    afficher(
        "ajout d'une mesure",
        (mesure_ok,),
        batterie.mesures,
    )

    batterie.ajouter([mesure_ko])
    afficher(
        "deux ajouts successifs : mesures cumulées dans l'ordre",
        (mesure_ok, mesure_ko),
        batterie.mesures,
    )

    afficher(
        "la propriété mesures renvoie un tuple",
        tuple,
        type(batterie.mesures),
    )

    mesures_envoyees = [mesure_ok]
    autre_batterie = BatterieTests(instant)
    autre_batterie.ajouter(mesures_envoyees)
    mesures_envoyees.append(mesure_ko)
    afficher(
        "modifier la liste transmise ne modifie pas la batterie",
        (mesure_ok,),
        autre_batterie.mesures,
    )
