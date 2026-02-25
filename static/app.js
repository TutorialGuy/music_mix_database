console.log("app.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  const trackList = document.getElementById("trackList");
  if (!trackList) return; // це не сторінка mix_detail

  const mixId = trackList.dataset.mixId;

  const editBtn = document.getElementById("editTracklistBtn");
  const editBar = document.getElementById("editBar");
  const deleteBtn = document.getElementById("deleteSelectedBtn");

  // ---------- helpers ----------
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

  function setEditingMode(on) {
    trackList.dataset.editing = on ? "1" : "0";

    // показ/ховання елементів у списку
    trackList.querySelectorAll(".dragHandle").forEach((el) => {
      el.style.display = on ? "inline" : "none";
    });

    trackList.querySelectorAll(".selectBox").forEach((el) => {
      el.style.display = on ? "inline-block" : "none";
      if (!on) el.checked = false;
    });

    trackList.querySelectorAll(".toggleInlineEdit").forEach((el) => {
      el.style.display = on ? "inline-block" : "none";
    });

    // завжди ховаємо всі інлайн-форми при перемиканні режиму
    trackList.querySelectorAll(".editRow").forEach((el) => {
      el.style.display = "none";
    });

    // панель керування
    if (deleteBtn) deleteBtn.style.display = on ? "inline-block" : "none";
    if (editBar) editBar.style.display = on ? "flex" : "none";
    if (editBtn) editBtn.textContent = on ? "Завершити редагування" : "Редагувати трекліст";

    // пам'ятаємо режим редагування
    localStorage.setItem(`mix_edit_mode_${mixId}`, on ? "1" : "0");
  }

  function isEditing() {
    return trackList.dataset.editing === "1";
  }

  // ---------- restore edit mode ----------
  const saved = localStorage.getItem(`mix_edit_mode_${mixId}`);
  if (saved === "1") {
    setEditingMode(true);
  } else {
    setEditingMode(false);
  }

  // ---------- toggle edit mode button ----------
  if (editBtn) {
    editBtn.addEventListener("click", () => {
      setEditingMode(!isEditing());
    });
  }

  // ---------- open/close inline editor ----------
  trackList.addEventListener("click", (e) => {
    const btn = e.target.closest(".toggleInlineEdit");
    if (!btn) return;

    const li = btn.closest("li[data-track-id]");
    if (!li) return;

    const editRow = li.querySelector(".editRow");
    if (!editRow) return;

    const opened = editRow.style.display !== "none";

    // закриваємо всі інші
    trackList.querySelectorAll(".editRow").forEach((r) => {
      r.style.display = "none";
    });

    // відкриваємо/закриваємо цей
    editRow.style.display = opened ? "none" : "block";
  });

  // ---------- inline save (fetch) ----------
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

      const li = form.closest("li[data-track-id]");
      if (!li) return;

      const time = (fd.get("time") || "").toString().trim();
      const artist = (fd.get("artist") || "").toString().trim();
      const sc = (fd.get("soundcloud") || "").toString().trim();

      // оновимо "рядок перегляду" (viewRow)
      const viewRow = li.querySelector(".viewRow");
      if (viewRow) {
        const textBox = viewRow.querySelector("div[style*='flex:1']") || viewRow.querySelector("div");
        if (textBox) {
          let html = "";
          if (time) html += `<b>[${escapeHtml(time)}]</b> `;
          if (artist) html += `<b>${escapeHtml(artist)} — ${escapeHtml(title)}</b>`;
          else html += `<b>${escapeHtml(title)}</b>`;
          if (sc) html += ` ( <a href="${escapeAttr(sc)}" target="_blank">SoundCloud</a> )`;
          textBox.innerHTML = html;
        }
      }

      // не закриваємо панель редагування трекліста
      // але ховаємо форму цього треку
      const editRow = li.querySelector(".editRow");
      if (editRow) editRow.style.display = "none";
    } catch (err) {
      console.error(err);
      alert("Помилка збереження");
    }
  });

  // ---------- bulk delete ----------
  if (deleteBtn) {
    deleteBtn.addEventListener("click", async () => {
      const checkedIds = Array.from(trackList.querySelectorAll(".selectBox"))
        .filter((cb) => cb.checked)
        .map((cb) => cb.closest("li[data-track-id]")?.dataset.trackId)
        .filter((x) => !!x);

      if (checkedIds.length === 0) {
        alert("Спочатку відміть треки галочками.");
        return;
      }

      const ok = confirm(`Видалити обрані треки (${checkedIds.length})?`);
      if (!ok) return;

      try {
        const resp = await fetch(`/mix/${mixId}/delete-tracks`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: checkedIds })
        });

        if (!resp.ok) {
          alert("Не вдалося видалити треки");
          return;
        }

        // прибираємо з DOM
        checkedIds.forEach((id) => {
          const li = trackList.querySelector(`li[data-track-id="${id}"]`);
          if (li) li.remove();
        });

        // скинути всі галочки
        trackList.querySelectorAll(".selectBox").forEach((cb) => {
          cb.checked = false;
        });

        // панель НЕ закриваємо
      } catch (err) {
        console.error(err);
        alert("Помилка видалення");
      }
    });
  }
});