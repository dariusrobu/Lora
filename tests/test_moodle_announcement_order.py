from scripts.moodle_bridge import _announcement_markdown


def test_publication_order_and_repeated_discussion() -> None:
    old = '### Later event\n\n**Data:** Tuesday, 6 October 2026, 10:16 AM\n\nOld body\nhttps://example.test/discuss.php?d=1'
    new = '### Earlier event\n\n**Data:** Monday, 12 October 2026, 10:54 AM\n\nNew body\nhttps://example.test/discuss.php?d=2'
    course = {'sections': [{'title': 'General', 'items': [
        {'item_type': 'forum', 'content': old + '\n\n' + new},
        {'item_type': 'forum', 'content': old},
    ]}]}
    result = _announcement_markdown(course)
    assert result.count('Old body') == 1
    assert result.count('New body') == 1
    assert result.index('New body') < result.index('Old body')
