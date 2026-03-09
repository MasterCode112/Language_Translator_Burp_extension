# -*- coding: utf-8 -*-
# ============================================================
#  MasterCode Translator - Burp Suite Extension
#  Auto-detects ANY language and translates to English (online)
#  Appears as "Translator" tab on every request/response
#
#  Author  : MasterCode
#  GitHub  : https://github.com/mastercode/MasterCodeTranslator
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
VERSION     = "1.0.0"

# ============================================================
# TRANSLATION ENGINE  (Google Translate, no API key needed)
# ============================================================
_translate_cache = {}

def google_translate(text, src="auto", tgt="en"):
    """
    Free Google Translate endpoint - no API key required.
    src="auto" lets Google detect the language automatically.
    Returns translated string or original on failure.
    """
    if not text or not text.strip():
        return text, "unknown"
    cache_key = (src, tgt, text[:300])
    if cache_key in _translate_cache:
        cached = _translate_cache[cache_key]
        return cached[0], cached[1]
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = urllib.urlencode({
            "client": "gtx",
            "sl": src,
            "tl": tgt,
            "dt": ["t", "ld"],
            "q": text.encode("utf-8"),
        })
        req = urllib2.Request(url + "?" + params)
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urllib2.urlopen(req, timeout=8)
        raw  = resp.read()
        data = json.loads(raw)
        # data[0] = translation chunks, data[2] = detected lang
        translated = u"".join(
            chunk[0] for chunk in data[0] if chunk and chunk[0]
        )
        detected_lang = "unknown"
        try:
            detected_lang = str(data[2]) if len(data) > 2 and data[2] else "unknown"
        except Exception:
            pass
        _translate_cache[cache_key] = (translated, detected_lang)
        return translated, detected_lang
    except Exception as ex:
        return text, "error: " + str(ex)


def translate_json_obj(obj):
    """Recursively translate all string values inside a JSON object."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            tk, _ = google_translate(k)
            out[tk] = translate_json_obj(v)
        return out
    elif isinstance(obj, list):
        return [translate_json_obj(i) for i in obj]
    elif isinstance(obj, (str, unicode)):
        t, _ = google_translate(obj)
        return t
    return obj


def process_body(raw_bytes, helpers):
    """
    Detect body format, translate everything to English.
    Returns (original_str, translated_str, fmt, detected_lang, method).
    """
    if not raw_bytes or len(raw_bytes) == 0:
        return "", "<empty body>", "empty", "n/a", "n/a"

    try:
        raw = helpers.bytesToString(raw_bytes)
    except Exception:
        raw = str(raw_bytes)

    if not raw.strip():
        return raw, "<empty body>", "empty", "n/a", "n/a"

    # ---- JSON ------------------------------------------------
    try:
        parsed      = json.loads(raw)
        translated  = translate_json_obj(parsed)
        pretty_orig = json.dumps(parsed,     indent=2, ensure_ascii=False)
        pretty_tran = json.dumps(translated, indent=2, ensure_ascii=False)
        # detect lang from the raw string
        _, lang     = google_translate(raw[:200])
        return pretty_orig, pretty_tran, "JSON", lang, "google-auto"
    except Exception:
        pass

    # ---- URL-encoded form data --------------------------------
    if re.search(r'^[\w%+.~-]+=', raw.strip()) and ("&" in raw or "=" in raw):
        try:
            orig_lines, tran_lines = [], []
            detected_lang = "unknown"
            for pair in raw.split("&"):
                if "=" in pair:
                    k, _, v = pair.partition("=")
                    k_d = urllib.unquote_plus(k)
                    v_d = urllib.unquote_plus(v)
                    v_t, lang = google_translate(v_d)
                    if lang not in ("unknown", "en", "error"):
                        detected_lang = lang
                    orig_lines.append(u"  {} = {}".format(k_d, v_d))
                    tran_lines.append(u"  {} = {}".format(k_d, v_t))
                else:
                    orig_lines.append(pair)
                    tran_lines.append(pair)
            return (u"\n".join(orig_lines), u"\n".join(tran_lines),
                    "form-urlencoded", detected_lang, "google-auto")
        except Exception:
            pass

    # ---- Plain text / XML / HTML / other ---------------------
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
        print("  Tab label : '{}'".format(TAB_CAPTION))
        print("  Engine    : Google Translate (auto-detect)")
        print("  Target    : any language  ->  English")
        print("=" * 55)

    def createNewInstance(self, controller, editable):
        return TranslatorTab(self._callbacks, self._helpers, controller, editable)


# ============================================================
# MESSAGE EDITOR TAB
# ============================================================
class TranslatorTab(IMessageEditorTab):

    # ---- colour palette (dark theme) ----
    BG_DARK    = Color(0x1e, 0x1e, 0x2e)
    BG_MID     = Color(0x24, 0x27, 0x3a)
    BG_BAR     = Color(0x13, 0x13, 0x20)
    FG_MAIN    = Color(0xca, 0xd3, 0xf5)
    FG_GREEN   = Color(0xa6, 0xe3, 0xa1)
    FG_CYAN    = Color(0x89, 0xdc, 0xeb)
    FG_ORANGE  = Color(0xf5, 0xa9, 0x7a)
    FG_PINK    = Color(0xf3, 0x8b, 0xa8)
    FG_YELLOW  = Color(0xf9, 0xe2, 0xaf)
    FG_BORDER  = Color(0x6e, 0x73, 0x8d)
    FG_PURPLE  = Color(0xc6, 0xa0, 0xf6)

    FONT_BODY  = Font("Monospaced", Font.PLAIN,  12)
    FONT_BOLD  = Font("Monospaced", Font.BOLD,   12)
    FONT_SM    = Font("Monospaced", Font.PLAIN,  11)
    FONT_SMB   = Font("Monospaced", Font.BOLD,   11)
    FONT_IT    = Font("Monospaced", Font.ITALIC, 11)

    def __init__(self, callbacks, helpers, controller, editable):
        self._callbacks  = callbacks
        self._helpers    = helpers
        self._controller = controller
        self._editable   = editable
        self._msg        = None
        self._is_req     = True
        self._build_ui()

    # ----------------------------------------------------------
    # BUILD UI
    # ----------------------------------------------------------
    def _build_ui(self):
        self._panel = JPanel(BorderLayout(0, 0))
        self._panel.setBackground(self.BG_DARK)

        # ---- TOP TOOLBAR ----
        bar = JPanel(FlowLayout(FlowLayout.LEFT, 8, 4))
        bar.setBackground(self.BG_BAR)

        title = JLabel("  MasterCode Translator  |  auto-detect -> EN")
        title.setForeground(self.FG_CYAN)
        title.setFont(self.FONT_BOLD)
        bar.add(title)

        sep = JLabel("  |  ")
        sep.setForeground(self.FG_BORDER)
        bar.add(sep)

        self._auto_cb = JCheckBox("Auto-translate", True)
        self._auto_cb.setForeground(self.FG_GREEN)
        self._auto_cb.setBackground(self.BG_BAR)
        self._auto_cb.setFont(self.FONT_SM)
        bar.add(self._auto_cb)

        ext = self

        class ReTranslate(ActionListener):
            def actionPerformed(self, e):
                ext._run_translate()

        btn_retrans = JButton("Translate")
        btn_retrans.setBackground(self.FG_CYAN)
        btn_retrans.setForeground(self.BG_BAR)
        btn_retrans.setFont(self.FONT_SMB)
        btn_retrans.setFocusPainted(False)
        btn_retrans.addActionListener(ReTranslate())
        bar.add(btn_retrans)

        class ClearCache(ActionListener):
            def actionPerformed(self, e):
                n = len(_translate_cache)
                _translate_cache.clear()
                ext._set_status("Cache cleared  ({} entries removed)".format(n),
                                ext.FG_ORANGE)
        btn_cache = JButton("Clear Cache")
        btn_cache.setBackground(self.FG_ORANGE)
        btn_cache.setForeground(self.BG_BAR)
        btn_cache.setFont(self.FONT_SMB)
        btn_cache.setFocusPainted(False)
        btn_cache.addActionListener(ClearCache())
        bar.add(btn_cache)

        # info badges
        self._lang_lbl = JLabel("  lang: --")
        self._lang_lbl.setForeground(self.FG_YELLOW)
        self._lang_lbl.setFont(self.FONT_SMB)
        bar.add(self._lang_lbl)

        self._fmt_lbl = JLabel("  fmt: --")
        self._fmt_lbl.setForeground(self.FG_PURPLE)
        self._fmt_lbl.setFont(self.FONT_SM)
        bar.add(self._fmt_lbl)

        self._cache_lbl = JLabel("  cache: 0")
        self._cache_lbl.setForeground(self.FG_BORDER)
        self._cache_lbl.setFont(self.FONT_SM)
        bar.add(self._cache_lbl)

        # ---- TEXT AREAS ----
        self._orig_area  = self._textarea(self.BG_MID,  self.FG_MAIN)
        self._trans_area = self._textarea(self.BG_DARK, self.FG_GREEN)

        orig_pane  = self._scroll(self._orig_area,  "Original",          self.FG_BORDER)
        trans_pane = self._scroll(self._trans_area, "Translated  (EN)",  self.FG_CYAN)

        split = JSplitPane(JSplitPane.HORIZONTAL_SPLIT, orig_pane, trans_pane)
        split.setResizeWeight(0.45)
        split.setDividerSize(4)
        split.setBackground(self.BG_DARK)

        # ---- STATUS BAR ----
        self._status = JLabel("  Ready  --  select any request or response")
        self._status.setForeground(self.FG_ORANGE)
        self._status.setFont(self.FONT_IT)
        self._status.setBackground(self.BG_BAR)
        self._status.setOpaque(True)

        self._panel.add(bar,          BorderLayout.NORTH)
        self._panel.add(split,        BorderLayout.CENTER)
        self._panel.add(self._status, BorderLayout.SOUTH)

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
            self._status.setText("  " + msg)
            self._status.setForeground(c)
        SwingUtilities.invokeLater(_u)

    def _set_badges(self, fmt, lang, ms):
        def _u():
            self._lang_lbl.setText(
                "  lang: {}".format(lang.upper() if lang else "?"))
            self._fmt_lbl.setText("  fmt: {}".format(fmt))
            self._cache_lbl.setText("  cache: {}".format(len(_translate_cache)))
        SwingUtilities.invokeLater(_u)

    # ----------------------------------------------------------
    # IMessageEditorTab interface
    # ----------------------------------------------------------
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

    # ----------------------------------------------------------
    # Translation worker
    # ----------------------------------------------------------
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
                    info   = (helpers.analyzeRequest(msg)
                              if is_req else
                              helpers.analyzeResponse(msg))
                    offset    = info.getBodyOffset()
                    body_raw  = msg[offset:]

                    orig, translated, fmt, lang, method = process_body(
                        body_raw, helpers)

                    ms  = int((time.time() - t0) * 1000)
                    ok  = "[OK]" if not lang.startswith("error") else "[WARN]"
                    status = "{} {} | detected: {} | {}ms | cache: {}".format(
                        ok, fmt, lang.upper(), ms, len(_translate_cache))

                    try:
                        first_line = str(info.getHeaders()[0])
                    except Exception:
                        first_line = ""

                    def upd():
                        display_orig = (first_line + "\n\n" + orig
                                        if first_line else orig)
                        ext._orig_area.setText(display_orig)
                        ext._trans_area.setText(translated)
                        ext._set_badges(fmt, lang, ms)
                        color = ext.FG_GREEN if ok == "[OK]" else ext.FG_YELLOW
                        ext._set_status(status, color)

                    SwingUtilities.invokeLater(upd)

                except Exception as ex:
                    err_msg = str(ex)
                    def show_err():
                        ext._trans_area.setText("ERROR:\n" + err_msg)
                        ext._set_status("Translation failed: " + err_msg, ext.FG_PINK)
                    SwingUtilities.invokeLater(show_err)

        Worker().start()
