# gamescope-session-tools

Arch-пакет (`PKGBUILD`, `arch=('any')`): evdev-демон кнопок питания/громкости для gamescope, переключатель сессий desktop<->gamescope, заглушки SteamOS.

## Структура
- Скрипты и systemd-unit — в `src/`; `PKGBUILD`/`README.md`/`LICENSE` в корне.
- `PKGBUILD` тянет весь репозиторий как git-source: `source=("$pkgname::git+$url.git")`, `sha256sums=('SKIP')`, `package()` делает `cd "$srcdir/$pkgname"` и ставит из `src/`.

## Пакетирование (важно)
- makepkg НЕ поддерживает локальные source из подкаталога: `get_filepath` ищет `$startdir/<basename>` (`/usr/share/makepkg/util/source.sh`). Поэтому `source=('src/foo')` или `'foo::src/foo'` не работают — файл не находится. Решение: git+https source на весь репозиторий (тогда `src/` законен и sums не нужны).
- `makepkg` запускать НЕ в корне репо: `mkdir /tmp/gst && cp PKGBUILD /tmp/gst/ && cd /tmp/gst && makepkg -f`. Иначе клонирует git-source прямо в дерево (`/gamescope-session-tools/`, в .gitignore).
- Проверка без сборки: `bash -n PKGBUILD`, `makepkg --printsrcinfo`. Внимание: `--printsrcinfo` тоже создаёт клон — `$srcdir` = `<startdir>/src`, то есть в корне репо появится `src/gamescope-session-tools/` (свой `.git`). Запускать из `/tmp/gst`, не из репо.
- `.SRCINFO` в `.gitignore` (не трекается) — править его вручную нет смысла, генерировать `makepkg --printsrcinfo > .SRCINFO` в скрэтч-каталоге.

## Демон ввода (gamescope-input-daemon)
- `evdev.list_devices()` по умолчанию `writable=True`: возвращает только узлы с правом И чтения, И записи. `/dev/input/event*` = `root:input 0660`, поэтому процесс в группе `input`, но не root, видит НОЛЬ устройств и работает вслепую. Скан устройств в демоне сделан вручную: `os.open(path, O_RDONLY|O_NONBLOCK)` + имена/phys/uniq из `/proc/bus/input/devices`.
- `evdev.InputDevice(fd)` НЕ обходит это: при передаче fd evdev переоткрывает его с `O_RDWR` (на новых версиях `TypeError: open: path should be string, ...`). Нужно передавать путь — тогда evdev сам откатывается на `O_RDONLY`.
- Suspend/resume инвалидирует fd: беспроводные клавиатуры (`AULA-F75`, `MCHOSE G7`) исчезают из `/dev/input`. Одноразовый «переоткрыть при ошибке чтения» бесполезен — срабатывает раньше, чем устройства вернутся. Поэтому в демоне постоянный watcher: udev-монитор (`python-pyudev`), а без него — опрос `/dev/input` раз в 2 с; сверка по отпечатку (`name`/`phys`/`uniq` со счётчиком), а не по номеру `eventN` (после resume номера меняются).
- Очистка устройства навешена на `add_done_callback` задачи чтения, а НЕ на `finally` корутины: задача, отменённая до первого шага, корутину не запускает, и `finally` не выполняется — fd утекает.
- `_drop_device` обязан убирать узел из `self._devices` синхронно: teardown задачи отрабатывает только на следующем тике цикла, и до этого вернувшееся устройство считалось бы «уже открытым».
- basedpyright 1.40 не разворачивает `evdev.InputDevice[str]` в аннотациях ПОЛЕЙ класса (в аннотациях параметров — разворачивает). Поэтому `_OpenDevice` — обычный `@final` класс с `__init__`, а не dataclass.
- Тесты reconcile: `/usr/bin/python3 tests/test_reconcile.py` (устройства подменяются, реальное железо не нужно; `/dev/null` используется как «живой» узел для проверки `_is_alive` по `st_rdev`/`st_ino`).
- Ручная проверка доступа к устройствам: `sudo tests/manual-check.sh` (не-root без группы `input` покажет 0 — это норма).

## Git
- remote `origin` = git@github.com:Givemegitpls/gamescope-session-tools.git, ветка `main`.
- Агентам запрещены мутирующие git-команды (allowlist: diff/show/log/status/remote -v/branch --show-current и т.п. — только read-only). Коммит/пуш делает пользователь.
