# -*- coding: utf-8 -*-
# ============================================================
#  MasterCode Translator - Burp Suite Extension  v1.1.0
#  Auto-detects ANY language -> translates to English (online)
#  Tab caption: "Translator"
#
#  Author : MasterCode
#  Fixed  : NoneType iterable crash on Google API response
# ============================================================

from burp import IBurpExtender, IMessageEditorTabFactory, IMessageEditorTab
from javax.swing import (JPanel, JTextArea, JScrollPane, JLabel,
                         JButton, JSplitPane, JCheckBox, BorderFactory,
                         SwingUtilities)
from java.awt import BorderLayout, Color, Font, FlowLayout
from java.awt.event import ActionListener
import json, re, urllib, urllib2, threading, time

EXT_NAME    = "MasterCode Translator"
TAB_CAPTION = "Translator"
VERSION     = "1.1.0"

# ============================================================
# TRANSLATION ENGINE
# ============================================================
_translate_cache = {}


def google_translate(text, src="auto", tgt="en"):
    """
    Free Google Translate endpoint - no API key required.
    src="auto" -> Google detects language automatically.
    Returns (translated_str, detected_lang_code).
    Never raises - always returns something safe.
    """
    # Guard: skip empty / non-string / pure whitespace
    if not text:
        return text, "unknown"
    if not isinstance(text, (str, unicode)):
        return str(text), "unknown"
    stripped = text.strip()
    if len(stripped) < 2:
        return text, "unknown"

    cache_key = (src, tgt, stripped[:300])
    if cache_key in _translate_cache:
        return _translate_cache[cache_key]

    try:
        # Build URL manually - avoids urllib.urlencode issues with repeated "dt" params
        q_enc = urllib.quote(stripped.encode("utf-8"), safe="")
        url = (
            "https://translate.googleapis.com/translate_a/single"
            "?client=gtx"
            "&sl=" + src +
            "&tl=" + tgt +
            "&dt=t"
            "&dt=ld"
            "&q=" + q_enc
        )
        req = urllib2.Request(url)
        req.add_header(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        req.add_header("Accept", "application/json, text/javascript, */*")

        resp = urllib2.urlopen(req, timeout=8)
        raw  = resp.read()
        data = json.loads(raw)

        # ---- Parse translation chunks safely ----
        # data[0] = list of [translated_part, original_part, ...]
        # Any element can be None  <-- this was the crash
        translated_parts = []
        try:
            chunks = data[0]            # can be None if Google returns weird response
            if chunks and isinstance(chunks, list):
                for chunk in chunks:
                    if not chunk:       # chunk itself is None/empty
                        continue
                    if not isinstance(chunk, list):
                        continue
                    part = chunk[0] if len(chunk) > 0 else None
                    if part and isinstance(part, (str, unicode)):
                        translated_parts.append(part)
        except Exception:
            pass

        translated = u"".join(translated_parts) if translated_parts else stripped

        # ---- Parse detected language safely ----
        detected_lang = "unknown"
        try:
            if isinstance(data, list) and len(data) > 2:
                lang_val = data[2]
                if lang_val and isinstance(lang_val, (str, unicode)):
                    detected_lang = str(lang_val).strip()
        except Exception:
            pass

        result = (translated, detected_lang)
        _translate_cache[cache_key] = result
        return result

    except urllib2.HTTPError as e:
        return text, "http-{}".format(e.code)
    except urllib2.URLError:
        return text, "network-error"
    except ValueError:
        return text, "parse-error"
    except Exception:
        return text, "error"


def _translate_obj(obj):
    """Recursively translate all string values in a JSON object."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            tk, _ = google_translate(k)
            out[tk] = _translate_obj(v)
        return out
    elif isinstance(obj, list):
        return [_translate_obj(i) for i in obj]
    elif isinstance(obj, (str, unicode)):
        t, _ = google_translate(obj)
        return t
    return obj


def process_body(raw_bytes, helpers):
    """
    Detect body format, translate all text to English.
    Returns (original_str, translated_str, fmt, detected_lang, method).
    """
    if not raw_bytes or len(raw_bytes) == 0:
        return "", "<empty body>", "empty", "n/a", "n/a"

    try:
        raw = helpers.bytesToString(raw_bytes)
    except Exception:
        try:
            raw = raw_bytes.tostring()
        except Exception:
            raw = str(raw_bytes)

    if not raw or not raw.strip():
        return raw or "", "<empty body>", "empty", "n/a", "n/a"

    # ---- JSON ----------------------------------------------------
    try:
        parsed = json.loads(raw)
        # detect lang from first 300 chars of raw JSON
        _, lang = google_translate(raw[:300])
        # translate all string values recursively
        translated = _translate_obj(parsed)
        pretty_orig = json.dumps(parsed,     indent=2, ensure_ascii=False)
        pretty_tran = json.dumps(translated, indent=2, ensure_ascii=False)
        return pretty_orig, pretty_tran, "JSON", lang, "google-auto"
    except Exception:
        pass

    # ---- URL-encoded form data -----------------------------------
    if "=" in raw and not raw.strip().startswith("<"):
        try:
            orig_lines, tran_lines = [], []
            detected_lang = "unknown"
            for pair in raw.split("&"):
                pair = pair.strip()
                if not pair:
                    continue
                if "=" in pair:
                    k, _, v = pair.partition("=")
                    k_d = urllib.unquote_plus(k)
                    v_d = urllib.unquote_plus(v)
                    v_t, lang = google_translate(v_d)
                    if lang and lang not in ("unknown", "en") and not lang.startswith("error") and not lang.startswith("http"):
                        detected_lang = lang
                    orig_lines.append(u"  {} = {}".format(k_d, v_d))
                    tran_lines.append(u"  {} = {}".format(k_d, v_t))
                else:
                    orig_lines.append(pair)
                    tran_lines.append(pair)
            if orig_lines:
                return (
                    u"\n".join(orig_lines),
                    u"\n".join(tran_lines),
                    "form-urlencoded",
                    detected_lang,
                    "google-auto"
                )
        except Exception:
            pass

    # ---- Plain text / XML / HTML --------------------------------
    translated, lang = google_translate(raw)
    return raw, translated, "text", lang, "google-auto"


# ============================================================
# BURP ENTRY POINT
# ============================================================
class BurpExtender(IBurpExtender, IMessageEditorTabFactory):

    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        self._helpers   = callbacks.getHelpers()
        callbacks.setExtensionName(EXT_NAME)
        callbacks.registerMessageEditorTabFactory(self)
        print("=" * 55)
        print("  {} v{}  loaded".format(EXT_NAME, VERSION))
        print("  Tab      : '{}'".format(TAB_CAPTION))
        print("  Engine   : Google Translate (sl=auto -> EN)")
        print("  Fix v1.1 : NoneType iterable crash resolved")
        print("=" * 55)

    def createNewInstance(self, controller, editable):
        return TranslatorTab(self._callbacks, self._helpers, controller, editable)


# ============================================================
# MESSAGE EDITOR TAB
# ============================================================
class TranslatorTab(IMessageEditorTab):

    BG_DARK   = Color(0x1e, 0x1e, 0x2e)
    BG_MID    = Color(0x24, 0x27, 0x3a)
    BG_BAR    = Color(0x13, 0x13, 0x20)
    FG_MAIN   = Color(0xca, 0xd3, 0xf5)
    FG_GREEN  = Color(0xa6, 0xe3, 0xa1)
    FG_CYAN   = Color(0x89, 0xdc, 0xeb)
    FG_ORANGE = Color(0xf5, 0xa9, 0x7a)
    FG_PINK   = Color(0xf3, 0x8b, 0xa8)
    FG_YELLOW = Color(0xf9, 0xe2, 0xaf)
    FG_BORDER = Color(0x6e, 0x73, 0x8d)
    FG_PURPLE = Color(0xc6, 0xa0, 0xf6)

    FONT_BODY = Font("Monospaced", Font.PLAIN,  12)
    FONT_BOLD = Font("Monospaced", Font.BOLD,   12)
    FONT_SM   = Font("Monospaced", Font.PLAIN,  11)
    FONT_SMB  = Font("Monospaced", Font.BOLD,   11)
    FONT_IT   = Font("Monospaced", Font.ITALIC, 11)

    def __init__(self, callbacks, helpers, controller, editable):
        self._callbacks  = callbacks
        self._helpers    = helpers
        self._controller = controller
        self._editable   = editable
        self._msg        = None
        self._is_req     = True
        self._build_ui()

    def _build_ui(self):
        self._panel = JPanel(BorderLayout(0, 0))
        self._panel.setBackground(self.BG_DARK)

        # ---- TOOLBAR ----
        bar = JPanel(FlowLayout(FlowLayout.LEFT, 8, 4))
        bar.setBackground(self.BG_BAR)

        title = JLabel("  MasterCode Translator  |  auto-detect -> EN")
        title.setForeground(self.FG_CYAN)
        title.setFont(self.FONT_BOLD)
        bar.add(title)

        bar.add(self._sep())

        self._auto_cb = JCheckBox("Auto-translate", True)
        self._auto_cb.setForeground(self.FG_GREEN)
        self._auto_cb.setBackground(self.BG_BAR)
        self._auto_cb.setFont(self.FONT_SM)
        bar.add(self._auto_cb)

        ext = self

        class DoTranslate(ActionListener):
            def actionPerformed(self, e):
                ext._run_translate()

        class DoClear(ActionListener):
            def actionPerformed(self, e):
                n = len(_translate_cache)
                _translate_cache.clear()
                ext._set_status("Cache cleared ({} entries)".format(n), ext.FG_ORANGE)
                ext._cache_lbl.setText("  cache: 0")

        btn_tr = self._btn("Translate",   self.FG_CYAN,   DoTranslate())
        btn_cl = self._btn("Clear Cache", self.FG_ORANGE, DoClear())
        bar.add(btn_tr)
        bar.add(btn_cl)

        self._lang_lbl  = self._badge("  lang: --",  self.FG_YELLOW)
        self._fmt_lbl   = self._badge("  fmt: --",   self.FG_PURPLE)
        self._cache_lbl = self._badge("  cache: 0",  self.FG_BORDER)
        bar.add(self._lang_lbl)
        bar.add(self._fmt_lbl)
        bar.add(self._cache_lbl)

        # ---- TEXT AREAS ----
        self._orig_area  = self._textarea(self.BG_MID,  self.FG_MAIN)
        self._trans_area = self._textarea(self.BG_DARK, self.FG_GREEN)

        orig_pane  = self._scroll(self._orig_area,  "Original",         self.FG_BORDER)
        trans_pane = self._scroll(self._trans_area, "Translated (EN)",  self.FG_CYAN)

        split = JSplitPane(JSplitPane.HORIZONTAL_SPLIT, orig_pane, trans_pane)
        split.setResizeWeight(0.45)
        split.setDividerSize(4)
        split.setBackground(self.BG_DARK)

        # ---- STATUS BAR ----
        self._status = JLabel("  Ready -- select any request or response")
        self._status.setForeground(self.FG_ORANGE)
        self._status.setFont(self.FONT_IT)
        self._status.setBackground(self.BG_BAR)
        self._status.setOpaque(True)

        self._panel.add(bar,           BorderLayout.NORTH)
        self._panel.add(split,         BorderLayout.CENTER)
        self._panel.add(self._status,  BorderLayout.SOUTH)

    # ---- widget helpers ----
    def _sep(self):
        lbl = JLabel("  |  ")
        lbl.setForeground(self.FG_BORDER)
        return lbl

    def _badge(self, txt, color):
        lbl = JLabel(txt)
        lbl.setForeground(color)
        lbl.setFont(self.FONT_SM)
        return lbl

    def _btn(self, label, bg, listener):
        b = JButton(label)
        b.setBackground(bg)
        b.setForeground(self.BG_BAR)
        b.setFont(self.FONT_SMB)
        b.setFocusPainted(False)
        b.addActionListener(listener)
        return b

    def _textarea(self, bg, fg):
        ta = JTextArea()
        ta.setEditable(False)
        ta.setBackground(bg)
        ta.setForeground(fg)
        ta.setFont(self.FONT_BODY)
        ta.setLineWrap(True)
        ta.setWrapStyleWord(True)
        ta.setCaretColor(fg)
        return ta

    def _scroll(self, comp, title, border_col):
        sp = JScrollPane(comp)
        sp.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createLineBorder(border_col, 1), title))
        return sp

    def _set_status(self, msg, color=None):
        c = color or self.FG_ORANGE
        def _u():
            self._status.setText("  " + str(msg))
            self._status.setForeground(c)
        SwingUtilities.invokeLater(_u)

    def _set_badges(self, fmt, lang, ms):
        def _u():
            self._lang_lbl.setText(
                "  lang: {}".format((lang or "?").upper()))
            self._fmt_lbl.setText("  fmt: {}".format(fmt))
            self._cache_lbl.setText("  cache: {}".format(len(_translate_cache)))
        SwingUtilities.invokeLater(_u)

    # ---- IMessageEditorTab ----
    def getTabCaption(self):
        return TAB_CAPTION

    def getUiComponent(self):
        return self._panel

    def isEnabled(self, content, isRequest):
        return content is not None and len(content) > 0

    def setMessage(self, content, isRequest):
        self._msg    = content
        self._is_req = isRequest
        if not content or len(content) == 0:
            self._orig_area.setText("")
            self._trans_area.setText("<no content>")
            self._set_status("No content")
            return
        if self._auto_cb.isSelected():
            self._run_translate()
        else:
            try:
                info = (self._helpers.analyzeRequest(content)
                        if isRequest else
                        self._helpers.analyzeResponse(content))
                raw = self._helpers.bytesToString(content[info.getBodyOffset():])
                self._orig_area.setText(raw)
                self._trans_area.setText("(auto-translate OFF  --  press Translate)")
                self._set_status("Auto-translate OFF", self.FG_YELLOW)
            except Exception as ex:
                self._orig_area.setText(str(ex))

    def getMessage(self):
        return self._msg

    def isModified(self):
        return False

    def getSelectedData(self):
        sel = self._trans_area.getSelectedText()
        return self._helpers.stringToBytes(sel) if sel else None

    # ---- worker thread ----
    def _run_translate(self):
        msg     = self._msg
        is_req  = self._is_req
        helpers = self._helpers
        ext     = self
        self._set_status("Detecting language and translating...", self.FG_YELLOW)

        class Worker(threading.Thread):
            def run(self):
                t0 = time.time()
                try:
                    info = (helpers.analyzeRequest(msg)
                            if is_req else
                            helpers.analyzeResponse(msg))
                    body_raw = msg[info.getBodyOffset():]

                    orig, translated, fmt, lang, method = process_body(
                        body_raw, helpers)

                    ms = int((time.time() - t0) * 1000)
                    is_err = (not lang or
                              lang.startswith("err") or
                              lang.startswith("http") or
                              lang.startswith("network") or
                              lang.startswith("parse"))
                    tag    = "[WARN]" if is_err else "[OK]"
                    status = "{} {} | lang:{} | {}ms | cache:{}".format(
                        tag, fmt, (lang or "?").upper(), ms,
                        len(_translate_cache))

                    try:
                        first_line = str(info.getHeaders()[0])
                    except Exception:
                        first_line = ""

                    def upd():
                        disp = (first_line + "\n\n" + orig) if first_line else orig
                        ext._orig_area.setText(disp)
                        ext._trans_area.setText(translated)
                        ext._set_badges(fmt, lang, ms)
                        ext._set_status(
                            status,
                            ext.FG_YELLOW if is_err else ext.FG_GREEN)

                    SwingUtilities.invokeLater(upd)

                except Exception as ex:
                    err = str(ex)
                    def show_err():
                        ext._trans_area.setText("ERROR:\n" + err)
                        ext._set_status("Failed: " + err, ext.FG_PINK)
                    SwingUtilities.invokeLater(show_err)

        Worker().start()
