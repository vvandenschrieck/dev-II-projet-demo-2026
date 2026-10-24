# CLAUDE.md — Projet-démo Dev II : monitoring de sites web

Application Python de surveillance de sites web pour M. Durant (utilisatrice unique).
Projet-démo du cours de Développement informatique II (EPHEC) : le code est lu par
des étudiants de Bac 2. Il doit rester simple, lisible et exemplaire.

## Sources de référence

La documentation se trouve dans `docs/wiki` (sous-module Git du wiki GitHub).
- Périmètre de l'itération en cours : `docs/wiki/MVP-‐-Minimum-Viable-Product.md`.
  **Cette page prévaut** sur le cahier des charges en cas de différence.
- Exigences et règles métier : `docs/wiki/Cahier-des-charges.md` (identifiants EF-xx, RM-xx, Q-xx).
- Conception complète (cible à long terme) : `docs/wiki/Le-diagramme-de-classes.md`
  et `docs/wiki/Quelques-diagrammes-de-séquence.md`.

Règles :
- `docs/wiki` est en **lecture seule** : ne jamais modifier ce dossier.
- Implémenter **uniquement** le périmètre de la page MVP. Ne rien ajouter « pour plus tard ».
- Respecter les noms et signatures du diagramme de classes du MVP.
- Si une exigence est ambiguë, si deux pages se contredisent ou si une question
  ouverte (Q-xx) bloque : s'arrêter et poser la question. Ne pas trancher seul.

## Environnement

- Python 3.12.
- Domaine, testeurs et TUI simple : bibliothèque standard uniquement. Requêtes HTTP avec
  `http.client` (ne suit pas les redirections, conformément à Q-03).
- Seule dépendance externe autorisée : `textual`, utilisée uniquement par
  `moniteur/interface/tui_textual.py` et déclarée dans `requirements.txt`.
- Aucune autre dépendance sans accord explicite.

## Structure

```
main.py                 # point d'assemblage : crée testeurs, configuration, registre,
                        #   puis lance l'interface choisie
moniteur/
  domaine/              # classes du diagramme (Site, RegistreSites, BatterieTests, Mesure,
                        #   Testeur, ConfigurationTests, énumérations) — aucun accès réseau
  testeurs/             # testeurs concrets (TesteurHttp) — seuls à accéder au réseau
  interface/
    tui_simple.py       # menus en print() / input()
    tui_textual.py      # interface Textual
requirements.txt        # textual
```

## Deux interfaces pour un même domaine

- Les deux interfaces offrent les mêmes fonctionnalités du MVP et utilisent le domaine
  exactement de la même façon. Aucune modification du domaine ne doit être nécessaire
  pour l'une ou l'autre : si c'est le cas, s'arrêter et le signaler.
- `main.py` choisit l'interface selon un argument de ligne de commande (module `argparse`) :
  `python main.py --interface simple` (valeur par défaut) ou `python main.py --interface textual`.
- `textual` n'est importé que si cette interface est choisie : la TUI simple doit
  fonctionner sans que `textual` soit installé.
- Les deux interfaces ne partagent pas de code entre elles. Ce qu'elles ont en commun
  appartient au domaine.

## Conventions de code

- Le code respecte la PEP 8 : indentation de 4 espaces, lignes de 79 caractères
  au maximum, `snake_case` pour les fonctions, méthodes et variables, `PascalCase`
  pour les classes, `MAJUSCULES` pour les constantes et les membres d'énumération,
  imports en tête de module groupés dans l'ordre bibliothèque standard / externe / projet,
  deux lignes vides entre les définitions de premier niveau.
- Identifiants en français, sans accents, comme dans le diagramme de classes
  (`lancer_batterie`, `statut_disponibilite`). Commentaires et docstrings en français.
- Type hints sur toutes les signatures.
- Attributs privés avec double souligné (`self.__nom`) ; lecture via `@property`.
  Les propriétés qui exposent une collection renvoient un `tuple` (jamais la liste interne).
- `Mesure` et `ConfigurationTests` : `@dataclass(frozen=True)`.
- Le domaine n'importe jamais `testeurs/` ni `interface/`. L'interface importe le domaine,
  jamais l'inverse.
- Aucun `print()` ni `input()` hors de `interface/`, sauf dans les blocs de tests manuels.
- Aucun appel direct à `datetime.now()` dans le domaine : l'horloge est passée en paramètre.
- Refus métier (nom en double, URI vide) : lever `ValueError` avec un message clair.
  Un site injoignable n'est pas une erreur : c'est une mesure KO.
- Fonctions et méthodes courtes. Pas de classes ni de couches d'abstraction
  absentes du diagramme sans en discuter d'abord.

## Docstrings

- Chaque module, classe et méthode publique a une docstring (PEP 257), en français.
  Les propriétés (`@property`) suivent la même règle.
- Les fonctions et méthodes sont documentées par un contrat (programmation par
  contrat), dans une docstring placée sous la signature. Trois rubriques :
  - **Résumé** : une phrase qui dit ce que fait la méthode. Référencer la règle
    métier si c'est pertinent (EF-01.2, RM-03…).
  - **PRE** : ce que l'appelant doit garantir (paramètres et état de `self`).
    `PRE : aucune.` si rien n'est exigé.
  - **POST** : le cas normal (valeur renvoyée, puis ce qui est modifié, ou
    « Ne modifie rien. »), puis une ligne par exception, indentée sous la POST :
    `Exception <Type> : <condition>`. Cela vaut aussi pour une exception propagée
    depuis un appel : on décrit sa condition, sans citer la méthode appelée (le
    contrat ne dépend pas de l'implémentation). Une exception interceptée dans le
    corps n'apparaît pas ; une exception transformée apparaît sous son nouveau type.
- Pas de sections `Args:`, `Returns:` ou `Parameters`. Les types ne sont pas répétés :
  ils sont donnés par les type hints.
- L'invariant de classe figure dans la docstring de la classe, sous la mention
  `INVARIANT`. Il est établi par le constructeur et préservé par les méthodes publiques.
- Précondition faible pour une méthode publique (elle gère tous les cas) ; une
  précondition forte n'est acceptable que pour une méthode interne (préfixe `_`).
- Une commande modifie et ne renvoie rien ; une requête renvoie une valeur et ne
  modifie rien. Une fonction pure dit « Ne modifie rien. »
- Si la règle métier ne tranche pas un cas, ne pas inventer de comportement :
  signaler la question (Q-xx si elle existe).
- Exemple :

      def moyenne_classe(code: str) -> float:
          """Calcule la moyenne des notes d'une classe.

          PRE : aucune.
          POST : renvoie la moyenne des notes de la classe. Ne modifie rien.
                 Exception ValueError : si le code de la classe n'existe pas.
                 Exception ValueError : si la classe n'a aucune note.
          """

## Tests manuels  (les tests unitaires viendront plus tard)

- Un bloc `if __name__ == "__main__":` n'est ajouté à un module que s'il a un réel
  intérêt pédagogique : montrer un comportement non évident, une règle métier
  (EF-xx, RM-xx), un cas d'erreur ou un critère d'acceptation de la page MVP.
  Pas de scénario qui ne fait que vérifier un accesseur ou une affectation triviale,
  et pas de bloc dans un module qui n'a rien d'intéressant à montrer.
- En cas de doute, proposer le scénario et attendre validation avant de l'écrire.
- Lancement depuis la racine du projet : `python -m moniteur.domaine.site`
  (et non `python moniteur/domaine/site.py`, qui casse les imports du paquet).
- Peu de scénarios, bien choisis, plutôt qu'une couverture exhaustive.
  Format de sortie pour chaque scénario :
      Scénario : ajout d'un site avec un nom déjà utilisé (EF-01.2)
        attendu : ValueError
        obtenu  : ValueError
        → OK
- Les `print()` sont autorisés dans ce bloc uniquement.
- Les scénarios du domaine n'accèdent jamais au réseau : utiliser un faux testeur
  (sous-classe de `Testeur` qui renvoie des mesures fixées) et une fausse horloge,
  définis dans le bloc de test.
- `TesteurHttp` se teste contre un serveur local (`http.server` lancé dans le bloc de test),
  jamais contre des sites réels.
- Les interfaces se vérifient à la main, en suivant les critères d'acceptation de la page MVP.
- Lancer les tests manuels existants des modules modifiés avant chaque commit.

## Manière de travailler

1. Avant d'écrire du code, proposer un plan et attendre validation.
2. Ordre de réalisation : domaine, puis `TesteurHttp`, puis `main.py` avec la TUI simple,
   puis la TUI Textual.
3. Avancer par petites étapes : une classe (ou une méthode) à la fois, avec ses tests manuels
   lorsqu'ils sont utiles (voir « Tests manuels »).
4. Après chaque étape : expliquer brièvement les choix faits et ce qui reste ouvert.
5. Un commit par étape, message en français à l'impératif
   (« Ajoute le calcul du statut de disponibilité »).
6. Signaler toute incohérence repérée dans la documentation, sans la corriger.
