# OpenCode Visual Control

**Open-source prototype (v0.1.0)** — Codex-style **visible** desktop control for Windows 10/11 using OpenCode, an MCP server and a persistent safety overlay.

[Русский](#русский) · [English](#english)

## Русский

Это отдельный проект: агент OpenCode может **действительно двигать системный курсор**, нажимать, прокручивать, перетаскивать, печатать и получать скриншоты. Пользователь всё видит на экране. Реализовано на Python + стандартном MCP; не требуется изменять исходники OpenCode.

### Что работает в прототипе

- **Настоящий курсор Windows:** плавное движение с easing, клики и drag & drop, прокрутка.
- **Постоянная верхняя плашка:** «OpenCode управляет вашим компьютером», PAUSE/RESUME и закрытие.
- **Подсветка кликов:** бирюзовые круги в месте нажатия.
- **Глобальный Esc:** немедленно ставит управление на паузу. Для возобновления **человек нажимает RESUME** на плашке.
- **Screen capture в MCP:** изображения передаются модели как изображения, а не текст base64.
- **Локальная архитектура:** MCP общается с GUI-хостом через `127.0.0.1`; необходим случайный токен. Нет удалённого сервера, скрытого управления или команд shell.
- **Скилл OpenCode:** правила разрешения и проверки действий.

> Статус: **экспериментальный прототип**. Базовая логика проверена юнит-тестами; работа поверх реальной Windows и совместимость с установленной версией OpenCode требуют проверки на ПК пользователя. Это не официальный продукт OpenAI, Codex или OpenCode.

### Требования

- Windows 10/11, обычная **разблокированная интерактивная сессия**, основной монитор.
- Python 3.10+ (`python` доступен в PATH), OpenCode, PowerShell.
- Интернет при установке Python-зависимостей.
- OpenCode 2: установщик по умолчанию. Для OpenCode 1 передать `-Legacy`.

### Быстрая установка

Открой PowerShell в распакованной папке и выполни:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
.\start-host.ps1
```

Появится верхняя плашка. **Сам нажми `RESUME`**, чтобы разрешить управление. После установки **перезапусти OpenCode**. Хост должен оставаться запущенным в отдельном терминале. Если используешь OpenCode 1, вместо второго пункта выполни `.\install.ps1 -Legacy`.

В OpenCode можно написать:

> Проверь `computer_status`, затем покажи рабочий стол и открой Блокнот с помощью MCP computer tools. После каждого действия проверяй скриншот.

Инструменты называются `visual_computer_computer_status`, `visual_computer_computer_screenshot`, `visual_computer_computer_move`, `visual_computer_computer_click`, `visual_computer_computer_drag`, `visual_computer_computer_scroll`, `visual_computer_computer_type`, `visual_computer_computer_hotkey` (в интерфейсе имена могут группироваться по MCP-серверу).

### Публикация на GitHub

В комплекте уже есть `.git` (в ZIP) и PowerShell-скрипт. Установи [GitHub CLI](https://cli.github.com/), затем:

```powershell
gh auth login
.\publish.ps1
```

Скрипт создаст **публичный** репозиторий `opencode-visual-control` в твоём GitHub и загрузит код. Чтобы сделать **приватный**: `.\publish.ps1 -Private`. Имя можно выбрать: `.\publish.ps1 -Name другое-имя`.

### Безопасность и ограничения

- На каждом запуске контроллер **по умолчанию на паузе**. Только локальное нажатие `RESUME` разрешает команды (включая скриншоты). Нажми `Esc`, `PAUSE` или `✕` для остановки.
- Данные экрана остаются на компьютере **до передачи OpenCode/подключённой модели**. Политика хранения и обработки зависит от выбранного провайдера модели. Не открывай чувствительную информацию в поле зрения агента.
- Ввод кириллицы и другого Unicode использует буфер обмена и **заменяет его предыдущие данные**. Сохранить их перед использованием при необходимости.
- Поддерживается **основной монитор**; скриншоты могут масштабироваться (по умолчанию до 1600 px в ширину), поэтому для координат учитывай масштаб. Скриншот и координаты в GUI относятся к физическому размеру основного экрана.
- Не управляет UAC/secure desktop и окнами с более высокими правами; **не запускай от администратора**.
- Действия короткие, не предназначены для дистанционного контроля. Подсветка и внешний вид плашки будут отличаться от официального Codex.
- Установщик сохраняет резервную копию `~/.config/opencode/opencode.json.visual-control.bak`, но записывает форматированный JSON; в текущей версии не читает JSONC с комментариями. Проверь настройки после установки.
- Порт `48721` доступен **только** на loopback `127.0.0.1`, запросы требуют временного токена из `%LOCALAPPDATA%\OpenCodeVisualControl\host.token`.

### Как устроено

```text
OpenCode ──MCP/stdio──> mcp_server.py
                            │
                    HTTP 127.0.0.1 + token
                            │
                        host.py ──> Windows mouse / keyboard / screenshots
                            │
                 ALWAYS-VISIBLE TOP BAR + ESC + click effect
```

`install.ps1` устанавливает сервер и скилл глобально для текущего пользователя. Файлы Python копируются в `%LOCALAPPDATA%\OpenCodeVisualControl`, зависимости ставятся в отдельную виртуальную среду. Не открывай порт во внешнюю сеть.

### Разработка и тесты

```powershell
python -m unittest discover -s tests -v
python -m compileall -q actions.py bridge.py host.py mcp_server.py
```

Юнит-тесты проверяют запрет действий в состоянии паузы, валидацию координат, запрещённое сочетание с Esc, перемещение и безопасное отпускание кнопки мыши при прерывании. Саму Windows GUI-интеграцию нужно тестировать вручную.

## English

Windows-only, Codex-style **visible desktop automation** for OpenCode via a Python MCP server and a user-visible GUI host. It moves the real OS cursor and offers clicks, drags, scrolls, typing, screenshots, an overlay, click indicators, and physical ESC emergency pause.

**Quick start:** install Python 3.10+ and OpenCode, then from Windows PowerShell run `Set-ExecutionPolicy -Scope Process Bypass`, `.\install.ps1`, and `.\start-host.ps1`. Click **RESUME** in the overlay, restart OpenCode, and ask the agent to use the `visual_computer` MCP tools. For older OpenCode 1 installations, use `.\install.ps1 -Legacy`.

**Security:** always starts paused, local loopback with random token, no shell tool; screen images are then sent through the configured LLM provider by OpenCode. Unicode typing replaces your clipboard. Only primary monitor supported. Not Windows-tested in this environment; v0.1.0 is a prototype, not an official Codex integration.

**Publish:** `gh auth login` followed by `.\publish.ps1` creates and pushes the prepared repository under your authenticated GitHub account.

### License

MIT — see [LICENSE](LICENSE).
