import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root
  property var manifest: ({})
  property string omarchyPath: ""
  property var shell: null
  property string pluginDir: Quickshell.env("HOME") + "/.config/omarchy/plugins/" + String(manifest.id || "org.dusec.sstp-manager")
  property string lastState: ""
  property string lastProfile: ""
  function poll() { statusProcess.command = ["python3", pluginDir + "/scripts/backend.py", "status"]; statusProcess.running = true }
  Timer { interval: 5000; repeat: true; running: true; triggeredOnStart: true; onTriggered: root.poll() }
  Process {
    id: statusProcess
    command: []
    stdout: StdioCollector { id: output; waitForEnd: true }
    onExited: function(code) {
      if (code !== 0) return
      try {
        var status = JSON.parse(output.text)
        var key = String(status.state || "") + ":" + String(status.profileId || "")
        if (root.lastState !== "" && key !== root.lastState && (status.state === "connected" || status.state === "disconnected" || status.state === "error")) {
          var title = status.state === "connected" ? "SSTP connected" : status.state === "error" ? "SSTP error" : "SSTP disconnected"
          var body = String(status.message || status.profileName || "VPN state changed").replace(/[<>]/g, "").slice(0, 240)
          Quickshell.execDetached([(root.omarchyPath || "/usr/share/omarchy") + "/bin/omarchy-notification-send", title, body])
        }
        root.lastState = key
      } catch (_) {}
    }
  }
}
