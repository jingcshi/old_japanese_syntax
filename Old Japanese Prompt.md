# Prompt A: Script Function

You are working on an Old Japanese Man'yōgana usage.

## Task

You will receive a text corpus of old Japanese. For each graph in the input text, determine whether it functions as:

- **PHON** = phonograph 
- **LOG** = logograph
- **UNC** = uncertain

Use surrounding context, corpus conventions, and known Man'yōgana patterns.

## Important

- Make sure you annotate every character in the correct order. Do not miss and do not duplicate.
- Do NOT transliterate.
- Analyze each graph in context.
- If evidence is insufficient, choose UNC.

## Example

**Input:**
```
篭毛與
```

**Output:**
```json
{
  "text":[
    {"char":"篭","annotation":"LOG", "reasoning":null},
    {"char":"毛","annotation":"PHON", "reasoning":null},
    {"char":"與","annotation":"PHON", "reasoning":null}
  ]
}
```

**Now analyze:**

**Input:**
```
{TEXT}
```

---

# Prompt B: Historical Transcription

You are a historical linguist specializing in Old Japanese phonology, Man'yōgana orthography, and early Japanese philology.

## Task

Convert the input Man'yōgana text into Old Japanese phonemic transcription.

You MUST use the Script Function labels from Prompt A for each graph:

- **PHON** = phonographic graph (used for sound value)
- **LOG** = logographic graph (used for semantic value)
- **UNC** = uncertain or ambiguous usage

Your goal is to recover the most plausible Old Japanese linguistic form represented by the text.

## I. Transcription Pathways

### A. PHON graphs
Transcribe according to phonographic Man'yōgana sound values.

### B. LOG graphs
Transcribe according to the most plausible Old Japanese lexical reading (native reading / established kun-reading / historically justified lexical equivalent).

**Examples:**
- 山 → yama
- 川 → kapa / kawa
- 春 → paru
- 花 → pana

### C. UNC graphs
Return multiple plausible candidates with explanation.

## II. Phonological Assumptions

Use a five-vowel Old Japanese system:

```
a i u e o
```

i / e / o series must be assigned ONE of the following categories:
- **KO** (kō-rui)
- **OT** (otsu-rui)
- **NE** (neutral)

### Series mapping

**i-series:**
- KO = i
- OT = wi
- NE = i

**e-series:**
- KO = ye
- OT = e
- NE = e

**o-series:**
- KO = wo
- OT = o
- NE = o

**a-series:**
- a (no distinction)

**u-series:**
- u (no distinction)

## III. Decision Hierarchy

When multiple readings are possible, follow this order:

1. Established lexical reading in supplied lexicon or corpus tradition
2. Corpus-attested historical usage
3. Prompt A script-function label (PHON / LOG / UNC)
4. Conservative phonological reconstruction
5. If unresolved, return multiple candidates

## IV. Rules

- Do NOT modernize pronunciation.
- Prefer Old Japanese forms over Modern Japanese readings.
- Preserve morpheme boundaries whenever recoverable.
- Preserve token order.
- Do NOT invent unattested forms unless clearly marked uncertain.
- If confidence is low, return multiple candidates.
- If graph is LOG, do NOT use Sino-Japanese reading unless explicitly justified.
- If graph sequence forms a known lexical item, prioritize whole-word reading over character-by-character reading.

## V. Output Format

Valid JSON only:

```json
{
  "items": [
    {
      "char": "...",
      "index": 0,
      "function": "PHON | LOG | UNC",
      "transcription": ["candidate1", "candidate2"],
      "selected": "candidate1",
      "raw_confidence": 0.00,
      "reason_codes": [
        "lexical_reading",
        "phonographic_value",
        "corpus_attested",
        "multiple_possible"
      ],
      "reason": "brief explanation"
    }
  ],
  "full_transcription": ["..."],
  "metadata": {
    "confidence_definition": "raw_confidence reflects contextual certainty only, not calibrated probability",
    "notation_system": "Frellesvig-Whitman inspired five-vowel system"
  }
}
```

## VI. Allowed reason_codes

- `lexical_reading`
- `phonographic_value`
- `corpus_attested`
- `graph_default_value`
- `conservative_reconstruction`
- `multiple_possible`
- `uncertain_graph`
- `context_match`
- `context_conflict`
- `mixed_usage_possible`

## VII. Example 1 (Phonographic Sequence)

**Input:**
```
美阿止都久留
```

**Prompt A labels:**
```json
[
 {"char":"美","index":0,"function":"PHON"},
 {"char":"阿","index":1,"function":"PHON"},
 {"char":"止","index":2,"function":"PHON"},
 {"char":"都","index":3,"function":"PHON"},
 {"char":"久","index":4,"function":"PHON"},
 {"char":"留","index":5,"function":"PHON"}
]
```

**Output:**
```json
{
  "items":[
    {"char":"美","index":0,"function":"PHON","transcription":["mi"],"selected":"mi","raw_confidence":0.95,"reason_codes":["phonographic_value"],"reason":"Common phonographic value mi."},
    {"char":"阿","index":1,"function":"PHON","transcription":["a"],"selected":"a","raw_confidence":0.94,"reason_codes":["phonographic_value"],"reason":"Common phonographic value a."}
  ],
  "full_transcription":["miatotukuru"]
}
```

## VIII. Example 2 (Logographic Graph)

**Input:**
```
山
```

**Prompt A labels:**
```json
[
 {"char":"山","index":0,"function":"LOG"}
]
```

**Output:**
```json
{
  "items":[
    {"char":"山","index":0,"function":"LOG","transcription":["yama"],"selected":"yama","raw_confidence":0.97,"reason_codes":["lexical_reading"],"reason":"Established Old Japanese lexical reading."}
  ],
  "full_transcription":["yama"]
}
```

## IX. Example 3 (Uncertain)

**Input:**
```
川
```

**Prompt A labels:**
```json
[
 {"char":"川","index":0,"function":"LOG"}
]
```

**Output:**
```json
{
  "items":[
    {"char":"川","index":0,"function":"LOG","transcription":["kapa","kawa"],"selected":"kapa","raw_confidence":0.63,"reason_codes":["multiple_possible"],"reason":"Multiple historically plausible lexical readings."}
  ],
  "full_transcription":["kapa","kawa"]
}
```

**Now analyze:**

**Input:**
```
{TEXT}
```

**Prompt A labels:**
```
{LABELS}
```

---

# Prompt C: Lexicon-Constrained Tokenisation

You are an expert in Old Japanese lexicography, historical morphology, and early Japanese philology.

## Task

Perform lexicon-constrained tokenisation of the input Old Japanese transcription.

Your goal is to segment the input into the most plausible lexical units using ONLY the supplied lexicon.

You must consider:

1. lexical coverage
2. grammatical plausibility
3. morphological compatibility
4. corpus frequency (if available)
5. semantic coherence (if gloss data is available)

## I. Lexicon Format

Each lexicon entry may contain:

```json
{
  "id": "L000035",
  "form": "mi",
  "lemma": "mi",
  "pos": "N",
  "gloss": "body",
  "frequency": 128
}
```

### Field definitions

- **id** = unique lexicon identifier
- **form** = attested surface form
- **lemma** = dictionary base form
- **pos** = part of speech
- **gloss** = short English meaning
- **frequency** = corpus frequency (optional)

## II. POS Tagset

Use these tags when evaluating segmentation:

### Parts of speech: Words

- **VB** = verb
- **ADJ** = adjective
- **WH-ADJ** = indeterminate adjective
- **COP** = copula
- **N** = noun
- **DVN** = deverbal noun
- **PEN** = personal name
- **PLN** = place name
- **PRO-N** = nominal pro-form
- **WH-N** = indeterminate noun
- **ADV** = adverb
- **PRO-ADV** = adverbial pro-form
- **WH-ADV** = indeterminate adverb
- **INTJ** = interjection
- **NUM** = numeral
- **WH-NUM** = indeterminate numeral
- **P** = particle
- **XTN** = extension (inflecting modal clitic)
- **MK** = makura kotoba
- **WORD** = illegible or uninterpretable word

### Parts of speech: Bound morphemes

- **ACP** = adjectival copula
- **VAX** = verbal auxiliary
- **PFX** = prefix
- **SFX** = suffix
- **CL** = classifier

### Inflectional categories

For verbs, copula, adjectival copula, extensions and verbal auxiliaries:

- **-ADI** = syncretic adnominal and infinitive
- **-ADN** = adnominal
- **-ADC** = syncretic adnominal and conclusive
- **-CLS** = conclusive
- **-CND** = conditional
- **-CSS** = concessive
- **-CTT** = continuative
- **-EXC** = exclamatory
- **-GER** = gerund
- **-IFC** = syncretic infinitive and conclusive
- **-IMP** = imperative
- **-INF** = infinitive
- **-NGC** = negative conjectural
- **-NML** = nominal
- **-OPT** = optative
- **-PRV** = provisional
- **-SEM** = semblative
- **-STM** = stem

### Categories of verbal auxiliaries

- **-CJR** = conjectural
- **-CTV** = causative
- **-MPST** = modal past
- **-NEG** = negative
- **-PASS** = passive
- **-PRF** = perfective
- **-RSP** = respect
- **-SJV** = subjunctive
- **-SPST** = simple past
- **-STV** = stative (in VAX-STV)

### Categories of particles

- **-CASE** = case
- **-TOP** = topic
- **-FOC** = focus
- **-COMP** = complementizer
- **-CONN** = conjunctional
- **-FNL** = sentence final
- **-INTJ** = interjective
- **-RES** = restrictive

### Categories of case particles

- **-ABL** = ablative
- **-ACC** = accusative
- **-ALL** = allative
- **-COM** = comitative
- **-DAT** = dative
- **-GEN** = genitive
- **-NOM** = nominative

### Categories of sentence final particles

- **-DES** = desiderative
- **-EVD** = evidential
- **-MPH** = emphatic (in P-FNL-MPH)
- **-PHB** = prohibitive
- **-XCL** = exclamative

### Specification of prefixes

- **-HON** = honorific
- **-MPH** = emphatic (in PFX-MPH)
- **-POT** = potential
- **-STV** = stative (in PFX-STV)

### Aspectual function for auxiliary verbs

- **-PGS** = progressive
- **-STV** = stative (in VB-STV)

### Phrases

- **NP** = noun phrase
- **PP** = particle phrase
- **IP** = inflectional phrase (clause)
- **CP** = complementizer phrase (used in CP-FINAL, clauses with a right dislocated element)

### Syntactic roles and functions for nominal phrases

For noun phrases, particle phrases and nominalized clauses (IP-NMZ):

- **-SBJ** = subject
- **-OB1** = primary object
- **-OB2** = secondary object
- **-MPT** = empty theta role (for subjects raised to object position)
- **-ARG** = argument (where subject or object status cannot be determined)
- **-ADV** = adverbial
- **-PRD** = predicate nominal
- **-VOC** = vocative
- **-IHRC** = internally-headed relative clause (an extension for IP-NMZ)
- **-HST** = host to a quantifier
- **-QFR** = quantifier
- **-APP** = apposition, marked on both head and appositive

### Semantic roles for nominal phrases

- **-GOL** = goal
- **-PTH** = path
- **-SRC** = source
- **-AGT** = agentive
- **-CZZ** = causee
- **-XPR** = experiencer

### Clause types (IP and CP)

- **-MAT** = matrix
- **-ADV** = adverbial subordinate clause
- **-ARG** = argument clause
- **-PRP** = purposive subordinate clause, used with motion verbs
- **-REL** = relative clause
- **-EMB** = embedding (gapless adnominal) clause
- **-NMZ** = nominalized clause
- **-SUB** = syntactic island (marks a clause followed by a right dislocated element)
- **-FINAL** = used in CP-FINAL, clauses with a right dislocated element
- **-EPT** = epithet (modification by makura kotoba)
- **-RDP** = reduplicated (in [V ni] V with two identical V)

### Modes of writing

- **PHON** = phonographic writing
- **LOG** = logographic writing
- **NLOG** = no written representation
- **PLOG** = conventional writing of a place name
- **NULL** = null element, used about "zero" morphemes, currently only applied to the "zero" conclusive ending of the adjectival copula when used with shiku-adjectives
- **ILL** = illegible

### Extensions for phonographic writing

- **-KUN** = kun-gana
- **-ON** = on-gana

### Rhetorical annotation

- **-ZYO** = zyo kotoba
- **-KKE** = kake kotoba

### Special node labels

- **multi-sentence** = multiple sentences in series
- **FRAG** = fragment
- **CONJP** = coordinated phrase

## III. Segmentation Rules

1. Use ONLY supplied lexicon entries.
2. Do NOT invent unattested lexical items.
3. Prefer segmentations with highest total lexical coverage.
4. Prefer grammatically coherent sequences.
5. Prefer historically plausible morphology.
6. Prefer higher-frequency entries when ambiguity remains.
7. If multiple analyses remain plausible, return all ranked candidates.
8. If a segment is not found, label it UNK.

## IV. Grammatical Preferences

Prefer common Old Japanese patterns such as:

- N + PRT + N
- N + V
- V + AUX
- ADJ + N
- ADV + V

Avoid unlikely sequences unless strongly supported by lexicon.

## V. Output Format

Valid JSON only:

```json
{
  "input": "...",
  "segmentations": [
    {
      "rank": 1,
      "tokens": [
        {
          "id": "L000035",
          "form": "mi",
          "lemma": "mi",
          "pos": "N",
          "gloss": "body",
          "start": 0,
          "end": 2
        },
        {
          "id": "L050877",
          "form": "ato",
          "lemma": "ato",
          "pos": "N",
          "gloss": "trace",
          "start": 2,
          "end": 5
        }
      ],
      "coverage_score": 0.95,
      "grammar_score": 0.82,
      "frequency_score": 0.70,
      "raw_confidence": 0.86,
      "reason_codes": [
        "full_coverage",
        "valid_pos_sequence",
        "high_frequency_entries"
      ],
      "reason": "Complete segmentation with plausible noun sequence."
    }
  ],
  "metadata": {
    "confidence_definition": "raw_confidence reflects segmentation plausibility only, not calibrated probability"
  }
}
```

## VI. Allowed reason_codes

- `full_coverage`
- `partial_coverage`
- `valid_pos_sequence`
- `unlikely_pos_sequence`
- `high_frequency_entries`
- `rare_entries`
- `semantic_coherence`
- `morphological_match`
- `ambiguous_segmentation`
- `contains_unknown_segment`

## VII. Example 1

**Input:**
```
miatotukuru
```

**Lexicon:**
```json
[
 {"id":"L000035","form":"mi","lemma":"mi","pos":"N","gloss":"body","frequency":120},
 {"id":"L050877","form":"ato","lemma":"ato","pos":"N","gloss":"trace","frequency":45},
 {"id":"L031144a","form":"tukuru","lemma":"tukuru","pos":"V","gloss":"make","frequency":60}
]
```

**Output:**
```json
{
  "input":"miatotukuru",
  "segmentations":[
    {
      "rank":1,
      "tokens":[
        {"id":"L000035","form":"mi","lemma":"mi","pos":"N","gloss":"body","start":0,"end":2},
        {"id":"L050877","form":"ato","lemma":"ato","pos":"N","gloss":"trace","start":2,"end":5},
        {"id":"L031144a","form":"tukuru","lemma":"tukuru","pos":"V","gloss":"make","start":5,"end":11}
      ],
      "coverage_score":1.00,
      "grammar_score":0.84,
      "frequency_score":0.72,
      "raw_confidence":0.88,
      "reason_codes":["full_coverage","valid_pos_sequence"],
      "reason":"All segments matched lexicon with plausible syntax."
    }
  ]
}
```

## VIII. Example 2 (Ambiguous)

**Input:**
```
yamakapa
```

**Output:**
```json
{
  "input":"yamakapa",
  "segmentations":[
    {
      "rank":1,
      "tokens":[
        {"id":"L000101","form":"yama","lemma":"yama","pos":"N","gloss":"mountain","start":0,"end":4},
        {"id":"L000202","form":"kapa","lemma":"kapa","pos":"N","gloss":"river","start":4,"end":8}
      ],
      "coverage_score":1.00,
      "grammar_score":0.80,
      "frequency_score":0.66,
      "raw_confidence":0.84,
      "reason_codes":["full_coverage","semantic_coherence"],
      "reason":"Compound noun sequence."
    }
  ]
}
```

**Now analyze:**

**Input:**
```
{TEXT}
```

**Lexicon:**
```
{DICTIONARY}
```
