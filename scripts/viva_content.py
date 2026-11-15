"""Questions and answers for the viva: one source for docs/viva_notes.md and the viva guide PDF.

Every number comes from scripts/doc_results.py (R), where each one carries its `# from: <file>:<key path>`
comment, or from a pipeline constant that scripts/check_claims.py accepts (thresholds, chunk sizes, the
bootstrap settings, the targets). Inline markup: **bold**, *italic*, `code`.

A section is (title, [card, ...]); a card is a dict with
  q       the question
  a       the short answer (one or two sentences)
  points  supporting lines (optional)
  formula a boxed formula or number line (optional)
  table   (header, rows) (optional)
  asks    [(examiner question, honest answer), ...] (optional)
"""
from doc_results import R, f2, f3, met, n, pct, pct_ci, pts, pts_ci, num_ci, group_languages

TITLE = "Grantha Heritage Tracker: grouping old Indian books by subject without labels"
SUBTITLE = ("Problem SIH26096 · Section K3P24XC · CO2 & CO3 · Units III & IV · every number from the result files "
            "(`reports/deliverable_facts.json`, `reports/features/*.json`)")

_langs = "; ".join(f"{r['name']} {n(r['usable'])} of {n(r['harvested'])}" for r in R.by_language)
_minpts = ", ".join(str(m) for m in R.db_minpts_tried)
_nb = "; ".join(f"k = {x['k']}: ARI {f2(x['ari'])}" for x in R.neighbours)
_subjects = " and ".join(R.cat_subject)

SECTIONS = [
    ("Data and scale (Rubric Column 1)", [
        dict(q="Where does the dataset come from, and how big is it?",
             a=f"{n(R.harvested)} books from the Digital Library of India scans on the Internet Archive, in {R.languages} "
               f"languages; {n(R.usable)} ({pct(R.usable_share)}) pass the usability gate.",
             points=[f"**Harvest:** a fleet of Google Cloud VMs, one per language (Kannada and Tamil shared one), downloading "
                     f"single pages, never whole PDFs. {n(R.ocr_pages)} pages were read with Tesseract.",
                     f"**Per language (usable of harvested):** {_langs}."],
             asks=[("Why not NDLI directly?",
                    "NDLI aggregates catalogue records and has no bulk API; the Digital Library of India scans are the "
                    "files behind many of its records.")]),
        dict(q="What is the usability gate, and how many books fail it?",
             a=f"Word-weighted mean OCR confidence of at least 50 and at least 100 clean tokens. {n(R.excluded)} books "
               f"({pct(R.excluded_share)}) fail.",
             formula=f"usable = (mean_conf ≥ 50) ∧ (clean_tokens ≥ 100) · usable {n(R.usable)} · excluded {n(R.excluded)}",
             asks=[("Why drop books?",
                    "Gibberish OCR creates false closeness between unrelated books. Excluded books stay in the database, "
                    "flagged, so the decision can be revisited."),
                   ("Does the gate bias the corpus?",
                    f"Yes, towards readable scans: Telugu keeps only {pct(R.telugu_share, 0)} of its books while English "
                    "keeps almost all. The results describe readable books, and we say so.")]),
        dict(q="How are books split for evaluation?",
             a="By a hash of each book's identifier: 60% train, 20% validation, 20% test, the same for a book forever.",
             formula=f"train {n(R.train)} · validation {n(R.val)} · test {n(R.test)}",
             points=["Every fitting step (stopwords, PCA, centring, clustering, DBSCAN eps, the edition threshold) sees "
                     "the train books only.",
                     "An earlier version shuffled the whole corpus; when the corpus grew, held-out books became training "
                     "books. The hash fixes that, and the change is logged as a deviation in `docs/evaluation_log.md`."]),
    ]),
    ("Preprocessing and vectors (Rubric Column 1)", [
        dict(q="How was OCR done, and which text is embedded?",
             a="Tesseract 5 LSTM (--oem 1 --psm 3) with orientation and script detection; if the detected script "
               "disagrees with the catalogue, both models read the page and the more confident one wins.",
             points=[f"This run embeds whole-book text: the archive's own OCR for {n(R.text_archive)} books "
                     f"({n(R.text_hocr)} from hOCR, {n(R.text_djvu)} from DjVu text), and our five Tesseract pages for the "
                     f"{n(R.text_tesseract)} books with no archive text.",
                     "Our own Tesseract pages still measure OCR quality for the usability gate."]),
        dict(q="Which variables were kept or dropped?",
             a="Kept: text, script, year (median-imputed plus a missing flag), log pages, OCR confidence, log tokens. "
               "Dropped: scanning centre and source library (provenance leakage), subject field, free-text fields.",
             points=["Numeric fields are standardised so year (hundreds) does not outweigh confidence (tens); script is "
                     "one-hot encoded. Adding these fields to the text vectors is tested separately "
                     "(`reports/study/sensitivity.json`); the final groups use the text alone."]),
        dict(q="How are books turned into vectors, and why centre by language?",
             a=f"{R.encoder} (text-multilingual-embedding-002, 768-d): up to 10 evenly spaced 64-word chunks per book, "
               f"averaged; each language's mean vector subtracted; PCA to {R.dims} dims.",
             formula="μℓ = mean of the train books in language ℓ;  x̃ = (x − μℓ(x)) / ‖x − μℓ(x)‖",
             points=[f"On the {n(R.ce_train_books)} train books, before centring, groups follow script (NMI "
                     f"{f3(R.ce_nmi_before)}) and {pct(R.ce_knn_before)} of each book's 10 nearest neighbours share its "
                     f"script. After centring: NMI {f3(R.ce_nmi_after)}, and {pct(R.ce_knn_after)}."],
             asks=[("Why is centring the key step?",
                    "Without it the strongest signal in a multilingual vector is the language itself, so the groups are "
                    "language piles we already knew. Removing each language's average is what lets subject show."),
                   ("Was the encoder chosen by a test?",
                    "The pre-registered encoder comparison (" + ", ".join(R.encoders_compared) + ") ran on the earlier, "
                    f"smaller study; centring helped every one of them. {R.encoder} was a team decision and was not in "
                    "that comparison. We say so on the deck.")]),
    ]),
    ("Hierarchical clustering (Unit III, Rubric Column 2)", [
        dict(q="Compare the linkages and distances.",
             a="The grid runs Ward, average and complete linkage for k from 2 to 15 on the train books. Single linkage "
               f"chains books one by one, so it cannot give topic groups. In the distance study {R.metric} won "
               f"{R.distance_wins.get('euclidean', 0)} comparisons and Manhattan {R.distance_wins.get('cityblock', 0)}.",
             table=(["Linkage", "Merges by", "Behaviour here"],
                    [["Ward", "least increase in within-group variance", "compact groups of similar size"],
                     ["Complete", "largest pairwise distance", "sensitive to outlying books"],
                     ["Average", "mean pairwise distance", "between the two"],
                     ["Single", "smallest pairwise distance", "chains books one by one; unusable for topics"]])),
        dict(q="How was the final setting chosen?",
             a=f"By a rule fixed before any results, on the train books: {R.linkage} linkage, {R.metric}, k = {R.k}. "
               + ("The rule was met." if R.rule_met else "No setting met the rule, so the pre-registered fallback applied."),
             points=[f"Rule: {R.rule}. Fallback if nothing passes: the setting with the lowest script NMI, reported as a "
                     "rule failure."],
             formula=f"train books: silhouette {f3(R.sil_train)} · script NMI {f3(R.nmi_train)} · bootstrap ARI {f2(R.t3)};  "
                     f"all usable books: silhouette {f3(R.sil_all)} · script NMI {f3(R.nmi_all)} · bootstrap ARI {f2(R.boot_all)}",
             asks=[("Why is silhouette so low?",
                    "Books on one subject vary a lot in vocabulary, so groups overlap; silhouette near zero is common for "
                    f"text. Even within one script it stays low (weighted mean {f3(R.within_script_sil)}). We judge the "
                    "groups by held-out subject accuracy instead."),
                   ("Is k = 3 too few for a library?",
                    f"Yes, the groups are broad shelves. The rule fell back to k = {R.k}, and we report that rather than "
                    "pick a larger k by eye.")]),
        dict(q="How stable are the groups (target T3)?",
             a=f"Not stable enough. On train books the median bootstrap ARI is {f2(R.t3)} against a target of "
               f"{f2(R.target_t3)}: {met(R.met_t3)}. On all usable books it is {f2(R.boot_all)}, with most re-runs between "
               f"{f2(R.boot_p10)} and {f2(R.boot_p90)} (20 resamples of 80%).",
             points=[f"Neighbouring cuts of the same tree agree with the k = {R.k} cut ({_nb}), so the choice of k is not "
                     "what moves the groups; resampling the books is.",
                     f"Refitting on the {n(R.hc_books)} high-confidence books ({pct(R.hc_share)}) agrees with the full "
                     f"grouping at ARI {f2(R.hc_ari)} only."],
             asks=[("So are the groups real?",
                    "They carry some subject signal (next section), but their boundaries shift between samples. We "
                    "present them as a navigation aid, not a catalogue.")]),
    ]),
    ("DBSCAN (Unit IV, Rubric Column 2)", [
        dict(q="How were eps and MinPts chosen, and what does noise mean?",
             a=f"Sorted k-distance curves set the eps range ({f3(R.db_eps_range[0])} to {f3(R.db_eps_range[1])}); with "
               f"MinPts {_minpts}, {R.db_settings} settings were run, and the best silhouette among valid ones is eps "
               f"{f3(R.db_eps)}, MinPts {R.db_minpts}: {R.db_clusters} clusters, {pct(R.db_noise)} noise.",
             points=["Noise (-1) = a book with fewer than MinPts neighbours within eps, and not near a core book.",
                     f"Agreement with the hierarchical groups on non-noise books: ARI {R.db_vs_hier:.4f}, no agreement.",
                     f"HDBSCAN as a check: {R.hdb_clusters} clusters with {pct(R.hdb_noise)} of books noise."],
             asks=[("Why is the catalogue hierarchical, not DBSCAN?",
                    "It assigns every book; DBSCAN's verdict is shown next to it in the app as 'in a dense region' or "
                    "'noise'."),
                   ("DBSCAN is steadier. Why not use it?",
                    f"Its bootstrap ARI is {f2(R.db_boot)}, but it leaves {pct(R.db_noise)} of books unassigned, finds "
                    f"only {R.db_clusters} clusters, and those do not match the hierarchical groups. A steady split into "
                    "two dense regions says little about subject.")]),
    ]),
    ("PCA (CO3, Rubric Column 2)", [
        dict(q="What does PCA do here, and how much variance is kept?",
             a=f"PCA reduces 768 → {R.dims} dims for clustering (keeps {pct(R.pca_kept)}); for display, PC1 {pct(R.pc1)} "
               f"and PC2 {pct(R.pc2)} of the {R.dims}-d variance.",
             formula="Σ = (1/N) XᵀX on centred X; Σ vᵢ = λᵢ vᵢ; share of PC i = λᵢ / Σλ",
             asks=[("Only about a fifth of the variance in 2D?",
                    "Topics spread over many directions, so a 2D view always shows overlap that the full space does not "
                    "have. We use PCA rather than t-SNE or UMAP because it does not invent gaps.")]),
    ]),
    ("Evaluation (Rubric Column 3)", [
        dict(q="How did you check that the groups mean something (target T2)?",
             a=f"On {R.t2_test_labels} labelled test books, each group's majority subject is right {pct(R.t2_acc)} of the "
               f"time (95% CI {pct_ci(R.t2_acc_ci)}), against {pct(R.t2_script)} for guessing from the script alone and "
               f"{pct(R.t2_common)} for always guessing the most common subject: {pts(R.t2_points)} points over the best "
               f"simple guess (95% CI {pts_ci(R.t2_points_ci)}), p = {R.t2_p:.4f} from 2,000 label shuffles. Target "
               f"+{R.target_t2:.0f} points: {met(R.met_t2)}.",
             table=(["Target (fixed in advance)", "Validation", "Test", "Result"],
                    [[f"T1: a page lands with its own book (≥ {pct(R.target_t1, 0)})", pct(R.t1_val), pct(R.t1), met(R.met_t1)],
                     [f"T2: subject gain over best simple guess (≥ +{R.target_t2:.0f} points)", pts(R.t2_val_points),
                      pts(R.t2_points), met(R.met_t2)],
                     [f"T3: bootstrap ARI on train books (≥ {f2(R.target_t3)})", f2(R.t3), f2(R.t3), met(R.met_t3)]]),
             points=["Test numbers were measured once, after every choice was made on train and validation books.",
                     f"Validation books: {pct(R.t2_val_acc)} vs {pct(R.t2_val_script)} for the script guess, "
                     f"{pts(R.t2_val_points)} points (95% CI {pts_ci(R.t2_val_points_ci)}, p = {R.t2_val_p:.4f}) on "
                     f"{R.t2_val_labels} books: below the target.",
                     f"Groups are named from {R.t2_train_labels} labelled train books. Labels come from titles, catalogue "
                     "fields and an OCR snippet, made with an AI assistant for the team to spot-check; they never form or "
                     "choose groups."],
             asks=[("Is this supervised?",
                    "No. Clustering never sees a label; labels only measure the groups afterwards."),
                   ("Validation says +4.2 and test says +14.5. Which is true?",
                    f"Both are measurements on just over a hundred labelled books each, so both are noisy: the intervals overlap "
                    f"(validation {pts_ci(R.t2_val_points_ci)}, test {pts_ci(R.t2_points_ci)}). The plan judges the "
                    "target on the test split, measured once, so we report T2 as met, but the test interval reaches "
                    "below +10 and we do not claim the gain is reliably that large.")]),
        dict(q="Does a single new page land with its own book (target T1)?",
             a=f"{pct(R.t1)} of single test pages land in their own book's group (95% CI {pct_ci(R.t1_ci)}), against "
               f"{pct(R.t1_chance)} by chance. Target {pct(R.target_t1, 0)}: {met(R.met_t1)}.",
             points=[f"{n(R.t1_books)} test books; the app abstained on {pct(R.t1_abstain)} of pages.",
                     f"Counting a page as right when its book's group is among its tags (up to 3) gives "
                     f"{pct(R.t1_tagged)}; that is a looser measure, not the target."],
             asks=[("Why does a page miss its book's group a quarter of the time?",
                    "One page is a small sample of a book, and the groups overlap heavily (silhouette near zero), so a "
                    "page near a boundary can fall on either side. The app shows the runner-up group and its evidence "
                    "for that reason.")]),
        dict(q="Do the groups match the librarians' catalogue classes?",
             a=f"No. As an exploratory check on {n(R.cat_labels)} test books with a mappable class code, the groups are "
               f"right {pct(R.cat_acc)} of the time against {pct(R.cat_script)} for guessing from the script: "
               f"{pts(R.cat_points)} points (95% CI {pts_ci(R.cat_points_ci)}).",
             points=[f"Every group's majority class is {_subjects}, so the {R.k} groups cannot separate the catalogue's main "
                     f"classes; NMI between groups and classes is {f3(R.nmi_class)}.",
                     "This check was exploratory in the plan; we report it because it cuts against the headline."]),
    ]),
    ("Tools for the archivist (Rubric Column 3)", [
        dict(q="How good is the class suggestion for an uncatalogued book?",
             a=f"On {n(R.sug_heldout)} held-out books with a catalogue class, the top suggestion is the book's own class "
               f"{pct(R.sug_top1)} of the time (95% CI {pct_ci(R.sug_top1_ci)}), against {pct(R.sug_base)} for always "
               f"suggesting the most common class and {pct(R.cat_script)} for guessing from the script. The right class "
               f"is among the top three {pct(R.sug_top3)} of the time (95% CI {pct_ci(R.sug_top3_ci)}).",
             points=[f"Method: a distance-weighted vote of the {R.sug_k} nearest of {n(R.sug_train)} classed train books; "
                     "nothing is fitted on the held-out books.",
                     "No simple-guess baseline was computed for top-three, so that number stands alone."],
             asks=[("Why does the suggestion beat the simple guesses on catalogue classes when the groups do not?",
                    "The groups are three broad shelves; the suggestion uses a book's own nearest classed neighbours, "
                    "which is a much finer signal.")]),
        dict(q="Does the tool find related books in other scripts?",
             a=f"Among each train book's {R.rel_k} nearest neighbours ({n(R.rel_books)} books), {pct(R.rel_centred)} are in "
               f"another script after centring, against {pct(R.rel_uncentred)} before.",
             points=["This shows that books in other scripts now reach the neighbour list; it does not by itself show they "
                     "share the subject. The deck's example is one recorded answer, not an evaluation."]),
        dict(q="How well does the edition finder work?",
             a=f"Precision {f2(R.ed_precision)} and recall {pct(R.ed_recall)} (95% CI {pct_ci(R.ed_recall_ci)}), on only "
               f"{R.ed_groups} held-out edition groups among {n(R.ed_heldout)} test books.",
             points=[f"The distance threshold ({R.ed_threshold:.4f}) is calibrated on train books only.",
                     "An edition counts only when the normalised title and author match exactly, so transliterated or "
                     "translated editions are not counted as found or missed."],
             asks=[("How sure are you of that recall?",
                    f"Not sure at all. With {R.ed_groups} groups the 95% interval runs from {pct(R.ed_recall_ci[0])} to "
                    f"{pct(R.ed_recall_ci[1])}. The precision interval is {num_ci(R.ed_precision_ci, f2)} only because "
                    "every candidate in this tiny sample was right; that does not make precision certain. It needs "
                    "many more held-out groups before we can quote a recall.")]),
        dict(q="Does scan triage predict which books need re-OCR?",
             a=f"No. Its score ranks books against 'our OCR agrees with the archive's OCR less than the median' with an "
               f"AUC of {f3(R.tri_auc)} (95% CI {num_ci(R.tri_auc_ci)}) on {R.tri_books} books: no better than chance.",
             points=["The rules reuse the usability gate's thresholds (confidence below 50, fewer than 100 words) plus "
                     "DBSCAN noise; their weights (" + ", ".join(f"{k} {v}" for k, v in R.tri_weights.items())
                     + ") are design choices, not fitted."],
             asks=[("Your triage AUC is 0.50. Why keep it?",
                    "As a check it failed, and we report it that way. The verdicts only restate the gate's own rules "
                    "(why a book was flagged), which is still useful to read, but the score must not be read as a "
                    "prediction of OCR disagreement.")]),
    ]),
    ("Groups and limits (Rubric Column 3)", [
        dict(q="What are the groups?",
             a=f"{len(R.groups)} groups, each named by the majority subject of its labelled train books; every group mixes "
               f"all {R.languages} languages, and no language holds more than {pct(R.max_lang_share, 0)} of any group.",
             table=(["Group", "Books", "Majority subject", "Largest languages"],
                    [[f"Group {g['group'] + 1}", n(g["books"]), g["majority_subject"] or "-", group_languages(g)]
                     for g in R.groups])),
        dict(q="What are the limits, and how does the app behave responsibly?",
             a=f"{R.n_met} of 3 targets met. Page agreement and stability missed; the groups are broad and do not match "
               "the catalogue's classes; scan triage is no better than chance; the edition finder is barely tested; "
               "labels are AI-assisted; OCR quality is uneven by language; the encoder is an online Google service.",
             points=["The app abstains below 20 readable words and cautions when OCR confidence is below 50 or a page has "
                     "fewer than 100 words, the same bars the archive books passed.",
                     "Every answer lists the five nearest archive books, how far the page is from its group's centre "
                     "relative to the group's own spread, and DBSCAN's verdict.",
                     "Checking a page sends its text to Google to be embedded."]),
    ]),
]
