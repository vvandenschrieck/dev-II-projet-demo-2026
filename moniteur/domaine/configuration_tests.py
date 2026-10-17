"""Configuration des tests : paramètres communs à tous les sites."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigurationTests:
    """Paramètres utilisés lors du lancement d'une batterie de tests.

    Dans le MVP, la configuration ne contient que le délai maximal
    d'attente d'une réponse, en secondes. Au-delà, le test est
    considéré en échec (EF-03.5). La valeur reste à fixer avec la
    cliente (Q-07) ; 5 secondes sont utilisées en attendant (page MVP,
    section 5).

    La classe est figée : une configuration se remplace plutôt qu'elle
    ne se modifie.
    """

    timeout_s: float


if __name__ == "__main__":
    from dataclasses import FrozenInstanceError

    config = ConfigurationTests(5.0)

    print("Scénario : création avec le délai provisoire de 5 s (Q-07)")
    attendu = 5.0
    obtenu = config.timeout_s
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print()

    print("Scénario : modification d'une configuration existante")
    attendu = "FrozenInstanceError"
    try:
        config.timeout_s = 10.0
        obtenu = "aucune erreur"
    except FrozenInstanceError:
        obtenu = "FrozenInstanceError"
    print(f"  attendu : {attendu}")
    print(f"  obtenu  : {obtenu}")
    print("  → OK" if obtenu == attendu else "  → ÉCHEC")
    print()
