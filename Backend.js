.pragma library

function safeDisplay(value, maxLength) {
  return String(value === undefined || value === null ? "" : value).replace(/[<>]/g, "").slice(0, maxLength || 256)
}

function profileId() {
  return "p" + Date.now().toString(36) + Math.floor(Math.random() * 0xffffff).toString(36)
}

function elapsedSince(epochSeconds) {
  var seconds = Math.max(0, Math.floor(Date.now() / 1000 - Number(epochSeconds || 0)))
  var hours = Math.floor(seconds / 3600)
  var minutes = Math.floor((seconds % 3600) / 60)
  return hours > 0 ? hours + "h " + minutes + "m" : minutes + "m"
}
