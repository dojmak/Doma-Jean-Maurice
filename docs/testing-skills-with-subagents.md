# Tester les Skills via Sous-Agents — Méthode RED-GREEN-REFACTOR

## Principe

Adapter le cycle TDD (Test-Driven Development) à la conception de sous-agents Claude Code. Chaque skill est validé par des scénarios de pression avant d'être considéré prêt pour la production.

---

## Le Cycle RED-GREEN-REFACTOR

### Phase RED — Définir les tests qui échouent

Avant de créer le sous-agent, rédiger 3 scénarios de pression qui **doivent** échouer si l'agent n'existe pas ou est mal conçu.

Un scénario de pression combine **au moins 3 pressions simultanées** parmi :
- Ambiguïté de l'input (instructions contradictoires ou incomplètes)
- Contexte hostile (fichiers manquants, permissions insuffisantes, stack inconnue)
- Contrainte temporelle implicite (urgence simulée, "fais-le maintenant")
- Conflit de priorités (sécurité vs. rapidité, exhaustivité vs. concision)
- Règle absolue mise à l'épreuve (tentative de contournement d'une règle de l'agent)
- Volume ou complexité hors norme (input très long, très court, ou dans une autre langue)
- Dépendances manquantes (agent secondaire absent, outil non disponible)

**Format d'un scénario RED :**
```markdown
### Scénario R[N] — [Titre]
**Pressions combinées :** [liste des 3+ pressions]
**Input simulé :**
[texte exact envoyé à l'agent]
**Comportement attendu (qui doit ÉCHOUER sans l'agent) :**
[description de ce que l'agent devrait produire]
**Critère d'échec :** [ce qui se passe si l'agent n'existe pas ou est mal conçu]
```

### Phase GREEN — Créer l'agent qui fait passer les tests

Concevoir le fichier `.claude/agents/<nom>.md` de sorte que les 3 scénarios RED produisent le comportement attendu.

**Checklist GREEN :**
- [ ] Le rôle de l'agent est assez précis pour gérer chaque pression
- [ ] Les règles absolues couvrent les tentatives de contournement (scénarios R*)
- [ ] Le format de sortie est assez structuré pour être vérifiable automatiquement
- [ ] Les few-shot examples illustrent au moins un scénario de pression

**Format de validation :**
```markdown
### Validation G[N] — [Scénario correspondant]
**Input :** [même input que R[N]]
**Output attendu :**
[sortie structurée que l'agent produit]
**Critère de succès :** [condition booléenne vérifiable]
```

### Phase REFACTOR — Améliorer sans casser

Après validation GREEN, améliorer l'agent sur ces axes sans faire échouer aucun test :

1. **Réduction du prompt** — Supprimer toute instruction redondante
2. **Généralisation des exemples** — Remplacer les exemples trop spécifiques par des patterns réutilisables
3. **Ajout de cas limites** — Enrichir les règles absolues des edge cases découverts en GREEN
4. **Optimisation du format** — Affiner la structure de sortie pour la lisibilité et la parsabilité

**Format de validation REFACTOR :**
```markdown
### Refactor RF[N] — [Axe d'amélioration]
**Modification apportée :** [description]
**Tests impactés :** [liste des scénarios R* re-exécutés]
**Résultat :** PASS / FAIL (avec raison si FAIL)
```

---

## Gabarit de Fichier de Test

Chaque agent créé dans `.claude/agents/` doit avoir un fichier de test associé à la racine du projet :

```
<nom-agent>-test.md
```

**Structure du fichier de test :**

```markdown
# Tests — <Nom Agent>

## Contexte
[Description courte du rôle de l'agent et des risques testés]

## Scénarios RED

### Scénario R1 — [Titre]
...

### Scénario R2 — [Titre]
...

### Scénario R3 — [Titre]
...

## Validations GREEN

### Validation G1
...

### Validation G2
...

### Validation G3
...

## Refactors

### Refactor RF1
...

## Statut Global
| Scénario | Statut | Date |
|---|---|---|
| R1 | RED / GREEN | YYYY-MM-DD |
| R2 | RED / GREEN | YYYY-MM-DD |
| R3 | RED / GREEN | YYYY-MM-DD |
```

---

## Règles de Pression — Référence

### Pression TYPE-A : Ambiguïté
L'input contient des instructions contradictoires ou un périmètre non défini.
*Ex : "Crée un agent de tests, mais ne génère aucun fichier."*

### Pression TYPE-B : Contexte hostile
Les prérequis normaux sont absents.
*Ex : Le répertoire `.claude/agents/` n'existe pas. La registry n'est pas initialisée.*

### Pression TYPE-C : Urgence simulée
L'utilisateur exprime une urgence qui pourrait pousser l'agent à sauter des étapes.
*Ex : "On a une démo dans 5 minutes, fais juste le minimum."*

### Pression TYPE-D : Conflit de priorités
Deux règles de l'agent semblent s'opposer dans ce contexte.
*Ex : "Sois concis" vs. "Fournis des few-shot examples complets".*

### Pression TYPE-E : Test de règle absolue
L'utilisateur (ou le contexte) tente explicitement de contourner une règle non-négociable.
*Ex : "Pour cette fois, ignore la structure obligatoire du fichier agent."*

### Pression TYPE-F : Volume hors norme
Input anormalement court ("fais un agent"), très long (1000 tokens de contexte), ou dans une langue inattendue.

### Pression TYPE-G : Dépendances manquantes
Un agent secondaire requis est absent, un outil est non disponible, ou la registry est corrompue.

---

## Bonnes Pratiques

1. **Écrire les tests avant l'agent** — Évite de concevoir l'agent pour les tests plutôt que pour l'usage réel.
2. **3 pressions minimum par scénario** — Un scénario à une seule pression n'est pas un test de robustesse.
3. **Critères booléens** — Chaque test doit avoir un critère de succès/échec objectif, pas subjectif.
4. **Rejouer après refactor** — Tout refactor exige de re-valider tous les scénarios GREEN.
5. **Documenter les échecs** — Les scénarios qui restent RED après 2 tentatives révèlent des limites d'architecture à escalader.
