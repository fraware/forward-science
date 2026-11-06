# Forward Science — Editorial evidence audit

**Source baseline:** Six June 2026 essays, imported from the author's official Substack export, with recorded SHA-256 provenance. This report audits the relationship of links and claims. It is **not** a revised publication and does not certify each factual claim. Source prose and link destinations remain unchanged.

## Reference inventory

Run `python scripts/audit_references.py --json /tmp/forward-science-reference-inventory.json` from the repository root. The command performs an **offline** extraction from source-verified article HTML. Each entry records the original essay, paragraph number (matching `p-01` etc. in the rendered reader), anchor text, destination, hostname, and a bounded paragraph context. It excludes only the six exported Substack subscription footers.

| Essay | Substantive reference links |
| --- | ---: |
| 00 — Forward Science | 10 |
| 01 — Forward-Deployed Scientists | 9 |
| 02 — The Unit of Deployment Is the Scientific Loop | 4 |
| 03 — From Extension Agents to Forward-Deployed Scientists | 17 |
| 04 — Who Pays for the Scientist Who Makes Other Scientists Better | 0 |
| 05 — Between the Manual Lab and the Self-Driving Lab | 6 |
| **Total** | **46 links; 32 distinct external URLs** |

These numbers indicate source-link presence. They are neither a citation-quality score nor evidence that referenced claims are true.

## Priority editorial findings

### 1. Source mismatch — sequencing core

**Essay 03, paragraph 8.** The anchor **“sequencing core”** points to the NHGRI page [DNA Sequencing Costs: Data](https://www.genome.gov/about-genomics/fact-sheets/DNA-Sequencing-Costs-Data). The linked page documents costs and accounting assumptions, while the essay concerns the expertise and services of scientific facilities. This is a **subject mismatch**, even though the linked data originate from a reputable scientific institution.

A better primary institutional example is the [NHLBI DNA Sequencing and Genomics Core](https://www.nhlbi.nih.gov/science/dna-sequencing-and-genomics-core), describing research consultation, sequencing instrumentation, data acquisition, and computational analysis. This is a proposed alternative, **not an approved source-text change**.

### 2. Historical chronology — experiment stations and extension

**Essay 03, paragraph 3.** The agricultural-extension analogy refers to a nineteenth-century experiment station. The [USDA NIFA history](https://www.nifa.usda.gov/about-nifa/who-we-are/history) distinguishes the **Hatch Act of 1887**, which created a national experiment-station system, from the **Smith–Lever Act of 1914**, which established the Cooperative Extension System. Earlier extension-like demonstrations preceded the formal system. The analogy is supportable if the text differentiates an experiment station, an extension agent, and the later federally organized extension system with chronological precision.

A nineteenth-century hypothetical farmer and experimental result should be presented as an illustration unless a documented historical case is supplied.

### 3. Unsupported firsthand attribution — National Laboratories

**Essay 01, paragraph 2.** The linked [National Laboratories homepage](https://nationallabs.org/) establishes the existence and mission of the U.S. national-laboratory system. It is insufficient evidence for the statement that the laboratories firsthand observed the particular institutional diagnosis in the passage. The essay itself frames the surrounding materials-group example as imagined. Separate the illustrative scenario from independently documented observations, or support the empirical attribution with a specific publicly documented case.

### 4. Sponsored product announcement — research-loop diagnosis

**Essay 01, paragraph 9.** The linked [Hudson Lab Automation article](https://www.the-scientist.com/hudson-lab-automation-launches-rapid-ph-plustm-at-asms-2026-74606) is expressly presented as material from Hudson Lab Automation. It documents a manufacturer's announced pH automation platform, including throughput and workflow features. It **does not establish** that the limiting factor for a particular laboratory was experiment selection or institutional coordination. If the passage is an illustrative diagnosis, label it accordingly. If it claims a real observed failure, document the independent case.

### 5. Weak background support — the “hype cycle” reference

**Essay 02, paragraph 6.** The linked [Medium essay](https://medium.com/design-bootcamp/5-counter-intuitive-truths-about-ai-that-go-beyond-the-hype-c9a84d1f73ef) is a general opinion piece primarily discussing causal AI and insurance, with its author disclosing NotebookLM-assisted drafting. It does not study the institutional uptake of AI inside research laboratories. Its relevance to the scientific-loop argument is peripheral. The passage should rely on direct evidence about scientific workflows, or state the critique as the author's own argument.

### 6. Political economy — evidence classification rather than citation accumulation

**Essay 04.** The source export contains **no substantive external hyperlinks** in its 23 essay paragraphs. That fact alone does not invalidate an institutional argument. The next pass should classify assertions as (i) proposed institutional design, (ii) analytical prediction, (iii) comparative institutional fact, or (iv) quantitative empirical statement. The latter two categories warrant independent substantiation; the first two need transparent assumptions and scope.

### 7. Additional inspection — discussion of model access

**Essay 01, paragraph 5.** A New York Times URL about Anthropic Mythos/Fable 5 accompanies the word “discussion.” Its article content could not be independently retrieved in the audit environment. Assess whether the linked reporting substantively supports the *AI-for-science access* claim. This remains a **review item**, not a confirmed mismatch.

## Evidence and edition policy

For each finding, reviewers should record the exact claim, the source title and date, its type (primary / academic / institutional / journalistic / sponsored / opinion), the claim it directly supports, and the remaining inference. A working URL proves availability only; a recognizable institution proves neither the specific proposition nor causality.

The published HTML and the original author-export hashes remain unchanged. Any accepted editorial correction should follow the source-level errata issue [#20](https://github.com/fraware/forward-science/issues/20) and evidentiary review issue [#26](https://github.com/fraware/forward-science/issues/26), with a traceable decision about the relationship to the original Substack edition. Permanent narration manuscripts must be regenerated and re-reviewed if their source text changes.

**Audit boundary:** Structural extraction is complete for the current source-verified files. Full manual source-claim adjudication, current live-Substack comparison, and replacement-source approvals remain open.
