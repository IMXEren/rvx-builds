"""Inject a custom default search engine into a Chromium profile.

Operates on two artifacts inside ``<profile_dir>/Default/``:

* ``Web Data`` -- SQLite database (``keywords`` table + ``meta`` table).
* ``Preferences`` -- JSON file (``default_search_provider`` +
  ``default_search_provider_data``).

The ``url_hash`` column required by Chromium is computed using the **v1**
format (``id`` + ``url``) and encrypted with the old ``OSCrypt`` AES-128-CBC
key that Chromium falls back to on headless Linux without a keyring.

Usage::

    from src.browser.profile.search_engine import SearchEngineInjector

    injector = SearchEngineInjector("path/to/profile")
    injector.inject(
        keyword="google.com",
        url="https://www.google.com/search?q={searchTerms}",
        short_name="Google",
    )
    injector.close()
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
import uuid
from pathlib import Path
from typing import Self

from Crypto.Cipher import AES

# Chromium OSCrypt fallback: PBKDF2-HMAC-SHA1("peanuts", "saltysalt", 1 iter)
_OSCRYPT_KEY: bytes = hashlib.pbkdf2_hmac(
    "sha1",
    b"peanuts",
    b"saltysalt",
    1,
    dklen=16,
)
_OSCRYPT_IV: bytes = b" " * 16  # fixed IV: 16 spaces


def _compute_url_hash_v1(row_id: int, url: str) -> bytes:
    """Build the 51-byte ``url_hash`` BLOB (v1 format, AES-128-CBC)."""
    url_bytes = url.encode("utf-8")

    # base::Pickle payload: WriteInt64(id) + WriteString(url)
    payload = struct.pack("<q", row_id)
    payload += struct.pack("<i", len(url_bytes))
    payload += url_bytes
    payload += b"\x00" * ((4 - len(url_bytes) % 4) % 4)  # 4-byte alignment

    # Full pickle = 4-byte header (payload_size LE) + payload
    pickle = struct.pack("<I", len(payload)) + payload

    raw = b"\x01" + hashlib.sha256(pickle).digest()  # version 1 + SHA-256

    # PKCS#7 pad to 16 bytes, then AES-128-CBC encrypt, prepend "v10"
    pad_len = 16 - (len(raw) % 16)

    cipher = AES.new(_OSCRYPT_KEY, AES.MODE_CBC, _OSCRYPT_IV)
    return b"v10" + cipher.encrypt(raw + bytes([pad_len] * pad_len))  # type: ignore[no-any-return]


def _next_keyword_id(db: sqlite3.Connection) -> int:
    """Return the next available ``id`` for the ``keywords`` table."""
    row = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM keywords").fetchone()
    return row[0]  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class SearchEngineInjector:
    """Inject a custom search engine and promote it to the default.

    The *profile_dir* must already contain a Chrome-generated ``Default/Web Data``
    SQLite database.  This class does **not** create the file -- Chrome must have
    been launched at least once in the profile.
    """

    def __init__(self, profile_dir: str | Path) -> None:
        profile = Path(profile_dir)
        default = profile / "Default"

        self._db_path = default / "Web Data"
        self._prefs_path = default / "Preferences"

        if not self._db_path.exists():
            msg = (
                f"Web Data not found at {self._db_path}. " "Launch Chrome in this profile at least once to generate it."
            )
            raise RuntimeError(msg)

        self._conn = sqlite3.connect(str(self._db_path), timeout=10)

    def inject(
        self,
        *,
        keyword: str,
        url: str,
        short_name: str = "",
        favicon_url: str = "",
        suggest_url: str = "",
    ) -> int:
        """Insert (or replace) *keyword* and set it as the default.

        Returns the row ``id`` of the inserted engine.
        """
        # --- Remove any existing row with the same keyword ---
        self._conn.execute("DELETE FROM keywords WHERE keyword = ?", (keyword,))

        row_id = _next_keyword_id(self._conn)
        sync_guid = str(uuid.uuid4())
        url_hash = _compute_url_hash_v1(row_id, url)

        self._conn.execute(
            """INSERT INTO keywords
                (id, short_name, keyword, favicon_url, url,
                 safe_for_autoreplace, originating_url,
                 input_encodings, suggest_url,
                 prepopulate_id, sync_guid, is_active,
                 alternate_urls, search_url_post_params,
                 suggest_url_post_params, new_tab_url,
                 url_hash)
             VALUES (?, ?, ?, ?, ?, 0, '',
                     '', ?,
                     0, ?, 1,
                     '[]', '', '', '',
                     ?)""",
            (row_id, short_name, keyword, favicon_url, url, suggest_url, sync_guid, url_hash),
        )

        # --- Promote to default ---
        self._conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('Default Search Provider ID', ?)",
            (str(row_id),),
        )
        self._conn.commit()

        # --- Mirror in Preferences ---
        self._update_preferences(row_id, keyword, url, short_name, favicon_url, suggest_url, sync_guid)

        return row_id

    def _update_preferences(  # noqa: PLR0913
        self,
        row_id: int,
        keyword: str,
        url: str,
        short_name: str,
        favicon_url: str,
        suggest_url: str,
        sync_guid: str,
    ) -> None:
        if not self._prefs_path.exists():
            return

        prefs = json.loads(self._prefs_path.read_text())

        prefs.setdefault("default_search_provider", {})
        prefs["default_search_provider"]["guid"] = sync_guid
        prefs["default_search_provider"]["reset_occurred"] = False

        template = {
            "alternate_urls": [],
            "contextual_search_url": "",
            "created_from_play_api": False,
            "date_created": "0",
            "doodle_url": "",
            "enforced_by_policy": False,
            "favicon_url": favicon_url,
            "featured_by_policy": False,
            "id": str(row_id),
            "image_search_branding_label": "",
            "image_translate_source_language_param_key": "",
            "image_translate_target_language_param_key": "",
            "image_translate_url": "",
            "image_url": "",
            "image_url_post_params": "",
            "input_encodings": [],
            "is_active": 1,
            "keyword": keyword,
            "last_modified": "0",
            "last_visited": "0",
            "logo_url": "",
            "new_tab_url": "",
            "originating_url": "",
            "policy_origin": 0,
            "preconnect_to_search_url": False,
            "prefetch_likely_navigations": False,
            "prepopulate_id": 0,
            "safe_for_autoreplace": False,
            "search_intent_params": [],
            "search_url_post_params": "",
            "send_x_geo_header": False,
            "short_name": short_name,
            "starter_pack_id": 0,
            "suggestions_url": suggest_url,
            "suggestions_url_post_params": "",
            "synced_guid": sync_guid,
            "url": url,
            "usage_count": 0,
        }

        dspd = prefs.setdefault("default_search_provider_data", {})
        dspd["template_url_data"] = template
        dspd["mirrored_template_url_data"] = {**template}

        self._prefs_path.write_text(json.dumps(prefs, indent=2))

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> Self:
        """Enable context manager protocol."""
        return self

    def __exit__(self, *args: object) -> None:
        """Close DB connection on context exit."""
        self.close()


# ============================================================================
# RE DOCUMENTATION -- keep for reference when forking
# ruff: noqa: ERA001
# ============================================================================
#
# The ``url_hash`` BLOB in the ``keywords`` table is Chromium's integrity
# check so that a tampered ``url`` or ``keyword`` is detected on load (hash
# verification is enforced on Windows; skipped on Linux and macOS).
#
# Hash evolution (DB migration milestones):
#
#   v1 (0x01) -- DB version 137
#       pickle = Header + WriteInt64(id) + WriteString(url)
#       hash   = 0x01 + SHA-256(pickle)
#
#   v2 (0x02) -- DB version 152
#       pickle = Header + WriteInt64(id) + WriteString(url)
#              + WriteString16(keyword) + WriteInt(enforced_by_policy)
#              + WriteInt(starter_pack_id)
#       hash   = 0x02 + SHA-256(pickle)
#
# ``base::Pickle`` binary layout (little-endian, 4-byte aligned, zero-padded):
#
#   Header:
#       uint32 payload_size    4 bytes
#
#   WriteInt64(v):
#       int64 v                8 bytes
#
#   WriteString(s):
#       int32 len(s)           4 bytes
#       uint8 s[i]            len(s) bytes
#       uint8 0x00            pad to 4-byte boundary
#
#   WriteString16(s):
#       int32 char_count       4 bytes
#       uint16 s[i]           char_count * 2 bytes (UTF-16LE)
#       uint8 0x00            pad to 4-byte boundary
#
#   WriteBool / WriteInt:
#       int32 (0 or 1)         4 bytes
#
# After hashing, the 33-byte raw hash (1 version + 32 SHA-256) is encrypted
# before storage.  The encryption path depends on the platform:
#
#   Desktop Linux (keyring available)  -> os_crypt_async -> AES-256-GCM  64 B
#   Headless Linux / no keyring        -> old OSCrypt    -> AES-128-CBC  51 B
#   macOS                              -> Keychain       -> AES-128-CBC  51 B
#   Windows                            -> DPAPI          -> AES-256-GCM  64 B
#
# On headless Linux without a keyring daemon, Chromium falls back to the
# old OSCrypt path with a hardcoded key:
#
#   PBKDF2-HMAC-SHA1("peanuts", "saltysalt", iterations=1) -> 16-byte key
#   Fixed IV: 16 spaces (0x20)
#   AES-128-CBC with PKCS#7 padding
#   Prefixed with provider tag "v10" (3 bytes)
#
# This module uses the v1 format because the profile DB version is 0
# (migrations never ran), and v1 only hashes ``id`` + ``url`` -- making it
# resilient to URL modifications (unlike v2 which also hashes keyword,
# enforced_by_policy, and starter_pack_id).
#
# Verified against a fresh Chrome v150 profile -- all 11 prepopulated
# engine rows match the v2 pickle computation exactly.

# ============================================================================
# Windows support (pending)
# ============================================================================
#
# The current implementation only works on **headless Linux** because it
# relies on the hardcoded OSCrypt "peanuts" key and AES-128-CBC.  To
# support Windows the following changes are required:
#
# --------------------------------------------------------------------------
# 1. Encryption layer
# --------------------------------------------------------------------------
#
# Windows uses **DPAPI** (``CryptProtectData``) via ``os_crypt_async`` with
# AES-256-GCM.  The encrypted BLOB is 64 bytes:
#
#     "v10" (3) + nonce (12) + AES-GCM(plaintext, 33) + tag (16) = 64
#
# The DPAPI key is per-user, per-machine -- you cannot pre-compute hashes
# offline.  Options:
#
#   a) Run the injection via a small native helper that calls
#      ``os_crypt_async::Encryptor::EncryptString``, or shell out to a
#      Chromium-based tool.
#
#   b) Use the HackBrowserData cross-host workflow:
#      ``dumpkeys`` on Windows to export the master key, then encrypt
#      locally with that key.
#
#   c) Call ``CryptProtectData`` directly via ``ctypes`` / ``pywin32``.
#      The os_crypt prefix on Windows is still "v10", and the cipher is
#      AES-256-GCM with a 12-byte random nonce prepended to the ciphertext.
#
# --------------------------------------------------------------------------
# 2. Hash format -- upgrade to v2
# --------------------------------------------------------------------------
#
# Windows enforces hash verification.  The hash must use **v2** format
# (five fields) and compute correctly:
#
#   pickle = Header + WriteInt64(id) + WriteString(url)
#          + WriteString16(keyword) + WriteInt(enforced_by_policy)
#          + WriteInt(starter_pack_id)
#   hash   = b"\x02" + SHA-256(pickle)
#
#   stored = Encrypt_via_DPAPI(hash)   # on the Windows machine
#
# The v2 pickle construction is identical to v1 except it appends the
# three extra fields (keyword as UTF-16LE string, enf as int32, spid as
# int32) before hashing.
#
# --------------------------------------------------------------------------
# 3. DB version bump (optional but recommended)
# --------------------------------------------------------------------------
#
# The ``Web Data`` SQLite ``user_version`` should be 152+ for v2 hashes.
# Chromium runs migrations on startup; if the version is 0 it will
# migrate from scratch.  Bumping the version avoids a full migration:
#
#     PRAGMA user_version = 152;
#
# When the version is >= 152, Chromium will NOT trigger the v1->v2 hash
# migration (``MigrateToVersion152ExpandHashColumn``), which would
# otherwise recompute and overwrite your injected hashes.
#
# --------------------------------------------------------------------------
# 4. Summary of required changes
# --------------------------------------------------------------------------
#
#   | Component           | Linux (current)          | Windows (target)        |
#   |---------------------|--------------------------|-------------------------|
#   | Encryption          | peanuts + AES-128-CBC    | DPAPI + AES-256-GCM     |
#   | Hash version        | v1 (0x01)                | v2 (0x02)               |
#   | Hash fields         | id + url                 | id + url + kw + enf + spid |
#   | Blob size           | 51 bytes                 | 64 bytes                |
#   | DB user_version     | 0 (ignored)              | >= 152 (recommended)    |
#   | Hash enforced?      | No                       | Yes (row dropped on fail) |
#
#   To make ``_compute_url_hash`` cross-platform, refactor it into:
#
#       _compute_hash_raw(row_id, url, keyword, enf, spid) -> bytes (33)
#       _encrypt_hash(raw_hash)                            -> bytes (51 or 64)
#
#   Then swap the encryptor based on ``sys.platform``.

# ============================================================================
# Pitfall -- prepopulated engine reconciliation
# ============================================================================
#
# Chromium's ``TemplateURLService`` reconciles prepopulated engines on
# startup.  Any row with ``prepopulate_id > 0`` is compared against the
# built-in engine definition.  If it doesn't match, it is **replaced**
# with the ``No Search`` placeholder (``keyword="nosearch"``,
# ``url="http://{searchTerms}"``).
#
# To prevent this:
#
#   prepopulate_id     = 0    <- "I am user-added, NOT prepopulated"
#   safe_for_autoreplace = 0  <- "Hands off -- do not replace me"
#
# This is separate from ``url_hash`` verification.  The reconciliation
# runs on all platforms; hash verification is Windows-only.

# ============================================================================
# Reconciliation behaviour (tested + confirmed)
# ============================================================================
#
# ``TemplateURLService`` runs two passes on startup when ``Builtin Keyword
# Version`` in the ``meta`` table differs from the built-in data version:
#
# 1. ``RemoveDuplicatePrepopulateIDs()``
#    Rows sharing the same ``prepopulate_id`` are deduplicated -- one is kept,
#    the rest are **deleted** from the database.  Selection priority:
#    DSP keyword match > prepopulated keyword match > lowest id.
#
# 2. ``MergeEnginesFromPrepopulateData()`` via ``MergeIntoEngineData()``
#    Each surviving ``prepopulate_id > 0`` row is merged with the current
#    built-in definition.  ``safe_for_autoreplace=0`` protects ``short_name``
#    and ``keyword`` from being overwritten, but the **URL is always
#    overwritten** with the built-in definition.  Other fields (favicon,
#    suggest URL, etc.) are also replaced.
#
# The only reliable way to prevent Chrome from touching an injected engine:
#
#   prepopulate_id = 0   <- skip reconciliation entirely (treated as user-added)
#
# This also means you should remove any leftover ``prepopulate_id > 0``
# placeholder rows (like ``nosearch`` at id=2) to avoid duplicate-ID
# conflicts if you ever set ``prepopulate_id > 0``.
