# gamescope-session-tools

Arch-пакет (`PKGBUILD`, `arch=('any')`): evdev-демон кнопок питания/громкости для gamescope, переключатель сессий desktop<->gamescope, заглушки SteamOS.

## Структура
- Скрипты и systemd-unit — в `src/`; `PKGBUILD`/`README.md`/`LICENSE` в корне.
- `PKGBUILD` тянет весь репозиторий как git-source: `source=("$pkgname::git+$url.git")`, `sha256sums=('SKIP')`, `package()` делает `cd "$srcdir/$pkgname"` и ставит из `src/`.

## Пакетирование (важно)
- makepkg НЕ поддерживает локальные source из подкаталога: `get_filepath` ищет `$startdir/<basename>` (`/usr/share/makepkg/util/source.sh`). Поэтому `source=('src/foo')` или `'foo::src/foo'` не работают — файл не находится. Решение: git+https source на весь репозиторий (тогда `src/` законен и sums не нужны).
- `makepkg` запускать НЕ в корне репо: `mkdir /tmp/gst && cp PKGBUILD /tmp/gst/ && cd /tmp/gst && makepkg -f`. Иначе клонирует git-source прямо в дерево (`/gamescope-session-tools/`, в .gitignore).
- Проверка без сборки: `bash -n PKGBUILD`, `makepkg --printsrcinfo`.

## Git
- remote `origin` = git@github.com:Givemegitpls/gamescope-session-tools.git, ветка `main`.
- Агентам запрещены мутирующие git-команды (allowlist: diff/show/log/status/remote -v/branch --show-current и т.п. — только read-only). Коммит/пуш делает пользователь.
