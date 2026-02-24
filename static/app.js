document.addEventListener("DOMContentLoaded", () => {

  const trackList = document.querySelector("#trackList");
const mixId = trackList ? trackList.dataset.mixId : null;

if (!mixId) {
  console.warn("mixId not found in #trackList[data-mix-id]");
  return;
}
  if (!mixId) {
    console.warn("MIX_ID not found");
    return;
  }

  // ============================
  // AJAX редагування треку
  // ============================

  document.querySelectorAll(".inlineEditForm").forEach(form => {

    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const url = form.action || form.dataset.url;
      if (!url) {
        console.error("No form URL");
        return;
      }

      const fd = new FormData(form);

      const response = await fetch(url, {
        method: "POST",
        body: fd,
        headers: { "X-Requested-With": "XMLHttpRequest" }
      });

      if (!response.ok) {
        alert("Не вдалося зберегти трек");
        return;
      }

      const data = await response.json();

      const li = form.closest("li");
      const view = li.querySelector(".trackView");

      let html = "";
      if (data.time) html += `<b>[${escapeHtml(data.time)}]</b> `;
      if (data.artist)
        html += `<b>${escapeHtml(data.artist)} — ${escapeHtml(data.title)}</b>`;
      else
        html += `<b>${escapeHtml(data.title)}</b>`;

      if (data.soundcloud)
        html += ` ( <a href="${escapeAttr(data.soundcloud)}" target="_blank">SoundCloud</a> )`;

      view.innerHTML = html;

    });

  });

});


function escapeHtml(str) {
  return (str || "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;");
}

function escapeAttr(str) {
  return escapeHtml(str).replaceAll('"',"&quot;");
}