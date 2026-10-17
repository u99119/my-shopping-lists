"""Application object: owns the database, the screens, navigation and the lock flow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from kivy.core.window import Window
from kivy.uix.screenmanager import NoTransition, ScreenManager
from kivymd.app import MDApp

from . import APP_NAME, services
from .core.currency import Rates
from .core.db import connect
from .core.repository import Repository
from .core.seed import seed_catalog
from .core.sharetext import format_list_text
from .core.viewmodel import build_list_view
from .ui.catalogscreen import CatalogScreen
from .ui.homescreen import HomeScreen
from .ui.listscreen import ListScreen
from .ui.lockscreen import LockScreen
from .ui.settingsscreen import LOCK_KEY, SettingsScreen
from .ui.widgets import toast

ESCAPE = 27  # Android back button arrives as the Escape key


class ShoppingListsApp(MDApp):
    title = APP_NAME

    def __init__(self, db_path: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._db_path = db_path
        self.repo: Repository
        self.rates: Rates
        self.manager: ScreenManager

    # ------------------------------------------------------------ lifecycle
    def build(self) -> ScreenManager:
        self.theme_cls.primary_palette = "Teal"
        path = self._db_path or str(Path(self.user_data_dir) / "shopping.db")
        self.repo = Repository(connect(path))
        seed_catalog(self.repo)
        self.rates = Rates(self.repo)

        self.manager = ScreenManager(transition=NoTransition())
        for screen in (HomeScreen(), ListScreen(), CatalogScreen(), SettingsScreen(),
                       LockScreen()):
            self.manager.add_widget(screen)
        self.manager.current = "lock" if self.lock_enabled() else "home"
        Window.bind(on_keyboard=self._on_key)
        return self.manager

    def on_start(self) -> None:
        if self.manager.current == "lock":
            self.ask_unlock()

    def on_pause(self) -> bool:
        return True  # keep the process alive when the app goes to the background

    def on_resume(self) -> None:
        if self.lock_enabled() and self.manager.current != "lock":
            self.manager.current = "lock"
            self.ask_unlock()

    def on_stop(self) -> None:
        self.repo.conn.close()

    # ----------------------------------------------------------------- lock
    def lock_enabled(self) -> bool:
        return self.repo.get_meta(LOCK_KEY) == "1"

    def ask_unlock(self) -> None:
        services.authenticate(self._unlocked)

    def _unlocked(self, ok: bool) -> None:
        if ok:
            self.manager.current = "home"
        else:
            toast("Unlock cancelled")

    # ----------------------------------------------------------- navigation
    def open_screen(self, name: str) -> None:
        self.manager.current = name

    def go_home(self) -> None:
        self.manager.current = "home"

    def open_list(self, list_id: str) -> None:
        screen = self.manager.get_screen("list")
        screen.open_list(list_id)
        self.manager.current = "list"

    def _on_key(self, _window: Any, key: int, *_args: Any) -> bool:
        if key != ESCAPE:
            return False
        current = self.manager.current
        if current == "lock":
            return True  # never let back bypass the lock screen
        if current == "home":
            return False  # let Android close the app
        if current == "catalog":
            self.manager.get_screen("catalog").on_back()
        else:
            self.go_home()
        return True

    # -------------------------------------------------------------- sharing
    def share_list(self, list_id: str, include_closed: bool) -> None:
        view = build_list_view(self.repo, list_id)
        if view is None:
            return
        message = services.share_text(format_list_text(view, include_closed),
                                      view.shopping_list.name)
        if message:
            toast(message)
