# Vérification manuelle des interfaces

Cette liste de contrôle permet de vérifier à la main que les deux interfaces
se comportent comme prévu. Les scénarios 1 à 5 reprennent les critères
d'acceptation de la page MVP du wiki ; les suivants vérifient les testeurs
L3 et L4 et quelques cas limites ; les scénarios 19 à 25 vérifient les pages
d'un site et la modification d'un site (sprint 2).

Les scénarios 1 à 9, 24 et 25 contactent de vrais sites (`www.google.com`,
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
Le RTT (ligne du site) et le chargement (ligne de chaque page) comparent la
moyenne de la dernière fenêtre (30 minutes) à la moyenne de tous les tests :
tant que le site n'a pas plus de 30 minutes d'historique, l'écart n'est pas
calculable et s'affiche `(-)`.

## Lecture de l'écran

Chaque site occupe une ligne, suivie d'une ligne par page, en retrait, la
« Page d'accueil » en premier.

- La **ligne d'un site** donne ses statuts de disponibilité et de
  performance, son RTT, l'horodatage du dernier test et les diagnostics L3
  et L4. Elle est verte (DISPONIBLE), **orange** (PARTIELLEMENT_INDISPONIBLE),
  rouge (INDISPONIBLE) ou jaune (INCONNU, ou DISPONIBLE aux performances
  dégradées).
- La **ligne d'une page** donne le verdict et le diagnostic (code HTTP) de
  son dernier test, son chargement moyen et son URI. Elle est rouge si le
  verdict est KO, jaune si la page est OK mais plus lente que 500 ms, verte
  sinon. Une page jamais testée affiche `-` et n'a pas de couleur.

## Gérer les pages et modifier un site

- **TUI simple** : les choix `5` (modifier un site), `6` (ajouter une page) et
  `7` (supprimer une page) demandent le nom du site, puis les autres
  informations.
- **TUI Textual** : sélectionner une ligne avec les flèches, remplir les champs
  « Nom » et « URI », puis cliquer un bouton. « Ajouter une page » ajoute la
  page au site de la ligne sélectionnée ; « Supprimer la page » exige une
  ligne de page ; « Modifier le site » remplace le nom et l'URI du site de la
  ligne sélectionnée.
- Dans les deux interfaces, une saisie vide n'est pas remplacée par la valeur
  actuelle : elle est refusée.

## Scénarios

Pour chaque scénario, cochez la case de l'interface vérifiée.

| # | Scénario | Saisie | Résultat attendu | Simple | Textual |
|---|---|---|---|---|---|
| 1 | Ajout d'un site (critère 1) | `ClientABC` / `www.google.com` | Ligne de site jaune, statuts de disponibilité et de performance INCONNU, RTT, horodatage et diagnostic `-`, URI principale `https://www.google.com` ; dessous, une ligne de page « Page d'accueil » sans couleur (verdict, chargement et diagnostic `-`) avec la même URI | ☐ | ☐ |
| 2 | Refus d'un doublon (critère 2) | `ClientABC` une seconde fois, puis `clientabc` | Refus avec le message « Un site nommé « ClientABC » existe déjà. » ; la liste ne change pas ; en Textual, le formulaire garde sa saisie | ☐ | ☐ |
| 3 | Refus d'une URI vide (critère 3) | Un nom avec une URI vide | Refus « L'URI principale du site ne peut pas être vide. » | ☐ | ☐ |
| 4 | Test d'un site qui répond (critères 4 et 5) | Tester `ClientABC` | Site DISPONIBLE (vert), horodatage affiché, diagnostic du site `L3: 6/6 sondes, L4: port 443 ouvert` ; page d'accueil verte, verdict OK, diagnostic `200` | ☐ | ☐ |
| 5 | Page absente (critère 6) | `Absent` / `https://www.google.com/page-inexistante-ephec`, puis le tester | Site INDISPONIBLE (rouge) ; page d'accueil rouge, verdict KO, diagnostic `404` | ☐ | ☐ |
| 6 | Nom de domaine inexistant (critère 7) | `Fantome` / `site-inexistant.invalid`, puis le tester | Site INDISPONIBLE (rouge), `L3` et `L4` « nom de domaine introuvable » ; page d'accueil sans mesure (verdict et diagnostic `-`) | ☐ | ☐ |
| 7 | ICMP bloqué, web en ordre (compensation par L4) | `Bloque` / `https://httpbin.org/get`, puis le tester | DISPONIBLE malgré `L3: 0/6 sondes` | ☐ | ☐ |
| 8 | Aucun serveur sur le port prévu (arrêt de la batterie sur L4) | `PortFerme` / `http://www.google.com:81`, puis le tester | INDISPONIBLE, `L4: délai dépassé (port 81)` ; page d'accueil sans mesure (verdict `-`) | ☐ | ☐ |
| 9 | Performance dégradée (RM-08) | `Lent` / `https://httpbin.org/delay/1`, puis le tester | Site DISPONIBLE mais performance DEGRADEES ; la ligne du site est en **jaune** ; la page d'accueil, verdict OK, affiche un chargement d'environ 1000 ms (au-dessus de 500 ms) et est aussi en **jaune** | ☐ | ☐ |
| 10 | Écart par rapport à la moyenne globale (sans réseau externe) | Mettre `FENETRE_PERFORMANCE_MIN = 1` dans `main.py`, ajouter `Local` / `localhost`, le tester, attendre plus d'une minute, puis le tester de nouveau | Après le 1er test, le RTT (ligne du site) et le chargement (ligne de la page d'accueil) affichent `(-)` (pas d'écart à comparer) ; après le 2e, un écart apparaît, par exemple `0.05 ms (-12 %)`. Remettre ensuite la valeur à 30 | ☐ | ☐ |
| 11 | Test de tous les sites (critère 9) | Les sites précédents, puis « Tester tous les sites » (simple : choix 3 ; Textual : `a`) | Tous les statuts et horodatages sont mis à jour ; en Textual, la ligne change site par site | ☐ | ☐ |
| 12 | URI sans schéma et espaces | `  Test  ` / `  www.google.com  ` | Nom `Test`, URI `https://www.google.com`, sans espaces | ☐ | ☐ |
| 13 | Choix ou nom invalide (simple) | Choix `x` ; tester un nom qui n'existe pas ; quitter avec Ctrl+D | « Choix inconnu. » ; « Refus : Aucun site nommé « … ». » ; « Au revoir. » sans trace d'erreur | ☐ | — |
| 14 | Écran réactif (Textual) | Lancer le test de tous les sites (`a`) et déplacer le curseur pendant les tests | L'écran répond ; le message « Test de … en cours… » change | — | ☐ |
| 15 | Tableau vide (Textual) | Au démarrage, appuyer sur `t` | Message « Aucun site à tester. », sans erreur | — | ☐ |
| 16 | Crochets dans un nom (Textual) | `[red]Test` / `www.google.com` | Le nom s'affiche tel quel, sans couleur parasite | — | ☐ |
| 17 | Tests automatiques (Textual) | Lancer `main.py --demo --interface textual` et ne rien faire pendant environ une minute | Les sites jamais testés sont testés automatiquement, un par un (messages « Test automatique de … en cours… », lignes mises à jour au fur et à mesure). Un site testé à la main n'est retesté qu'au bout de 15 minutes | — | ☐ |
| 18 | Surveillance (TUI simple) | Lancer `main.py --demo`, choisir `4` et attendre | Les sites jamais testés sont testés un par un (« Test automatique de … en cours… »), le tableau est réaffiché après chaque test ; Ctrl+C affiche « Surveillance arrêtée. » et ramène au menu | ☐ | — |
| 19 | Ajout de pages (EF-01.4) | Site `ClientABC` / `www.google.com`, puis les pages `PageA` / `www.google.com/a` et `PageB` / `www.google.com/b` | Deux lignes de page apparaissent sous le site, après « Page d'accueil », dans l'ordre d'ajout, avec le verdict `-` ; confirmation « Page « PageA » ajoutée » (Textual : « … ajoutée au site « ClientABC » ») ; une URI sans schéma reçoit `https://` | ☐ | ☐ |
| 20 | Refus d'une page en double ou vide (EF-01.4, EF-01.6) | Sur `ClientABC` : `pagea` / `www.google.com/autre` ; puis `Copie` / `www.google.com/a` ; puis une page sans nom ; puis une page avec une URI vide | Quatre refus : « Une page nommée « PageA » existe déjà. » ; « La page « PageA » a déjà l'URI https://www.google.com/a. » ; « Le nom de la page ne peut pas être vide. » ; « L'URI de la page ne peut pas être vide. » ; la liste des pages ne change pas ; en Textual, le formulaire garde sa saisie | ☐ | ☐ |
| 21 | Suppression d'une page (EF-01.5) | Supprimer `PageB`, puis tenter de supprimer `Page d'accueil` ; (simple) tenter de supprimer `PageB` une seconde fois ; (Textual) sélectionner la ligne d'un site et cliquer « Supprimer la page » | `PageB` disparaît (« … supprimée (ses mesures restent dans l'historique). ») ; « Refus : La page principale ne peut pas être supprimée. » ; simple : « Refus : Aucune page nommée « PageB ». » ; Textual : « Sélectionnez la ligne de la page à supprimer. » | ☐ | ☐ |
| 22 | Modification d'un site (EF-01.2, EF-01.3) | Après avoir testé `ClientABC` (scénario 4), le modifier : nom `ClientXYZ`, URI `www.google.be` | « Site « ClientXYZ » modifié. » ; le site a son nouveau nom et l'URI principale `https://www.google.be`, à la même position dans la liste ; l'URI de la page d'accueil change aussi ; `PageA` est inchangée ; l'horodatage, les statuts et le verdict de la page d'accueil sont conservés jusqu'au prochain test | ☐ | ☐ |
| 23 | Refus d'une modification (EF-01.2, EF-01.3, EF-01.6) | Avec `ClientXYZ` (scénario 22) et un site `Autre` / `localhost` : modifier `Autre` avec le nom `clientxyz` ; modifier `ClientXYZ` avec une URI vide ; modifier `ClientXYZ` avec l'URI `www.google.com/a` (celle de `PageA`) ; enfin renommer `Autre` en `AUTRE` | Trois refus : « Un site nommé « ClientXYZ » existe déjà. » ; « L'URI principale du site ne peut pas être vide. » ; « La page « PageA » a déjà l'URI https://www.google.com/a. » ; les sites ne changent pas ; le renommage en `AUTRE` (même nom, autre casse) est accepté | ☐ | ☐ |
| 24 | Disponibilité partielle (RM-04) | Site `Partiel` / `www.google.com`, avec la page `Absente` / `https://www.google.com/page-inexistante-ephec`, puis le tester | Site PARTIELLEMENT_INDISPONIBLE, ligne du site en **orange** ; page d'accueil verte (OK, `200`) ; `Absente` rouge (KO, `404`) | ☐ | ☐ |
| 25 | Performance calculée page par page (RM-08) | Sur `Partiel` : supprimer `Absente`, ajouter la page `Lente` / `https://httpbin.org/delay/1`, puis tester le site ; enfin supprimer `Lente` | Performance DEGRADEES alors que la page d'accueil est rapide ; ligne `Lente` **jaune** (chargement d'environ 1000 ms), page d'accueil verte ; après la suppression de `Lente`, la performance redevient NORMALES sans nouveau test (si le RTT reste sous 100 ms) | ☐ | ☐ |

## Dashboard (ENF-05)

`venv/bin/python main.py --demo --dashboard` ouvre une fenêtre Tkinter en plus
de l'interface simple du terminal. Le dashboard se combine seulement avec
l'interface simple pour l'instant. Tkinter doit être installé pour la version
de Python du projet (sur macOS avec Homebrew : `brew install python-tk@3.12`).

| # | Scénario | Action | Résultat attendu | OK |
|---|---|---|---|---|
| D1 | Affichage initial (EF-02.1) | Lancer avec `--demo --dashboard` | Une fenêtre liste les 7 sites, en jaune, statuts INCONNU, dernier test `-` ; le menu de la TUI s'affiche dans le terminal | ☐ |
| D2 | Rafraîchissement après un test manuel (EF-02.3) | TUI, choix 2 : tester `ClientABC` | La ligne `ClientABC` du dashboard change toute seule en moins d'une seconde (vert si disponible), sans toucher à la fenêtre | ☐ |
| D3 | Rafraîchissement à chaque site testé | TUI, choix 3 : tester tous les sites | Les lignes se mettent à jour une à une, pendant que la TUI teste ; `Absent` et `Fantome` en rouge (EF-02.4) | ☐ |
| D4 | Ajout d'un site | TUI, choix 1 : ajouter `Nouveau` / `www.google.com` | Une nouvelle ligne jaune apparaît dans le dashboard | ☐ |
| D5 | Modification d'un site | TUI, choix 5 : renommer `Nouveau` en `Renomme` | La ligne porte le nouveau nom | ☐ |
| D6 | Test automatique sans action (EF-03.7) | TUI, choix 4 (surveiller), laisser tourner | Les sites jamais testés sont testés et le dashboard se met à jour sans action ; Ctrl+C dans le terminal affiche « Surveillance arrêtée. » et ramène au menu, la fenêtre reste ouverte | ☐ |
| D7 | Sélection | Cliquer sur une ligne, puis attendre un rafraîchissement (D2 ou D6) | La ligne reste sélectionnée après le rafraîchissement ; cliquer sur les titres ne change rien | ☐ |
| D8 | Fermeture depuis la TUI | TUI, choix 0 | La fenêtre se ferme et le programme se termine | ☐ |
| D9 | Fermeture de la fenêtre | Fermer la fenêtre avec le bouton de fermeture | Le programme se termine | ☐ |
| D10 | Combinaison refusée | `main.py --dashboard --interface textual` | Message d'erreur « --dashboard se combine seulement avec --interface simple », aucune fenêtre | ☐ |
| D11 | Test d'un site depuis la fenêtre (EF-03.1) | Sélectionner `Google`, puis « Tester le site sélectionné » | La ligne indique « (test en cours) » aussitôt, la fenêtre reste utilisable pendant le test, puis la ligne prend ses statuts sans autre action | ☐ |
| D12 | Sans sélection | Désélectionner (ou lancer sans rien sélectionner), puis « Tester le site sélectionné » | Le message « Sélectionnez d'abord un site. » apparaît sous le tableau, aucun test | ☐ |
| D13 | Test de tous les sites (EF-03.4) | « Tester tous les sites » | Tous les sites passent en « test en cours », puis se mettent à jour l'un après l'autre ; la TUI du terminal reste utilisable | ☐ |
| D14 | Test déjà en cours | Cliquer deux fois de suite sur « Tester tous les sites » | Le message « Test déjà en cours. » apparaît, chaque site n'est testé qu'une fois | ☐ |
| D15 | Les deux interfaces actives (scénario 3) | Lancer un test depuis la fenêtre, puis un autre depuis la TUI (choix 2) | Le dashboard montre les deux résultats ; la TUI affiche le résultat du test fait depuis la fenêtre au prochain affichage de l'écran | ☐ |

## Sites d'essai préchargés

Pour ne pas saisir les sites à la main, ajoutez `--demo` :
`venv/bin/python main.py --demo` (ou `--demo --interface textual`). Le
registre contient alors `ClientABC`, `Absent`, `Fantome`, `Bloque`,
`PortFerme`, `Lent` et `Local`, en statut INCONNU : il suffit de les tester
(un par un, ou tous ensemble). Ces sites sont ceux des scénarios 4 à 11 (le scénario 10 utilise `Local`).
Pour les scénarios d'ajout et de refus (1 à 3 et 12) et pour ceux des pages et de la modification d'un site (19 à 25), lancez sans `--demo` : leurs sites se saisissent à la main.
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
