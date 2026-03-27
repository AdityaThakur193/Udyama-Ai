"""Browser-based persistence using IndexedDB for session data."""

from __future__ import annotations

import streamlit as st


# ── Python helpers ────────────────────────────────────────────────────────────

def inject_storage_script() -> None:
    """Inject the IndexedDB script into the page exactly once per Streamlit session.

    FIX 2: Previously the caller injected the raw script string on every render.
    Streamlit re-runs the entire script on every widget interaction, so without
    this guard the JS was re-injected dozens of times per session — resetting
    window.UdyamaDBReady and losing the udyamaDB reference each time.
    """
    if st.session_state.get("_storage_injected"):
        return
    st.markdown(get_indexeddb_script(), unsafe_allow_html=True)
    st.session_state["_storage_injected"] = True


def get_clear_all_js() -> str:
    """Return inline JS snippet to clear all IndexedDB data.

    Usage in app.py:
        if st.button("Clear History"):
            st.components.v1.html(get_clear_all_js(), height=0)
            st.session_state.pop("_storage_injected", None)  # force re-init next render
    """
    return """
    <script>
    (function() {
        if (window.UdyamaStorage && window.UdyamaStorage.isReady()) {
            window.UdyamaStorage.clearAll()
                .then(() => console.log("All Udyama storage cleared."))
                .catch(err => console.error("Clear failed:", err));
        }
    })();
    </script>
    """


# ── JavaScript payload ────────────────────────────────────────────────────────

def get_indexeddb_script() -> str:
    """Return idempotent JavaScript code for IndexedDB management."""
    return """
    <script>
    // FIX 1: Idempotency guard — the entire block is skipped if it has already
    //         run in this browser tab. Without this, Streamlit re-injects this
    //         script on every widget interaction, re-declaring all functions and
    //         resetting window.UdyamaDBReady = false, causing the DB to appear
    //         uninitialised even after a successful open.
    if (!window.UdyamaStorageLoaded) {
    window.UdyamaStorageLoaded = true;

    // FIX 3: Use window.udyamaDB instead of `let udyamaDB`.
    //         A `let` declaration inside a re-injected <script> block is reset
    //         to null every time — the open DB handle was being lost on each
    //         Streamlit re-render, forcing a new indexedDB.open() call every time.
    window.udyamaDB = window.udyamaDB || null;
    // FIX 1 (cont): Guard the ready flag — never reset to false if already true.
    if (window.UdyamaDBReady === undefined) window.UdyamaDBReady = false;

    function initIndexedDB() {
        return new Promise((resolve, reject) => {
            if (window.udyamaDB) { resolve(window.udyamaDB); return; }

            const request = indexedDB.open("UdyamaAI", 1);

            request.onerror = () => reject(request.error);

            request.onsuccess = () => {
                window.udyamaDB = request.result;
                window.UdyamaDBReady = true;
                resolve(window.udyamaDB);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains("sessionData")) {
                    db.createObjectStore("sessionData", { keyPath: "id" });
                }
                if (!db.objectStoreNames.contains("chatHistory")) {
                    const store = db.createObjectStore("chatHistory", { keyPath: "id", autoIncrement: true });
                    store.createIndex("timestamp", "timestamp", { unique: false });
                }
            };
        });
    }

    function saveSessionData(key, data) {
        if (!window.udyamaDB) return Promise.resolve(null);
        return new Promise((resolve, reject) => {
            try {
                const tx = window.udyamaDB.transaction(["sessionData"], "readwrite");
                const req = tx.objectStore("sessionData").put({
                    id: key,
                    data: JSON.stringify(data),
                    timestamp: Date.now()
                });
                req.onerror = () => reject(req.error);
                req.onsuccess = () => resolve(req.result);
            } catch (err) { reject(err); }
        });
    }

    function getSessionData(key) {
        if (!window.udyamaDB) return Promise.resolve(null);
        return new Promise((resolve, reject) => {
            try {
                const req = window.udyamaDB
                    .transaction(["sessionData"], "readonly")
                    .objectStore("sessionData").get(key);
                req.onerror = () => reject(req.error);
                req.onsuccess = () => resolve(req.result ? JSON.parse(req.result.data) : null);
            } catch (err) { reject(err); }
        });
    }

    // FIX 4: Added listSessions() — required to render the session history panel
    //         in the UI. Previously only individual keys could be fetched, not enumerated.
    function listSessions() {
        if (!window.udyamaDB) return Promise.resolve([]);
        return new Promise((resolve, reject) => {
            try {
                const req = window.udyamaDB
                    .transaction(["sessionData"], "readonly")
                    .objectStore("sessionData").getAll();
                req.onerror = () => reject(req.error);
                req.onsuccess = () => resolve(
                    req.result.map(item => ({
                        id: item.id,
                        timestamp: item.timestamp,
                        data: JSON.parse(item.data)
                    })).sort((a, b) => b.timestamp - a.timestamp)
                );
            } catch (err) { reject(err); }
        });
    }

    function deleteSessionData(key) {
        if (!window.udyamaDB) return Promise.resolve();
        return new Promise((resolve, reject) => {
            try {
                const req = window.udyamaDB
                    .transaction(["sessionData"], "readwrite")
                    .objectStore("sessionData").delete(key);
                req.onerror = () => reject(req.error);
                req.onsuccess = () => resolve();
            } catch (err) { reject(err); }
        });
    }

    function addChatMessage(message) {
        if (!window.udyamaDB) return Promise.resolve(null);
        return new Promise((resolve, reject) => {
            try {
                const req = window.udyamaDB
                    .transaction(["chatHistory"], "readwrite")
                    .objectStore("chatHistory").add({
                        question: message.question,
                        answer: message.answer,
                        timestamp: Date.now()
                    });
                req.onerror = () => reject(req.error);
                req.onsuccess = () => resolve(req.result);
            } catch (err) { reject(err); }
        });
    }

    function getChatHistory() {
        if (!window.udyamaDB) return Promise.resolve([]);
        return new Promise((resolve, reject) => {
            try {
                const req = window.udyamaDB
                    .transaction(["chatHistory"], "readonly")
                    .objectStore("chatHistory").getAll();
                req.onerror = () => reject(req.error);
                req.onsuccess = () => resolve(
                    req.result.map(i => ({ question: i.question, answer: i.answer }))
                );
            } catch (err) { reject(err); }
        });
    }

    function clearChatHistory() {
        if (!window.udyamaDB) return Promise.resolve();
        return new Promise((resolve, reject) => {
            try {
                const req = window.udyamaDB
                    .transaction(["chatHistory"], "readwrite")
                    .objectStore("chatHistory").clear();
                req.onerror = () => reject(req.error);
                req.onsuccess = () => resolve();
            } catch (err) { reject(err); }
        });
    }

    // FIX 5: Added clearAll() — wipes both stores atomically.
    //         Required for the "Clear History" button in the UI.
    function clearAll() {
        return Promise.all([
            clearChatHistory(),
            new Promise((resolve, reject) => {
                try {
                    const req = window.udyamaDB
                        .transaction(["sessionData"], "readwrite")
                        .objectStore("sessionData").clear();
                    req.onerror = () => reject(req.error);
                    req.onsuccess = () => resolve();
                } catch (err) { reject(err); }
            })
        ]);
    }

    // Initialise DB once — safe to call even if DOM is already ready.
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            initIndexedDB().catch(err => console.warn("IndexedDB unavailable:", err));
        });
    } else {
        initIndexedDB().catch(err => console.warn("IndexedDB unavailable:", err));
    }

    window.UdyamaStorage = {
        init: initIndexedDB,
        saveSession: saveSessionData,
        getSession: getSessionData,
        listSessions: listSessions,
        deleteSession: deleteSessionData,
        addChatMsg: addChatMessage,
        getChatHist: getChatHistory,
        clearChatHist: clearChatHistory,
        clearAll: clearAll,
        isReady: () => window.UdyamaDBReady
    };

    } // end idempotency guard
    </script>
    """
