from app.core.html_sanitize import sanitize_html


def test_allows_email_safe_tags():
    html = "<p><strong>bold</strong> <em>italic</em> <a href=\"https://x.com\">link</a></p>"

    result = sanitize_html(html)

    assert "<strong>bold</strong>" in result
    assert "<em>italic</em>" in result
    assert 'href="https://x.com"' in result


def test_preserves_text_align_style_on_paragraph_and_heading():
    """Regression guard: Tiptap's TextAlign extension sets style="text-align:..."
    directly on <p>/<h1-6>. If these tags aren't allowed a style attribute,
    alignment silently vanishes on the next save."""
    p = sanitize_html('<p style="text-align: center">Hi</p>')
    h2 = sanitize_html('<h2 style="text-align:right">Title</h2>')

    assert 'style="text-align: center"' in p
    assert 'style="text-align:right"' in h2


def test_strips_script_tag_and_content():
    result = sanitize_html("<script>alert(1)</script>safe")

    assert "script" not in result
    assert "alert" not in result
    assert result == "safe"


def test_strips_event_handler_attributes():
    result = sanitize_html('<img src="x.png" onerror="alert(1)">')

    assert "onerror" not in result
    assert 'src="x.png"' in result


def test_strips_javascript_url_scheme():
    result = sanitize_html('<a href="javascript:alert(1)">click</a>')

    assert "javascript:" not in result


def test_allows_table_structure_with_colspan_and_style():
    html = '<table><tr><td colspan="2" style="color:red">cell</td></tr></table>'

    result = sanitize_html(html)

    assert 'colspan="2"' in result
    assert 'style="color:red"' in result
    assert "<td>cell</td>" not in result  # style must survive, not be stripped


def test_empty_and_none_input_return_empty_string():
    assert sanitize_html(None) == ""
    assert sanitize_html("") == ""


def test_link_gets_safe_rel_attribute():
    result = sanitize_html('<a href="https://x.com">x</a>')

    assert 'rel="noopener noreferrer"' in result
