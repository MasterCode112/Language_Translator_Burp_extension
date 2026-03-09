# MasterCode Translator

> **Burp Suite extension** that auto-detects any language in HTTP traffic and translates it live to English — directly inside the message editor, styled as a native "Translator" tab.

---

## Preview

```
+-----------------------------------------------------------+
|  MasterCode Translator  |  auto-detect -> EN              |
|  [Auto-translate] [Translate] [Clear Cache]               |
|  lang: FR   fmt: JSON   cache: 12                         |
+------------------------+----------------------------------+
|  Original              |  Translated (EN)                 |
|                        |                                  |
|  {                     |  {                               |
|    "statut": "succes", |    "status": "success",          |
|    "montant": "5000",  |    "amount": "5000",             |
|    "message": "Vire-  |    "message": "Transfer          |
|     ment effectue"     |     completed"                   |
|  }                     |  }                               |
+------------------------+----------------------------------+
|  [OK] JSON | detected: FR | 312ms | cache: 12             |
+-----------------------------------------------------------+
```

---

## Features

| Feature | Detail |
|---|---|
| **Auto language detection** | Google auto-detects the source language — works with French, Arabic, Portuguese, Spanish, Chinese, and 100+ others |
| **Translates to English** | All output is in English regardless of the original language |
| **All body formats** | Handles JSON (recursive), `application/x-www-form-urlencoded`, plain text, XML |
| **Background threading** | Translation runs in a separate thread — Burp never freezes |
| **In-memory cache** | Identical values are only translated once per session |
| **Auto-translate toggle** | Enable/disable auto-translation per click |
| **Manual re-translate** | Button to re-run at any time |
| **Dark theme UI** | Styled to blend with Burp's dark mode |
| **No API key needed** | Uses the free public Google Translate endpoint |

---

## Requirements

| Requirement | Version |
|---|---|
| Burp Suite | Community or Pro, any recent version |
| Jython | **2.7.x standalone JAR** |
| Internet access | Required for translation (no offline mode) |

---

## Installation

### Step 1 — Configure Jython in Burp

1. Download the **Jython 2.7 standalone JAR** from [jython.org](https://www.jython.org/download)
2. In Burp: `Extender` → `Options` → `Python Environment`
3. Set the path to the downloaded `.jar` file

### Step 2 — Load the extension

1. `Extender` → `Extensions` → `Add`
2. Extension type: **Python**
3. Extension file: browse to `MasterCodeTranslator.py`
4. Click **Next** — you should see in the Output tab:

```
=======================================================
  MasterCode Translator v1.0.0  loaded
  Tab label : 'Translator'
  Engine    : Google Translate (auto-detect)
  Target    : any language  ->  English
=======================================================
```

---

## Usage

1. Open **Proxy** → **HTTP history** (or any Repeater / Intruder request)
2. Click any request or response
3. Look for the **"Translator"** tab in the message editor panel
4. The original body appears on the **left**, the English translation on the **right**
5. The status bar shows: detected language, format, response time, cache size

### Toolbar controls

| Control | Action |
|---|---|
| **Auto-translate** checkbox | When checked, translates automatically on every click |
| **Translate** button | Manually trigger translation (useful when auto is OFF) |
| **Clear Cache** button | Wipes the in-memory translation cache |

---

## Supported Body Formats

### JSON
Recursively walks the entire object tree — both keys and values are translated:
```json
// Original
{ "statut": "succes", "message": "Virement effectue", "montant": 5000 }

// Translated
{ "status": "success", "message": "Transfer completed", "amount": 5000 }
```

### URL-encoded form data
Each `key=value` pair is URL-decoded then translated:
```
// Original
AUTHID=<!DEDACT>&MSISDN=<!DEDACT>&TYPE=<!DEDACT>

// Translated
AUTHID = <!DEDACT>
MSISDN = <!DEDACT>
TYPE   = <!DEDACT>
```

### Plain text / XML / HTML
The entire body is passed to Google Translate as-is.

---

## How It Works

```
Request/Response body
        |
        v
  [ Format Detection ]
   JSON / form / text
        |
        v
  [ Google Translate API ]
  src=auto  tgt=en
  (free endpoint, no key)
        |
        v
  [ In-memory cache ]
  skip duplicate values
        |
        v
  [ UI update on EDT ]
  Original | Translated
```

The extension calls:
```
https://translate.googleapis.com/translate_a/single
  ?client=gtx&sl=auto&tl=en&dt=t&q=<text>
```
`sl=auto` tells Google to detect the source language automatically. The detected language code is shown in the status bar.

---

## Tested Against

- Vodafone M-Pesa Tanzania (`com.vodafone.mpesa.tanzania`) — Flutter app
- NdeHatru / Eximbank Comoros (`ndehatru.eximbank-km.com:8443`) — Flutter/Dart app
- Any app with French, Arabic, or Portuguese API responses

---

## Limitations

| Limitation | Notes |
|---|---|
| Requires internet | All translation is online via Google |
| Rate limiting | Google may throttle requests on very high traffic — use the cache to reduce calls |
| Large bodies | Bodies over ~5000 chars are truncated by Google's free endpoint |
| Jython 2.x only | Uses `urllib2` and `unicode` — not compatible with Jython 3 / Python 3 |

---

## File Structure

```
MasterCodeTranslator/
|-- MasterCodeTranslator.py    # Main extension (single file, no dependencies)
|-- README.md                  # This file
|-- screenshots/
|   |-- tab_preview.png
|   |-- json_example.png
|   `-- form_example.png
```

---

## Contributing

Pull requests are welcome. To add support for a new body format:

1. Add a new `# ---- FORMAT ----` block inside `process_body()` 
2. Parse the format into key/value pairs
3. Call `google_translate(value)` on each value
4. Return `(original_str, translated_str, "FORMAT_NAME", lang, "google-auto")`

---

## License

MIT License — free to use, modify, and distribute.

---

## Author

**MasterCode** — Security Researcher  
Specializing in mobile application penetration testing and traffic analysis.

> Built during real-world assessment of Flutter banking applications.
