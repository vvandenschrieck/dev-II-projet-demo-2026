# Vérification manuelle des interfaces

Cette liste de contrôle permet de vérifier à la main que les deux interfaces
se comportent comme prévu. Les scénarios 1 à 5 reprennent les critères
d'acceptation de la page MVP du wiki ; les suivants vérifient les testeurs
L3 et L4 et quelques cas limites.

Les scénarios 1 à 9 contactent de vrais sites (`www.google.com`,
`httpbin.org`). Ils demandent donc un accès à Internet, et leur résultat peut
changer si un site change de comportement ou si votre réseau filtre certains
paquets (ICMP, ports). En cas de doute, comparez avec `ping` et `curl` sur la
même machine avant de conclure à un défaut du programme.

## Lancement

Depuis la racine du projet :

- TUI simple : `venv/bin/python main.py`
- TUI Textual : `venv/bin/python main.py --interface textual` (quitter avec `q`)

Le délai maximal d'attente d'un test est de 5 secondes : un test complet
peut donc durer jusqu'à une dizaine de secondes pour un site qui ne répond pas.
Dans la TUI simple, l'écran n'est pas rafraîchi pendant un test.
Les colonnes « RTT L3/L4 » et « Chargement L7 » comparent la moyenne
de la dernière fenêtre (30 minutes) à la moyenne de tous les tests du site :
tant que le site n'a pas plus de 30 minutes d'historique, l'écart n'est pas
calculable et s'affiche `(-)`.

## Scénarios

Pour chaque scénario, cochez la case de l'interface vérifiée.

| # | Scénario | Saisie | Résultat attendu | Simple | Textual |
|---|---|---|---|---|---|
| 1 | Ajout d'un site (critère 1) | `ClientABC` / `www.google.com` | Ligne jaune, statuts de disponibilité et de performance INCONNU, RTT, chargement, horodatage et diagnostic `-`, URI `https://www.google.com` | ☐ | ☐ |
| 2 | Refus d'un doublon (critère 2) | `ClientABC` une seconde fois, puis `clientabc` | Refus avec le message « Un site nommé « ClientABC » existe déjà. » ; la liste ne change pas ; en Textual, le formulaire garde sa saisie | ☐ | ☐ |
| 3 | Refus d'une URI vide (critère 3) | Un nom avec une URI vide | Refus « L'URI principale du site ne peut pas être vide. » | ☐ | ☐ |
| 4 | Test d'un site qui répond (critères 4 et 5) | Tester `ClientABC` | Statut DISPONIBLE (vert), horodatage affiché, diagnostic `L3: 6/6 sondes, L4: port 443 ouvert, L7: 200` | ☐ | ☐ |
| 5 | Page absente (critère 6) | `Absent` / `https://www.google.com/page-inexistante-ephec`, puis le tester | INDISPONIBLE (rouge), `L7: 404` | ☐ | ☐ |
| 6 | Nom de domaine inexistant (critère 7) | `Fantome` / `site-inexistant.invalid`, puis le tester | INDISPONIBLE (rouge), `L3` et `L4` « nom de domaine introuvable », aucune mesure `L7` | ☐ | ☐ |
| 7 | ICMP bloqué, web en ordre (compensation par L4) | `Bloque` / `https://httpbin.org/get`, puis le tester | DISPONIBLE malgré `L3: 0/6 sondes` | ☐ | ☐ |
| 8 | Aucun serveur sur le port prévu (arrêt de la batterie sur L4) | `PortFerme` / `http://www.google.com:81`, puis le tester | INDISPONIBLE, `L4: délai dépassé (port 81)`, aucune mesure `L7` | ☐ | ☐ |
| 9 | Performance dégradée (RM-08) | `Lent` / `https://httpbin.org/delay/1`, puis le tester | Statut DISPONIBLE mais performance DEGRADEES (la colonne « Chargement L7 » affiche environ 1000 ms, au-dessus de 500 ms) ; la ligne est en **jaune** | ☐ | ☐ |
| 10 | Écart par rapport à la moyenne globale (sans réseau externe) | Mettre `FENETRE_PERFORMANCE_MIN = 1` dans `main.py`, ajouter `Local` / `localhost`, le tester, attendre plus d'une minute, puis le tester de nouveau | Après le 1er test, les colonnes RTT et Chargement affichent `(-)` (pas d'écart à comparer) ; après le 2e, un écart apparaît, par exemple `0.05 ms (-12 %)`. Remettre ensuite la valeur à 30 | ☐ | ☐ |
| 11 | Test de tous les sites (critère 9) | Les sites précédents, puis « Tester tous les sites » (simple : choix 3 ; Textual : `a`) | Tous les statuts et horodatages sont mis à jour ; en Textual, la ligne change site par site | ☐ | ☐ |
| 12 | URI sans schéma et espaces | `  Test  ` / `  www.google.com  ` | Nom `Test`, URI `https://www.google.com`, sans espaces | ☐ | ☐ |
| 13 | Choix ou nom invalide (simple) | Choix `x` ; tester un nom qui n'existe pas ; quitter avec Ctrl+D | « Choix inconnu. » ; « Refus : Aucun site nommé « … ». » ; « Au revoir. » sans trace d'erreur | ☐ | — |
| 14 | Écran réactif (Textual) | Lancer le test de tous les sites (`a`) et déplacer le curseur pendant les tests | L'écran répond ; le message « Test de … en cours… » change | — | ☐ |
| 15 | Tableau vide (Textual) | Au démarrage, appuyer sur `t` | Message « Aucun site à tester. », sans erreur | — | ☐ |
| 16 | Crochets dans un nom (Textual) | `[red]Test` / `www.google.com` | Le nom s'affiche tel quel, sans couleur parasite | — | ☐ |
| 17 | Tests automatiques (Textual) | Lancer `main.py --demo --interface textual` et ne rien faire pendant environ une minute | Les sites jamais testés sont testés automatiquement, un par un (messages « Test automatique de … en cours… », lignes mises à jour au fur et à mesure). Un site testé à la main n'est retesté qu'au bout de 15 minutes | — | ☐ |
| 18 | Surveillance (TUI simple) | Lancer `main.py --demo`, choisir `4` et attendre | Les sites jamais testés sont testés un par un (« Test automatique de … en cours… »), le tableau est réaffiché après chaque test ; Ctrl+C affiche « Surveillance arrêtée. » et ramène au menu | ☐ | — |

## Sites d'essai préchargés

Pour ne pas saisir les sites à la main, ajoutez `--demo` :
`venv/bin/python main.py --demo` (ou `--demo --interface textual`). Le
registre contient alors `ClientABC`, `Absent`, `Fantome`, `Bloque`,
`PortFerme`, `Lent` et `Local`, en statut INCONNU : il suffit de les tester
(un par un, ou tous ensemble). Ces sites sont ceux des scénarios 4 à 11 (le scénario 10 utilise `Local`).
Pour les scénarios d'ajout et de refus (1 à 3 et 12), lancez sans `--demo`.
Avec Textual, les sites jamais testés sont testés automatiquement dans la minute
qui suit le lancement : ils contactent donc de vrais sites sans action de votre
part. Dans la TUI simple, cela n'arrive que si vous choisissez `4. Surveiller`
(voir les deux derniers scénarios).

## Alternative locale pour le scénario 8

Une URI `http://localhost` (port 80 fermé sur la plupart des machines) doit
donner `L4: connexion refusée (port 80)`, sans passer par Internet.

## Série automatique sur de vrais sites

Le fichier `essais_reels.py`, à la racine du projet, vérifie les mêmes
comportements sans passer par les interfaces. Il commence par contrôler que
le réseau fonctionne : `venv/bin/python essais_reels.py`.
