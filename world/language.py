"""
Language handling for says in emotes: lang"text" is garbled for viewers who don't know the language.
Uses Evennia's rplanguage for obfuscation. Characters can have db.languages = {"english": 1.0, "gutter": 0.5}.
Level 1.0 = full understanding (no garbling), 0.0 = none (full garbling).

Lore languages: english (default), gutter, high imperial, cant, trade, rite.
Call ensure_lore_languages() once at server startup to register all of them.
"""

import re

# Canonical list of lore language keys (for help, validation, defaults)
LORE_LANGUAGE_KEYS = ("english", "gutter", "high_imperial", "cant", "trade", "rite")


def ensure_lore_languages():
    """
    Register all lore-fitting languages so lang"..." in emotes works.
    Call once at server startup (e.g. in server/conf/at_server_start.py or a startup hook).
    """
    try:
        from evennia.contrib.rpg.rpsystem.rplanguage import add_language
    except ImportError:
        return
    # English – common tongue; standard phoneme set (garbled = generic foreign)
    add_language(key="english", force=False)
    # Grammar/phonemes must include v, vv, c, cc (single/double vowel, single/double consonant)
    _v = "a e i o u y"
    _vv = "ea oh ae aa ou ey oi"
    _c = "p t k b d g f s m n l r w"
    _cc = "sh ch ng th zh"
    # Gutter – undercity/tunnel street speech; harsh, clipped
    add_language(
        key="gutter",
        phonemes="%s %s %s k g t d p b f s z sh kh r l n m ng" % (_v, _vv, _c),
        grammar="v c vc cv cvc vcc cvcc ccv cvcv",
        vowels="aeiouy",
        word_length_variance=0,
        force=False,
    )
    # High Imperial – Authority/formal; Latin-ish, longer words
    add_language(
        key="high_imperial",
        phonemes="%s %s %s %s p t k b d g f s th v z m n l r w y" % (_v, _vv, _c, _cc),
        grammar="v cv vc cvv vcc cvc cvvc vccv cvcvc cvccvc",
        vowels="aeiouy",
        word_length_variance=1,
        noun_translate=False,
        force=False,
    )
    # Cant – underworld/thieves' slang; sharp, short
    add_language(
        key="cant",
        phonemes="%s %s %s %s k t p s z f th g d b r l n m" % (_v, _vv, _c, _cc),
        grammar="v c cv vc cvc ccv cvcv",
        vowels="aeiouy",
        word_length_variance=0,
        force=False,
    )
    # Trade – mixed trade tongue; simple, merchant creole
    add_language(
        key="trade",
        phonemes="%s %s %s %s p t k b d g s z m n l r w y" % (_v, _vv, _c, _cc),
        grammar="v cv vc cvc cvv vcc cvcv",
        vowels="aeiouy",
        word_length_variance=0,
        force=False,
    )
    # Rite – ritual/occult (the Rite, the Below); archaic, ritualistic
    add_language(
        key="rite",
        phonemes="%s %s %s %s th dh kh gh s z m n l r v" % (_v, _vv, _c, _cc),
        grammar="v cv vc cvv vcc cvc cvvc vccv cvcvc",
        vowels="aeiouy",
        word_length_variance=1,
        noun_translate=False,
        force=False,
    )


def ensure_default_language():
    """Call once at startup to ensure default/English exists. Prefer ensure_lore_languages() instead."""
    ensure_lore_languages()


def process_language_for_viewer(speaker, quote_text, lang_key, viewer):
    """
    Return the quote text as the viewer hears it (possibly garbled).
    speaker: who said it; viewer: who hears it; lang_key: language id or None for English.
    If viewer is None (e.g. camera feed), return clear text.
    """
    if not quote_text:
        return quote_text
    if viewer is None:
        return quote_text
    lang_key = (lang_key or "english").strip().lower() or "english"
    if lang_key == "default":
        lang_key = "english"
    # Friendly aliases for lore languages
    _alias = {
        "high imperial": "high_imperial",
        "highimperial": "high_imperial",
        "imperial": "high_imperial",
    }
    lang_key = _alias.get(lang_key, lang_key)
    try:
        from evennia.contrib.rpg.rpsystem.rplanguage import obfuscate_language
    except ImportError:
        return quote_text
    # Viewer's skill in this language (0 = no understanding, 1 = full)
    skills = getattr(viewer.db, "languages", None) or {}
    if isinstance(skills, dict):
        level = skills.get(lang_key, 0.0)
    else:
        level = 0.0
    # level is understanding: 1.0 = clear, 0.0 = full obfuscation
    obfuscate_level = 1.0 - max(0.0, min(1.0, float(level)))
    if obfuscate_level <= 0:
        return quote_text
    try:
        return obfuscate_language(quote_text, level=obfuscate_level, language=lang_key)
    except Exception:
        return quote_text


# Words that are not language keys (pronouns, contractions)
_NOT_LANG = frozenset(
    "i im ive id ill we you he she they the a an is it s t re ve ll d m".split()
)


def parse_quoted_speech(text):
    """
    Find lang"..." and "..." in text. Replace with placeholders __LANG_0__, __LANG_1__, ...
    Returns (text_with_placeholders, [(placeholder_id, lang_key, quote_text), ...]).
    lang_key is None for plain "..." (default language).
    """
    out = []
    result = []
    # Match optional word (language key) + "..." . Skip if "word" looks like pronoun/contraction.
    pattern = re.compile(r'(?:(?P<lang>\w+))?"(?P<quote>[^"]*)"', re.UNICODE)
    last_end = 0
    n = 0
    for m in pattern.finditer(text):
        lang = m.group("lang")
        quote = m.group("quote")
        if lang and lang.lower() in _NOT_LANG:
            continue
        placeholder = "__LANG_%d__" % n
        n += 1
        result.append((placeholder, lang.strip() if lang else None, quote))
        out.append(text[last_end:m.start()])
        out.append(placeholder)
        last_end = m.end()
    out.append(text[last_end:])
    return ("".join(out), result)
