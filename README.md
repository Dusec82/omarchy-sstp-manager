# SSTP Manager for Omarchy

A third-party Quickshell plugin for managing `sstp-client` VPN connections from the Omarchy bar. The widget, panel, and service run inside the existing `omarchy-shell`; the plugin does not start another Quickshell process.

## Installation

1. Install dependencies: `sudo pacman -S sstp-client ppp python`.
2. Install and enable the plugin: `omarchy plugin add https://github.com/Dusec82/omarchy-sstp-manager --enable`.
3. From the installed plugin directory, run `sudo ./scripts/install.sh`. This installs the privileged helper, Polkit policy, and PPP route hooks.
4. Restart the shell if needed: `omarchy-restart-shell`. Place the widget with `omarchy bar move org.dusec.sstp-manager --section right`.

Profiles are stored in `~/.config/omarchy/sstp-manager/profiles/` with directory permissions `0700` and file permissions `0600`. The first connect, disconnect, or test may prompt for Polkit authentication. Runtime connection logs are stored in `/run/omarchy-sstp-manager/` and are removed at reboot.

## Usage

Click the SSTP bar icon to add, edit, duplicate, delete, test, connect, or disconnect profiles. The panel shows connection state, the VPN IPv4 address and interface when detected, DNS, uptime, and recent logs.

For split tunneling, leave **Route all traffic through VPN** unchecked and add work networks as CIDR ranges, for example `192.168.1.0/24` and `10.20.0.0/16`. Use `/32` for one IPv4 host. PPP hooks install these routes on the VPN interface and remove them when it disconnects. Other traffic keeps its normal route. **Check routes** reports whether the configured work routes use PPP and whether Internet traffic follows the selected route mode.

Enable **Route all traffic through VPN** only if the VPN server forwards Internet traffic. The profile also supports server-route preservation, TLS hostname extension, certificate warning mode, a CA certificate, an HTTP proxy, detailed connection logs, and a curated set of PPP options. Only port 443 is currently supported by the installed `sstpc` command line; TLS protocol version selection is not exposed.

Use **View log** to show recent SSTP/PPP output and **Clear log** to empty the current runtime log. Logs are temporary and disappear at reboot. For troubleshooting, enable detailed logging in the profile, reconnect, and watch `tail -F /run/omarchy-sstp-manager/$(id -u).log`; disable detailed logging afterwards.

The helper passes PPP `noauth` for client mode. This disables server authentication at the PPP layer; SSTP server identity is still checked with TLS certificates, and profile credentials still authenticate the client. `--cert-warn` weakens certificate verification. Passwords are stored in user-owned profile files with mode `0600`; profile saves send form data to the backend over stdin. While connected, the privileged helper keeps the password in a root-only `/etc/ppp/chap-secrets` entry so `pppd` can authenticate without putting the password in process arguments. The managed entry is removed when PPP goes down or a test connection ends.

## Разработка

Запустите `omarchy plugin validate .` из корня репозитория. QML-код использует API Quickshell и компоненты Omarchy `qs.Ui` и `qs.Commons`. Плагин загружается в существующий `omarchy-shell` и не должен запускать отдельный процесс Quickshell.

## Установка

1. Установите зависимости: `sudo pacman -S sstp-client ppp python`.
2. Установите и включите плагин: `omarchy plugin add https://github.com/Dusec82/omarchy-sstp-manager --enable`.
3. В каталоге установленного плагина выполните `sudo ./scripts/install.sh`. Скрипт устанавливает привилегированный helper, правило Polkit и PPP hooks для маршрутов.
4. При необходимости перезапустите оболочку: `omarchy-restart-shell`. Переместить виджет можно командой `omarchy bar move org.dusec.sstp-manager --section right`.

Профили хранятся в `~/.config/omarchy/sstp-manager/profiles/`: права каталога — `0700`, файлов — `0600`. При первом подключении, отключении или тестировании Polkit может запросить подтверждение администратора. Текущие журналы соединения находятся в `/run/omarchy-sstp-manager/` и удаляются при перезагрузке.

## Использование

Нажмите значок SSTP в панели, чтобы добавлять, изменять, дублировать и удалять профили, тестировать соединение, подключаться и отключаться. Панель показывает состояние соединения, IPv4-адрес и интерфейс VPN (если определены), DNS, время работы и журнал.

Для split tunneling оставьте переключатель **Route all traffic through VPN** выключенным и добавьте рабочие сети в формате CIDR, например `192.168.1.0/24` и `10.20.0.0/16`. Для одного IPv4-хоста используйте `/32`. PPP hooks добавляют маршруты через интерфейс VPN и удаляют их при отключении. Остальной трафик идёт обычным маршрутом. Кнопка **Check routes** показывает, направлены ли рабочие сети через PPP и соответствует ли маршрут в Интернет выбранному режиму.

Включайте **Route all traffic through VPN**, только если VPN-сервер маршрутизирует трафик в Интернет. Профиль также поддерживает сохранение маршрута к серверу, TLS hostname extension, предупреждение о сертификате, CA-сертификат, HTTP proxy, подробные журналы и ограниченный список PPP-параметров. Установленная версия `sstpc` поддерживает только порт 443; выбрать версию TLS через командную строку нельзя.

Нажмите **View log**, чтобы открыть последние сообщения SSTP/PPP, и **Clear log**, чтобы очистить текущий журнал. Журналы временные и удаляются при перезагрузке. Для диагностики включите подробный журнал в профиле, переподключитесь и наблюдайте за файлом командой `tail -F /run/omarchy-sstp-manager/$(id -u).log`; после диагностики отключите подробное логирование.

Для клиентского режима helper передаёт PPP-параметр `noauth`. Это отключает проверку аутентификации сервера на уровне PPP; сертификат SSTP-сервера продолжает проверяться через TLS, а учётные данные профиля по-прежнему используются для аутентификации клиента. Параметр `--cert-warn` ослабляет проверку сертификата. Пароль хранится в пользовательском файле с правами `0600`, а данные формы передаются backend через stdin. Пока соединение активно, привилегированный helper хранит пароль в `/etc/ppp/chap-secrets`, доступном только root, чтобы `pppd` мог выполнить аутентификацию без передачи пароля в аргументах процессов. Управляемая запись удаляется при завершении PPP-соединения или тестового подключения.
