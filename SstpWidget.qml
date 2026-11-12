import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Backend.js" as Backend

Panel {
  id: root
  moduleName: "org.dusec.sstp-manager"
  ipcTarget: "org.dusec.sstp-manager"
  property var manifest: ({})
  property string omarchyPath: ""
  property var shell: null
  property var profiles: []
  property var activeStatus: ({ state: "disconnected", profileId: "", ip: "", since: 0, message: "" })
  property string selectedId: ""
  property bool editing: false
  property bool busy: false
  property bool workerPending: false
  property bool showLog: false
  property bool fullRouteDraft: false
  property string logText: ""
  property string routeText: ""
  property string message: ""
  property string currentOperation: ""
  property var draft: ({ id: "", name: "", server: "", port: 443, username: "", password: "", certWarn: false, saveServerRoute: true, proxy: "", tlsVersion: "default", caCert: "", routeMode: "split", routes: [], pppOptions: ["require-mschap-v2", "refuse-eap", "usepeerdns", "noauth"], debugLogging: false, tlsExt: false })
  readonly property string pluginDir: Quickshell.env("HOME") + "/.config/omarchy/plugins/" + String(manifest.id || "org.dusec.sstp-manager")
  readonly property color dim: Qt.darker(barForeground, 1.6)
  readonly property string dnsText: activeStatus.dns && activeStatus.dns.length > 0 ? " · DNS " + activeStatus.dns.join(", ") : ""
  implicitWidth: barButton.implicitWidth
  implicitHeight: barButton.implicitHeight

  function run(command, args) {
    if (workerPending) return
    workerPending = true
    busy = command !== "status" && command !== "logs" && command !== "list"
    currentOperation = command
    worker.command = ["python3", pluginDir + "/scripts/backend.py", command].concat(args || [])
    worker.running = true
  }
  function refresh() { run("list", []) }
  function editProfile(item) {
    draft = JSON.parse(JSON.stringify(item))
    draft.password = ""
    draft.routes = draft.routes || []
    fullRouteDraft = draft.routeMode === "full"
    routeText = draft.routes.join(", ")
    selectedId = item.id
    editing = true
    message = ""
  }
  function newProfile() {
    draft = ({ id: "", name: "", server: "", port: 443, username: "", password: "", certWarn: false, saveServerRoute: true, proxy: "", tlsVersion: "default", caCert: "", routeMode: "split", routes: [], pppOptions: ["require-mschap-v2", "refuse-eap", "usepeerdns", "noauth"], debugLogging: false, tlsExt: false })
    selectedId = ""
    editing = true
    fullRouteDraft = false
    routeText = ""
  }
  function saveProfile() {
    var id = selectedId || "p" + Date.now().toString(36)
    draft.id = id
    draft.routeMode = fullRouteDraft ? "full" : "split"
    draft.routes = routeText.split(",").map(function(item) { return item.trim() }).filter(function(item) { return item !== "" })
    run("save", [id, JSON.stringify(draft)])
  }
  function connectProfile(id) { selectedId = id; run("connect", [id]) }
  function loadLog() { run("logs", []) }
  function activateOperation(cmd, id) { run(cmd, [id]) }

  Component.onCompleted: refresh()

  Process {
    id: worker
    command: []
    stdout: StdioCollector { id: workerOut; waitForEnd: true }
    stderr: StdioCollector { id: workerErr; waitForEnd: true }
    onExited: function(code) {
      var output = String(workerOut.text || "").trim()
      var errorText = String(workerErr.text || "").trim()
      root.workerPending = false
      root.busy = false
      if (code !== 0) {
        try { var e = JSON.parse(errorText); root.message = e.error || errorText }
        catch (_) { root.message = errorText || "Operation failed" }
      } else if (root.currentOperation === "list") {
        try { root.profiles = JSON.parse(output || "[]") } catch (_) { root.message = "Could not read profiles" }
      } else if (root.currentOperation === "status") {
        try { root.activeStatus = JSON.parse(output) } catch (_) {}
      } else if (root.currentOperation === "logs") root.logText = output
      else {
        root.message = output
        root.editing = false
        root.refresh()
      }
      if (root.currentOperation === "connect" || root.currentOperation === "disconnect") statusTimer.restart()
    }
  }
  Timer { id: statusTimer; interval: 1200; repeat: false; onTriggered: root.run("status", []) }
  Timer { interval: 5000; repeat: true; running: true; onTriggered: root.run("status", []) }
  Timer { interval: 2500; repeat: true; running: root.opened && root.showLog; onTriggered: root.loadLog() }

  BarIconButton {
    id: barButton
    iconComponent: vpnIcon
    active: root.activeStatus.state === "connected"
    activeColor: Commons.Color.accent
    foreground: root.barForeground
    tooltipText: root.activeStatus.state === "connected" ? Backend.safeDisplay(root.activeStatus.profileName || "SSTP", 80) + (root.activeStatus.ip ? " · " + root.activeStatus.ip : "") : "SSTP VPN"
    onPressed: function(buttonCode) { if (buttonCode === Qt.LeftButton) root.toggle() }
  }

  Component {
    id: vpnIcon
    Item {
      Image { anchors.fill: parent; source: root.activeStatus.state === "connected" ? Qt.resolvedUrl("icons/vpn-connected.svg") : Qt.resolvedUrl("icons/vpn-disconnected.svg"); fillMode: Image.PreserveAspectFit }
    }
  }

  KeyboardPanel {
    id: popup
    anchorItem: barButton
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: popup.fittedContentWidth(Style.space(430))
    contentHeight: popup.fittedContentHeight(popup.loadedContentHeight, Style.space(700))
    content: PanelKeyCatcher {
      anchors.fill: parent
      implicitHeight: contentColumn.implicitHeight
      ColumnLayout {
        id: contentColumn
        anchors.fill: parent
        anchors.margins: Style.space(12)
        spacing: Style.space(8)
        Layout.minimumWidth: 0

        RowLayout {
          Layout.fillWidth: true
          Layout.minimumWidth: 0
          Text { text: "SSTP Manager"; textFormat: Text.PlainText; color: root.barForeground; font.pixelSize: 18; font.bold: true; Layout.fillWidth: true }
          Button { text: "+ Add"; onClicked: root.newProfile() }
        }
        Text {
          Layout.fillWidth: true
          Layout.minimumWidth: 0
          textFormat: Text.PlainText
          color: root.activeStatus.state === "connected" ? Commons.Color.accent : root.dim
          text: root.activeStatus.state === "connected" ? "Connected · " + (root.activeStatus.profileName || "") + (root.activeStatus.ip ? " · " + root.activeStatus.ip : "") + root.dnsText + " · " + Backend.elapsedSince(root.activeStatus.since) : root.activeStatus.state === "connecting" ? "Connecting…" : root.activeStatus.state === "error" ? (root.activeStatus.message || "Connection error") : "Disconnected"
          wrapMode: Text.Wrap
        }
        Button {
          Layout.minimumWidth: 0
          visible: root.activeStatus.state === "connected" || root.activeStatus.state === "connecting"
          enabled: !root.busy
          text: "Disconnect active profile"
          onClicked: root.activateOperation("disconnect", String(root.activeStatus.profileId || "active"))
        }
        Text { Layout.fillWidth: true; Layout.minimumWidth: 0; visible: root.message !== ""; textFormat: Text.PlainText; color: Commons.Color.urgent; text: root.message; wrapMode: Text.Wrap }

        ColumnLayout {
          Layout.fillWidth: true
          Layout.minimumWidth: 0
          visible: !root.editing
          Repeater {
            model: root.profiles
            delegate: Rectangle {
              required property var modelData
              Layout.fillWidth: true
              implicitHeight: row.implicitHeight + Style.space(12)
              radius: Style.cornerRadius
              color: Qt.darker(root.barForeground, 1.9)
              RowLayout {
                id: row
                Layout.minimumWidth: 0
                anchors.fill: parent
                anchors.margins: Style.space(6)
                ColumnLayout {
                  Layout.fillWidth: true
                  Layout.minimumWidth: 0
                  Text { Layout.fillWidth: true; Layout.minimumWidth: 0; textFormat: Text.PlainText; text: modelData.name; elide: Text.ElideRight; color: root.barForeground; font.bold: true }
                  Text { Layout.fillWidth: true; Layout.minimumWidth: 0; textFormat: Text.PlainText; text: modelData.server + ":" + modelData.port; elide: Text.ElideRight; color: root.dim; font.pixelSize: 12 }
                }
                Button { text: root.activeStatus.profileId === modelData.id && (root.activeStatus.state === "connected" || root.activeStatus.state === "connecting") ? "Disconnect" : "Connect"; enabled: !root.busy; onClicked: root.activeStatus.profileId === modelData.id && (root.activeStatus.state === "connected" || root.activeStatus.state === "connecting") ? root.activateOperation("disconnect", modelData.id) : root.connectProfile(modelData.id) }
                ToolButton { text: "⋯"; onClicked: root.editProfile(modelData) }
              }
            }
          }
          Text { visible: root.profiles.length === 0; text: "No profiles yet. Add one to get started."; textFormat: Text.PlainText; color: root.dim; padding: 8 }
        }

        ColumnLayout {
          visible: root.editing
          Layout.fillWidth: true
          Layout.minimumWidth: 0
          Layout.maximumWidth: popup.contentWidth
          TextField { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; placeholderText: "Profile name"; text: root.draft.name; onTextChanged: root.draft.name = text }
          TextField { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; placeholderText: "Server hostname or IP"; text: root.draft.server; onTextChanged: root.draft.server = text }
          RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.maximumWidth: popup.contentWidth
            TextField {
              Layout.fillWidth: true
              Layout.minimumWidth: 0
              Layout.maximumWidth: popup.contentWidth
              placeholderText: "Port"
              text: String(root.draft.port || 443)
              validator: IntValidator {
                bottom: 1
                top: 65535
              }
              onTextChanged: if (acceptableInput) root.draft.port = Number(text)
            }
            TextField { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; placeholderText: "Username"; text: root.draft.username; onTextChanged: root.draft.username = text }
          }
          TextField { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; placeholderText: root.selectedId ? "Password (blank keeps saved password)" : "Password"; echoMode: TextInput.Password; text: root.draft.password; onTextChanged: root.draft.password = text }
          TextField { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; placeholderText: "HTTP proxy (optional): http://proxy:8080"; text: root.draft.proxy; onTextChanged: root.draft.proxy = text }
          TextField { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; placeholderText: "CA certificate path (optional)"; text: root.draft.caCert; onTextChanged: root.draft.caCert = text }
          TextField { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; placeholderText: "PPP options, comma-separated"; text: (root.draft.pppOptions || []).join(", "); onTextChanged: root.draft.pppOptions = text.split(",").map(function(item) { return item.trim() }).filter(function(item) { return item !== "" }) }
          CheckBox { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; text: "Ignore certificate warnings"; checked: root.draft.certWarn; onToggled: root.draft.certWarn = checked }
          CheckBox { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; text: "Detailed connection logs"; checked: root.draft.debugLogging === true; onToggled: root.draft.debugLogging = checked }
          CheckBox { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; text: "Send TLS hostname extension (--tls-ext)"; checked: root.draft.tlsExt; onToggled: root.draft.tlsExt = checked }
          CheckBox { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; text: "Preserve a route to the VPN server"; checked: root.draft.saveServerRoute; onToggled: root.draft.saveServerRoute = checked }
          CheckBox { Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.maximumWidth: popup.contentWidth; text: "Route all traffic through VPN"; checked: root.fullRouteDraft; onToggled: root.fullRouteDraft = checked }
          Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            visible: !root.fullRouteDraft
            text: "Only these work networks use SSTP; other traffic keeps its normal route."
            textFormat: Text.PlainText
            color: root.dim
            wrapMode: Text.Wrap
          }
          TextField {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.maximumWidth: popup.contentWidth
            visible: !root.fullRouteDraft
            placeholderText: "Work networks (CIDR, comma-separated)"
            text: root.routeText
            onTextChanged: root.routeText = text
          }
          RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.maximumWidth: popup.contentWidth
            Button { text: "Save"; enabled: !root.busy; onClicked: root.saveProfile() }
            Button { text: "Test connection"; enabled: !root.busy && root.selectedId !== ""; onClicked: root.activateOperation("test", root.selectedId) }
            Button { text: "Cancel"; onClicked: root.editing = false }
          }
          RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.maximumWidth: popup.contentWidth
            visible: root.selectedId !== ""
            Button { text: "Duplicate"; onClicked: root.run("duplicate", [root.selectedId, "p" + Date.now().toString(36)]) }
            Button { text: "Delete"; onClicked: root.run("delete", [root.selectedId]) }
          }
        }

        RowLayout {
          Layout.fillWidth: true
          Layout.minimumWidth: 0
          Button { text: "Refresh"; onClicked: { root.refresh(); statusTimer.restart() } }
          Button { text: "View log"; onClicked: { root.showLog = !root.showLog; if (root.showLog) root.loadLog() } }
          Button {
            text: "Copy profiles folder path"
            onClicked: {
              Quickshell.execDetached(["wl-copy", Quickshell.env("HOME") + "/.config/omarchy/sstp-manager/profiles"])
              root.message = "Profiles folder path copied"
            }
          }
        }
        ScrollView {
          Layout.fillWidth: true
          Layout.minimumWidth: 0
          Layout.preferredHeight: root.showLog ? 130 : 0
          visible: root.showLog
          TextArea { text: root.logText; readOnly: true; wrapMode: TextEdit.Wrap; textFormat: TextEdit.PlainText; color: root.barForeground; selectByMouse: true }
        }
      }
    }
  }
}
