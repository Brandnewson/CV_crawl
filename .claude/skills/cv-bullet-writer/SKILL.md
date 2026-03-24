# cv-bullet-writer skill

Applies whenever you are writing or generating CV bullet points - for work experience
or technical projects. These rules are non-negotiable and override any general writing
preferences.

---

## Bullet quality rules

Every bullet MUST satisfy ALL of the following:

1. **Keyword hit OR concrete technical action** - the bullet must either mirror at
   least one JD keyword verbatim, OR describe a concrete technical action (tool,
   method, system, language, result). A bullet that only restates the job title
   adds no value and must be rejected.

2. **Outcome or impact** - state what the work produced, enabled, or improved.
   Acceptable forms: a metric, a system that now works, a team capability unlocked,
   a process automated. "Worked on X" with no outcome is not acceptable.

3. **British English** - use British spelling throughout (e.g. "optimised" not
   "optimized", "analysed" not "analyzed", "modelling" not "modeling").

4. **No duplicates** - check all bullets already written in the CV. No bullet may
   restate the same fact in the same phrasing as an existing bullet.

5. **No filler openings** - do not open with constructions like:
   - "Served as a [title] in..."
   - "Was responsible for..."
   - "Assisted with..."
   - "Helped to..."
   These waste the opening verb slot and add no information.

6. **Strong past-tense action verb as first word** - examples:
   Developed, Built, Implemented, Designed, Delivered, Deployed, Automated,
   Engineered, Integrated, Optimised, Analysed, Modelled, Led, Trained, Mentored.

---

## Bad example (REJECT)

> "Served as an NCO technical specialist in the Republic of Singapore Navy defense
> environment."

Failures: filler opening ("Served as"), no keyword hit, no concrete action, no outcome.

## Good example (ACCEPT)

> "Taught 4-stroke and 2-stroke engine operation to reservists, bringing teams of up
> to 10 up to speed on marine systems within constrained timeframes."

Why: strong verb ("Taught"), concrete action (engine instruction), outcome (team
capability restored), no filler.

---

## Work experience constraint

For work experience bullets, ONLY use facts from `data/cv-work-experience.json`.
Do not infer, extrapolate, or add anything beyond what is explicitly listed in the
verified_facts for each role. If you do not have enough verified facts to fill a
bullet slot with a quality bullet, ask the user rather than inventing content.

---

## Length

- Target: 100-110 characters per bullet
- Hard maximum: 120 characters
- Hard minimum: 80 characters (a bullet shorter than this is almost certainly
  too vague)

