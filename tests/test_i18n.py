"""Tests for the i18n and startup systems."""

import importlib
import os

from minisweagent import i18n


def test_detect_system_language_english():
    importlib.reload(os) if False else None
    os.environ.pop("LANGUAGE", None)
    os.environ.pop("LC_ALL", None)
    os.environ.pop("LC_MESSAGES", None)
    os.environ["LANG"] = "en_US.UTF-8"
    assert i18n.detect_system_language() == "en"


def test_detect_system_language_chinese():
    os.environ.pop("LANGUAGE", None)
    os.environ.pop("LC_ALL", None)
    os.environ.pop("LC_MESSAGES", None)
    os.environ["LANG"] = "zh_CN.UTF-8"
    assert i18n.detect_system_language() == "zh"


def test_english_is_identity():
    i18n.set_language("en")
    msg = "Switched to [bold green]{mode}[/bold green] mode."
    assert i18n.t(msg).format(mode="yolo") == msg.format(mode="yolo")


def test_chinese_translation_applied():
    i18n.set_language("zh")
    out = i18n.t("Switched to [bold green]{mode}[/bold green] mode.").format(mode="yolo")
    assert "已切换" in out
    i18n.set_language("en")


def test_missing_translation_falls_back_to_source():
    i18n.set_language("zh")
    custom = "This string has no translation entry at all"
    assert i18n.t(custom) == custom
    i18n.set_language("en")


def test_set_language_unknown_falls_back_to_en():
    assert i18n.set_language("klingon") == "en"
