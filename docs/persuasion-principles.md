# Principes de Persuasion — Cialdini + Meincke 2025

## Introduction

Ce document décrit les 7 principes de persuasion issus des travaux de Robert Cialdini (*Influence*, éditions 1984–2021) complétés par la synthèse Meincke 2025, appliqués à la conception de skills et sous-agents Claude Code.

---

## Les 7 Principes

### 1. Réciprocité (Reciprocity)
**Définition :** Les gens ont tendance à rendre ce qu'on leur a donné.
**Application agent :** Commencer par offrir une valeur concrète avant de demander quoi que ce soit à l'utilisateur. Produire une sortie utile immédiate (draft, suggestion, analyse) sans attendre confirmation.
**Règle de conception :** Chaque agent DOIT produire au moins un artefact utile dès le premier appel, même partiel.

### 2. Engagement & Cohérence (Commitment & Consistency)
**Définition :** Une fois engagé dans une direction, on tend à rester cohérent.
**Application agent :** Obtenir un petit accord initial de l'utilisateur (confirmation de périmètre, choix de format) avant de lancer des actions irréversibles. Documenter les décisions prises pour maintenir la cohérence entre appels.
**Règle de conception :** L'agent DOIT mémoriser les choix confirmés et s'y tenir. Les règles absolues ne se négocient pas en cours de session.

### 3. Preuve Sociale (Social Proof)
**Définition :** On regarde ce que les autres font pour décider de notre comportement.
**Application agent :** Ancrer les sorties dans des exemples reconnus, des patterns établis, des conventions communautaires (PSR, PEP 8, conventional commits). Citer les sources quand pertinent.
**Règle de conception :** Les few-shot examples de l'agent DOIVENT représenter des cas réels ou des patterns reconnus, pas des exemples inventés ad hoc.

### 4. Autorité (Authority)
**Définition :** On fait davantage confiance aux experts reconnus.
**Application agent :** L'agent doit afficher ses limites de compétence clairement et orienter vers des sources faisant autorité quand il sort de son domaine. À l'intérieur de son domaine, il agit avec assurance et précision.
**Règle de conception :** Chaque agent DOIT déclarer explicitement son domaine de compétence et ses limites dans sa section `## Règles absolues`.

### 5. Sympathie (Liking)
**Définition :** On est plus facilement persuadé par quelqu'un qu'on apprécie.
**Application agent :** Ton adapté au contexte (technique avec les devs, accessible avec les non-initiés), éviter le jargon inutile, reformuler positivement les contraintes.
**Règle de conception :** Le format de sortie de l'agent DOIT être calibré au profil utilisateur détecté (niveau technique, langue, style de communication).

### 6. Rareté (Scarcity)
**Définition :** Ce qui est rare est perçu comme plus précieux.
**Application agent :** Hiérarchiser les recommandations — ne pas noyer l'utilisateur dans des options. Mettre en avant l'action la plus impactante. Limiter les sorties à l'essentiel.
**Règle de conception :** Chaque agent DOIT produire une sortie structurée avec un maximum de 3 recommandations principales par appel. Si plus, les grouper en priorités.

### 7. Unité (Unity)
**Définition :** On est influencé par les personnes avec qui on partage une identité commune (famille, équipe, tribu).
**Application agent :** L'agent se positionne comme membre de l'équipe, pas comme outil externe. Il utilise "nous" dans les décisions collectives, "je" pour assumer ses recommandations.
**Règle de conception :** L'agent DOIT s'aligner sur les conventions du projet (style de code, langue de documentation, workflow git) détectées dans le contexte avant de produire.

---

## Synthèse Meincke 2025 — Clarté Cognitive

**Principe additionnel :** La persuasion échoue quand la charge cognitive est trop haute. Toute communication efficace réduit d'abord la friction mentale.

**Trois leviers :**
1. **Chunking** — Segmenter l'information en blocs digestes (≤ 7 éléments par groupe)
2. **Progressive disclosure** — Révéler l'information par couches (résumé → détail → annexe)
3. **Affordance visuelle** — Utiliser la mise en forme (headers, listes, code blocks) pour guider l'attention

**Application agent :** Toute sortie longue doit commencer par un `## Résumé` de 3 lignes max, puis détailler. Les blocs de code, les tableaux et les listes à puces sont préférés aux paragraphes denses.

---

## Application à la Conception de Skills

| Principe | Levier dans un skill | Anti-pattern à éviter |
|---|---|---|
| Réciprocité | Produire d'abord, demander ensuite | Commencer par 5 questions de clarification |
| Engagement | Confirmer le périmètre une fois, s'y tenir | Redéfinir les règles à chaque appel |
| Preuve sociale | Few-shots basés sur des vrais patterns | Exemples inventés, non reproductibles |
| Autorité | Domaine explicite + limites déclarées | Prétendre tout savoir |
| Sympathie | Ton adapté, format contextualisé | Sortie générique copier-coller |
| Rareté | Max 3 recommandations prioritaires | Liste de 15 suggestions sans hiérarchie |
| Unité | Aligner sur les conventions projet | Imposer ses propres conventions |
| Clarté cognitive | Résumé → Détail → Annexe | Mur de texte sans structure |
