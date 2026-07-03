from app.services.template_service import extract_variables, render_template


def test_extract_variables_returns_unique_placeholders():
    variables = extract_variables("Hi {{name}}, welcome to {{brand}}. {{name}}")

    assert sorted(variables) == ["brand", "name"]


def test_render_template_replaces_known_variables():
    subject, body = render_template(
        "Hi {{first_name}}",
        "<p>{{first_name}}, welcome to {{brand}}</p>",
        {"first_name": "Sam", "brand": "UGC Outreach"},
    )

    assert subject == "Hi Sam"
    assert body == "<p>Sam, welcome to UGC Outreach</p>"
