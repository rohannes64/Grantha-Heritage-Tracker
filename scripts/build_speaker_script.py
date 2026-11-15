"""docs/Grantha_Speaker_Script.md: what each presenter says, slide by slide, for the 20-slide deck.

    python scripts/build_speaker_script.py

Follows Grantha_Heritage_Tracker_SIH26096.pptx (built by scripts/build_deck.py) in slide order. The script is
written here, not copied from the deck's notes, so that every number comes from the result files through
scripts/doc_results.py (each with its `# from: <file>:<key path>` comment). The worked example on slides 11 to 13
names a recorded app answer (web/fixtures, the same files the deck shows); only its titles, scripts and
classes are used, never a number from it. Presenters: Rohan slides 1 to 5, Rajith 6 to 10, Sai Pranav 11 to 20.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_results import R, ROOT, f2, fixture, met, n, pct, pct_ci, pts, pts_ci  # noqa: E402

OUT = ROOT / "docs" / "Grantha_Speaker_Script.md"
EXAMPLE_BOOK = "dli.56E228"                          # the deck's uncatalogued Tamil book (scripts/build_deck.py)
CHECK_FIXTURE = "post_check__in.ernet.dli.2015.294941"   # the deck's checked page (scripts/build_deck.py)

ROHAN, RAJITH, SAI = "VEMURI ROHAN", "RAJITH SUNDAR", "ETIKALA SAI PRANAV"


def slides() -> list[tuple[str, str, str]]:
    """(presenter, slide title as on the deck, what to say)."""
    lang = {r["name"]: r for r in R.by_language}
    eng, tel, san = lang["English"], lang["Telugu"], lang["Sanskrit"]
    book = fixture(f"get_documents__{EXAMPLE_BOOK}")
    sugg = [s["class"] for s in fixture(f"get_suggest__{EXAMPLE_BOOK}")["suggestions"]]
    rel = fixture(f"get_related__{EXAMPLE_BOOK}")["neighbours"]
    rel_scripts = sorted({x["script"] for x in rel[:8]})
    chk = fixture(CHECK_FIXTURE)
    g = R.groups
    subj = [x["majority_subject"] for x in g]
    lit = [i + 1 for i, s in enumerate(subj) if s == "literature"]
    rel_phil = [i + 1 for i, s in enumerate(subj) if s == "religion and philosophy"]
    return [
        ("ALL PRESENTERS - OPENING (Rohan speaks)", "Grantha Heritage Tracker",
         "Good morning. We are Rohan, Rajith and Sai Pranav, and this is the Grantha Heritage Tracker, for Smart India "
         "Hackathon problem SIH26096.\n\n"
         "The idea in one line: old printed Indian books sit in a digital library in many scripts, and we asked whether "
         "a computer can group them by subject without being told the subjects.\n\n"
         "Every number you will hear comes from our result files. We set three targets before seeing any results; we "
         f"met {R.n_met} of them, and where we missed, we say so.\n\n"
         "- I will cover the problem, the data and the method.\n"
         "- Rajith will cover the clustering, the groups and how well they hold up.\n"
         "- Sai Pranav will cover the tools for the archivist and our limits."),
        (ROHAN, "About half the books carry no library class",
         "Start with the problem an archivist has.\n\n"
         f"Of the {n(R.usable)} books we could use, only {n(R.classified_books)} carry a library class, the subject "
         "code a librarian gives a book. The rest have none, so a subject search cannot find them.\n\n"
         "And books in different scripts never meet: a Tamil book and a Telugu book on the same subject sit in "
         "separate piles.\n\n"
         "So our question: can the computer read the books and group them by subject on its own?"),
        (ROHAN, f"{n(R.usable)} of {n(R.harvested)} books were clear enough to use",
         f"Our data: books from the Digital Library of India, mirrored on the Internet Archive, in {R.languages} "
         f"languages. A fleet of Google Cloud machines downloaded {n(R.harvested)} books.\n\n"
         "To read a scan we use OCR, software that turns a picture of a page into text. A book is usable only when "
         "its OCR confidence is at least 50 and it has at least 100 clean words.\n\n"
         f"{n(R.usable)} books pass, which is {pct(R.usable_share)}. The grey bar is what we downloaded, the red bar "
         f"is what we could use. English keeps {n(eng['usable'])} of {n(eng['harvested'])}. Telugu keeps the fewest, "
         f"{pct(R.telugu_share, 0)}, because its scans are the hardest to read.\n\n"
         f"The {n(R.excluded)} excluded books are not deleted; they stay in the database, marked. The usable books are "
         f"split by a hash of each identifier into {n(R.train)} training, {n(R.val)} validation and {n(R.test)} test "
         "books, so a book never changes split as the corpus grows."),
        (ROHAN, "Telugu and Sanskrit scans are the hardest to read",
         "This chart shows how sure the OCR is of the words it reads, from 0 to 100, for the middle book in each "
         "language.\n\n"
         f"English reads best, at {eng['median_conf']:.1f}. Telugu is lowest at {tel['median_conf']:.1f}, then "
         f"Sanskrit at {san['median_conf']:.1f}.\n\n"
         "Why it matters: a badly read book gives the computer fewer real words, so it is harder to place. That is why "
         "the app warns when a page is poorly read instead of guessing silently. For most books we embed the "
         f"archive's own whole-book text ({n(R.text_archive)} books); our five Tesseract pages are the text for the "
         f"other {n(R.text_tesseract)}."),
        (ROHAN, "Five steps from a scanned page to a subject group",
         "Here is the whole method in five steps.\n\n"
         "One, read: OCR turns each page into text.\n\n"
         "Two, embed: an embedding is a list of numbers that stands for the meaning of a text, so books on similar "
         f"topics get similar numbers. We use {R.encoder}, which reads all our languages.\n\n"
         "Three, centre: we subtract each language's average list of numbers. Without this, the strongest signal is "
         "the language itself, not the subject. This is our key step.\n\n"
         "Four, group: hierarchical clustering joins the closest books step by step into a tree, and we cut the tree "
         "into groups. We also run DBSCAN, which looks for crowded regions.\n\n"
         "Five, check: we test the groups on books we kept aside, and compare with simple guesses.\n\n"
         "I now hand over to Rajith."),
        (RAJITH, "Counting words, books group by language first",
         "Thank you, Rohan. This is our main finding.\n\n"
         "When we grouped books by simply counting their words, in an earlier study, every group turned out to be one "
         "language: English books, Bengali books, Tamil books and so on. That is correct, but useless: we already "
         "know each book's language.\n\n"
         "To measure this we use NMI, a score of how much the groups follow language: 0 means not at all, 1 means "
         "each group is exactly one language.\n\n"
         f"Embeddings alone still follow language: on the training books, before centring, NMI is "
         f"{f2(R.ce_nmi_before)}. After we subtract each language's average it falls to {f2(R.ce_nmi_after)}, and "
         f"the final groups score {f2(R.nmi_all)}: they no longer follow language, so subject can come through."),
        (RAJITH, "Removing each language's average helps every model find subjects",
         "Does centring really help with subject? We checked it on four embedding models, "
         + ", ".join(R.encoders_compared) + ", on labelled books from the earlier study.\n\n"
         "The test is simple: guess a book's subject from the books closest to it. If close books share a subject, the "
         "guess is right more often.\n\n"
         "Grey is the model as it comes. Red is after we subtract each language's average. For every model, red is "
         "longer: once language is removed, a book's neighbours are more often on the same subject.\n\n"
         f"One honest note: {R.encoder}, the model behind our final groups, was not part of this comparison."),
        (RAJITH, f"{len(g)} broad groups, each mixing all {R.languages} languages",
         f"These are the groups the model found on all {n(R.usable)} usable books, using {R.linkage} linkage cut into "
         f"{R.k} groups. Our selection rule, written before the results, asked for groups that do not follow script "
         "and that survive resampling; no setting passed, so the rule's pre-registered fallback chose this one, and "
         "we report that as a rule failure.\n\n"
         + "\n".join(f"- Group {x['group'] + 1}: {n(x['books'])} books, most common subject {x['majority_subject']}."
                     for x in g) + "\n\n"
         "Each row of the table shows what share of the group comes from each language. No language holds more than "
         f"{pct(R.max_lang_share, 0)} of any group, so the groups are not language piles any more.\n\n"
         "We did not name the groups by hand: the subject is the most common one among the labelled training books in "
         "the group.\n\n"
         "Be honest about what this shows: the groups are broad. "
         + (f"Groups {' and '.join(map(str, rel_phil))} both lean to religion and philosophy, so they split one "
            "subject by something else in the vocabulary. " if len(rel_phil) > 1 else "")
         + "These are rough shelves, not a catalogue."),
        (RAJITH, f"The groups guess subject {R.t2_points:.1f} points better than the best simple guess",
         "How good are the groups? We kept some books aside and never used them to build the groups. For "
         f"{R.t2_test_labels} of these test books we have a subject label.\n\n"
         f"Each group predicts its most common subject. That is right {pct(R.t2_acc)} of the time.\n\n"
         f"Is that good? Compare with simple guesses. Guessing from the script alone is right {pct(R.t2_script)} of "
         f"the time. Always guessing the most common subject is right {pct(R.t2_common)}.\n\n"
         f"So the groups beat the best simple guess by {R.t2_points:.1f} points. Our target, written before the "
         f"results, was {R.target_t2:.0f} points, so this target is {met(R.met_t2)}. Shuffling the subject labels at "
         f"random almost never gives a gain this big: p = {R.t2_p:.4f}.\n\n"
         f"But it is a small sample, so say the uncertainty: the likely range of the accuracy is "
         f"{pct_ci(R.t2_acc_ci)}, and of the gain {pts_ci(R.t2_points_ci)} points, which reaches below our target. "
         f"On the validation books the gain was only {R.t2_val_points:.1f} points. The gain is real; its size is "
         "uncertain."),
        (RAJITH, "The groups change when we re-run on other books",
         "A good grouping should not change much if we start from a slightly different set of books. So we re-ran the "
         "grouping 20 times, each time on a random 80% of the books, and compared each result with the full grouping.\n\n"
         "We compare groupings with ARI, a score of how much two groupings agree: 1 means identical, 0 means no better "
         "than chance.\n\n"
         f"Each red dot is one re-run of our hierarchical groups. The middle value is {f2(R.boot_all)}, and most runs "
         f"fall between {f2(R.boot_p10)} and {f2(R.boot_p90)}. Our target was {R.target_t3}, measured on the training "
         f"books, where we got {f2(R.t3)}: {met(R.met_t3)}. The groups are broad and partly shift.\n\n"
         f"The grey dots are DBSCAN, which looks for crowded regions of books. It is steadier, around "
         f"{f2(R.db_boot)}, but it calls {pct(R.db_noise)} of the books noise, meaning they sit in no crowded region, "
         f"and it finds only {R.db_clusters} clusters, which do not match the hierarchical groups. So we use the "
         "hierarchical groups as the shelves and show DBSCAN's verdict beside them.\n\n"
         "I now hand over to Sai Pranav for what an archivist gets."),
        (SAI, "For a book with no class, the tool suggests one",
         "Thank you, Rajith. What does an archivist get? This is a real answer from our app, recorded from the final "
         "model.\n\n"
         f"The book is {book['title']}, a {book['script']} book printed {book['era'].replace('pre-', 'before ')}. "
         "It has no library class.\n\n"
         "The tool looks at the nearest books that do have a class and lets them vote; closer books count more. The "
         f"bars are each class's share of the vote. The top suggestion is {sugg[0]}, then {sugg[1]}.\n\n"
         f"How often is it right? On {n(R.sug_heldout)} test books that do have a class, the top suggestion is the "
         f"book's own class {pct(R.sug_top1)} of the time, against {pct(R.sug_base)} for always suggesting the most "
         f"common class; the right class is in the top three {pct(R.sug_top3)} of the time.\n\n"
         "It is a suggestion for the archivist to accept or reject, shown with its evidence."),
        (SAI, f"One {book['script']} book's closest neighbours come from {len(rel_scripts)} other scripts",
         "The second tool connects books across scripts, which a normal catalogue search cannot do.\n\n"
         f"We take the same {book['script']} book and ask for its closest books written in other scripts. These are the first 8 "
         f"answers, again recorded from the app. They come from {', '.join(rel_scripts)} books; the closest is "
         f"{rel[0]['title']}.\n\n"
         "The model never saw a translation dictionary: it found these because, after centring, books sit close by "
         f"meaning whatever their script. Across the training books, {pct(R.rel_centred)} of a book's "
         f"{R.rel_k} nearest neighbours are in another script after centring, against {pct(R.rel_uncentred)} before. "
         "That shows other scripts now reach the list; it does not by itself prove they share the subject.\n\n"
         "A related tool looks for other editions of the same book. We tested it on only "
         f"{R.ed_groups} edition groups among the test books: precision {f2(R.ed_precision)}, recall "
         f"{pct(R.ed_recall)}, with a likely range for recall of {pct_ci(R.ed_recall_ci)}. Too few to trust yet."),
        (SAI, "A single new page lands in its book's group most of the time",
         "The third tool: an archivist scans one new page, and the app places it among the archive's books.\n\n"
         "The number on the left is our test of exactly this. We took one page from each test book and checked "
         f"whether it lands in the same group as its whole book. It does {pct(R.t1)} of the time, likely range "
         f"{pct_ci(R.t1_ci)}. A random guess would manage {pct(R.t1_chance)}. Our target was "
         f"{pct(R.target_t1, 0)}, so it is {met(R.met_t1)}.\n\n"
         f"On the right is a real check of a {chk['script']} page. The app shows the closest archive books, with "
         "links, so the archivist can see why it decided. It also says when it is unsure: here DBSCAN says the page "
         + ("sits in a crowded region" if chk["dbscan"]["in_dense_group"] else "is not in any crowded region")
         + ", and the app shows that too. When a page has fewer than 20 readable words, it refuses to guess."),
        (SAI, "On the archive map, English books sit apart until centring mixes them in",
         "This is the picture behind our main finding, and it is a page of the site: the archive map.\n\n"
         "Each dot is one book, placed by the numbers the model gives its text, flattened to two directions. The red "
         "dots are English books; the grey dots are every other language.\n\n"
         "On the left, the numbers as the model gives them: the English books sit in their own corner. On the right, "
         "after we subtract each language's average: the same books sit among the others, so a book's neighbours can "
         "come from any script.\n\n"
         f"The slide shows a sample of the {n(R.usable)} books. On the site the map is in 3-D with every book: you can "
         "turn it, colour the dots by language or by group, and open sample books. A flat picture loses detail, so we "
         "use the map to explain and the measurements to prove."),
        (SAI, "The scan quality page lists books to scan again, but its score is not proven",
         "The archive also needs to know which scans to redo. The scan quality page gives every downloaded book one of "
         "three verdicts: fine, read again with OCR, or scan again.\n\n"
         "The chart counts the flagged books in each language, taken from the app. Red is scan again: our OCR was "
         "unsure and the archive has no text of its own. Grey is read again: the book has too few readable words.\n\n"
         f"Does the score work? We tested it on {n(R.tri_books)} books where we can compare our OCR with the archive's "
         f"own. Its AUC is {f2(R.tri_auc)}, where 0.5 is a coin toss, so it is no better than chance. We show the page "
         "as a work list built from plain rules, not as a proven predictor."),
        (SAI, f"The edition finder is right when it answers, but finds {pct(R.ed_recall, 0)} of known editions",
         "The last tool looks for other editions of the same book, so an archive does not catalogue or preserve the "
         "same work twice without knowing.\n\n"
         "Two books count as editions of one work when they share a title and an author, after spelling is evened "
         "out. The finder proposes the books that sit closer to a book than a set distance.\n\n"
         f"Of the pairs it reported, {pct(R.ed_precision)} were true editions. Of the true editions, it found "
         f"{pct(R.ed_recall)}, with a likely range of {pct_ci(R.ed_recall_ci)}. The range is wide because the test is "
         f"small: only {R.ed_groups} groups of known editions among the test books. Careful but incomplete, and too "
         "little tested to trust yet."),
        (SAI, "One site puts every tool in an archivist's hands, in 7 pages",
         "Everything you have seen runs in one web app. These are its pages.\n\n"
         "Check a page is the working desk: upload a scan or paste text, and it returns the group, the closest archive "
         "books and a catalogue card. Browse groups lists each group's books. The archive map, scan quality and "
         "editions pages are the three tools from the last slides.\n\n"
         "Two pages explain rather than do. Impact tells the story as three archive problems, each beside its measured "
         "result. The study page shows every result with its method, has a presenter mode, and offers a guide for "
         "repeating the study as a PDF.\n\n"
         "The site was redesigned for reading, with a light and a dark theme. Behind the pages is an API that gives "
         "the same answers to other software, including a check for a whole list of books at once."),
        (SAI, "What this changes for an archive",
         "Before the limits, the case for the tool in three numbers. These are the three stories on the site's impact "
         "page.\n\n"
         f"One, books meet across scripts. As the model gives them, only {pct(R.rel_uncentred)} of a book's "
         f"{R.rel_k} closest books are in another script. After centring, {pct(R.rel_centred)}.\n\n"
         f"Two, a class for books that have none. On {n(R.sug_heldout)} held-out books that do have a class, the "
         f"book's own class is among the first three suggestions {pct(R.sug_top3)} of the time; the top suggestion "
         f"alone is right {pct(R.sug_top1)}, against {pct(R.sug_base)} for always naming the most common class.\n\n"
         f"Three, a loose page finds its book. A single page lands in its own book's group {pct(R.t1)} of the time, "
         f"against {pct(R.t1_chance)} by chance, and the app refuses to guess when a page has too few readable words: "
         f"{pct(R.t1_abstain)} of the test pages."),
        (SAI, "What it does not do yet",
         "Our limits, plainly.\n\n"
         f"We set three targets before seeing any results, and this study met {R.n_met} of them. A page lands with "
         f"its book {pct(R.t1)} of the time against a target of {pct(R.target_t1, 0)}: {met(R.met_t1)}. The subject "
         f"gain is {R.t2_points:.1f} points against {R.target_t2:.0f}: {met(R.met_t2)}, though its likely range is "
         f"wide. Stability, measured on the training books, is {f2(R.t3)} against {R.target_t3}: {met(R.met_t3)}.\n\n"
         f"Two more weak results. Against the librarians' own classes the groups do worse than guessing from the "
         f"script, {pts(R.cat_points)} points. And our scan-triage score, which flags books for re-scanning, has an "
         f"AUC of {f2(R.tri_auc)}: no better than chance at predicting where our OCR disagrees with the archive's.\n\n"
         f"The groups are broad: {R.k} groups for a whole library. Hard-to-read languages are under-represented; "
         f"Telugu keeps only {pct(R.telugu_share, 0)} of its books. The subject labels we test with were made with an "
         "AI assistant and checked by us; they are a measuring tool, not expert cataloguing. And the embedding model is "
         "an online Google service, so checking a page sends its text to Google.\n\n"
         "So we offer this as a helper that shows its evidence, not as a catalogue."),
        (SAI, "Take away the language, and subject starts to show",
         "To sum up in three sentences.\n\n"
         "One: multilingual book vectors group by language first; subtracting each language's average is what lets "
         "subject come through.\n\n"
         f"Two: the groups beat simple guesses on books kept aside by {R.t2_points:.1f} points, past our target of "
         f"{R.target_t2:.0f}, but the range is wide, a page lands with its book less often than we aimed, and the "
         "groups are not yet stable.\n\n"
         "Three: even now the model is useful to an archivist as a helper: it suggests a class for an uncatalogued "
         "book, links books across scripts, and places a new page, always with its evidence.\n\n"
         "On behalf of Rohan, Rajith and myself, thank you. We are happy to take your questions."),
    ]


def build() -> str:
    out = ["# Speaker script: Grantha Heritage Tracker (SIH26096)", "",
           "Generated by `scripts/build_speaker_script.py` from the result files, following the deck "
           "`Grantha_Heritage_Tracker_SIH26096.pptx` slide by slide. Edit the builder, not this file.", "",
           "Where the deck's own speaker notes differ from this script, this script follows the result files: the "
           "subject target is met, and two of the groups lean to religion and philosophy.", ""]
    for i, (who, title, text) in enumerate(slides(), 1):
        out += [f"## Slide {i}: {title}", "", f"[{who} - SLIDE {i}]", "", text, ""]
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
