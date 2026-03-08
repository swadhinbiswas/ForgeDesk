/**
 * Forge JS Runtime v2.0
 * High-performance bridge between JS and Rust-Python Core.
 *
 * Supports two transport modes:
 *   1. Native IPC (desktop) — window.ipc.postMessage (Rust/wry)
 *   2. WebSocket  (web)     — ws:// or wss:// to Forge web server
 *
 * Public API:
 *   forge.invoke(cmd, args)   — call a Python command, returns Promise
 *   forge.on(event, cb)       — subscribe to a Python event
 *   forge.off(event, cb?)     — unsubscribe (specific or all)
 *   forge.emit(event, payload) — emit event to Python (WebSocket mode)
 */

(function () {
    "use strict";

    if (window.__forge__) return;

    // ─── Internal state ───
    var listeners      = new Map();
    var pendingInvokes = new Map();
    var invokeId       = 0;
    var protocolVersion = "1.0";
    var ws             = null;  // WebSocket instance (web mode only)
    var wsReady        = false;
    var wsQueue        = [];    // messages queued before WS is open
    var managedWindows = new Map();

    // ─── Transport detection ───
    var hasNativeIPC = !!(window.ipc && typeof window.ipc.postMessage === "function");

    /**
     * Send a raw JSON string to the backend.
     * Picks the correct transport automatically.
     */
    function send(jsonStr) {
        if (hasNativeIPC) {
            window.ipc.postMessage(jsonStr);
        } else if (ws && wsReady) {
            ws.send(jsonStr);
        } else if (ws) {
            // WS exists but not yet open — queue it
            wsQueue.push(jsonStr);
        } else {
            console.error("[Forge] No transport available (no native IPC, no WebSocket)");
        }
    }

    /**
     * Handle an incoming message from the backend (both transports).
     */
    function handleMessage(msg) {
        var data;
        try {
            data = typeof msg === "string" ? JSON.parse(msg) : msg;
        } catch (e) {
            console.error("[Forge] Failed to parse message:", e);
            return;
        }

        if (data.type === "reply" || ("id" in data && ("result" in data || "error" in data))) {
            // IPC response
            var pending = pendingInvokes.get(data.id);
            if (pending) {
                if (data.error) {
                    pending.reject(new Error(data.error));
                } else {
                    pending.resolve(pending.detailed ? data : data.result);
                }
                pendingInvokes.delete(data.id);
            }
        } else if (data.type === "event") {
            // Python → JS event
            var cbs = listeners.get(data.event);
            if (cbs) {
                cbs.forEach(function (cb) {
                    try { cb(data.payload); } catch (e) {
                        console.error("[Forge] Event listener error:", e);
                    }
                });
            }
        } else if (data.type === "dialog") {
            // Dialog action descriptor from Python → handle on JS side
            _handleDialog(data);
        } else if (data.type === "clipboard") {
            // Clipboard action descriptor from Python → handle on JS side
            _handleClipboard(data);
        }
    }

    // ─── Dialog handler (JS-side) ───

    function _handleDialog(data) {
        var action = data.action;
        var result = null;

        if (action === "alert") {
            window.alert(data.message || "");
        } else if (action === "confirm") {
            result = window.confirm(data.message || "");
        } else if (action === "prompt") {
            result = window.prompt(data.message || "", data.default_value || "");
        } else if (action === "open_file") {
            // Create a hidden file input
            var input = document.createElement("input");
            input.type = "file";
            if (data.accept) input.accept = data.accept;
            if (data.multiple) input.multiple = true;
            input.onchange = function () {
                var files = Array.from(input.files || []).map(function (f) {
                    return { name: f.name, size: f.size, type: f.type };
                });
                // Emit result back to Python via event
                window.__forge__.emit("dialog:result", {
                    id: data.id,
                    files: files
                });
            };
            input.click();
            return;  // async — result comes via event
        } else if (action === "save_file") {
            // Trigger a download
            var blob = new Blob([data.content || ""], { type: data.mime || "text/plain" });
            var url = URL.createObjectURL(blob);
            var a = document.createElement("a");
            a.href = url;
            a.download = data.filename || "download.txt";
            a.click();
            URL.revokeObjectURL(url);
        }

        // If there's a pending invoke, resolve it
        if (data.id && pendingInvokes.has(data.id)) {
            var pending = pendingInvokes.get(data.id);
            pending.resolve(result);
            pendingInvokes.delete(data.id);
        }
    }

    // ─── Clipboard handler (JS-side) ───

    function _handleClipboard(data) {
        var action = data.action;

        if (action === "write" && navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(data.text || "").then(function () {
                _resolveById(data.id, true);
            }).catch(function (err) {
                _rejectById(data.id, err);
            });
        } else if (action === "read" && navigator.clipboard && navigator.clipboard.readText) {
            navigator.clipboard.readText().then(function (text) {
                _resolveById(data.id, text);
            }).catch(function (err) {
                _rejectById(data.id, err);
            });
        } else {
            _rejectById(data.id, new Error("Clipboard API not available"));
        }
    }

    function _resolveById(id, value) {
        if (id != null && pendingInvokes.has(id)) {
            pendingInvokes.get(id).resolve(value);
            pendingInvokes.delete(id);
        }
    }

    function _rejectById(id, err) {
        if (id != null && pendingInvokes.has(id)) {
            pendingInvokes.get(id).reject(err);
            pendingInvokes.delete(id);
        }
    }

    function resolveDescriptor(result) {
        if (!result || typeof result !== "object" || !result.action) {
            return Promise.resolve(result);
        }

        if (result.action === "clipboard_read") {
            return navigator.clipboard.readText();
        }

        if (result.action === "clipboard_write") {
            return navigator.clipboard.writeText(result.text || "").then(function () {
                return true;
            });
        }

        if (result.action === "open_file") {
            return new Promise(function (resolve) {
                var input = document.createElement("input");
                input.type = "file";
                if (result.multiple) input.multiple = true;
                input.onchange = function () {
                    var files = Array.from(input.files || []).map(function (f) {
                        return {
                            name: f.name,
                            size: f.size,
                            type: f.type
                        };
                    });
                    resolve(result.multiple ? files : (files[0] || null));
                };
                input.click();
            });
        }

        if (result.action === "open_directory") {
            return Promise.resolve(null);
        }

        if (result.action === "save_file") {
            return Promise.resolve(result.default_path || null);
        }

        if (result.action === "message") {
            window.alert(result.body || "");
            return Promise.resolve(true);
        }

        if (result.action === "confirm") {
            return Promise.resolve(window.confirm(result.message || result.body || ""));
        }

        return Promise.resolve(result);
    }

    function buildWindowFeatures(descriptor) {
        var features = [];
        if (descriptor.width) features.push("width=" + descriptor.width);
        if (descriptor.height) features.push("height=" + descriptor.height);
        features.push("resizable=" + (descriptor.resizable === false ? "no" : "yes"));
        return features.join(",");
    }

    function openManagedWindow(descriptor) {
        if (!descriptor || !descriptor.label) {
            return null;
        }
        var popup = window.open(
            descriptor.url,
            descriptor.label,
            buildWindowFeatures(descriptor)
        );
        managedWindows.set(descriptor.label, popup || null);
        return popup;
    }

    function closeManagedWindow(label) {
        if (!managedWindows.has(label)) {
            return false;
        }
        var popup = managedWindows.get(label);
        if (popup && !popup.closed) {
            popup.close();
        }
        managedWindows.delete(label);
        return true;
    }

    function currentWindowLabel() {
        try {
            if (window.name) {
                return String(window.name).trim().toLowerCase() || "main";
            }
        } catch (err) {
            console.warn("[Forge] Failed to inspect window name:", err);
        }
        return "main";
    }

    function currentOrigin() {
        try {
            if (window.location && window.location.href) {
                return window.location.href;
            }
        } catch (err) {
            console.warn("[Forge] Failed to inspect location href:", err);
        }
        return "forge://app/index.html";
    }

    // ─── WebSocket initialization ───

    function connectWebSocket(url) {
        try {
            ws = new WebSocket(url);
        } catch (e) {
            console.error("[Forge] WebSocket connection failed:", e);
            return;
        }

        ws.onopen = function () {
            wsReady = true;
            console.log("[Forge] WebSocket connected:", url);
            // Flush queued messages
            while (wsQueue.length > 0) {
                ws.send(wsQueue.shift());
            }
        };

        ws.onmessage = function (event) {
            handleMessage(event.data);
        };

        ws.onclose = function (event) {
            wsReady = false;
            console.log("[Forge] WebSocket closed (code " + event.code + ")");
            // Auto-reconnect after 2s unless intentional close
            if (event.code !== 1000) {
                setTimeout(function () { connectWebSocket(url); }, 2000);
            }
        };

        ws.onerror = function (err) {
            console.error("[Forge] WebSocket error:", err);
        };
    }

    // ─── Public API ───

    window.__forge__ = {
        /**
         * Invoke a Python command.
         *
         * @param {string} cmd  — command name
         * @param {object} args — keyword arguments (default: {})
         * @returns {Promise<any>}
         */
        invoke: function (cmd, args) {
            return window.__forge__.invokeDetailed(cmd, args, {});
        },

        /**
         * Invoke a Python command and optionally receive protocol metadata.
         *
         * @param {string} cmd
         * @param {object} args
         * @param {object} options
         * @returns {Promise<any>}
         */
        invokeDetailed: function (cmd, args, options) {
            var id = ++invokeId;
            options = options || {};
            return new Promise(function (resolve, reject) {
                pendingInvokes.set(id, {
                    resolve: resolve,
                    reject: reject,
                    detailed: !!options.detailed
                });

                try {
                    var message = JSON.stringify({
                        type: "invoke",
                        protocol: protocolVersion,
                        id: id,
                        cmd: cmd,
                        args: args || {},
                        trace: !!options.trace,
                        meta: {
                            origin: currentOrigin(),
                            window_label: currentWindowLabel()
                        }
                    });
                    send(message);
                } catch (err) {
                    pendingInvokes.delete(id);
                    reject(err);
                }
            });
        },

        fs: {
            read: function (path, max_size) {
                return window.__forge__.invoke("read", { path: path, max_size: max_size });
            },
            write: function (path, content) {
                return window.__forge__.invoke("write", { path: path, content: content });
            },
            exists: function (path) {
                return window.__forge__.invoke("exists", { path: path });
            },
            list: function (path, include_hidden) {
                return window.__forge__.invoke("list", {
                    path: path,
                    include_hidden: !!include_hidden
                });
            },
            delete: function (path, recursive) {
                return window.__forge__.invoke("delete", {
                    path: path,
                    recursive: !!recursive
                });
            },
            mkdir: function (path, parents) {
                return window.__forge__.invoke("mkdir", {
                    path: path,
                    parents: parents !== false
                });
            }
        },

        clipboard: {
            read: function () {
                return window.__forge__.invoke("clipboard_read", {}).then(resolveDescriptor);
            },
            write: function (text) {
                return window.__forge__.invoke("clipboard_write", { text: text }).then(resolveDescriptor);
            },
            clear: function () {
                return window.__forge__.invoke("clipboard_clear", {}).then(resolveDescriptor);
            }
        },

        dialog: {
            open: function (options) {
                options = options || {};
                return window.__forge__.invoke("open", options).then(resolveDescriptor);
            },
            save: function (options) {
                options = options || {};
                return window.__forge__.invoke("save", options).then(resolveDescriptor);
            },
            message: function (title, body, level) {
                return window.__forge__.invoke("message", {
                    title: title,
                    body: body,
                    level: level || "info"
                }).then(resolveDescriptor);
            },
            confirm: function (title, message, level) {
                return window.__forge__.invoke("confirm", {
                    title: title,
                    message: message,
                    level: level || "info"
                }).then(resolveDescriptor);
            },
            openDirectory: function (options) {
                options = options || {};
                return window.__forge__.invoke("open_directory", options).then(resolveDescriptor);
            }
        },

        app: {
            version: function () {
                return window.__forge__.invoke("version", {});
            },
            platform: function () {
                return window.__forge__.invoke("platform", {});
            },
            info: function () {
                return window.__forge__.invoke("info", {});
            },
            exit: function () {
                return window.__forge__.invoke("exit", {});
            }
        },

        menu: {
            set: function (items) {
                return window.__forge__.invoke("menu_set", { items: items || [] });
            },
            get: function () {
                return window.__forge__.invoke("menu_get", {});
            },
            clear: function () {
                return window.__forge__.invoke("menu_clear", {});
            },
            enable: function (itemId) {
                return window.__forge__.invoke("menu_enable", { item_id: itemId });
            },
            disable: function (itemId) {
                return window.__forge__.invoke("menu_disable", { item_id: itemId });
            },
            check: function (itemId, checked) {
                return window.__forge__.invoke("menu_check", {
                    item_id: itemId,
                    checked: checked !== false
                });
            },
            uncheck: function (itemId) {
                return window.__forge__.invoke("menu_uncheck", { item_id: itemId });
            },
            trigger: function (itemId, payload) {
                return window.__forge__.invoke("menu_trigger", {
                    item_id: itemId,
                    payload: payload || null
                });
            }
        },

        tray: {
            setIcon: function (iconPath) {
                return window.__forge__.invoke("tray_set_icon", { icon_path: iconPath });
            },
            setMenu: function (items) {
                return window.__forge__.invoke("tray_set_menu", { items: items || [] });
            },
            show: function () {
                return window.__forge__.invoke("tray_show", {});
            },
            hide: function () {
                return window.__forge__.invoke("tray_hide", {});
            },
            isVisible: function () {
                return window.__forge__.invoke("tray_is_visible", {});
            },
            state: function () {
                return window.__forge__.invoke("tray_state", {});
            },
            trigger: function (action, payload) {
                return window.__forge__.invoke("tray_trigger", {
                    action: action,
                    payload: payload || null
                });
            }
        },

        notifications: {
            notify: function (title, body, options) {
                options = options || {};
                return window.__forge__.invoke("notification_notify", {
                    title: title,
                    body: body,
                    icon: options.icon || null,
                    app_name: options.appName || null,
                    timeout: options.timeout == null ? 5 : options.timeout
                });
            },
            state: function () {
                return window.__forge__.invoke("notification_state", {});
            },
            history: function (limit) {
                return window.__forge__.invoke("notification_history", {
                    limit: limit == null ? 20 : limit
                });
            }
        },

        deepLink: {
            open: function (url) {
                return window.__forge__.invoke("deep_link_open", { url: url });
            },
            state: function () {
                return window.__forge__.invoke("deep_link_state", {});
            },
            protocols: function () {
                return window.__forge__.invoke("deep_link_protocols", {});
            }
        },

        runtime: {
            health: function () {
                return window.__forge__.invoke("__forge_runtime_health", {});
            },
            diagnostics: function () {
                return window.__forge__.invoke("__forge_runtime_diagnostics", {});
            },
            commands: function () {
                return window.__forge__.invoke("__forge_runtime_commands", {});
            },
            protocol: function () {
                return window.__forge__.invoke("__forge_runtime_protocol", {});
            },
            plugins: function () {
                return window.__forge__.invoke("__forge_runtime_plugins", {});
            },
            security: function () {
                return window.__forge__.invoke("__forge_runtime_security", {});
            },
            lastCrash: function () {
                return window.__forge__.invoke("__forge_runtime_last_crash", {});
            },
            logs: function (limit) {
                return window.__forge__.invoke("__forge_runtime_logs", {
                    limit: limit == null ? 100 : limit
                });
            },
            state: function () {
                return window.__forge__.invoke("__forge_runtime_get_state", {});
            },
            navigate: function (url) {
                return window.__forge__.invoke("__forge_runtime_navigate", { url: url });
            },
            reload: function () {
                return window.__forge__.invoke("__forge_runtime_reload", {});
            },
            back: function () {
                return window.__forge__.invoke("__forge_runtime_go_back", {});
            },
            forward: function () {
                return window.__forge__.invoke("__forge_runtime_go_forward", {});
            },
            openDevtools: function () {
                return window.__forge__.invoke("__forge_runtime_open_devtools", {});
            },
            closeDevtools: function () {
                return window.__forge__.invoke("__forge_runtime_close_devtools", {});
            },
            toggleDevtools: function () {
                return window.__forge__.invoke("__forge_runtime_toggle_devtools", {});
            },
            exportSupportBundle: function (destination) {
                return window.__forge__.invoke("__forge_runtime_export_support_bundle", {
                    destination: destination || null
                });
            }
        },

        updater: {
            currentVersion: function () {
                return window.__forge__.invoke("updater_current_version", {});
            },
            channels: function () {
                return window.__forge__.invoke("updater_channels", {});
            },
            config: function () {
                return window.__forge__.invoke("updater_config", {});
            },
            manifestSchema: function () {
                return window.__forge__.invoke("updater_manifest_schema", {});
            },
            generateManifest: function (options) {
                options = options || {};
                return window.__forge__.invoke("updater_generate_manifest", options);
            },
            check: function (manifestUrl, currentVersion) {
                return window.__forge__.invoke("updater_check", {
                    manifest_url: manifestUrl || null,
                    current_version: currentVersion || null
                });
            },
            verify: function (manifestUrl, publicKey) {
                return window.__forge__.invoke("updater_verify", {
                    manifest_url: manifestUrl || null,
                    public_key: publicKey || null
                });
            },
            download: function (options) {
                options = options || {};
                return window.__forge__.invoke("updater_download", {
                    manifest_url: options.manifestUrl || null,
                    destination: options.destination || null,
                    artifact_url: options.artifactUrl || null,
                    public_key: options.publicKey || null
                });
            },
            apply: function (options) {
                options = options || {};
                return window.__forge__.invoke("updater_apply", {
                    download_path: options.downloadPath || null,
                    manifest_url: options.manifestUrl || null,
                    install_dir: options.installDir || null,
                    backup_dir: options.backupDir || null,
                    public_key: options.publicKey || null
                });
            },
            update: function (options) {
                options = options || {};
                return window.__forge__.invoke("updater_update", {
                    manifest_url: options.manifestUrl || null,
                    install_dir: options.installDir || null,
                    destination: options.destination || null,
                    public_key: options.publicKey || null
                });
            }
        },

        window: {
            current: function () {
                return window.__forge__.invoke("__forge_windows_current", {});
            },
            list: function () {
                return window.__forge__.invoke("__forge_windows_list", {});
            },
            get: function (label) {
                return window.__forge__.invoke("__forge_windows_get", { label: label });
            },
            create: function (options) {
                options = options || {};
                return window.__forge__.invoke("__forge_window_create", options);
            },
            closeLabel: function (label) {
                return window.__forge__.invoke("__forge_window_close_label", { label: label });
            },
            setTitle: function (title) {
                return window.__forge__.invoke("__forge_window_set_title", { title: title });
            },
            setPosition: function (x, y) {
                return window.__forge__.invoke("__forge_window_set_position", {
                    x: x,
                    y: y
                });
            },
            setSize: function (width, height) {
                return window.__forge__.invoke("__forge_window_set_size", {
                    width: width,
                    height: height
                });
            },
            setFullscreen: function (enabled) {
                return window.__forge__.invoke("__forge_window_set_fullscreen", {
                    enabled: !!enabled
                });
            },
            setAlwaysOnTop: function (enabled) {
                return window.__forge__.invoke("__forge_window_set_always_on_top", {
                    enabled: !!enabled
                });
            },
            position: function () {
                return window.__forge__.invoke("__forge_window_get_position", {});
            },
            state: function () {
                return window.__forge__.invoke("__forge_window_get_state", {});
            },
            isVisible: function () {
                return window.__forge__.invoke("__forge_window_is_visible", {});
            },
            isFocused: function () {
                return window.__forge__.invoke("__forge_window_is_focused", {});
            },
            isMinimized: function () {
                return window.__forge__.invoke("__forge_window_is_minimized", {});
            },
            isMaximized: function () {
                return window.__forge__.invoke("__forge_window_is_maximized", {});
            },
            show: function () {
                return window.__forge__.invoke("__forge_window_show", {});
            },
            hide: function () {
                return window.__forge__.invoke("__forge_window_hide", {});
            },
            focus: function () {
                return window.__forge__.invoke("__forge_window_focus", {});
            },
            minimize: function () {
                return window.__forge__.invoke("__forge_window_minimize", {});
            },
            unminimize: function () {
                return window.__forge__.invoke("__forge_window_unminimize", {});
            },
            maximize: function () {
                return window.__forge__.invoke("__forge_window_maximize", {});
            },
            unmaximize: function () {
                return window.__forge__.invoke("__forge_window_unmaximize", {});
            },
            close: function () {
                return window.__forge__.invoke("__forge_window_close", {});
            }
        },

        introspect: {
            commands: function () {
                return window.__forge__.invoke("__forge_describe_commands", {});
            },
            protocol: function () {
                return window.__forge__.invoke("__forge_protocol_info", {});
            }
        },

        /**
         * Subscribe to a Python event.
         *
         * @param {string}   event    — event name
         * @param {function} callback — handler
         */
        on: function (event, callback) {
            if (!listeners.has(event)) {
                listeners.set(event, []);
            }
            listeners.get(event).push(callback);
        },

        /**
         * Unsubscribe from a Python event.
         *
         * If callback is provided, only that specific listener is removed.
         * If callback is omitted, ALL listeners for the event are removed.
         *
         * @param {string}   event    — event name
         * @param {function} [callback] — optional specific handler to remove
         */
        off: function (event, callback) {
            if (!listeners.has(event)) return;

            if (callback) {
                var cbs = listeners.get(event);
                var idx = cbs.indexOf(callback);
                if (idx !== -1) {
                    cbs.splice(idx, 1);
                }
                if (cbs.length === 0) {
                    listeners.delete(event);
                }
            } else {
                // Remove all listeners for this event
                listeners.delete(event);
            }
        },

        /**
         * Emit an event to the Python backend (WebSocket mode only).
         * In native IPC mode this is a no-op since events flow Python → JS.
         *
         * @param {string} event   — event name
         * @param {any}    payload — data to send
         */
        emit: function (event, payload) {
            var message = JSON.stringify({
                type: "event",
                event: event,
                payload: payload
            });
            send(message);
        },

        /**
         * Connect to a Forge web server via WebSocket.
         * Only needed in web mode; desktop mode uses native IPC.
         *
         * @param {string} [url] — WebSocket URL (default: auto-detect)
         */
        connect: function (url) {
            if (!url) {
                var proto = window.location.protocol === "https:" ? "wss:" : "ws:";
                url = proto + "//" + window.location.host + "/ws";
            }
            connectWebSocket(url);
        },

        /**
         * Internal: handle messages from Python (called by Rust evaluate_script).
         */
        _handleMessage: handleMessage,

        /**
         * Internal: open a managed secondary window.
         */
        __openManagedWindow: openManagedWindow,

        /**
         * Internal: close a managed secondary window.
         */
        __closeManagedWindow: closeManagedWindow,

        /**
         * Internal: active IPC protocol version.
         */
        _protocolVersion: function () { return protocolVersion; },

        /**
         * Internal: check if native IPC is available.
         */
        _isNative: function () { return hasNativeIPC; }
    };

    // ─── Auto-connect ───
    // In native mode (desktop), IPC is already available.
    // In web mode, auto-connect WebSocket if no native IPC is detected.
    if (!hasNativeIPC) {
        // Defer to allow page to set up custom URL first
        if (document.readyState === "complete" || document.readyState === "interactive") {
            setTimeout(function () {
                if (!ws) window.__forge__.connect();
            }, 0);
        } else {
            document.addEventListener("DOMContentLoaded", function () {
                if (!ws) window.__forge__.connect();
            });
        }
    }

    console.log("[Forge] Runtime v2.0 initialized (" + (hasNativeIPC ? "native IPC" : "WebSocket") + ")");
})();
