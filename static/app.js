document.addEventListener("DOMContentLoaded", () => {
  const trackList = document.getElementById("trackList");
  const editBtn = document.getElementById("editTracklistBtn");
  const editBar = document.getElementById("editBar");
  const deleteBtn = document.getElementById("deleteSelectedBtn");

    function initTagAutocomplete(inputId, boxId, dataScriptId) {
    const input = document.getElementById(inputId);
    const box = document.getElementById(boxId);
    const dataScript = document.getElementById(dataScriptId);

    if (!input || !box || !dataScript) return;

    let allTags = [];
    try {
      allTags = JSON.parse(dataScript.textContent || "[]");
    } catch (err) {
      console.error("Не вдалося прочитати JSON тегів", err);
      return;
    }

    allTags = Array.from(
      new Set(
        allTags
          .map(t => String(t).trim())
          .filter(Boolean)
      )
    ).sort((a, b) => a.localeCompare(b));

    let activeIndex = -1;
    let currentItems = [];

    function closeSuggest() {
      box.innerHTML = "";
      box.style.display = "none";
      activeIndex = -1;
      currentItems = [];
    }

    function getCurrentTokenParts() {
      const value = input.value;
      const caret = input.selectionStart ?? value.length;

      const beforeCaret = value.slice(0, caret);
      const afterCaret = value.slice(caret);

      const lastComma = beforeCaret.lastIndexOf(",");
      const prefix = lastComma >= 0 ? beforeCaret.slice(0, lastComma + 1) : "";
      const currentRaw = lastComma >= 0 ? beforeCaret.slice(lastComma + 1) : beforeCaret;
      const leadingSpaces = (currentRaw.match(/^\s*/) || [""])[0];
      const query = currentRaw.trim().toLowerCase();

      return {
        prefix,
        afterCaret,
        leadingSpaces,
        query
      };
    }

    function alreadyUsedTags() {
  const caret = input.selectionStart ?? input.value.length;
  const beforeCaret = input.value.slice(0, caret);
  const lastComma = beforeCaret.lastIndexOf(",");
  const currentToken = (lastComma >= 0
    ? beforeCaret.slice(lastComma + 1)
    : beforeCaret).trim().toLowerCase();

  return input.value
    .split(",")
    .map(s => s.trim().toLowerCase())
    .filter(s => s && s !== currentToken);
}

    function applyTag(tagName) {
      const value = input.value;
      const caret = input.selectionStart ?? value.length;

      const beforeCaret = value.slice(0, caret);
      const afterCaret = value.slice(caret);

      const lastComma = beforeCaret.lastIndexOf(",");
      const prefix = lastComma >= 0 ? beforeCaret.slice(0, lastComma + 1) : "";
      const currentRaw = lastComma >= 0 ? beforeCaret.slice(lastComma + 1) : beforeCaret;
      const leadingSpaces = (currentRaw.match(/^\s*/) || [""])[0];

      const cleanedAfter = afterCaret.replace(/^\s*,?\s*/, "");
      const newValue = `${prefix}${leadingSpaces}${tagName}${cleanedAfter}`;

      input.value = newValue;

      const newCaret = (prefix + leadingSpaces + tagName).length;
      input.focus();
      input.setSelectionRange(newCaret, newCaret);

      closeSuggest();
    }

    function renderSuggest() {
      const parts = getCurrentTokenParts();
      const used = alreadyUsedTags();

      if (!parts.query) {
        closeSuggest();
        return;
      }

      const matches = allTags
        .filter(tag => tag.toLowerCase().startsWith(parts.query))
        .filter(tag => !used.includes(tag.toLowerCase()))
        .slice(0, 8);

      if (matches.length === 0) {
        box.innerHTML = '<div class="tagSuggestEmpty">Нічого не знайдено</div>';
        box.style.display = "block";
        activeIndex = -1;
        currentItems = [];
        return;
      }

      currentItems = matches;
      box.innerHTML = "";
      box.style.display = "block";

      matches.forEach((tagName, index) => {
        const item = document.createElement("div");
        item.className = "tagSuggestItem";
        item.textContent = tagName;

        if (index === activeIndex) {
          item.classList.add("active");
        }

        item.addEventListener("mousedown", (e) => {
          e.preventDefault();
          applyTag(tagName);
        });

        box.appendChild(item);
      });
    }

    input.addEventListener("input", () => {
      activeIndex = -1;
      renderSuggest();
    });

    input.addEventListener("keydown", (e) => {
      if (box.style.display !== "block") return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        activeIndex = Math.min(activeIndex + 1, currentItems.length - 1);
        renderSuggest();
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        renderSuggest();
      }

      if (e.key === "Enter") {
        if (activeIndex >= 0 && currentItems[activeIndex]) {
          e.preventDefault();
          applyTag(currentItems[activeIndex]);
        }
      }

      if (e.key === "Escape") {
        closeSuggest();
      }
    });

    input.addEventListener("blur", () => {
      setTimeout(closeSuggest, 120);
    });

    input.addEventListener("focus", () => {
      renderSuggest();
    });
  }

  initTagAutocomplete("mixTagsInput", "mixTagsSuggest", "mixAllTagsData");
  initTagAutocomplete("addMixTagsInput", "addMixTagsSuggest", "addMixAllTagsData");

// ----- теги: режим редагування -----
  const editTagsBtn = document.getElementById("editTagsBtn");
  const cancelTagsBtn = document.getElementById("cancelTagsBtn");
  const tagsViewMode = document.getElementById("tagsViewMode");
  const tagsEditMode = document.getElementById("tagsEditMode");
  const tagsEditBox = document.getElementById("tagsEditBox");
  const tagsHidden = document.getElementById("tagsHidden");
  const tagsForm = document.getElementById("tagsForm");

  let currentTags = [];

  function getTagsFromDisplay() {
    return Array.from(
      document.querySelectorAll("#tagsDisplayBox .tag")
    ).map(el => el.dataset.tag || el.textContent.trim().replace(/\d+$/, "").trim());
  }

  function renderEditTags() {
    // видаляємо всі теги-пігулки (але не інпут)
    tagsEditBox.querySelectorAll(".tagEdit").forEach(el => el.remove());

    const inputWrap = tagsEditBox.querySelector(".tagInputWrap");

    currentTags.forEach(tag => {
      const isArtist = tag.startsWith("artist:");
      const span = document.createElement("span");
      span.className = "tag tagEdit" + (isArtist ? " tag-artist" : "");
      span.dataset.tag = tag;
      span.innerHTML = `${escapeHtml(tag)} <button type="button" class="tagRemoveBtn" data-tag="${escapeAttr(tag)}">×</button>`;
      tagsEditBox.insertBefore(span, inputWrap);
    });

    tagsHidden.value = currentTags.join(", ");
  }

  function enterEditMode() {
    currentTags = Array.from(
      document.querySelectorAll("#tagsDisplayBox .tag")
    ).map(el => (el.dataset.tag || el.textContent.trim().replace(/\s*\d+\s*$/, "").trim()));

    renderEditTags();
    tagsViewMode.style.display = "none";
    tagsEditMode.style.display = "block";
    document.getElementById("mixTagsInput").focus();
  }

  function exitEditMode() {
    tagsViewMode.style.display = "block";
    tagsEditMode.style.display = "none";
    document.getElementById("mixTagsInput").value = "";
  }

  if (editTagsBtn) editTagsBtn.addEventListener("click", enterEditMode);
  if (cancelTagsBtn) cancelTagsBtn.addEventListener("click", exitEditMode);

  // видалення тегу кнопкою ×
  if (tagsEditBox) {
    tagsEditBox.addEventListener("click", (e) => {
      const btn = e.target.closest(".tagRemoveBtn");
      if (!btn) return;
      const tag = btn.dataset.tag;
      currentTags = currentTags.filter(t => t !== tag);
      renderEditTags();
    });
  }

  // додавання тегу через Enter або кому
  const tagInlineInput = document.getElementById("mixTagsInput");
  if (tagInlineInput) {
    tagInlineInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === ",") {
        e.preventDefault();
        const val = tagInlineInput.value.trim().replace(/,$/, "");
        if (val && !currentTags.includes(val)) {
          currentTags.push(val);
          renderEditTags();
        }
        tagInlineInput.value = "";
      }
    });
  }

  // збереження через AJAX
  if (tagsForm) {
    tagsForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      tagsHidden.value = currentTags.join(", ");
      const fd = new FormData(tagsForm);
      console.log("TAGS: відправляємо ->", fd.get("tags"));

      const resp = await fetch(tagsForm.action, { method: "POST", body: fd });
      console.log("TAGS: статус відповіді ->", resp.status);

      if (!resp.ok) {
        alert("Не вдалося зберегти теги");
        return;
      }

      const data = await resp.json();
      console.log("TAGS: отримали від сервера ->", data);

      // оновлюємо блок перегляду
      const displayBox = document.getElementById("tagsDisplayBox");
      console.log("TAGS: displayBox знайдено ->", !!displayBox);
      if (displayBox) {
        displayBox.innerHTML = data.tags
          .map(([name, cnt]) => `<a href="/tag/${encodeURIComponent(name)}"
            class="tag tagDisplay${name.startsWith("artist: ") ? " tag-artist" : ""}"
            style="text-decoration:none;"
            data-tag="${escapeAttr(name)}">
            ${escapeHtml(name)} <span class="tag-count">${cnt}</span>
          </a>`)
          .join("");
        console.log("TAGS: displayBox оновлено");
      }

      exitEditMode();
    });
  }

  if (!trackList || !editBtn) return;

  if (!trackList || !editBtn) return;

  const mixId = trackList.dataset.mixId;

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

        if (time) {
          const yt = (trackList.dataset.youtube || "").trim();
          const sec = timeToSeconds(time);

          if (yt && sec !== null) {
            const join = yt.includes("?") ? "&" : "?";
            const href = `${yt}${join}t=${sec}`;
            html += `<a href="${escapeAttr(href)}" target="_blank"><b>[${escapeHtml(time)}]</b></a> `;
          } else {
            html += `<b>[${escapeHtml(time)}]</b> `;
          }
        }

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
// ----- очистити трекліст -----
  const clearTracklistBtn = document.getElementById("clearTracklistBtn");
  if (clearTracklistBtn) {
    clearTracklistBtn.addEventListener("click", async () => {
      if (!confirm("Ви впевнені? Весь трекліст буде видалено безповоротно.")) return;

      const ids = Array.from(trackList.querySelectorAll("li[data-track-id]"))
        .map(li => li.dataset.trackId)
        .filter(Boolean);

      if (ids.length === 0) {
        alert("Трекліст вже порожній.");
        return;
      }

      try {
        const resp = await fetch(`/mix/${mixId}/delete-tracks`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids })
        });

        if (!resp.ok) {
          alert("Не вдалося очистити трекліст");
          return;
        }

        trackList.querySelectorAll("li[data-track-id]").forEach(li => li.remove());

      } catch (err) {
        console.error(err);
        alert("Помилка очищення");
      }
    });
  }

// ----- пошук треку на сервісах -----
  trackList.addEventListener("click", (e) => {
    const btn = e.target.closest(".trackSearchBtn");
    if (!btn) return;

    const li = btn.closest("li[data-track-id]");
    if (!li) return;

    const searchRow = li.querySelector(".searchRow");
    if (!searchRow) return;

    const isOpen = searchRow.style.display === "block";

    // закриваємо всі інші панелі
    trackList.querySelectorAll(".searchRow").forEach(r => r.style.display = "none");
    trackList.querySelectorAll(".editRow").forEach(r => r.style.display = "none");

    if (isOpen) return;

    // формуємо пошуковий запит з тексту треку
    const trackText = li.querySelector(".trackText");
    let query = "";
    if (trackText) {
      query = trackText.innerText
        .replace(/\[.*?\]/g, "")  // прибираємо таймкод
        .replace(/—/g, "-")       // замінюємо тире на дефіс для сумісності
        .replace(/\s+/g, " ")
        .trim();
    }

    const q = encodeURIComponent(query);
    const links = li.querySelector(".searchLinks");
    if (links) {
      links.innerHTML = [
        { name: "SoundCloud",    url: `https://soundcloud.com/search?q=${q}`,               color: "#ff7733", icon: "soundcloud.svg" },
        { name: "YouTube",       url: `https://www.youtube.com/results?search_query=${q}`,   color: "#ff4444", icon: "youtube.svg" },
        { name: "YouTube Music", url: `https://music.youtube.com/search?q=${q}`,             color: "#ff6666", icon: "youtubemusic.svg" },
        { name: "Spotify",       url: `https://open.spotify.com/search/${q}`,                color: "#1ed760", icon: "spotify.svg" },
        { name: "Bandcamp",      url: `https://bandcamp.com/search?q=${q}`,                  color: "#408294", icon: "bandcamp.svg" },
        { name: "Last.fm",       url: `https://www.last.fm/search/tracks?q=${q}`,            color: "#d51007", icon: "lastfm.svg" },
      ].map(s => `
        <a href="${s.url}" target="_blank" style="
          display:flex; align-items:center; gap:10px;
          padding:7px 10px; border-radius:6px;
          border:1px solid rgba(255,255,255,0.08);
          text-decoration:none; color:${s.color};
          font-size:13px; font-weight:500;
          background:rgba(255,255,255,0.04);">
          <img src="/static/icons/${s.icon}"
               style="width:16px; height:16px; object-fit:contain; flex-shrink:0;"
               alt="${escapeHtml(s.name)}">
          ${escapeHtml(s.name)}
          <span style="margin-left:auto; color:#555; font-size:12px;">↗</span>
        </a>
      `).join("");
    }

    searchRow.style.display = "block";
  });

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

  // ----- редагування назви міксу -----
  const editTitleBtn = document.getElementById("editTitleBtn");
  const cancelTitleBtn = document.getElementById("cancelTitleBtn");
  const saveTitleBtn = document.getElementById("saveTitleBtn");
  const titleEditForm = document.getElementById("titleEditForm");
  const titleInput = document.getElementById("titleInput");
  const mixTitleText = document.getElementById("mixTitleText");
  const titleError = document.getElementById("titleError");

  if (editTitleBtn) {
    editTitleBtn.addEventListener("click", () => {
      titleEditForm.style.display = "block";
      editTitleBtn.style.display = "none";
      titleInput.focus();
      titleInput.select();
    });

    cancelTitleBtn.addEventListener("click", () => {
      titleEditForm.style.display = "none";
      editTitleBtn.style.display = "inline-block";
      titleError.style.display = "none";
      titleInput.value = mixTitleText.textContent;
    });

    saveTitleBtn.addEventListener("click", async () => {
      const newTitle = titleInput.value.trim();
      if (!newTitle) {
        titleError.textContent = "Назва не може бути порожньою";
        titleError.style.display = "block";
        return;
      }

      const mixId = (trackList || document.getElementById("tagsBlock"))
        ?.dataset?.mixId
        || window.location.pathname.split("/")[2];

      const fd = new FormData();
      fd.append("title", newTitle);

      try {
        const resp = await fetch(`/mix/${mixId}/update-title`, {
          method: "POST",
          body: fd
        });
        const data = await resp.json();

        if (!resp.ok) {
          titleError.textContent = data.error || "Помилка збереження";
          titleError.style.display = "block";
          return;
        }

        // оновлюємо назву скрізь на сторінці
        mixTitleText.textContent = data.title;
        document.title = `Мікс: ${data.title}`;

        // оновлюємо посилання в блоці linksBox
        document.querySelectorAll(".linkValue a").forEach(a => {
          a.textContent = data.title;
        });

        titleEditForm.style.display = "none";
        editTitleBtn.style.display = "inline-block";
        titleError.style.display = "none";

      } catch (err) {
        titleError.textContent = "Помилка збереження";
        titleError.style.display = "block";
      }
    });

    // зберігати по Enter
    titleInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") saveTitleBtn.click();
      if (e.key === "Escape") cancelTitleBtn.click();
    });
  }
//---ось тут кінець---
});

function timeToSeconds(t) {
  if (!t) return null;
  const s = String(t).trim();
  if (!s) return null;

  const parts = s.split(":").map(x => x.trim());
  if (parts.length === 2) {
    const mm = parseInt(parts[0], 10);
    const ss = parseInt(parts[1], 10);
    if (Number.isNaN(mm) || Number.isNaN(ss)) return null;
    return mm * 60 + ss;
  }
  if (parts.length === 3) {
    const hh = parseInt(parts[0], 10);
    const mm = parseInt(parts[1], 10);
    const ss = parseInt(parts[2], 10);
    if (Number.isNaN(hh) || Number.isNaN(mm) || Number.isNaN(ss)) return null;
    return hh * 3600 + mm * 60 + ss;
  }
  return null;
}