from chat_app import demo


def test_ai_chat_screen_has_only_chatbot_interface():
    config = str(demo.get_config())

    assert "GoodWe IA Chat" in config
    assert "Calcular previsão" not in config
    assert "Previsão de recarga" not in config
