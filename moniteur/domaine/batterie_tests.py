"""Batterie de tests : mesures réalisées sur un site au même instant."""

from datetime import datetime

from moniteur.domaine.enumerations import Declenchement, Verdict
from moniteur.domaine.mesure import Mesure


class BatterieTests:
    """Ensemble des mesures produites lors d'un lancement de tests.

    Une batterie est créée par un site à chaque lancement de tests
    (EF-03.1). Elle porte l'horodatage du lancement, affiché à
    l'utilisatrice (EF-02.2), et regroupe les mesures renvoyées par
    les testeurs.

    INVARIANT : l'horodatage et le déclenchement ne changent jamais
    après la construction ; les mesures sont conservées dans l'ordre de
    leur ajout.
    """

    def __init__(
        self, horodatage: datetime, declenchement: Declenchement
    ) -> None:
        """Crée une batterie vide, datée de l'instant reçu.

        PRE : aucune.
        POST : la batterie est créée, datée de horodatage, lancée de la
               façon indiquée par declenchement, sans mesure.
        """
        self.__horodatage = horodatage
        self.__declenchement = declenchement
        self.__mesures: list[Mesure] = []

    @property
    def horodatage(self) -> datetime:
        """Donne l'instant du lancement de la batterie (EF-02.2).

        PRE : aucune.
        POST : renvoie l'horodatage de la batterie. Ne modifie rien.
        """
        return self.__horodatage

    @property
    def declenchement(self) -> Declenchement:
        """Donne la façon dont la batterie a été lancée.

        PRE : aucune.
        POST : renvoie MANUEL ou PERIODIQUE (EF-03.7). Ne modifie rien.
        """
        return self.__declenchement

    @property
    def mesures(self) -> tuple[Mesure, ...]:
        """Donne les mesures de la batterie, dans l'ordre de leur ajout.

        PRE : aucune.
        POST : renvoie un tuple des mesures (sous forme de copie :
               le code extérieur ne peut pas modifier la liste interne).
               Ne modifie rien.
        """
        return tuple(self.__mesures)

    @property
    def interrompue(self) -> bool:
        """Dit si la batterie doit s'arrêter après ses mesures (EF-03.2).

        PRE : aucune.
        POST : renvoie True si une mesure KO porte sur une couche
               bloquante (L4), False sinon. Un échec en L3 n'interrompt
               pas la batterie. Ne modifie rien.
        """
        for mesure in self.__mesures:
            if mesure.couche.bloquante and mesure.verdict == Verdict.KO:
                return True
        return False

    def ajouter(self, mesures: list[Mesure]) -> None:
        """Ajoute à la batterie les mesures renvoyées par un testeur.

        PRE : aucune.
        POST : les éléments de mesures sont ajoutés à la fin de la
               batterie, dans leur ordre. La liste mesures donnée en
               paramètre n'est ni modifiée ni conservée.
        """
        self.__mesures.extend(mesures)


if __name__ == "__main__":
    from moniteur.domaine.enumerations import Couche, Verdict

    instant = datetime(2026, 10, 17, 14, 30)
    mesure_ok = Mesure(instant, Couche.L7, Verdict.OK, 0.12, "200")
    mesure_ko = Mesure(
        instant, Couche.L7, Verdict.KO, None, "délai dépassé"
    )
    batterie = BatterieTests(instant, Declenchement.MANUEL)

    print("Scénario : la propriété mesures renvoie un tuple")
    attendu = tuple
    obtenu = type(batterie.mesures)
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    def batterie_avec(couche: Couche, verdict: Verdict) -> BatterieTests:
        """Batterie de test : une seule mesure de la couche et du verdict."""
        nouvelle = BatterieTests(instant, Declenchement.MANUEL)
        nouvelle.ajouter([Mesure(instant, couche, verdict, None, "test")])
        return nouvelle

    print("Scénario : une mesure KO en L4 interrompt la batterie "
          "(EF-03.2)")
    attendu = True
    obtenu = batterie_avec(Couche.L4, Verdict.KO).interrompue
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : une mesure KO en L3 n'interrompt pas la batterie "
          "(Q-02, RM-06)")
    attendu = False
    obtenu = batterie_avec(Couche.L3, Verdict.KO).interrompue
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : une mesure OK en L4 n'interrompt pas la batterie")
    attendu = False
    obtenu = batterie_avec(Couche.L4, Verdict.OK).interrompue
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)

    print("Scénario : modifier la liste transmise ne modifie pas la "
          "batterie")
    mesures_a_encoder = [mesure_ok]
    batterie_2 = BatterieTests(instant, Declenchement.MANUEL)
    batterie_2.ajouter(mesures_a_encoder)
    mesures_a_encoder.append(mesure_ko)
    attendu = (mesure_ok,)
    obtenu = batterie_2.mesures
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print("-" * 40)
