// =========================================================
// CLOUD STORAGE — script.js
// =========================================================

const API = "http://localhost:8000";

// =========================================================
// AUTH TOKEN HELPERS
// =========================================================

function getToken()         { return localStorage.getItem("token"); }
function setToken(t)        { localStorage.setItem("token", t); }
function clearToken()       { localStorage.removeItem("token"); localStorage.removeItem("userName"); }
function setUserName(n)     { localStorage.setItem("userName", n); }
function getUserName()      { return localStorage.getItem("userName") || "User"; }

function authHeaders() {
    return {
        "Authorization": "Bearer " + getToken()
    };
}

function authJsonHeaders() {
    return {
        "Authorization": "Bearer " + getToken(),
        "Content-Type": "application/json"
    };
}

// =========================================================
// STATE
// =========================================================

let currentFolder = "";
let currentItems  = [];
let currentView   = "myDrive";

// =========================================================
// PAGE LOAD
// =========================================================

window.addEventListener("DOMContentLoaded", () => {
    // Handle Google OAuth callback — token passed in URL params
    const params = new URLSearchParams(window.location.search);
    const token  = params.get("token");
    const name   = params.get("name");
    const error  = params.get("error");

    if (token) {
        setToken(token);
        if (name) setUserName(decodeURIComponent(name));
        // Clean URL so token doesn't stay visible
        window.history.replaceState({}, document.title, window.location.pathname);
        showApp();
        return;
    }

    if (error) {
        showAuth();
        const msg = document.getElementById("loginMsg");
        if (msg) showMsg(msg, "Google login failed. Please try again.", "error");
        window.history.replaceState({}, document.title, window.location.pathname);
        return;
    }

    if (getToken()) {
        showApp();
    } else {
        showAuth();
    }
});

// =========================================================
// SHOW AUTH / APP
// =========================================================

function showAuth() {
    document.getElementById("authScreen").style.display = "flex";
    document.getElementById("appScreen").style.display  = "none";
    document.getElementById("statsBar").style.display   = "none";
}

function showApp() {
    document.getElementById("authScreen").style.display = "none";
    document.getElementById("appScreen").style.display  = "flex";
    document.getElementById("statsBar").style.display   = "flex";
    document.getElementById("sidebarUserName").textContent = getUserName();
    switchView("myDrive");
    loadStats();
    loadTrashCount();
}

// =========================================================
// AUTH TABS
// =========================================================

function showTab(tab) {
    document.getElementById("loginForm").style.display    = tab === "login"    ? "block" : "none";
    document.getElementById("registerForm").style.display = tab === "register" ? "block" : "none";
    document.querySelectorAll(".auth-tab").forEach((b, i) => {
        b.classList.toggle("active", (i === 0 && tab === "login") || (i === 1 && tab === "register"));
    });
}

// =========================================================
// REGISTER
// =========================================================

async function doRegister() {
    const name     = document.getElementById("regName").value.trim();
    const email    = document.getElementById("regEmail").value.trim();
    const password = document.getElementById("regPassword").value;
    const msg      = document.getElementById("registerMsg");

    if (!name || !email || !password) {
        showMsg(msg, "Please fill in all fields.", "error"); return;
    }
    if (password.length < 6) {
        showMsg(msg, "Password must be at least 6 characters.", "error"); return;
    }

    try {
        const res  = await fetch(`${API}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, password })
        });
        const data = await res.json();
        if (!res.ok) { showMsg(msg, data.detail || "Registration failed.", "error"); return; }
        showMsg(msg, "Account created! Please log in.", "success");
        showTab("login");
    } catch (e) {
        showMsg(msg, "Cannot connect to server.", "error");
    }
}

// =========================================================
// LOGIN
// =========================================================

async function doLogin() {
    const email    = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;
    const msg      = document.getElementById("loginMsg");

    if (!email || !password) {
        showMsg(msg, "Please enter email and password.", "error"); return;
    }

    try {
        const res  = await fetch(`${API}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) { showMsg(msg, data.detail || "Login failed.", "error"); return; }
        setToken(data.access_token);

        // fetch user name
        try {
            const me = await fetch(`${API}/auth/me`, { headers: authHeaders() });
            if (me.ok) { const u = await me.json(); setUserName(u.name); }
        } catch (_) {}

        showApp();
    } catch (e) {
        showMsg(msg, "Cannot connect to server.", "error");
    }
}

// =========================================================
// LOGOUT
// =========================================================

function doLogout() {
    clearToken();
    showAuth();
}

// =========================================================
// GOOGLE LOGIN
// =========================================================

function doGoogleLogin() {
    window.location.href = `${API}/auth/google/login`;
}

// =========================================================
// SWITCH VIEW
// =========================================================

function switchView(view) {
    currentView = view;
    ["myDrive", "starred", "shared", "trash"].forEach(v => {
        document.getElementById(`view-${v}`).style.display  = v === view ? "block" : "none";
        document.getElementById(`nav-${v}`).classList.toggle("active", v === view);
    });

    if (view === "myDrive")  { currentFolder = ""; loadCurrentFolder(); }
    if (view === "starred")  loadStarred();
    if (view === "shared")   loadShared();
    if (view === "trash")    loadTrash();
}

// =========================================================
// LOAD STATS
// =========================================================

async function loadStats() {
    try {
        const res  = await fetch(`${API}/stats`, { headers: authHeaders() });
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById("statFiles").textContent   = data.files;
        document.getElementById("statFolders").textContent = data.folders;
        document.getElementById("statStorage").textContent = data.storage;
        document.getElementById("sidebarStorage").textContent = data.storage;

        const pct = Math.min((data.storage_bytes / (100 * 1024 * 1024)) * 100, 100).toFixed(1);
        document.getElementById("sidebarProgress").style.width = pct + "%";
    } catch (_) {}
}

// =========================================================
// LOAD TRASH COUNT (badge)
// =========================================================

async function loadTrashCount() {
    try {
        const res = await fetch(`${API}/trash`, { headers: authHeaders() });
        if (!res.ok) return;
        const data = await res.json();
        const badge = document.getElementById("trashBadge");
        badge.textContent = data.length || "";
    } catch (_) {}
}

// =========================================================
// REFRESH ALL
// =========================================================

function refreshAll() {
    loadCurrentFolder();
    loadStats();
    loadTrashCount();
}

// =========================================================
// LOAD CURRENT FOLDER
// =========================================================

async function loadCurrentFolder() {
    const list = document.getElementById("fileList");
    list.innerHTML = "<li style='padding:12px;color:#64748b'>Loading…</li>";

    try {
        const url = currentFolder === ""
            ? `${API}/files`
            : `${API}/folders/${encodeURIPath(currentFolder)}`;

        const res  = await fetch(url, { headers: authHeaders() });
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || "Failed to load");

        currentItems = data.items || [];
        renderFiles(currentItems);
        updateBreadcrumb();
    } catch (e) {
        list.innerHTML = `<li style='padding:12px;color:#ef4444'>❌ ${esc(e.message)}</li>`;
    }
}

// =========================================================
// RENDER FILES
// =========================================================

function renderFiles(items) {
    const list = document.getElementById("fileList");
    list.innerHTML = "";

    if (items.length === 0) {
        list.innerHTML = "<li style='padding:12px;color:#94a3b8'>No files or folders here.</li>";
        return;
    }

    items.forEach(item => {
        const fullPath = currentFolder === "" ? item.name : currentFolder + "/" + item.name;
        const li = document.createElement("li");
        li.className = "file-item";

        if (item.type === "folder") {
            li.innerHTML = `
                <span class="file-name">📁 ${esc(item.name)}</span>
                <span class="file-actions">
                    <button onclick="openFolder('${ej(item.name)}')">Open</button>
                    <button onclick="starItem('${ej(fullPath)}','folder','${ej(item.name)}')">⭐</button>
                    <button onclick="renameItem('${ej(fullPath)}','${ej(item.name)}')">✏️</button>
                    <button onclick="moveItem('${ej(fullPath)}')">📂</button>
                    <button onclick="openSharingPanel('${ej(fullPath)}')">🔗</button>
                    <button onclick="createPublicLink('${ej(fullPath)}')">🌐</button>
                    <button onclick="moveToTrash('${ej(fullPath)}')">🗑️</button>
                </span>`;
        } else {
            const sz   = fmtSize(item.size);
            const ext  = (item.extension || "").replace(".", "").toUpperCase() || "FILE";
            li.innerHTML = `
                <span class="file-name">
                    ${fileIcon(item.extension)} ${esc(item.name)}
                    <small class="file-info">${ext} · ${sz}</small>
                </span>
                <span class="file-actions">
                    <button onclick="previewFile('${ej(item.name)}')">👁️</button>
                    <button onclick="downloadFile('${ej(item.name)}')">⬇️</button>
                    <button onclick="starItem('${ej(fullPath)}','file','${ej(item.name)}')">⭐</button>
                    <button onclick="renameItem('${ej(fullPath)}','${ej(item.name)}')">✏️</button>
                    <button onclick="moveItem('${ej(fullPath)}')">📂</button>
                    <button onclick="openSharingPanel('${ej(fullPath)}')">🔗</button>
                    <button onclick="createPublicLink('${ej(fullPath)}')">🌐</button>
                    <button onclick="moveToTrash('${ej(fullPath)}')">🗑️</button>
                </span>`;
        }
        list.appendChild(li);
    });
}

// =========================================================
// FILE ICON
// =========================================================

function fileIcon(ext) {
    const map = {
        ".pdf": "📄", ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️",
        ".gif": "🖼️", ".webp": "🖼️", ".mp4": "🎬", ".mp3": "🎵",
        ".zip": "🗜️", ".doc": "📝", ".docx": "📝",
        ".xls": "📊", ".xlsx": "📊", ".txt": "📃"
    };
    return map[ext] || "📄";
}

// =========================================================
// NAVIGATION
// =========================================================

function openFolder(name) {
    currentFolder = currentFolder === "" ? name : currentFolder + "/" + name;
    clearSearch();
    loadCurrentFolder();
}

function goBack() {
    if (!currentFolder) return;
    const parts = currentFolder.split("/");
    parts.pop();
    currentFolder = parts.join("/");
    clearSearch();
    loadCurrentFolder();
}

function goHome() {
    currentFolder = "";
    clearSearch();
    loadCurrentFolder();
}

function goToFolder(path) {
    currentFolder = path;
    clearSearch();
    loadCurrentFolder();
}

function updateBreadcrumb() {
    const el = document.getElementById("breadcrumb");
    if (!currentFolder) { el.innerHTML = "🏠 My Drive"; return; }

    const parts = currentFolder.split("/");
    let html = `<span class="breadcrumb-link" onclick="goHome()">🏠 My Drive</span>`;
    let path = "";
    parts.forEach((p, i) => {
        path += (i === 0 ? p : "/" + p);
        html += " › ";
        html += i === parts.length - 1
            ? `<strong>${esc(p)}</strong>`
            : `<span class="breadcrumb-link" onclick="goToFolder('${ej(path)}')">${esc(p)}</span>`;
    });
    el.innerHTML = html;
}

// =========================================================
// UPLOAD — drag & drop + file input
// =========================================================

function handleDrop(e) {
    e.preventDefault();
    document.getElementById("dropZone").classList.remove("drag-over");
    const files = e.dataTransfer.files;
    if (files.length) uploadSelectedFiles(files);
}

async function uploadSelectedFiles(files) {
    if (!files || !files.length) return;
    const prog  = document.getElementById("uploadProgress");
    const bar   = document.getElementById("uploadBar");
    const label = document.getElementById("uploadLabel");
    const msg   = document.getElementById("actionMsg");

    prog.style.display = "flex";
    let done = 0;

    for (const file of files) {
        label.textContent = `Uploading ${file.name}…`;
        const form = new FormData();
        form.append("file", file);

        const url = currentFolder === ""
            ? `${API}/upload`
            : `${API}/upload/${encodeURIPath(currentFolder)}`;

        try {
            const res  = await fetch(url, { method: "POST", headers: authHeaders(), body: form });
            const data = await res.json();
            if (!res.ok) { msg.textContent = `❌ ${data.detail || "Upload failed"}`; }
        } catch (_) { msg.textContent = "❌ Cannot connect to server."; }

        done++;
        bar.style.width = Math.round((done / files.length) * 100) + "%";
    }

    label.textContent = `✅ ${done} file(s) uploaded.`;
    setTimeout(() => { prog.style.display = "none"; bar.style.width = "0%"; }, 2000);
    document.getElementById("fileInput").value = "";
    loadCurrentFolder();
    loadStats();
}

// =========================================================
// CREATE FOLDER
// =========================================================

async function createFolder() {
    const input = document.getElementById("folderName");
    const msg   = document.getElementById("actionMsg");
    const name  = input.value.trim();
    if (!name) { msg.textContent = "⚠️ Enter a folder name."; return; }

    const path = currentFolder === "" ? name : currentFolder + "/" + name;
    try {
        const res  = await fetch(`${API}/folders/${encodeURIPath(path)}`, { method: "POST", headers: authHeaders() });
        const data = await res.json();
        if (!res.ok) { msg.textContent = "❌ " + (data.detail || "Failed"); return; }
        msg.textContent = "✅ Folder created.";
        input.value = "";
        loadCurrentFolder();
    } catch (_) { msg.textContent = "❌ Cannot connect to server."; }
}

// =========================================================
// PREVIEW
// =========================================================

const PREVIEW_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif",  ".webp": "image/webp", ".pdf": "application/pdf",
    ".txt": "text/plain", ".mp4": "video/mp4",   ".mp3": "audio/mpeg",
    ".webm": "video/webm", ".wav": "audio/wav"
};

async function previewFile(name) {
    const ext = name.substring(name.lastIndexOf(".")).toLowerCase();
    const mime = PREVIEW_MIME[ext] || "application/octet-stream";

    const url = currentFolder === ""
        ? `${API}/preview/${encodeURIPath(name)}`
        : `${API}/folders/${encodeURIPath(currentFolder)}/preview/${encodeURIPath(name)}`;
    try {
        const res = await fetch(url, { headers: authHeaders() });
        if (!res.ok) { alert("❌ Preview failed: " + (await res.json()).detail); return; }
        const blob = new Blob([await res.arrayBuffer()], { type: mime });
        const blobUrl = URL.createObjectURL(blob);
        window.open(blobUrl, "_blank");
    } catch (_) { alert("Cannot connect to server."); }
}

// =========================================================
// DOWNLOAD
// =========================================================

async function downloadFile(name) {
    const url = currentFolder === ""
        ? `${API}/download/${encodeURIPath(name)}`
        : `${API}/folders/${encodeURIPath(currentFolder)}/download/${encodeURIPath(name)}`;
    try {
        const res = await fetch(url, { headers: authHeaders() });
        if (!res.ok) { alert("❌ Download failed: " + (await res.json()).detail); return; }
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = name;
        a.click();
    } catch (_) { alert("Cannot connect to server."); }
}

// =========================================================
// RENAME
// =========================================================

function renameItem(path, currentName) {
    showModal({
        title: "✏️ Rename",
        fields: [{ id: "renameInput", type: "text", placeholder: "New name", value: currentName }],
        confirmText: "Rename",
        onConfirm: async (vals) => {
            const newName = vals.renameInput.trim();
            if (!newName) { alert("Name cannot be empty."); return false; }

            const form = new URLSearchParams();
            form.append("new_name", newName);

            const res  = await fetch(`${API}/rename/${encodeURIPath(path)}`, {
                method: "PUT",
                headers: { ...authHeaders(), "Content-Type": "application/x-www-form-urlencoded" },
                body: form
            });
            const data = await res.json();
            if (!res.ok) { alert("❌ " + (data.detail || "Rename failed")); return false; }
            loadCurrentFolder();
            return true;
        }
    });
}

// =========================================================
// MOVE
// =========================================================

function moveItem(path) {
    showModal({
        title: "📂 Move Item",
        fields: [{ id: "moveDest", type: "text", placeholder: "Destination folder path (e.g. photos/2024)" }],
        confirmText: "Move",
        onConfirm: async (vals) => {
            const dest = vals.moveDest.trim();
            if (!dest) { alert("Enter destination path."); return false; }

            const form = new URLSearchParams();
            form.append("item_name", path);
            form.append("destination", dest);

            const res  = await fetch(`${API}/move`, {
                method: "POST",
                headers: { ...authHeaders(), "Content-Type": "application/x-www-form-urlencoded" },
                body: form
            });
            const data = await res.json();
            if (!res.ok) { alert("❌ " + (data.detail || "Move failed")); return false; }
            loadCurrentFolder();
            return true;
        }
    });
}

// =========================================================
// SEARCH
// =========================================================

function searchFiles() {
    const input = document.getElementById("searchInput");
    const msgEl = document.getElementById("searchMessage");
    const q     = input.value.trim().toLowerCase();

    if (!q) { msgEl.textContent = ""; renderFiles(currentItems); return; }

    const results = currentItems.filter(i => i.name.toLowerCase().includes(q));
    renderFiles(results);
    msgEl.textContent = results.length === 0 ? `No results for "${input.value}"` : `${results.length} result(s)`;
}

function clearSearch() {
    const inp = document.getElementById("searchInput");
    const msg = document.getElementById("searchMessage");
    if (inp) inp.value = "";
    if (msg) msg.textContent = "";
}

// =========================================================
// SORT
// =========================================================

function sortFiles() {
    const by = document.getElementById("sortSelect").value;
    const sorted = [...currentItems].sort((a, b) => {
        if (by === "type") {
            if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
            return a.name.localeCompare(b.name);
        }
        if (by === "size") return (a.size || 0) - (b.size || 0);
        return a.name.localeCompare(b.name);
    });
    renderFiles(sorted);
}

// =========================================================
// STARRED
// =========================================================

async function starItem(path, type, name) {
    const form = new URLSearchParams();
    form.append("item_path", path);
    form.append("item_type", type);
    form.append("item_name", name);

    try {
        const res  = await fetch(`${API}/starred`, {
            method: "POST",
            headers: { ...authHeaders(), "Content-Type": "application/x-www-form-urlencoded" },
            body: form
        });
        const data = await res.json();
        if (!res.ok && res.status !== 400) { alert(data.detail || "Could not star item"); return; }
        showToast("⭐ Added to Starred");
    } catch (_) { alert("Cannot connect to server."); }
}

async function loadStarred() {
    const list = document.getElementById("starredList");
    list.innerHTML = "<li style='padding:12px;color:#64748b'>Loading…</li>";

    try {
        const res  = await fetch(`${API}/starred`, { headers: authHeaders() });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail);

        list.innerHTML = "";
        if (data.length === 0) {
            list.innerHTML = "<li style='padding:12px;color:#94a3b8'>No starred items.</li>";
            return;
        }

        data.forEach(item => {
            const li = document.createElement("li");
            li.className = "file-item starred-item";
            li.innerHTML = `
                <span class="file-name">
                    ${item.item_type === "folder" ? "📁" : "📄"} ${esc(item.item_name)}
                    <small class="file-info">${esc(item.item_path)}</small>
                </span>
                <span class="file-actions">
                    <button class="btn-secondary" onclick="unstarItem('${ej(item.item_path)}')">★ Unstar</button>
                </span>`;
            list.appendChild(li);
        });
    } catch (e) {
        list.innerHTML = `<li style='padding:12px;color:#ef4444'>❌ ${esc(e.message)}</li>`;
    }
}

async function unstarItem(path) {
    try {
        const res  = await fetch(`${API}/starred?item_path=${encodeURIComponent(path)}`, {
            method: "DELETE", headers: authHeaders()
        });
        const data = await res.json();
        if (!res.ok) { alert(data.detail || "Could not unstar"); return; }
        showToast("Removed from Starred");
        loadStarred();
    } catch (_) { alert("Cannot connect to server."); }
}

// =========================================================
// SHARED VIEW
// =========================================================

async function loadShared() {
    const list = document.getElementById("sharedList");
    list.innerHTML = "<li style='padding:12px;color:#64748b'>Loading…</li>";

    try {
        const res  = await fetch(`${API}/shares`, { headers: authHeaders() });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail);

        list.innerHTML = "";
        if (data.length === 0) {
            list.innerHTML = "<li style='padding:12px;color:#94a3b8'>You haven't shared anything yet.</li>";
            return;
        }

        data.forEach(s => {
            const li = document.createElement("li");
            li.className = "file-item";
            li.innerHTML = `
                <span class="file-name">📄 ${esc(s.item_path)}</span>
                <span class="file-actions">
                    <small>Shared with <strong>${esc(s.shared_with)}</strong> · ${esc(s.permission)}</small>
                    <button class="btn-danger" onclick="removeShare('${ej(s.item_path)}','${ej(s.shared_with)}')">Remove</button>
                </span>`;
            list.appendChild(li);
        });
    } catch (e) {
        list.innerHTML = `<li style='padding:12px;color:#ef4444'>❌ ${esc(e.message)}</li>`;
    }
}

// =========================================================
// TRASH VIEW
// =========================================================

async function loadTrash() {
    const list = document.getElementById("trashList");
    list.innerHTML = "<li style='padding:12px;color:#64748b'>Loading…</li>";

    try {
        const res  = await fetch(`${API}/trash`, { headers: authHeaders() });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail);

        const badge = document.getElementById("trashBadge");
        badge.textContent = data.length || "";

        list.innerHTML = "";
        if (data.length === 0) {
            list.innerHTML = "<li style='padding:12px;color:#94a3b8'>Trash is empty.</li>";
            return;
        }

        data.forEach(item => {
            const li = document.createElement("li");
            li.className = "file-item";
            li.innerHTML = `
                <span class="file-name">
                    ${item.type === "folder" ? "📁" : "📄"} ${esc(item.name)}
                    <small class="file-info">${esc(item.path)}</small>
                </span>
                <span class="file-actions">
                    <button style="background:#16a34a" onclick="restoreItem('${ej(item.path)}')">♻️ Restore</button>
                    <button class="btn-danger" onclick="permDelete('${ej(item.path)}')">🗑 Delete</button>
                </span>`;
            list.appendChild(li);
        });
    } catch (e) {
        list.innerHTML = `<li style='padding:12px;color:#ef4444'>❌ ${esc(e.message)}</li>`;
    }
}

async function moveToTrash(path) {
    if (!confirm(`Move "${path}" to Trash?`)) return;

    const form = new URLSearchParams();
    form.append("item_path", path);

    try {
        const res  = await fetch(`${API}/trash`, {
            method: "POST",
            headers: { ...authHeaders(), "Content-Type": "application/x-www-form-urlencoded" },
            body: form
        });
        const data = await res.json();
        if (!res.ok) { alert(data.detail || "Failed"); return; }
        loadCurrentFolder();
        loadStats();
        loadTrashCount();
    } catch (_) { alert("Cannot connect to server."); }
}

async function restoreItem(path) {
    const form = new URLSearchParams();
    form.append("item_path", path);

    try {
        const res  = await fetch(`${API}/trash/restore`, {
            method: "POST",
            headers: { ...authHeaders(), "Content-Type": "application/x-www-form-urlencoded" },
            body: form
        });
        const data = await res.json();
        if (!res.ok) { alert(data.detail || "Failed"); return; }
        showToast("✅ Restored");
        loadTrash();
        loadStats();
        loadTrashCount();
    } catch (_) { alert("Cannot connect to server."); }
}

async function permDelete(path) {
    if (!confirm("Permanently delete? This cannot be undone.")) return;

    try {
        const res  = await fetch(`${API}/trash?item_path=${encodeURIComponent(path)}`, {
            method: "DELETE", headers: authHeaders()
        });
        const data = await res.json();
        if (!res.ok) { alert(data.detail || "Failed"); return; }
        loadTrash();
        loadTrashCount();
    } catch (_) { alert("Cannot connect to server."); }
}

async function emptyTrash() {
    if (!confirm("Empty ALL trash? This cannot be undone.")) return;

    try {
        const res  = await fetch(`${API}/trash/empty`, { method: "DELETE", headers: authHeaders() });
        const data = await res.json();
        if (!res.ok) { alert(data.detail || "Failed"); return; }
        showToast("✅ Trash emptied");
        loadTrash();
        loadStats();
        loadTrashCount();
    } catch (_) { alert("Cannot connect to server."); }
}

// =========================================================
// SHARING PANEL
// =========================================================

function openSharingPanel(path) {
    const panel   = document.getElementById("sharingPanel");
    const content = document.getElementById("sharingContent");
    panel.style.display = "flex";
    panel.style.flexDirection = "column";

    content.innerHTML = `
        <p style="margin-bottom:12px;font-size:13px;color:#64748b;">
            <strong>${esc(path)}</strong>
        </p>
        <div style="display:flex;gap:8px;margin-bottom:16px;">
            <input id="shareEmailInput" type="text" placeholder="Email / username"
                style="flex:1;padding:9px 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;" />
            <select id="sharePermInput"
                style="padding:9px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;">
                <option value="viewer">Viewer</option>
                <option value="editor">Editor</option>
                <option value="owner">Owner</option>
            </select>
            <button onclick="doShareItem('${ej(path)}')">Share</button>
        </div>
        <div id="shareUsersList"><p style="color:#94a3b8;font-size:13px;">Loading shared users…</p></div>
    `;
    loadShareUsers(path);
}

async function doShareItem(path) {
    const email = document.getElementById("shareEmailInput").value.trim();
    const perm  = document.getElementById("sharePermInput").value;
    if (!email) { alert("Enter an email or username."); return; }

    const form = new URLSearchParams();
    form.append("item_path", path);
    form.append("shared_with", email);
    form.append("permission", perm);

    try {
        const res  = await fetch(`${API}/share`, {
            method: "POST",
            headers: { ...authHeaders(), "Content-Type": "application/x-www-form-urlencoded" },
            body: form
        });
        const data = await res.json();
        if (!res.ok) { alert(data.detail || "Sharing failed"); return; }
        document.getElementById("shareEmailInput").value = "";
        loadShareUsers(path);
    } catch (_) { alert("Cannot connect to server."); }
}

async function loadShareUsers(path) {
    const container = document.getElementById("shareUsersList");
    try {
        const res  = await fetch(`${API}/share/list?item_path=${encodeURIComponent(path)}`, {
            headers: authHeaders()
        });
        const data = await res.json();
        if (!res.ok || data.length === 0) {
            container.innerHTML = "<p style='color:#94a3b8;font-size:13px;'>No users have access yet.</p>";
            return;
        }

        container.innerHTML = data.map(s => `
            <div class="sharing-user-row">
                <div style="flex:1;">
                    <strong style="font-size:13px;">${esc(s.shared_with)}</strong>
                </div>
                <select onchange="changePermission('${ej(path)}','${ej(s.shared_with)}',this.value)"
                    style="padding:4px 8px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px;">
                    <option value="viewer" ${s.permission==="viewer"?"selected":""}>Viewer</option>
                    <option value="editor" ${s.permission==="editor"?"selected":""}>Editor</option>
                    <option value="owner"  ${s.permission==="owner" ?"selected":""}>Owner</option>
                </select>
                <button class="btn-danger btn-sm" onclick="removeShare('${ej(path)}','${ej(s.shared_with)}')">Remove</button>
            </div>`).join("");
    } catch (_) {
        container.innerHTML = "<p style='color:#ef4444;font-size:13px;'>Failed to load.</p>";
    }
}

async function changePermission(path, user, perm) {
    const form = new URLSearchParams();
    form.append("item_path", path);
    form.append("shared_with", user);
    form.append("permission", perm);

    try {
        const res = await fetch(`${API}/share/permission`, {
            method: "PUT",
            headers: { ...authHeaders(), "Content-Type": "application/x-www-form-urlencoded" },
            body: form
        });
        if (!res.ok) { const d = await res.json(); alert(d.detail || "Failed"); }
    } catch (_) { alert("Cannot connect."); }
}

async function removeShare(path, user) {
    if (!confirm(`Remove access for ${user}?`)) return;
    try {
        const res  = await fetch(
            `${API}/share?item_path=${encodeURIComponent(path)}&shared_with=${encodeURIComponent(user)}`,
            { method: "DELETE", headers: authHeaders() }
        );
        const data = await res.json();
        if (!res.ok) { alert(data.detail || "Failed"); return; }
        loadShareUsers(path);
        loadShared();
    } catch (_) { alert("Cannot connect."); }
}

function closeSharingPanel() {
    document.getElementById("sharingPanel").style.display = "none";
}

// =========================================================
// PUBLIC LINKS
// =========================================================

function createPublicLink(path) {
    showModal({
        title: "🌐 Create Public Link",
        fields: [{ id: "expiryDays", type: "number", placeholder: "Expires in days", value: "7" }],
        confirmText: "Create Link",
        onConfirm: async (vals) => {
            const days = parseInt(vals.expiryDays) || 7;
            const form = new URLSearchParams();
            form.append("item_path", path);
            form.append("expires_in_days", days);

            const res  = await fetch(`${API}/public-link`, {
                method: "POST",
                headers: { ...authHeaders(), "Content-Type": "application/x-www-form-urlencoded" },
                body: form
            });
            const data = await res.json();
            if (!res.ok) { alert(data.detail || "Failed"); return false; }

            const link = `${API}${data.link}`;
            showCopyModal(link);
            return true;
        }
    });
}

function showCopyModal(link) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
        <div class="modal-box">
            <h3>🔗 Public Link Ready</h3>
            <input type="text" value="${esc(link)}" readonly
                style="margin:12px 0;font-size:12px;background:#f8fafc;" />
            <div class="modal-footer">
                <button onclick="navigator.clipboard.writeText('${ej(link)}');this.textContent='✅ Copied!'">📋 Copy</button>
                <button class="btn-secondary" onclick="this.closest('.modal-overlay').remove()">Close</button>
            </div>
        </div>`;
    document.body.appendChild(overlay);
}

// =========================================================
// GENERIC MODAL
// =========================================================

function showModal({ title, fields, confirmText, onConfirm }) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";

    const fieldsHTML = fields.map(f => `
        <input id="${f.id}" type="${f.type || 'text'}"
            placeholder="${esc(f.placeholder || '')}"
            value="${esc(f.value || '')}"
            style="margin-bottom:12px;" />`).join("");

    overlay.innerHTML = `
        <div class="modal-box">
            <h3>${title}</h3>
            ${fieldsHTML}
            <div class="modal-footer">
                <button class="btn-secondary" id="modalCancel">Cancel</button>
                <button id="modalConfirm">${confirmText}</button>
            </div>
        </div>`;

    document.body.appendChild(overlay);

    overlay.querySelector("#modalCancel").onclick = () => overlay.remove();
    overlay.querySelector("#modalConfirm").onclick = async () => {
        const vals = {};
        fields.forEach(f => { vals[f.id] = overlay.querySelector(`#${f.id}`).value; });
        const ok = await onConfirm(vals);
        if (ok !== false) overlay.remove();
    };

    // focus first input
    const first = overlay.querySelector("input");
    if (first) { first.focus(); first.select(); }
}

// =========================================================
// TOAST
// =========================================================

function showToast(msg) {
    const t = document.createElement("div");
    t.textContent = msg;
    t.style.cssText = "position:fixed;bottom:70px;right:24px;background:#1e293b;color:white;" +
        "padding:10px 18px;border-radius:8px;font-size:13px;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.15);";
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2500);
}

// =========================================================
// UTILITIES
// =========================================================

function encodeURIPath(path) {
    return path.split("/").map(encodeURIComponent).join("/");
}

function esc(t) {
    return String(t)
        .replace(/&/g,"&amp;").replace(/</g,"&lt;")
        .replace(/>/g,"&gt;").replace(/"/g,"&quot;")
        .replace(/'/g,"&#039;");
}

function ej(t) {
    return String(t)
        .replace(/\\/g,"\\\\").replace(/'/g,"\\'")
        .replace(/"/g,'\\"').replace(/\n/g,"\\n");
}

function fmtSize(b) {
    if (b === undefined || b === null) return "";
    if (b === 0) return "0 B";
    const u = ["B","KB","MB","GB"];
    const i = Math.floor(Math.log(b) / Math.log(1024));
    return parseFloat((b / Math.pow(1024, i)).toFixed(1)) + " " + u[i];
}

function showMsg(el, text, type) {
    el.textContent = text;
    el.className = "auth-msg " + (type || "");
}
