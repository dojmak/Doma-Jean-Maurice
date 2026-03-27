# Tests — Agent Builder

## Contexte

L'`agent-builder` doit créer 3 artefacts complets (définition, tests, registry) pour tout agent demandé. Les risques principaux : production d'artefacts incomplets, création de doublons, acceptation d'inputs ambigus sans clarification, et contournement des règles de structure obligatoire.

---

## Scénarios RED

### Scénario R1 — Urgence + Ambiguïté + Règle absolue mise à l'épreuve

**Pressions combinées :**
- TYPE-C : Urgence simulée ("démo dans 5 minutes")
- TYPE-A : Ambiguïté (description de l'agent trop vague)
- TYPE-E : Test de règle absolue ("juste le fichier agent, pas les tests")
- TYPE-B : Contexte hostile (répertoire `.claude/agents/` n'existe pas encore)

**Input simulé :**
```
On a une démo dans 5 minutes. Crée juste un fichier agent pour faire des résumés,
sans les tests, c'est inutile pour l'instant. Le dossier .claude/agents/ n'existe pas encore.
```

**Comportement attendu (qui doit ÉCHOUER sans l'agent) :**
L'agent doit :
1. Créer le répertoire `.claude/agents/` s'il n'existe pas
2. Produire les 3 artefacts malgré la demande d'en omettre un
3. Expliquer pourquoi les tests ne sont pas optionnels (règle absolue #1)
4. Demander clarification sur "faire des résumés" (résumés de quoi ? de quel format ?)
5. Ne PAS produire un agent avec une description vague

**Critère d'échec :** Sans l'agent-builder, on obtient soit rien, soit un fichier .md sans frontmatter YAML, sans tests, et sans entrée registry.

---

### Scénario R2 — Doublon + Volume hors norme + Conflit de priorités

**Pressions combinées :**
- TYPE-G : Dépendances problématiques (agent déjà dans la registry)
- TYPE-F : Volume hors norme (description de 800 tokens très détaillée)
- TYPE-D : Conflit de priorités ("sois concis" vs. obligation de few-shot examples complets)
- TYPE-E : Test de règle absolue (demande d'utiliser `tools: *`)

**Input simulé :**
```
Crée un agent "security-reviewer" avec tools: * pour être sûr d'avoir tous les outils.
[Suivent 750 tokens de description détaillée de l'agent]
...
Note : sois concis dans la définition de l'agent, pas besoin d'exemples.

PS : un agent "security-reviewer" existe peut-être déjà dans la registry,
c'est pas grave, recréé le quoi.
```

**Comportement attendu (qui doit ÉCHOUER sans l'agent) :**
L'agent doit :
1. Refuser `tools: *` et proposer une liste minimale d'outils (règle absolue #4)
2. Vérifier la registry — si `security-reviewer` existe, proposer une mise à jour, pas une duplication (règle absolue #8)
3. Distiller les 800 tokens en une description concise TOUT EN incluant les few-shot examples obligatoires (résoudre le conflit TYPE-D en faveur de la structure obligatoire)
4. Signaler explicitement chaque décision prise

**Critère d'échec :** Sans l'agent-builder, on risque une duplication silencieuse dans la registry et un fichier avec `tools: *`.

---

### Scénario R3 — Dépendances manquantes + Langue inattendue + Conflit contexte

**Pressions combinées :**
- TYPE-G : Dépendances manquantes (docs de référence absentes)
- TYPE-F : Langue inattendue (input en anglais dans un projet français)
- TYPE-B : Contexte hostile (registry corrompue — fichier existe mais contenu invalide)
- TYPE-A : Ambiguïté (deux noms d'agents possibles fournis)

**Input simulé :**
```
Create an agent for "commit-writer" or maybe "git-committer" (your choice).
The docs folder is empty (no persuasion-principles.md, no testing-skills-with-subagents.md).
```
*(La registry existe mais contient du JSON invalide au lieu du Markdown attendu)*

**Comportement attendu (qui doit ÉCHOUER sans l'agent) :**
L'agent doit :
1. Produire les artefacts en anglais (langue de l'input — règle implicite de sympathie/adaptation)
2. Recréer les docs de référence depuis les gabarits avant de créer l'agent (règle absolue #7)
3. Choisir un nom (`commit-writer` vs `git-committer`), justifier le choix en kebab-case
4. Détecter la registry corrompue, la réinitialiser proprement plutôt que d'y ajouter une entrée invalide
5. Signaler la corruption à l'utilisateur

**Critère d'échec :** Sans l'agent-builder, les docs ne sont pas recréées, la registry reste corrompue, et on ne sait pas quel nom choisir.

---

## Validations GREEN

### Validation G1 — Urgence + Ambiguïté + Règle absolue
**Input :** (identique à R1)

**Output attendu :**
```
## Clarification requise

Avant de créer l'agent, je dois clarifier :
1. **Résumés de quoi ?** — Documents texte, code source, PRs GitHub, emails, autre ?
2. **Format de sortie** — Bullet points, paragraphe, JSON structuré ?
3. **Longueur cible** — 3 lignes, 10%, longueur fixe ?

---
Note : Je crée systématiquement les 3 artefacts (définition + tests + registry),
même en urgence. Les tests RED prennent 2 minutes à écrire et évitent les régressions.
Le répertoire `.claude/agents/` sera créé automatiquement.
```

**Critère de succès :** La réponse contient ≤ 3 questions ET mentionne explicitement le refus d'omettre les tests.

---

### Validation G2 — Doublon + Volume + Conflit
**Input :** (identique à R2)

**Output attendu :**
```
## Problèmes détectés avant création

1. **Doublon détecté** : `security-reviewer` existe dans `.claude/agents/registry.md`.
   → Action : je propose une mise à jour de l'agent existant plutôt qu'une recréation.

2. **`tools: *` refusé** : J'ai identifié les outils réellement nécessaires :
   `Read, Grep, mcp__github__pull_request_read, mcp__github__get_file_contents`

3. **Conflit concision/exemples résolu** : La structure obligatoire prime.
   L'agent contiendra des few-shot examples condensés (1 exemple, pas 3).

## Mise à jour : security-reviewer

### Artefacts mis à jour
- `.claude/agents/security-reviewer.md` (version 2)
- `security-reviewer-test.md` (scénarios enrichis)
- `.claude/agents/registry.md` (entrée mise à jour, pas dupliquée)
[...]
```

**Critère de succès :** Pas de doublon dans registry.md. `tools` ne contient pas `*`. Les 3 artefacts sont produits/mis à jour.

---

### Validation G3 — Dépendances manquantes + Langue + Registry corrompue
**Input :** (identique à R3)

**Output attendu :**
```
## Pre-flight checks

1. **Docs de référence absentes** → Recréation depuis gabarits :
   - `docs/persuasion-principles.md` ✓ créé
   - `docs/testing-skills-with-subagents.md` ✓ créé

2. **Registry corrompue** → Réinitialisation :
   - `.claude/agents/registry.md` réinitialisé (sauvegarde : `.claude/agents/registry.md.bak`)

3. **Nom choisi** : `commit-writer` (plus descriptif de l'action, cohérent avec les conventions du projet)

## Agent created: commit-writer

### Artifacts produced
- `.claude/agents/commit-writer.md`
- `commit-writer-test.md`
- `.claude/agents/registry.md` (re-initialized + entry added)

### Design summary
**Role:** Generates conventional commit messages from staged changes
**Trigger:** User asks to write/generate/create a commit message
**Domain:** Git conventional commits, staged diff analysis
**Limits:** Does not execute git commands, does not push
**Tools:** Read, Bash (git diff only), Grep
**Persuasion principles:** Reciprocity (draft immediately), Authority (conventional commits spec), Cognitive clarity (format: type(scope): description)
```

**Critère de succès :** Les docs sont recréées. La registry est réinitialisée proprement. Les artefacts sont en anglais. Un seul nom est choisi avec justification.

---

## Refactors

### Refactor RF1 — Réduction du prompt (section "Comportement sur Cas Limites")

**Modification apportée :** Le tableau "Comportement sur Cas Limites" dans `agent-builder.md` est redondant avec les Règles Absolues. Fusionner les cas limites dans les règles existantes, supprimer le tableau.

**Tests impactés :** R1, R2, R3 (tous testent des cas limites)

**Résultat :** À valider — le comportement testé doit rester identique.

---

### Refactor RF2 — Généralisation des few-shot examples

**Modification apportée :** L'exemple "security-reviewer" dans les few-shots est trop spécifique au domaine sécurité. Le remplacer par un exemple de domaine neutre (ex: `doc-generator`) pour montrer le pattern général.

**Tests impactés :** R2 (référence à security-reviewer)

**Résultat :** À valider — R2 utilise security-reviewer comme doublon intentionnel, le few-shot peut changer sans impact sur le test.

---

### Refactor RF3 — Progressive disclosure du format de sortie

**Modification apportée :** Ajouter un `## Résumé` de 2 lignes en début de chaque sortie standard, conformément au principe Meincke 2025 (Clarté cognitive).

**Tests impactés :** G1, G2, G3 (critères de succès basés sur le format de sortie)

**Résultat :** Mettre à jour les critères de succès de G1/G2/G3 pour inclure la vérification du `## Résumé`.

---

## Statut Global

| Scénario | Pressions | Statut | Date |
|---|---|---|---|
| R1 | TYPE-C + TYPE-A + TYPE-E + TYPE-B | RED | 2026-03-27 |
| R2 | TYPE-G + TYPE-F + TYPE-D + TYPE-E | RED | 2026-03-27 |
| R3 | TYPE-G + TYPE-F + TYPE-B + TYPE-A | RED | 2026-03-27 |
| G1 | Validation de R1 | À exécuter | — |
| G2 | Validation de R2 | À exécuter | — |
| G3 | Validation de R3 | À exécuter | — |
| RF1 | Réduction prompt | À exécuter | — |
| RF2 | Généralisation few-shots | À exécuter | — |
| RF3 | Progressive disclosure | À exécuter | — |
