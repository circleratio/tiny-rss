"""Windows taskbar integration (AppUserModelID and relaunch command).

Without this, the window is grouped under pythonw.exe and pinning it to the
taskbar creates a shortcut to pythonw.exe itself (Windows resolves it to the
IDLE Start-menu shortcut), so the pin starts IDLE instead of this app.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import tkinter as tk
from ctypes import wintypes

logger = logging.getLogger(__name__)

APP_ID = "circleratio.RSSReader"
DISPLAY_NAME = "RSS Reader"

VT_LPWSTR = 31

# IPropertyStore vtable indices (after IUnknown's 3 methods)
_RELEASE = 2
_SET_VALUE = 6
_COMMIT = 7


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, text: str) -> _GUID:
        h = text.strip("{}").replace("-", "")
        data4 = (ctypes.c_ubyte * 8)(*bytes.fromhex(h[16:]))
        return cls(int(h[0:8], 16), int(h[8:12], 16), int(h[12:16], 16), data4)


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", wintypes.DWORD)]


class _PROPVARIANT(ctypes.Structure):
    # Only the VT_LPWSTR member is used; the padding keeps the 16/24-byte size
    _fields_ = [
        ("vt", wintypes.USHORT),
        ("reserved1", wintypes.WORD),
        ("reserved2", wintypes.WORD),
        ("reserved3", wintypes.WORD),
        ("pwszVal", ctypes.c_wchar_p),
        ("padding", ctypes.c_void_p),
    ]


_IID_IPROPERTYSTORE = _GUID.parse("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")
_FMTID_APPUSERMODEL = "{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"
_PKEY_RELAUNCH_COMMAND = _PROPERTYKEY(_GUID.parse(_FMTID_APPUSERMODEL), 2)
_PKEY_RELAUNCH_ICON = _PROPERTYKEY(_GUID.parse(_FMTID_APPUSERMODEL), 3)
_PKEY_RELAUNCH_NAME = _PROPERTYKEY(_GUID.parse(_FMTID_APPUSERMODEL), 4)
_PKEY_ID = _PROPERTYKEY(_GUID.parse(_FMTID_APPUSERMODEL), 5)


def set_process_app_id(app_id: str = APP_ID) -> None:
    """Give the process its own taskbar identity; call before creating windows."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError):
        logger.warning("AppUserModelID を設定できませんでした", exc_info=True)


def set_window_relaunch(
    root: tk.Tk,
    command: str,
    icon: str,
    app_id: str = APP_ID,
    display_name: str = DISPLAY_NAME,
) -> None:
    """Tell the taskbar what to run when the pinned window is launched."""
    if sys.platform != "win32":
        return
    try:
        root.update_idletasks()  # make sure the top-level HWND exists
        hwnd = int(root.wm_frame(), 16)
        _set_window_properties(
            hwnd,
            [
                (_PKEY_RELAUNCH_COMMAND, command),
                (_PKEY_RELAUNCH_ICON, icon),
                (_PKEY_RELAUNCH_NAME, display_name),
                # The ID is set last so the taskbar sees the relaunch info with it
                (_PKEY_ID, app_id),
            ],
        )
    except (AttributeError, OSError, ValueError, tk.TclError):
        logger.warning("タスクバーの再起動情報を設定できませんでした", exc_info=True)


def _set_window_properties(hwnd: int, values: list[tuple[_PROPERTYKEY, str]]) -> None:
    store = ctypes.c_void_p()
    hr = ctypes.windll.shell32.SHGetPropertyStoreForWindow(
        wintypes.HWND(hwnd), ctypes.byref(_IID_IPROPERTYSTORE), ctypes.byref(store)
    )
    if hr != 0 or not store:
        raise OSError(f"SHGetPropertyStoreForWindow failed: 0x{hr & 0xFFFFFFFF:08X}")

    vtable = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    set_value = ctypes.WINFUNCTYPE(
        ctypes.HRESULT,
        ctypes.c_void_p,
        ctypes.POINTER(_PROPERTYKEY),
        ctypes.POINTER(_PROPVARIANT),
    )(vtable[_SET_VALUE])
    commit = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p)(vtable[_COMMIT])
    release = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(vtable[_RELEASE])
    try:
        for key, text in values:
            value = _PROPVARIANT(vt=VT_LPWSTR, pwszVal=text)
            set_value(store, ctypes.byref(key), ctypes.byref(value))
        commit(store)
    finally:
        release(store)
