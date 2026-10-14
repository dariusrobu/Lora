from integrations.moodle_readonly import (
    parse_course_html,
    parse_forum_discussion_links,
    parse_forum_html,
)


def test_parser_excludes_assessments() -> None:
    html = """
    <h1>Course</h1>
    <li class="section"><h3 class="sectionname">Evaluare intermediară</h3>
      <div class="activity modtype_resource"><a href="/test.pdf">Test grilă</a></div>
    </li>
    <li class="section"><h3 class="sectionname">Curs</h3>
      <div class="activity modtype_resource"><a href="/curs.pdf">Curs 1</a></div>
    </li>
    """
    result = parse_course_html(html, "https://example.test/course?id=1")
    titles = [item["title"] for section in result["sections"] for item in section["items"]]
    assert titles == ["Curs 1"]


def test_parse_forum_html_extracts_posts() -> None:
    html = """
    <article class="forum-post"><h3>Profesor</h3><div>Material nou pentru seminar.</div></article>
    <article class="forum-post"><h3>Student</h3><div>Mulțumesc!</div></article>
    """
    content = parse_forum_html(html, "https://example.test/forum")
    assert "Material nou pentru seminar." in content
    assert "Mulțumesc!" in content


def test_parse_forum_html_formats_post_metadata_and_links() -> None:
    html = """
    <article class="forum-post">
      <h3>RECUPERARE Seminar</h3>
      <div>RECUPERARE Seminar by POP Fănuța - Tuesday, 6 October 2026, 10:16 AM
        Number of replies: 0
        Stimați studenți! Întâlnire pe Zoom.
        <a href="https://example.test/zoom">LINK ZOOM</a>
        <span>Permalink</span>
      </div>
    </article>
    """
    content = parse_forum_html(html, "https://example.test/forum")
    assert "**Autor:** POP Fănuța" in content
    assert "**Mesaj:**" in content
    assert "[LINK ZOOM](https://example.test/zoom)" in content


def test_parse_forum_discussion_links_extracts_detail_pages() -> None:
    html = """
    <div class="discussion"><a href="/moodle/mod/forum/discuss.php?d=42">
      RECUPERARE Seminar
    </a></div>
    <a href="/moodle/mod/forum/view.php?id=10">Înapoi la forum</a>
    """
    links = parse_forum_discussion_links(html, "https://example.test/moodle/mod/forum/view.php?id=10")
    assert links == [{
        "title": "RECUPERARE Seminar",
        "url": "https://example.test/moodle/mod/forum/discuss.php?d=42",
    }]


def test_parse_course_html_preserves_sections_and_item_types() -> None:
    html = """
    <html><body>
      <h1>Analiză financiară_EG3_26-27</h1>
      <li class="section">
        <h3 class="sectionname">General</h3>
        <div class="activity modtype_forum unread">
          <a href="/moodle/mod/forum/view.php?id=10">Forum ANALIZĂ FINANCIARĂ</a>
          <span>1 unread post</span>
        </div>
      </li>
      <li class="section">
        <h3 class="sectionname">Fișa disciplinei</h3>
        <div class="activity modtype_resource">
          <a href="/moodle/pluginfile.php/1/file.pdf">Fișa disciplinei 2026</a>
        </div>
      </li>
    </body></html>
    """

    result = parse_course_html(html, "https://econ.example/moodle/course/view.php?id=9738")

    assert result["course_id"] == "9738"
    assert result["course"] == "Analiză financiară_EG3_26-27"
    assert [section["title"] for section in result["sections"]] == [
        "General",
        "Fișa disciplinei",
    ]
    forum = result["sections"][0]["items"][0]
    assert forum["item_type"] == "forum"
    assert forum["unread"] is True
    pdf = result["sections"][1]["items"][0]
    assert pdf["item_type"] == "file"
    assert pdf["file_url"] == "https://econ.example/moodle/pluginfile.php/1/file.pdf"
    assert pdf["fingerprint"]


def test_parser_deduplicates_same_activity() -> None:
    html = """
    <h1>Course</h1>
    <li class="section"><h3>General</h3>
      <div class="activity"><a href="/same">Same</a></div>
      <div class="activity"><a href="/same">Same</a></div>
    </li>
    """

    result = parse_course_html(html, "https://example.test/course?id=1")

    assert len(result["sections"][0]["items"]) == 1


def test_parser_finds_material_links_in_section_description() -> None:
    html = """
    <h1>Course</h1>
    <li class="section"><h3 class="sectionname">Tematică C1/S1</h3>
      <div class="summary">
        <a href="/moodle/mod/folder/view.php?id=44">Materiale seminar</a>
        <a href="/moodle/pluginfile.php/44/file/curs.pdf">Curs PDF</a>
      </div>
    </li>
    """
    result = parse_course_html(html, "https://example.test/moodle/course/view.php?id=1")
    items = result["sections"][0]["items"]
    assert [item["title"] for item in items] == ["Materiale seminar", "Curs PDF"]
    assert all(item["item_type"] == "file" for item in items)
