from pipeline import config, sampling


def test_parse_year():
    assert sampling.parse_year("1953-01-01T00:00:00Z") == 1953
    assert sampling.parse_year(["1912"]) == 1912
    assert sampling.parse_year("c. 1890?") == 1890
    assert sampling.parse_year("") is None
    assert sampling.parse_year(None) is None
    assert sampling.parse_year("unknown") is None


def test_era_bands():
    assert sampling.era_of(None) == "undated"
    assert sampling.era_of(1850) == "pre-1900"
    assert sampling.era_of(1899) == "pre-1900"
    assert sampling.era_of(1900) == "1900-1919"
    assert sampling.era_of(1939) == "1920-1939"
    assert sampling.era_of(1960) == "1940-1960"
    assert sampling.era_of(1961) is None  # out of heritage scope


def _items(n_per_band):
    items = []
    for band, n in n_per_band.items():
        items += [{"identifier": f"{band}-{i:03d}", "era": band} for i in range(n)]
    return items


def test_stratified_order_is_balanced_and_deterministic():
    items = _items({"pre-1900": 100, "1900-1919": 100, "1920-1939": 100, "1940-1960": 100, "undated": 100})
    a = sampling.stratified_order(items, seed=1)
    b = sampling.stratified_order(list(reversed(items)), seed=1)
    assert [x["identifier"] for x in a] == [x["identifier"] for x in b]  # input order does not matter
    first50 = a[:50]
    counts = {band: sum(1 for x in first50 if x["era"] == band) for band in
              ["pre-1900", "1900-1919", "1920-1939", "1940-1960", "undated"]}
    assert set(counts.values()) == {10}


def test_stratified_order_redistributes_small_bands():
    items = _items({"pre-1900": 3, "1940-1960": 100})
    order = sampling.stratified_order(items)
    assert len(order) == 103
    first20 = order[:20]
    assert sum(1 for x in first20 if x["era"] == "pre-1900") == 3


def test_pilot_is_prefix_of_full():
    items = _items({"pre-1900": 50, "1900-1919": 400, "undated": 400})
    order = sampling.stratified_order(items)
    assert order[:config.PILOT_PER_LANG] == order[:config.FULL_PER_LANG][:config.PILOT_PER_LANG]


def test_choose_leaves():
    leaves = sampling.choose_leaves(101)
    assert [l for l, _ in leaves] == [15, 30, 50, 70, 85]
    small = sampling.choose_leaves(3)
    assert len({l for l, _ in small}) == len(small)
    assert all(0 <= l < 3 for l, _ in small)


def test_parse_dc():
    desc = ('<p><b>Book Source:</b> x</p><p>dc.contributor.author: Mulla<br />'
            'dc.description.totalpages: 804<br />dc.subject.classification: Law<br />'
            'dc.subject.classification: Hindu Law<br />dc.title: Principles &amp; Practice<br /></p>')
    dc = sampling.parse_dc(desc)
    assert dc["description.totalpages"] == ["804"]
    assert dc["subject.classification"] == ["Law", "Hindu Law"]
    assert dc["title"] == ["Principles & Practice"]
    assert sampling.total_pages_of(dc, {}) == 804
    assert sampling.total_pages_of({}, {"imagecount": "212"}) == 212
    assert sampling.total_pages_of({}, {}) is None
