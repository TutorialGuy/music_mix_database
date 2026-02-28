console.log("app.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  const trackList = document.getElementById("trackList");
  const editBtn = document.getElementById("editTracklistBtn");
  const editBar = document.getElementById("editBar");
  const deleteBtn = document.getElementById("deleteSelectedBtn");

  console.log("DEBUG: trackList =", trackList);
  console.log("DEBUG: editBtn   =", editBtn);
  console.log("DEBUG: editBar   =", editBar);
  console.log("DEBUG: deleteBtn =", deleteBtn);

  if (!trackList || !editBtn) return;

  const mixId = trackList.dataset.mixId;
  console.log("DEBUG: mixId =", mixId, "dataset =", trackList.dataset);

  // ----- helpers -----
  function isEditing() {
    return trackList.dataset.editing === "1";
  }

  function setEditingMode(on) {
    trackList.dataset.editing = on ? "1" : "0";


    // показуємо/ховаємо панель
    if (editBar) editBar.style.display = on ? "flex" : "none";
    if (deleteBtn) deleteBtn.style.display = on ? "inline-block" : "none";
    editBtn.textContent = on ? "Завершити редагування" : "Редагувати трекліст";

    // показуємо/ховаємо елементи в рядках
    trackList.querySelectorAll(".dragHandle").forEach(el => {
      el.style.display = on ? "inline" : "none";
    });

    trackList.querySelectorAll(".selectBox").forEach(el => {
      el.style.display = on ? "inline-block" : "none";
      if (!on) el.checked = false;
    });

    trackList.querySelectorAll(".toggleInlineEdit").forEach(el => {
      el.style.display = on ? "inline-block" : "none";
    });

    // при виході з режиму — ховаємо всі editRow
    if (!on) {
      trackList.querySelectorAll(".editRow").forEach(el => {
        el.style.display = "none";
      });
    }

    console.log("DEBUG: setEditingMode(", on, ") -> dataset.editing =", trackList.dataset.editing);
  }

let dragSrcLi = null;

const dropIndicator = document.createElement("div");
dropIndicator.className = "dropIndicator";

function liFromEventTarget(target) {
  return target.closest("li[data-track-id]");
}

function persistOrder() {
  const ids = Array.from(trackList.querySelectorAll("li[data-track-id]"))
    .map(li => li.dataset.trackId);

  fetch(`/mix/${mixId}/reorder-tracks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids })
  })
  .then(resp => {
    if (!resp.ok) console.error("reorder save failed, status =", resp.status);
  })
  .catch(err => console.error("reorder save failed", err));
}

trackList.addEventListener("dragstart", (e) => {
  if (!isEditing()) return;
  if (!e.target.classList.contains("dragHandle")) return;

  const li = liFromEventTarget(e.target);
  if (!li) return;

  dragSrcLi = li;
  li.classList.add("dragging");

  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", li.dataset.trackId || "");
});

trackList.addEventListener("dragover", (e) => {
  if (!isEditing()) return;
  if (!dragSrcLi) return;

  e.preventDefault();

  const targetLi = liFromEventTarget(e.target);
  if (!targetLi || targetLi === dragSrcLi) return;

  const rect = targetLi.getBoundingClientRect();
  const before = (e.clientY - rect.top) < rect.height / 2;

  // ставимо індикатор ДО або ПІСЛЯ targetLi
  if (before) {
    trackList.insertBefore(dropIndicator, targetLi);
  } else {
    trackList.insertBefore(dropIndicator, targetLi.nextSibling);
  }
});

trackList.addEventListener("drop", (e) => {
  if (!isEditing()) return;
  if (!dragSrcLi) return;
  e.preventDefault();

  // якщо індикатор стоїть у списку — вставляємо туди
  if (dropIndicator.parentNode === trackList) {
    trackList.insertBefore(dragSrcLi, dropIndicator);
    dropIndicator.remove();
    persistOrder();
  }

  dragSrcLi.classList.remove("dragging");
  dragSrcLi = null;
});

trackList.addEventListener("dragend", () => {
  if (dragSrcLi) dragSrcLi.classList.remove("dragging");
  dragSrcLi = null;
  if (dropIndicator.parentNode) dropIndicator.remove();
});

  // ----- init -----
  setEditingMode(false);

  // ----- toggle edit mode -----
  editBtn.addEventListener("click", () => {
    const before = isEditing();
    const next = !before;
    console.log("DEBUG: editBtn CLICK, before =", before ? 1 : 0, "next =", next ? 1 : 0);
    setEditingMode(next);
  });

  // ----- open/close inline editor -----
  trackList.addEventListener("click", (e) => {
    const btn = e.target.closest(".toggleInlineEdit");
    if (!btn) return;

    const li = btn.closest("li[data-track-id]");
    if (!li) return;

    const editRow = li.querySelector(".editRow");
    if (!editRow) return;

    const opened = editRow.style.display === "block";
    trackList.querySelectorAll(".editRow").forEach(r => r.style.display = "none");
    editRow.style.display = opened ? "none" : "block";
  });

  // ----- inline save (fetch) -----
  trackList.addEventListener("submit", async (e) => {
    const form = e.target.closest("form.inlineEditForm");
    if (!form) return;

    e.preventDefault();

    const url = form.dataset.url;
    if (!url) {
      alert("Помилка: data-url порожній у form.inlineEditForm");
      return;
    }

    const fd = new FormData(form);
    const title = (fd.get("title") || "").toString().trim();
    if (!title) {
      alert("Помилка: назва треку обов'язкова");
      return;
    }

    try {
      const resp = await fetch(url, { method: "POST", body: fd });
      if (!resp.ok) {
        alert("Не вдалося зберегти трек");
        return;
      }

      // Оновлюємо текст у viewRow
      const li = form.closest("li[data-track-id]");
      if (!li) return;

      const time = (fd.get("time") || "").toString().trim();
      const artist = (fd.get("artist") || "").toString().trim();
      const sc = (fd.get("soundcloud") || "").toString().trim();

      const textBox = li.querySelector(".trackText");
      if (textBox) {
        let html = "";
        if (time) html += `<b>[${escapeHtml(time)}]</b> `;
        if (artist) html += `<b>${escapeHtml(artist)} — ${escapeHtml(title)}</b>`;
        else html += `<b>${escapeHtml(title)}</b>`;
        if (sc) html += ` ( <a href="${escapeAttr(sc)}" target="_blank">SoundCloud</a> )`;
        textBox.innerHTML = html;
      }

      // Закриваємо тільки інлайн-форму цього треку
      const editRow = li.querySelector(".editRow");
      if (editRow) editRow.style.display = "none";

    } catch (err) {
      console.error(err);
      alert("Помилка збереження");
    }
  });

  // ----- bulk delete -----
  if (deleteBtn) {
    deleteBtn.addEventListener("click", async () => {
      const ids = Array.from(trackList.querySelectorAll(".selectBox"))
        .filter(cb => cb.checked)
        .map(cb => cb.closest("li[data-track-id]")?.dataset.trackId)
        .filter(Boolean);

      if (ids.length === 0) {
        alert("Спочатку відміть треки галочками.");
        return;
      }

      if (!confirm(`Видалити обрані треки (${ids.length})?`)) return;

      try {
        const resp = await fetch(`/mix/${mixId}/delete-tracks`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids })
        });

        if (!resp.ok) {
          alert("Не вдалося видалити треки");
          return;
        }

        ids.forEach(id => {
          const li = trackList.querySelector(`li[data-track-id="${id}"]`);
          if (li) li.remove();
        });

        // скинути всі галочки
        trackList.querySelectorAll(".selectBox").forEach(cb => cb.checked = false);

      } catch (err) {
        console.error(err);
        alert("Помилка видалення");
      }
    });
  }

  // ----- escape helpers -----
  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
  function escapeAttr(s) {
    return escapeHtml(s);
  }
});