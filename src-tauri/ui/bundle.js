// node_modules/@tauri-apps/api/external/tslib/tslib.es6.js
function __classPrivateFieldGet(receiver, state2, kind, f) {
  if (kind === "a" && !f) throw new TypeError("Private accessor was defined without a getter");
  if (typeof state2 === "function" ? receiver !== state2 || !f : !state2.has(receiver)) throw new TypeError("Cannot read private member from an object whose class did not declare it");
  return kind === "m" ? f : kind === "a" ? f.call(receiver) : f ? f.value : state2.get(receiver);
}
function __classPrivateFieldSet(receiver, state2, value, kind, f) {
  if (kind === "m") throw new TypeError("Private method is not writable");
  if (kind === "a" && !f) throw new TypeError("Private accessor was defined without a setter");
  if (typeof state2 === "function" ? receiver !== state2 || !f : !state2.has(receiver)) throw new TypeError("Cannot write private member to an object whose class did not declare it");
  return kind === "a" ? f.call(receiver, value) : f ? f.value = value : state2.set(receiver, value), value;
}

// node_modules/@tauri-apps/api/core.js
var _Channel_onmessage;
var _Channel_nextMessageIndex;
var _Channel_pendingMessages;
var _Channel_messageEndIndex;
var _Resource_rid;
var SERIALIZE_TO_IPC_FN = "__TAURI_TO_IPC_KEY__";
function transformCallback(callback, once2 = false) {
  return window.__TAURI_INTERNALS__.transformCallback(callback, once2);
}
var Channel = class {
  constructor(onmessage) {
    _Channel_onmessage.set(this, void 0);
    _Channel_nextMessageIndex.set(this, 0);
    _Channel_pendingMessages.set(this, []);
    _Channel_messageEndIndex.set(this, void 0);
    __classPrivateFieldSet(this, _Channel_onmessage, onmessage || (() => {
    }), "f");
    this.id = transformCallback((rawMessage) => {
      const index = rawMessage.index;
      if ("end" in rawMessage) {
        if (index == __classPrivateFieldGet(this, _Channel_nextMessageIndex, "f")) {
          this.cleanupCallback();
        } else {
          __classPrivateFieldSet(this, _Channel_messageEndIndex, index, "f");
        }
        return;
      }
      const message = rawMessage.message;
      if (index == __classPrivateFieldGet(this, _Channel_nextMessageIndex, "f")) {
        __classPrivateFieldGet(this, _Channel_onmessage, "f").call(this, message);
        __classPrivateFieldSet(this, _Channel_nextMessageIndex, __classPrivateFieldGet(this, _Channel_nextMessageIndex, "f") + 1, "f");
        while (__classPrivateFieldGet(this, _Channel_nextMessageIndex, "f") in __classPrivateFieldGet(this, _Channel_pendingMessages, "f")) {
          const message2 = __classPrivateFieldGet(this, _Channel_pendingMessages, "f")[__classPrivateFieldGet(this, _Channel_nextMessageIndex, "f")];
          __classPrivateFieldGet(this, _Channel_onmessage, "f").call(this, message2);
          delete __classPrivateFieldGet(this, _Channel_pendingMessages, "f")[__classPrivateFieldGet(this, _Channel_nextMessageIndex, "f")];
          __classPrivateFieldSet(this, _Channel_nextMessageIndex, __classPrivateFieldGet(this, _Channel_nextMessageIndex, "f") + 1, "f");
        }
        if (__classPrivateFieldGet(this, _Channel_nextMessageIndex, "f") === __classPrivateFieldGet(this, _Channel_messageEndIndex, "f")) {
          this.cleanupCallback();
        }
      } else {
        __classPrivateFieldGet(this, _Channel_pendingMessages, "f")[index] = message;
      }
    });
  }
  cleanupCallback() {
    window.__TAURI_INTERNALS__.unregisterCallback(this.id);
  }
  set onmessage(handler) {
    __classPrivateFieldSet(this, _Channel_onmessage, handler, "f");
  }
  get onmessage() {
    return __classPrivateFieldGet(this, _Channel_onmessage, "f");
  }
  [(_Channel_onmessage = /* @__PURE__ */ new WeakMap(), _Channel_nextMessageIndex = /* @__PURE__ */ new WeakMap(), _Channel_pendingMessages = /* @__PURE__ */ new WeakMap(), _Channel_messageEndIndex = /* @__PURE__ */ new WeakMap(), SERIALIZE_TO_IPC_FN)]() {
    return `__CHANNEL__:${this.id}`;
  }
  toJSON() {
    return this[SERIALIZE_TO_IPC_FN]();
  }
};
async function invoke(cmd, args = {}, options) {
  return window.__TAURI_INTERNALS__.invoke(cmd, args, options);
}
function convertFileSrc(filePath, protocol = "asset") {
  return window.__TAURI_INTERNALS__.convertFileSrc(filePath, protocol);
}
var Resource = class {
  get rid() {
    return __classPrivateFieldGet(this, _Resource_rid, "f");
  }
  constructor(rid) {
    _Resource_rid.set(this, void 0);
    __classPrivateFieldSet(this, _Resource_rid, rid, "f");
  }
  /**
   * Destroys and cleans up this resource from memory.
   * **You should not call any method on this object anymore and should drop any reference to it.**
   */
  async close() {
    return invoke("plugin:resources|close", {
      rid: this.rid
    });
  }
};
_Resource_rid = /* @__PURE__ */ new WeakMap();

// config_controls.ts
var ASPECT_RATIO_RESOLUTIONS = {
  "1:1": [
    { width: 256, height: 256 },
    { width: 512, height: 512 },
    { width: 1024, height: 1024 }
  ],
  "16:9": [
    { width: 640, height: 360 },
    { width: 1280, height: 720 },
    { width: 1920, height: 1080 }
  ],
  "3:1": [
    { width: 900, height: 300 },
    { width: 1500, height: 500 },
    { width: 1800, height: 600 }
  ],
  "4:1": [
    { width: 1200, height: 300 },
    { width: 1600, height: 400 }
  ],
  "4:5": [
    { width: 540, height: 675 },
    { width: 1080, height: 1350 }
  ],
  "9:16": [
    { width: 360, height: 640 },
    { width: 1080, height: 1920 }
  ]
};
var SUPPORTED_RATIOS = Object.keys(ASPECT_RATIO_RESOLUTIONS);
function getDefaultResolution(ratio) {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions || resolutions.length === 0) {
    return { width: 256, height: 256 };
  }
  const first = resolutions[0];
  return first ?? { width: 256, height: 256 };
}
function getResolutionIndex(ratio, width, height) {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions) return 0;
  const index = resolutions.findIndex((r) => r.width === width && r.height === height);
  return index >= 0 ? index : 0;
}
function canIncreaseResolution(ratio, width, height) {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions || resolutions.length <= 1) return false;
  const index = getResolutionIndex(ratio, width, height);
  return index < resolutions.length - 1;
}
function canDecreaseResolution(ratio, width, height) {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions || resolutions.length <= 1) return false;
  const index = getResolutionIndex(ratio, width, height);
  return index > 0;
}
function getNextResolution(ratio, width, height) {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions) return null;
  const index = getResolutionIndex(ratio, width, height);
  if (index < resolutions.length - 1) {
    const next2 = resolutions[index + 1];
    return next2 ?? null;
  }
  return null;
}
function getPreviousResolution(ratio, width, height) {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions) return null;
  const index = getResolutionIndex(ratio, width, height);
  if (index > 0) {
    const prev2 = resolutions[index - 1];
    return prev2 ?? null;
  }
  return null;
}
var configUpdateQueue = Promise.resolve();
function updateResolutionButtons(ratio, width, height) {
  const decreaseBtn = document.getElementById("resolution-decrease");
  const increaseBtn = document.getElementById("resolution-increase");
  if (decreaseBtn) {
    decreaseBtn.disabled = !canDecreaseResolution(ratio, width, height);
  }
  if (increaseBtn) {
    increaseBtn.disabled = !canIncreaseResolution(ratio, width, height);
  }
}
function syncControlsFromState(state2) {
  const dimensionDisplay = document.getElementById("dimension-display");
  if (dimensionDisplay) {
    dimensionDisplay.textContent = `${state2.width}\xD7${state2.height}`;
  }
  const aspectRatioRadios = document.querySelectorAll('input[name="aspect-ratio"]');
  Array.from(aspectRatioRadios).forEach((radio) => {
    radio.checked = radio.value === state2.aspectRatio;
  });
  updateResolutionButtons(state2.aspectRatio, state2.width, state2.height);
}
function initConfigControls(initialPrompt, initialAspectRatio, initialWidth, initialHeight, state2, elements2) {
  state2.aspectRatio = SUPPORTED_RATIOS.includes(initialAspectRatio) ? initialAspectRatio : "1:1";
  state2.width = initialWidth;
  state2.height = initialHeight;
  const promptInput = document.getElementById("prompt-input");
  const dimensionDisplay = document.getElementById("dimension-display");
  const aspectRatioRadios = document.querySelectorAll('input[name="aspect-ratio"]');
  const decreaseBtn = document.getElementById("resolution-decrease");
  const increaseBtn = document.getElementById("resolution-increase");
  if (promptInput) {
    promptInput.value = initialPrompt;
    elements2.promptInput = promptInput;
  }
  syncControlsFromState(state2);
  const radios = Array.from(aspectRatioRadios);
  radios.forEach((radio) => {
    radio.checked = radio.value === state2.aspectRatio;
  });
  elements2.aspectRatioRadios = aspectRatioRadios;
  updateResolutionButtons(state2.aspectRatio, state2.width, state2.height);
  if (promptInput) {
    promptInput.addEventListener("blur", () => {
      const config = getCurrentConfig(elements2, state2);
      void handleConfigUpdate(config.prompt, config.aspectRatio, config.width, config.height, state2);
    });
    promptInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        promptInput.blur();
      }
    });
  }
  radios.forEach((radio) => {
    radio.addEventListener("change", () => {
      const ratio = radio.value;
      const dims = getDefaultResolution(ratio);
      if (dimensionDisplay) {
        dimensionDisplay.textContent = `${dims.width}\xD7${dims.height}`;
      }
      updateResolutionButtons(ratio, dims.width, dims.height);
      const config = getCurrentConfig(elements2, state2);
      void handleConfigUpdate(config.prompt, ratio, dims.width, dims.height, state2);
    });
  });
  if (decreaseBtn) {
    decreaseBtn.addEventListener("click", () => {
      const prevRes = getPreviousResolution(state2.aspectRatio, state2.width, state2.height);
      if (prevRes) {
        if (dimensionDisplay) {
          dimensionDisplay.textContent = `${prevRes.width}\xD7${prevRes.height}`;
        }
        updateResolutionButtons(state2.aspectRatio, prevRes.width, prevRes.height);
        const config = getCurrentConfig(elements2, state2);
        void handleConfigUpdate(config.prompt, config.aspectRatio, prevRes.width, prevRes.height, state2);
      }
    });
  }
  if (increaseBtn) {
    increaseBtn.addEventListener("click", () => {
      const nextRes = getNextResolution(state2.aspectRatio, state2.width, state2.height);
      if (nextRes) {
        if (dimensionDisplay) {
          dimensionDisplay.textContent = `${nextRes.width}\xD7${nextRes.height}`;
        }
        updateResolutionButtons(state2.aspectRatio, nextRes.width, nextRes.height);
        const config = getCurrentConfig(elements2, state2);
        void handleConfigUpdate(config.prompt, config.aspectRatio, nextRes.width, nextRes.height, state2);
      }
    });
  }
}
async function handleConfigUpdate(promptValue, aspectRatioValue, widthValue, heightValue, state2) {
  const trimmedPrompt = promptValue.trim();
  if (trimmedPrompt === "") {
    const promptInput = document.getElementById("prompt-input");
    if (promptInput) {
      showValidationError("Prompt cannot be empty", promptInput);
    }
    return;
  }
  const width = widthValue;
  const height = heightValue;
  if (trimmedPrompt === state2.prompt && aspectRatioValue === state2.aspectRatio && width === state2.width && height === state2.height) {
    return;
  }
  const previousPrompt = state2.prompt;
  const previousAspectRatio = state2.aspectRatio;
  const previousWidth = state2.width;
  const previousHeight = state2.height;
  state2.prompt = trimmedPrompt;
  state2.aspectRatio = aspectRatioValue;
  state2.width = width;
  state2.height = height;
  const attemptedPrompt = trimmedPrompt;
  const attemptedAspectRatio = aspectRatioValue;
  const attemptedWidth = width;
  const attemptedHeight = height;
  configUpdateQueue = configUpdateQueue.then(async () => {
    try {
      await invoke("update_generation_config", {
        prompt: attemptedPrompt,
        aspectRatio: attemptedAspectRatio,
        width: attemptedWidth,
        height: attemptedHeight
      });
      console.log("Configuration updated successfully");
    } catch (error) {
      console.error("Configuration update failed:", error);
      const isStillCurrent = state2.prompt === attemptedPrompt && state2.aspectRatio === attemptedAspectRatio && state2.width === attemptedWidth && state2.height === attemptedHeight;
      if (isStillCurrent) {
        state2.prompt = previousPrompt;
        state2.aspectRatio = previousAspectRatio;
        state2.width = previousWidth;
        state2.height = previousHeight;
        syncControlsFromState(state2);
      }
      const promptInput = document.getElementById("prompt-input");
      if (promptInput) {
        showValidationError(`Update failed: ${String(error)}`, promptInput);
      }
    }
  }).catch((queueError) => {
    console.error("Configuration update queue error:", queueError);
  });
  await configUpdateQueue;
}
function showValidationError(message, inputElement) {
  const existingErrors = document.querySelectorAll(".validation-error");
  existingErrors.forEach((error) => error.remove());
  const errorElement = document.createElement("div");
  errorElement.className = "validation-error";
  errorElement.textContent = message;
  errorElement.setAttribute("role", "alert");
  errorElement.setAttribute("aria-live", "polite");
  if (inputElement.parentNode) {
    inputElement.parentNode.insertBefore(errorElement, inputElement.nextSibling);
  }
  setTimeout(() => {
    errorElement.remove();
  }, 3e3);
}
function getCurrentConfig(elements2, state2) {
  const promptValue = elements2.promptInput ? elements2.promptInput.value : "";
  let aspectRatioValue = "1:1";
  if (elements2.aspectRatioRadios) {
    const radios = Array.from(elements2.aspectRatioRadios);
    const checked = radios.find((radio) => radio.checked);
    if (checked) {
      aspectRatioValue = checked.value;
    }
  }
  return {
    prompt: promptValue,
    aspectRatio: aspectRatioValue,
    width: state2.width,
    height: state2.height
  };
}

// theme-manager.ts
function initTheme() {
  const saved = localStorage.getItem("textbrush-theme");
  let theme;
  if (saved === "light" || saved === "dark") {
    theme = saved;
  } else {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    theme = prefersDark ? "dark" : "light";
  }
  document.documentElement.setAttribute("data-theme", theme);
  return theme;
}
function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const newTheme = current === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", newTheme);
  localStorage.setItem("textbrush-theme", newTheme);
  return newTheme;
}

// font-size-manager.ts
var FONT_SIZE_KEY = "textbrush-font-size";
var VALID_SIZES = ["small", "medium", "large"];
var DEFAULT_SIZE = "medium";
function initFontSize() {
  const saved = localStorage.getItem(FONT_SIZE_KEY);
  if (saved && isValidFontSize(saved)) {
    applyFontSize(saved);
    return saved;
  }
  applyFontSize(DEFAULT_SIZE);
  return DEFAULT_SIZE;
}
function setFontSize(size) {
  if (!isValidFontSize(size)) {
    console.warn(`Invalid font size: ${size}, using default`);
    size = DEFAULT_SIZE;
  }
  applyFontSize(size);
  localStorage.setItem(FONT_SIZE_KEY, size);
}
function getCurrentFontSize() {
  const size = document.documentElement.getAttribute("data-font-size");
  return isValidFontSize(size) ? size : DEFAULT_SIZE;
}
function isValidFontSize(value) {
  return typeof value === "string" && VALID_SIZES.includes(value);
}
function applyFontSize(size) {
  document.documentElement.setAttribute("data-font-size", size);
}

// list-manager.ts
function navigateToPrev(state2, displayImage) {
  if (state2.currentIndex <= 0) {
    return false;
  }
  state2.currentIndex--;
  const record = state2.imageList[state2.currentIndex];
  if (record) {
    displayImage(record);
  }
  return true;
}
function navigateToNext(state2, displayImage, requestNextImage) {
  if (state2.currentIndex < state2.imageList.length - 1) {
    state2.currentIndex++;
    const record = state2.imageList[state2.currentIndex];
    if (record) {
      displayImage(record);
    }
    return true;
  }
  requestNextImage();
  return true;
}

// button-flash.ts
function flashButton(buttonElement) {
  if (!buttonElement) {
    return;
  }
  buttonElement.classList.add("btn-pressed");
  setTimeout(() => {
    buttonElement.classList.remove("btn-pressed");
  }, 150);
}
function flashButtonById(buttonId) {
  const element = document.getElementById(buttonId);
  if (!element) {
    return false;
  }
  flashButton(element);
  return true;
}
function flashButtonForKey(key, ctrlOrCmd = false) {
  switch (key) {
    case "ArrowLeft":
      return flashButtonById("prev-btn");
    case "ArrowRight":
      return flashButtonById("next-btn");
    case " ":
      return flashButtonById("pause-btn");
    case "Enter":
      return flashButtonById("accept-btn");
    case "Escape":
      return flashButtonById("abort-btn");
    case "Delete":
    case "Backspace":
      if (ctrlOrCmd) {
        return flashButtonById("delete-btn");
      }
      return false;
    default:
      return false;
  }
}

// node_modules/@tauri-apps/api/event.js
var TauriEvent;
(function(TauriEvent2) {
  TauriEvent2["WINDOW_RESIZED"] = "tauri://resize";
  TauriEvent2["WINDOW_MOVED"] = "tauri://move";
  TauriEvent2["WINDOW_CLOSE_REQUESTED"] = "tauri://close-requested";
  TauriEvent2["WINDOW_DESTROYED"] = "tauri://destroyed";
  TauriEvent2["WINDOW_FOCUS"] = "tauri://focus";
  TauriEvent2["WINDOW_BLUR"] = "tauri://blur";
  TauriEvent2["WINDOW_SCALE_FACTOR_CHANGED"] = "tauri://scale-change";
  TauriEvent2["WINDOW_THEME_CHANGED"] = "tauri://theme-changed";
  TauriEvent2["WINDOW_CREATED"] = "tauri://window-created";
  TauriEvent2["WEBVIEW_CREATED"] = "tauri://webview-created";
  TauriEvent2["DRAG_ENTER"] = "tauri://drag-enter";
  TauriEvent2["DRAG_OVER"] = "tauri://drag-over";
  TauriEvent2["DRAG_DROP"] = "tauri://drag-drop";
  TauriEvent2["DRAG_LEAVE"] = "tauri://drag-leave";
})(TauriEvent || (TauriEvent = {}));
async function _unlisten(event, eventId) {
  window.__TAURI_EVENT_PLUGIN_INTERNALS__.unregisterListener(event, eventId);
  await invoke("plugin:event|unlisten", {
    event,
    eventId
  });
}
async function listen(event, handler, options) {
  var _a;
  const target = typeof (options === null || options === void 0 ? void 0 : options.target) === "string" ? { kind: "AnyLabel", label: options.target } : (_a = options === null || options === void 0 ? void 0 : options.target) !== null && _a !== void 0 ? _a : { kind: "Any" };
  return invoke("plugin:event|listen", {
    event,
    target,
    handler: transformCallback(handler)
  }).then((eventId) => {
    return async () => _unlisten(event, eventId);
  });
}
async function once(event, handler, options) {
  return listen(event, (eventData) => {
    void _unlisten(event, eventData.id);
    handler(eventData);
  }, options);
}
async function emit(event, payload) {
  await invoke("plugin:event|emit", {
    event,
    payload
  });
}
async function emitTo(target, event, payload) {
  const eventTarget = typeof target === "string" ? { kind: "AnyLabel", label: target } : target;
  await invoke("plugin:event|emit_to", {
    target: eventTarget,
    event,
    payload
  });
}

// node_modules/@tauri-apps/api/dpi.js
var LogicalSize = class {
  constructor(...args) {
    this.type = "Logical";
    if (args.length === 1) {
      if ("Logical" in args[0]) {
        this.width = args[0].Logical.width;
        this.height = args[0].Logical.height;
      } else {
        this.width = args[0].width;
        this.height = args[0].height;
      }
    } else {
      this.width = args[0];
      this.height = args[1];
    }
  }
  /**
   * Converts the logical size to a physical one.
   * @example
   * ```typescript
   * import { LogicalSize } from '@tauri-apps/api/dpi';
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   *
   * const appWindow = getCurrentWindow();
   * const factor = await appWindow.scaleFactor();
   * const size = new LogicalSize(400, 500);
   * const physical = size.toPhysical(factor);
   * ```
   *
   * @since 2.0.0
   */
  toPhysical(scaleFactor) {
    return new PhysicalSize(this.width * scaleFactor, this.height * scaleFactor);
  }
  [SERIALIZE_TO_IPC_FN]() {
    return {
      width: this.width,
      height: this.height
    };
  }
  toJSON() {
    return this[SERIALIZE_TO_IPC_FN]();
  }
};
var PhysicalSize = class {
  constructor(...args) {
    this.type = "Physical";
    if (args.length === 1) {
      if ("Physical" in args[0]) {
        this.width = args[0].Physical.width;
        this.height = args[0].Physical.height;
      } else {
        this.width = args[0].width;
        this.height = args[0].height;
      }
    } else {
      this.width = args[0];
      this.height = args[1];
    }
  }
  /**
   * Converts the physical size to a logical one.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const appWindow = getCurrentWindow();
   * const factor = await appWindow.scaleFactor();
   * const size = await appWindow.innerSize(); // PhysicalSize
   * const logical = size.toLogical(factor);
   * ```
   */
  toLogical(scaleFactor) {
    return new LogicalSize(this.width / scaleFactor, this.height / scaleFactor);
  }
  [SERIALIZE_TO_IPC_FN]() {
    return {
      width: this.width,
      height: this.height
    };
  }
  toJSON() {
    return this[SERIALIZE_TO_IPC_FN]();
  }
};
var Size = class {
  constructor(size) {
    this.size = size;
  }
  toLogical(scaleFactor) {
    return this.size instanceof LogicalSize ? this.size : this.size.toLogical(scaleFactor);
  }
  toPhysical(scaleFactor) {
    return this.size instanceof PhysicalSize ? this.size : this.size.toPhysical(scaleFactor);
  }
  [SERIALIZE_TO_IPC_FN]() {
    return {
      [`${this.size.type}`]: {
        width: this.size.width,
        height: this.size.height
      }
    };
  }
  toJSON() {
    return this[SERIALIZE_TO_IPC_FN]();
  }
};
var LogicalPosition = class {
  constructor(...args) {
    this.type = "Logical";
    if (args.length === 1) {
      if ("Logical" in args[0]) {
        this.x = args[0].Logical.x;
        this.y = args[0].Logical.y;
      } else {
        this.x = args[0].x;
        this.y = args[0].y;
      }
    } else {
      this.x = args[0];
      this.y = args[1];
    }
  }
  /**
   * Converts the logical position to a physical one.
   * @example
   * ```typescript
   * import { LogicalPosition } from '@tauri-apps/api/dpi';
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   *
   * const appWindow = getCurrentWindow();
   * const factor = await appWindow.scaleFactor();
   * const position = new LogicalPosition(400, 500);
   * const physical = position.toPhysical(factor);
   * ```
   *
   * @since 2.0.0
   */
  toPhysical(scaleFactor) {
    return new PhysicalPosition(this.x * scaleFactor, this.y * scaleFactor);
  }
  [SERIALIZE_TO_IPC_FN]() {
    return {
      x: this.x,
      y: this.y
    };
  }
  toJSON() {
    return this[SERIALIZE_TO_IPC_FN]();
  }
};
var PhysicalPosition = class {
  constructor(...args) {
    this.type = "Physical";
    if (args.length === 1) {
      if ("Physical" in args[0]) {
        this.x = args[0].Physical.x;
        this.y = args[0].Physical.y;
      } else {
        this.x = args[0].x;
        this.y = args[0].y;
      }
    } else {
      this.x = args[0];
      this.y = args[1];
    }
  }
  /**
   * Converts the physical position to a logical one.
   * @example
   * ```typescript
   * import { PhysicalPosition } from '@tauri-apps/api/dpi';
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   *
   * const appWindow = getCurrentWindow();
   * const factor = await appWindow.scaleFactor();
   * const position = new PhysicalPosition(400, 500);
   * const physical = position.toLogical(factor);
   * ```
   *
   * @since 2.0.0
   */
  toLogical(scaleFactor) {
    return new LogicalPosition(this.x / scaleFactor, this.y / scaleFactor);
  }
  [SERIALIZE_TO_IPC_FN]() {
    return {
      x: this.x,
      y: this.y
    };
  }
  toJSON() {
    return this[SERIALIZE_TO_IPC_FN]();
  }
};
var Position = class {
  constructor(position) {
    this.position = position;
  }
  toLogical(scaleFactor) {
    return this.position instanceof LogicalPosition ? this.position : this.position.toLogical(scaleFactor);
  }
  toPhysical(scaleFactor) {
    return this.position instanceof PhysicalPosition ? this.position : this.position.toPhysical(scaleFactor);
  }
  [SERIALIZE_TO_IPC_FN]() {
    return {
      [`${this.position.type}`]: {
        x: this.position.x,
        y: this.position.y
      }
    };
  }
  toJSON() {
    return this[SERIALIZE_TO_IPC_FN]();
  }
};

// node_modules/@tauri-apps/api/image.js
var Image = class _Image extends Resource {
  /**
   * Creates an Image from a resource ID. For internal use only.
   *
   * @ignore
   */
  constructor(rid) {
    super(rid);
  }
  /** Creates a new Image using RGBA data, in row-major order from top to bottom, and with specified width and height. */
  static async new(rgba, width, height) {
    return invoke("plugin:image|new", {
      rgba: transformImage(rgba),
      width,
      height
    }).then((rid) => new _Image(rid));
  }
  /**
   * Creates a new image using the provided bytes by inferring the file format.
   * If the format is known, prefer [@link Image.fromPngBytes] or [@link Image.fromIcoBytes].
   *
   * Only `ico` and `png` are supported (based on activated feature flag).
   *
   * Note that you need the `image-ico` or `image-png` Cargo features to use this API.
   * To enable it, change your Cargo.toml file:
   * ```toml
   * [dependencies]
   * tauri = { version = "...", features = ["...", "image-png"] }
   * ```
   */
  static async fromBytes(bytes) {
    return invoke("plugin:image|from_bytes", {
      bytes: transformImage(bytes)
    }).then((rid) => new _Image(rid));
  }
  /**
   * Creates a new image using the provided path.
   *
   * Only `ico` and `png` are supported (based on activated feature flag).
   *
   * Note that you need the `image-ico` or `image-png` Cargo features to use this API.
   * To enable it, change your Cargo.toml file:
   * ```toml
   * [dependencies]
   * tauri = { version = "...", features = ["...", "image-png"] }
   * ```
   */
  static async fromPath(path) {
    return invoke("plugin:image|from_path", { path }).then((rid) => new _Image(rid));
  }
  /** Returns the RGBA data for this image, in row-major order from top to bottom.  */
  async rgba() {
    return invoke("plugin:image|rgba", {
      rid: this.rid
    }).then((buffer) => new Uint8Array(buffer));
  }
  /** Returns the size of this image.  */
  async size() {
    return invoke("plugin:image|size", { rid: this.rid });
  }
};
function transformImage(image) {
  const ret = image == null ? null : typeof image === "string" ? image : image instanceof Image ? image.rid : image;
  return ret;
}

// node_modules/@tauri-apps/api/window.js
var UserAttentionType;
(function(UserAttentionType2) {
  UserAttentionType2[UserAttentionType2["Critical"] = 1] = "Critical";
  UserAttentionType2[UserAttentionType2["Informational"] = 2] = "Informational";
})(UserAttentionType || (UserAttentionType = {}));
var CloseRequestedEvent = class {
  constructor(event) {
    this._preventDefault = false;
    this.event = event.event;
    this.id = event.id;
  }
  preventDefault() {
    this._preventDefault = true;
  }
  isPreventDefault() {
    return this._preventDefault;
  }
};
var ProgressBarStatus;
(function(ProgressBarStatus2) {
  ProgressBarStatus2["None"] = "none";
  ProgressBarStatus2["Normal"] = "normal";
  ProgressBarStatus2["Indeterminate"] = "indeterminate";
  ProgressBarStatus2["Paused"] = "paused";
  ProgressBarStatus2["Error"] = "error";
})(ProgressBarStatus || (ProgressBarStatus = {}));
function getCurrentWindow() {
  return new Window(window.__TAURI_INTERNALS__.metadata.currentWindow.label, {
    // @ts-expect-error `skip` is not defined in the public API but it is handled by the constructor
    skip: true
  });
}
async function getAllWindows() {
  return invoke("plugin:window|get_all_windows").then((windows) => windows.map((w) => new Window(w, {
    // @ts-expect-error `skip` is not defined in the public API but it is handled by the constructor
    skip: true
  })));
}
var localTauriEvents = ["tauri://created", "tauri://error"];
var Window = class {
  /**
   * Creates a new Window.
   * @example
   * ```typescript
   * import { Window } from '@tauri-apps/api/window';
   * const appWindow = new Window('my-label');
   * appWindow.once('tauri://created', function () {
   *  // window successfully created
   * });
   * appWindow.once('tauri://error', function (e) {
   *  // an error happened creating the window
   * });
   * ```
   *
   * @param label The unique window label. Must be alphanumeric: `a-zA-Z-/:_`.
   * @returns The {@link Window} instance to communicate with the window.
   */
  constructor(label, options = {}) {
    var _a;
    this.label = label;
    this.listeners = /* @__PURE__ */ Object.create(null);
    if (!(options === null || options === void 0 ? void 0 : options.skip)) {
      invoke("plugin:window|create", {
        options: {
          ...options,
          parent: typeof options.parent === "string" ? options.parent : (_a = options.parent) === null || _a === void 0 ? void 0 : _a.label,
          label
        }
      }).then(async () => this.emit("tauri://created")).catch(async (e) => this.emit("tauri://error", e));
    }
  }
  /**
   * Gets the Window associated with the given label.
   * @example
   * ```typescript
   * import { Window } from '@tauri-apps/api/window';
   * const mainWindow = Window.getByLabel('main');
   * ```
   *
   * @param label The window label.
   * @returns The Window instance to communicate with the window or null if the window doesn't exist.
   */
  static async getByLabel(label) {
    var _a;
    return (_a = (await getAllWindows()).find((w) => w.label === label)) !== null && _a !== void 0 ? _a : null;
  }
  /**
   * Get an instance of `Window` for the current window.
   */
  static getCurrent() {
    return getCurrentWindow();
  }
  /**
   * Gets a list of instances of `Window` for all available windows.
   */
  static async getAll() {
    return getAllWindows();
  }
  /**
   *  Gets the focused window.
   * @example
   * ```typescript
   * import { Window } from '@tauri-apps/api/window';
   * const focusedWindow = Window.getFocusedWindow();
   * ```
   *
   * @returns The Window instance or `undefined` if there is not any focused window.
   */
  static async getFocusedWindow() {
    for (const w of await getAllWindows()) {
      if (await w.isFocused()) {
        return w;
      }
    }
    return null;
  }
  /**
   * Listen to an emitted event on this window.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const unlisten = await getCurrentWindow().listen<string>('state-changed', (event) => {
   *   console.log(`Got error: ${payload}`);
   * });
   *
   * // you need to call unlisten if your handler goes out of scope e.g. the component is unmounted
   * unlisten();
   * ```
   *
   * @param event Event name. Must include only alphanumeric characters, `-`, `/`, `:` and `_`.
   * @param handler Event handler.
   * @returns A promise resolving to a function to unlisten to the event.
   * Note that removing the listener is required if your listener goes out of scope e.g. the component is unmounted.
   */
  async listen(event, handler) {
    if (this._handleTauriEvent(event, handler)) {
      return () => {
        const listeners = this.listeners[event];
        listeners.splice(listeners.indexOf(handler), 1);
      };
    }
    return listen(event, handler, {
      target: { kind: "Window", label: this.label }
    });
  }
  /**
   * Listen to an emitted event on this window only once.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const unlisten = await getCurrentWindow().once<null>('initialized', (event) => {
   *   console.log(`Window initialized!`);
   * });
   *
   * // you need to call unlisten if your handler goes out of scope e.g. the component is unmounted
   * unlisten();
   * ```
   *
   * @param event Event name. Must include only alphanumeric characters, `-`, `/`, `:` and `_`.
   * @param handler Event handler.
   * @returns A promise resolving to a function to unlisten to the event.
   * Note that removing the listener is required if your listener goes out of scope e.g. the component is unmounted.
   */
  async once(event, handler) {
    if (this._handleTauriEvent(event, handler)) {
      return () => {
        const listeners = this.listeners[event];
        listeners.splice(listeners.indexOf(handler), 1);
      };
    }
    return once(event, handler, {
      target: { kind: "Window", label: this.label }
    });
  }
  /**
   * Emits an event to all {@link EventTarget|targets}.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().emit('window-loaded', { loggedIn: true, token: 'authToken' });
   * ```
   *
   * @param event Event name. Must include only alphanumeric characters, `-`, `/`, `:` and `_`.
   * @param payload Event payload.
   */
  async emit(event, payload) {
    if (localTauriEvents.includes(event)) {
      for (const handler of this.listeners[event] || []) {
        handler({
          event,
          id: -1,
          payload
        });
      }
      return;
    }
    return emit(event, payload);
  }
  /**
   * Emits an event to all {@link EventTarget|targets} matching the given target.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().emit('main', 'window-loaded', { loggedIn: true, token: 'authToken' });
   * ```
   * @param target Label of the target Window/Webview/WebviewWindow or raw {@link EventTarget} object.
   * @param event Event name. Must include only alphanumeric characters, `-`, `/`, `:` and `_`.
   * @param payload Event payload.
   */
  async emitTo(target, event, payload) {
    if (localTauriEvents.includes(event)) {
      for (const handler of this.listeners[event] || []) {
        handler({
          event,
          id: -1,
          payload
        });
      }
      return;
    }
    return emitTo(target, event, payload);
  }
  /** @ignore */
  _handleTauriEvent(event, handler) {
    if (localTauriEvents.includes(event)) {
      if (!(event in this.listeners)) {
        this.listeners[event] = [handler];
      } else {
        this.listeners[event].push(handler);
      }
      return true;
    }
    return false;
  }
  // Getters
  /**
   * The scale factor that can be used to map physical pixels to logical pixels.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const factor = await getCurrentWindow().scaleFactor();
   * ```
   *
   * @returns The window's monitor scale factor.
   */
  async scaleFactor() {
    return invoke("plugin:window|scale_factor", {
      label: this.label
    });
  }
  /**
   * The position of the top-left hand corner of the window's client area relative to the top-left hand corner of the desktop.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const position = await getCurrentWindow().innerPosition();
   * ```
   *
   * @returns The window's inner position.
   */
  async innerPosition() {
    return invoke("plugin:window|inner_position", {
      label: this.label
    }).then((p) => new PhysicalPosition(p));
  }
  /**
   * The position of the top-left hand corner of the window relative to the top-left hand corner of the desktop.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const position = await getCurrentWindow().outerPosition();
   * ```
   *
   * @returns The window's outer position.
   */
  async outerPosition() {
    return invoke("plugin:window|outer_position", {
      label: this.label
    }).then((p) => new PhysicalPosition(p));
  }
  /**
   * The physical size of the window's client area.
   * The client area is the content of the window, excluding the title bar and borders.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const size = await getCurrentWindow().innerSize();
   * ```
   *
   * @returns The window's inner size.
   */
  async innerSize() {
    return invoke("plugin:window|inner_size", {
      label: this.label
    }).then((s) => new PhysicalSize(s));
  }
  /**
   * The physical size of the entire window.
   * These dimensions include the title bar and borders. If you don't want that (and you usually don't), use inner_size instead.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const size = await getCurrentWindow().outerSize();
   * ```
   *
   * @returns The window's outer size.
   */
  async outerSize() {
    return invoke("plugin:window|outer_size", {
      label: this.label
    }).then((s) => new PhysicalSize(s));
  }
  /**
   * Gets the window's current fullscreen state.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const fullscreen = await getCurrentWindow().isFullscreen();
   * ```
   *
   * @returns Whether the window is in fullscreen mode or not.
   */
  async isFullscreen() {
    return invoke("plugin:window|is_fullscreen", {
      label: this.label
    });
  }
  /**
   * Gets the window's current minimized state.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const minimized = await getCurrentWindow().isMinimized();
   * ```
   */
  async isMinimized() {
    return invoke("plugin:window|is_minimized", {
      label: this.label
    });
  }
  /**
   * Gets the window's current maximized state.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const maximized = await getCurrentWindow().isMaximized();
   * ```
   *
   * @returns Whether the window is maximized or not.
   */
  async isMaximized() {
    return invoke("plugin:window|is_maximized", {
      label: this.label
    });
  }
  /**
   * Gets the window's current focus state.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const focused = await getCurrentWindow().isFocused();
   * ```
   *
   * @returns Whether the window is focused or not.
   */
  async isFocused() {
    return invoke("plugin:window|is_focused", {
      label: this.label
    });
  }
  /**
   * Gets the window's current decorated state.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const decorated = await getCurrentWindow().isDecorated();
   * ```
   *
   * @returns Whether the window is decorated or not.
   */
  async isDecorated() {
    return invoke("plugin:window|is_decorated", {
      label: this.label
    });
  }
  /**
   * Gets the window's current resizable state.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const resizable = await getCurrentWindow().isResizable();
   * ```
   *
   * @returns Whether the window is resizable or not.
   */
  async isResizable() {
    return invoke("plugin:window|is_resizable", {
      label: this.label
    });
  }
  /**
   * Gets the window's native maximize button state.
   *
   * #### Platform-specific
   *
   * - **Linux / iOS / Android:** Unsupported.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const maximizable = await getCurrentWindow().isMaximizable();
   * ```
   *
   * @returns Whether the window's native maximize button is enabled or not.
   */
  async isMaximizable() {
    return invoke("plugin:window|is_maximizable", {
      label: this.label
    });
  }
  /**
   * Gets the window's native minimize button state.
   *
   * #### Platform-specific
   *
   * - **Linux / iOS / Android:** Unsupported.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const minimizable = await getCurrentWindow().isMinimizable();
   * ```
   *
   * @returns Whether the window's native minimize button is enabled or not.
   */
  async isMinimizable() {
    return invoke("plugin:window|is_minimizable", {
      label: this.label
    });
  }
  /**
   * Gets the window's native close button state.
   *
   * #### Platform-specific
   *
   * - **iOS / Android:** Unsupported.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const closable = await getCurrentWindow().isClosable();
   * ```
   *
   * @returns Whether the window's native close button is enabled or not.
   */
  async isClosable() {
    return invoke("plugin:window|is_closable", {
      label: this.label
    });
  }
  /**
   * Gets the window's current visible state.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const visible = await getCurrentWindow().isVisible();
   * ```
   *
   * @returns Whether the window is visible or not.
   */
  async isVisible() {
    return invoke("plugin:window|is_visible", {
      label: this.label
    });
  }
  /**
   * Gets the window's current title.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const title = await getCurrentWindow().title();
   * ```
   */
  async title() {
    return invoke("plugin:window|title", {
      label: this.label
    });
  }
  /**
   * Gets the window's current theme.
   *
   * #### Platform-specific
   *
   * - **macOS:** Theme was introduced on macOS 10.14. Returns `light` on macOS 10.13 and below.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const theme = await getCurrentWindow().theme();
   * ```
   *
   * @returns The window theme.
   */
  async theme() {
    return invoke("plugin:window|theme", {
      label: this.label
    });
  }
  /**
   * Whether the window is configured to be always on top of other windows or not.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * const alwaysOnTop = await getCurrentWindow().isAlwaysOnTop();
   * ```
   *
   * @returns Whether the window is visible or not.
   */
  async isAlwaysOnTop() {
    return invoke("plugin:window|is_always_on_top", {
      label: this.label
    });
  }
  // Setters
  /**
   * Centers the window.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().center();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async center() {
    return invoke("plugin:window|center", {
      label: this.label
    });
  }
  /**
   *  Requests user attention to the window, this has no effect if the application
   * is already focused. How requesting for user attention manifests is platform dependent,
   * see `UserAttentionType` for details.
   *
   * Providing `null` will unset the request for user attention. Unsetting the request for
   * user attention might not be done automatically by the WM when the window receives input.
   *
   * #### Platform-specific
   *
   * - **macOS:** `null` has no effect.
   * - **Linux:** Urgency levels have the same effect.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().requestUserAttention();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async requestUserAttention(requestType) {
    let requestType_ = null;
    if (requestType) {
      if (requestType === UserAttentionType.Critical) {
        requestType_ = { type: "Critical" };
      } else {
        requestType_ = { type: "Informational" };
      }
    }
    return invoke("plugin:window|request_user_attention", {
      label: this.label,
      value: requestType_
    });
  }
  /**
   * Updates the window resizable flag.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setResizable(false);
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async setResizable(resizable) {
    return invoke("plugin:window|set_resizable", {
      label: this.label,
      value: resizable
    });
  }
  /**
   * Enable or disable the window.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setEnabled(false);
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   *
   * @since 2.0.0
   */
  async setEnabled(enabled) {
    return invoke("plugin:window|set_enabled", {
      label: this.label,
      value: enabled
    });
  }
  /**
   * Whether the window is enabled or disabled.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setEnabled(false);
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   *
   * @since 2.0.0
   */
  async isEnabled() {
    return invoke("plugin:window|is_enabled", {
      label: this.label
    });
  }
  /**
   * Sets whether the window's native maximize button is enabled or not.
   * If resizable is set to false, this setting is ignored.
   *
   * #### Platform-specific
   *
   * - **macOS:** Disables the "zoom" button in the window titlebar, which is also used to enter fullscreen mode.
   * - **Linux / iOS / Android:** Unsupported.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setMaximizable(false);
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async setMaximizable(maximizable) {
    return invoke("plugin:window|set_maximizable", {
      label: this.label,
      value: maximizable
    });
  }
  /**
   * Sets whether the window's native minimize button is enabled or not.
   *
   * #### Platform-specific
   *
   * - **Linux / iOS / Android:** Unsupported.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setMinimizable(false);
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async setMinimizable(minimizable) {
    return invoke("plugin:window|set_minimizable", {
      label: this.label,
      value: minimizable
    });
  }
  /**
   * Sets whether the window's native close button is enabled or not.
   *
   * #### Platform-specific
   *
   * - **Linux:** GTK+ will do its best to convince the window manager not to show a close button. Depending on the system, this function may not have any effect when called on a window that is already visible
   * - **iOS / Android:** Unsupported.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setClosable(false);
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async setClosable(closable) {
    return invoke("plugin:window|set_closable", {
      label: this.label,
      value: closable
    });
  }
  /**
   * Sets the window title.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setTitle('Tauri');
   * ```
   *
   * @param title The new title
   * @returns A promise indicating the success or failure of the operation.
   */
  async setTitle(title) {
    return invoke("plugin:window|set_title", {
      label: this.label,
      value: title
    });
  }
  /**
   * Maximizes the window.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().maximize();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async maximize() {
    return invoke("plugin:window|maximize", {
      label: this.label
    });
  }
  /**
   * Unmaximizes the window.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().unmaximize();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async unmaximize() {
    return invoke("plugin:window|unmaximize", {
      label: this.label
    });
  }
  /**
   * Toggles the window maximized state.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().toggleMaximize();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async toggleMaximize() {
    return invoke("plugin:window|toggle_maximize", {
      label: this.label
    });
  }
  /**
   * Minimizes the window.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().minimize();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async minimize() {
    return invoke("plugin:window|minimize", {
      label: this.label
    });
  }
  /**
   * Unminimizes the window.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().unminimize();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async unminimize() {
    return invoke("plugin:window|unminimize", {
      label: this.label
    });
  }
  /**
   * Sets the window visibility to true.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().show();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async show() {
    return invoke("plugin:window|show", {
      label: this.label
    });
  }
  /**
   * Sets the window visibility to false.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().hide();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async hide() {
    return invoke("plugin:window|hide", {
      label: this.label
    });
  }
  /**
   * Closes the window.
   *
   * Note this emits a closeRequested event so you can intercept it. To force window close, use {@link Window.destroy}.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().close();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async close() {
    return invoke("plugin:window|close", {
      label: this.label
    });
  }
  /**
   * Destroys the window. Behaves like {@link Window.close} but forces the window close instead of emitting a closeRequested event.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().destroy();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async destroy() {
    return invoke("plugin:window|destroy", {
      label: this.label
    });
  }
  /**
   * Whether the window should have borders and bars.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setDecorations(false);
   * ```
   *
   * @param decorations Whether the window should have borders and bars.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setDecorations(decorations) {
    return invoke("plugin:window|set_decorations", {
      label: this.label,
      value: decorations
    });
  }
  /**
   * Whether or not the window should have shadow.
   *
   * #### Platform-specific
   *
   * - **Windows:**
   *   - `false` has no effect on decorated window, shadows are always ON.
   *   - `true` will make undecorated window have a 1px white border,
   * and on Windows 11, it will have a rounded corners.
   * - **Linux:** Unsupported.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setShadow(false);
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async setShadow(enable) {
    return invoke("plugin:window|set_shadow", {
      label: this.label,
      value: enable
    });
  }
  /**
   * Set window effects.
   */
  async setEffects(effects) {
    return invoke("plugin:window|set_effects", {
      label: this.label,
      value: effects
    });
  }
  /**
   * Clear any applied effects if possible.
   */
  async clearEffects() {
    return invoke("plugin:window|set_effects", {
      label: this.label,
      value: null
    });
  }
  /**
   * Whether the window should always be on top of other windows.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setAlwaysOnTop(true);
   * ```
   *
   * @param alwaysOnTop Whether the window should always be on top of other windows or not.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setAlwaysOnTop(alwaysOnTop) {
    return invoke("plugin:window|set_always_on_top", {
      label: this.label,
      value: alwaysOnTop
    });
  }
  /**
   * Whether the window should always be below other windows.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setAlwaysOnBottom(true);
   * ```
   *
   * @param alwaysOnBottom Whether the window should always be below other windows or not.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setAlwaysOnBottom(alwaysOnBottom) {
    return invoke("plugin:window|set_always_on_bottom", {
      label: this.label,
      value: alwaysOnBottom
    });
  }
  /**
   * Prevents the window contents from being captured by other apps.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setContentProtected(true);
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async setContentProtected(protected_) {
    return invoke("plugin:window|set_content_protected", {
      label: this.label,
      value: protected_
    });
  }
  /**
   * Resizes the window with a new inner size.
   * @example
   * ```typescript
   * import { getCurrentWindow, LogicalSize } from '@tauri-apps/api/window';
   * await getCurrentWindow().setSize(new LogicalSize(600, 500));
   * ```
   *
   * @param size The logical or physical inner size.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setSize(size) {
    return invoke("plugin:window|set_size", {
      label: this.label,
      value: size instanceof Size ? size : new Size(size)
    });
  }
  /**
   * Sets the window minimum inner size. If the `size` argument is not provided, the constraint is unset.
   * @example
   * ```typescript
   * import { getCurrentWindow, PhysicalSize } from '@tauri-apps/api/window';
   * await getCurrentWindow().setMinSize(new PhysicalSize(600, 500));
   * ```
   *
   * @param size The logical or physical inner size, or `null` to unset the constraint.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setMinSize(size) {
    return invoke("plugin:window|set_min_size", {
      label: this.label,
      value: size instanceof Size ? size : size ? new Size(size) : null
    });
  }
  /**
   * Sets the window maximum inner size. If the `size` argument is undefined, the constraint is unset.
   * @example
   * ```typescript
   * import { getCurrentWindow, LogicalSize } from '@tauri-apps/api/window';
   * await getCurrentWindow().setMaxSize(new LogicalSize(600, 500));
   * ```
   *
   * @param size The logical or physical inner size, or `null` to unset the constraint.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setMaxSize(size) {
    return invoke("plugin:window|set_max_size", {
      label: this.label,
      value: size instanceof Size ? size : size ? new Size(size) : null
    });
  }
  /**
   * Sets the window inner size constraints.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setSizeConstraints({ minWidth: 300 });
   * ```
   *
   * @param constraints The logical or physical inner size, or `null` to unset the constraint.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setSizeConstraints(constraints) {
    function logical(pixel) {
      return pixel ? { Logical: pixel } : null;
    }
    return invoke("plugin:window|set_size_constraints", {
      label: this.label,
      value: {
        minWidth: logical(constraints === null || constraints === void 0 ? void 0 : constraints.minWidth),
        minHeight: logical(constraints === null || constraints === void 0 ? void 0 : constraints.minHeight),
        maxWidth: logical(constraints === null || constraints === void 0 ? void 0 : constraints.maxWidth),
        maxHeight: logical(constraints === null || constraints === void 0 ? void 0 : constraints.maxHeight)
      }
    });
  }
  /**
   * Sets the window outer position.
   * @example
   * ```typescript
   * import { getCurrentWindow, LogicalPosition } from '@tauri-apps/api/window';
   * await getCurrentWindow().setPosition(new LogicalPosition(600, 500));
   * ```
   *
   * @param position The new position, in logical or physical pixels.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setPosition(position) {
    return invoke("plugin:window|set_position", {
      label: this.label,
      value: position instanceof Position ? position : new Position(position)
    });
  }
  /**
   * Sets the window fullscreen state.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setFullscreen(true);
   * ```
   *
   * @param fullscreen Whether the window should go to fullscreen or not.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setFullscreen(fullscreen) {
    return invoke("plugin:window|set_fullscreen", {
      label: this.label,
      value: fullscreen
    });
  }
  /**
   * On macOS, Toggles a fullscreen mode that doesn’t require a new macOS space. Returns a boolean indicating whether the transition was successful (this won’t work if the window was already in the native fullscreen).
   * This is how fullscreen used to work on macOS in versions before Lion. And allows the user to have a fullscreen window without using another space or taking control over the entire monitor.
   *
   * On other platforms, this is the same as {@link Window.setFullscreen}.
   *
   * @param fullscreen Whether the window should go to simple fullscreen or not.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setSimpleFullscreen(fullscreen) {
    return invoke("plugin:window|set_simple_fullscreen", {
      label: this.label,
      value: fullscreen
    });
  }
  /**
   * Bring the window to front and focus.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setFocus();
   * ```
   *
   * @returns A promise indicating the success or failure of the operation.
   */
  async setFocus() {
    return invoke("plugin:window|set_focus", {
      label: this.label
    });
  }
  /**
   * Sets whether the window can be focused.
   *
   * #### Platform-specific
   *
   * - **macOS**: If the window is already focused, it is not possible to unfocus it after calling `set_focusable(false)`.
   *   In this case, you might consider calling {@link Window.setFocus} but it will move the window to the back i.e. at the bottom in terms of z-order.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setFocusable(true);
   * ```
   *
   * @param focusable Whether the window can be focused.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setFocusable(focusable) {
    return invoke("plugin:window|set_focusable", {
      label: this.label,
      value: focusable
    });
  }
  /**
   * Sets the window icon.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setIcon('/tauri/awesome.png');
   * ```
   *
   * Note that you may need the `image-ico` or `image-png` Cargo features to use this API.
   * To enable it, change your Cargo.toml file:
   * ```toml
   * [dependencies]
   * tauri = { version = "...", features = ["...", "image-png"] }
   * ```
   *
   * @param icon Icon bytes or path to the icon file.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setIcon(icon) {
    return invoke("plugin:window|set_icon", {
      label: this.label,
      value: transformImage(icon)
    });
  }
  /**
   * Whether the window icon should be hidden from the taskbar or not.
   *
   * #### Platform-specific
   *
   * - **macOS:** Unsupported.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setSkipTaskbar(true);
   * ```
   *
   * @param skip true to hide window icon, false to show it.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setSkipTaskbar(skip) {
    return invoke("plugin:window|set_skip_taskbar", {
      label: this.label,
      value: skip
    });
  }
  /**
   * Grabs the cursor, preventing it from leaving the window.
   *
   * There's no guarantee that the cursor will be hidden. You should
   * hide it by yourself if you want so.
   *
   * #### Platform-specific
   *
   * - **Linux:** Unsupported.
   * - **macOS:** This locks the cursor in a fixed location, which looks visually awkward.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setCursorGrab(true);
   * ```
   *
   * @param grab `true` to grab the cursor icon, `false` to release it.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setCursorGrab(grab) {
    return invoke("plugin:window|set_cursor_grab", {
      label: this.label,
      value: grab
    });
  }
  /**
   * Modifies the cursor's visibility.
   *
   * #### Platform-specific
   *
   * - **Windows:** The cursor is only hidden within the confines of the window.
   * - **macOS:** The cursor is hidden as long as the window has input focus, even if the cursor is
   *   outside of the window.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setCursorVisible(false);
   * ```
   *
   * @param visible If `false`, this will hide the cursor. If `true`, this will show the cursor.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setCursorVisible(visible) {
    return invoke("plugin:window|set_cursor_visible", {
      label: this.label,
      value: visible
    });
  }
  /**
   * Modifies the cursor icon of the window.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setCursorIcon('help');
   * ```
   *
   * @param icon The new cursor icon.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setCursorIcon(icon) {
    return invoke("plugin:window|set_cursor_icon", {
      label: this.label,
      value: icon
    });
  }
  /**
   * Sets the window background color.
   *
   * #### Platform-specific:
   *
   * - **Windows:** alpha channel is ignored.
   * - **iOS / Android:** Unsupported.
   *
   * @returns A promise indicating the success or failure of the operation.
   *
   * @since 2.1.0
   */
  async setBackgroundColor(color) {
    return invoke("plugin:window|set_background_color", { color });
  }
  /**
   * Changes the position of the cursor in window coordinates.
   * @example
   * ```typescript
   * import { getCurrentWindow, LogicalPosition } from '@tauri-apps/api/window';
   * await getCurrentWindow().setCursorPosition(new LogicalPosition(600, 300));
   * ```
   *
   * @param position The new cursor position.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setCursorPosition(position) {
    return invoke("plugin:window|set_cursor_position", {
      label: this.label,
      value: position instanceof Position ? position : new Position(position)
    });
  }
  /**
   * Changes the cursor events behavior.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setIgnoreCursorEvents(true);
   * ```
   *
   * @param ignore `true` to ignore the cursor events; `false` to process them as usual.
   * @returns A promise indicating the success or failure of the operation.
   */
  async setIgnoreCursorEvents(ignore) {
    return invoke("plugin:window|set_ignore_cursor_events", {
      label: this.label,
      value: ignore
    });
  }
  /**
   * Starts dragging the window.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().startDragging();
   * ```
   *
   * @return A promise indicating the success or failure of the operation.
   */
  async startDragging() {
    return invoke("plugin:window|start_dragging", {
      label: this.label
    });
  }
  /**
   * Starts resize-dragging the window.
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().startResizeDragging();
   * ```
   *
   * @return A promise indicating the success or failure of the operation.
   */
  async startResizeDragging(direction) {
    return invoke("plugin:window|start_resize_dragging", {
      label: this.label,
      value: direction
    });
  }
  /**
   * Sets the badge count. It is app wide and not specific to this window.
   *
   * #### Platform-specific
   *
   * - **Windows**: Unsupported. Use @{linkcode Window.setOverlayIcon} instead.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setBadgeCount(5);
   * ```
   *
   * @param count The badge count. Use `undefined` to remove the badge.
   * @return A promise indicating the success or failure of the operation.
   */
  async setBadgeCount(count) {
    return invoke("plugin:window|set_badge_count", {
      label: this.label,
      value: count
    });
  }
  /**
   * Sets the badge cont **macOS only**.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setBadgeLabel("Hello");
   * ```
   *
   * @param label The badge label. Use `undefined` to remove the badge.
   * @return A promise indicating the success or failure of the operation.
   */
  async setBadgeLabel(label) {
    return invoke("plugin:window|set_badge_label", {
      label: this.label,
      value: label
    });
  }
  /**
   * Sets the overlay icon. **Windows only**
   * The overlay icon can be set for every window.
   *
   *
   * Note that you may need the `image-ico` or `image-png` Cargo features to use this API.
   * To enable it, change your Cargo.toml file:
   *
   * ```toml
   * [dependencies]
   * tauri = { version = "...", features = ["...", "image-png"] }
   * ```
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from '@tauri-apps/api/window';
   * await getCurrentWindow().setOverlayIcon("/tauri/awesome.png");
   * ```
   *
   * @param icon Icon bytes or path to the icon file. Use `undefined` to remove the overlay icon.
   * @return A promise indicating the success or failure of the operation.
   */
  async setOverlayIcon(icon) {
    return invoke("plugin:window|set_overlay_icon", {
      label: this.label,
      value: icon ? transformImage(icon) : void 0
    });
  }
  /**
   * Sets the taskbar progress state.
   *
   * #### Platform-specific
   *
   * - **Linux / macOS**: Progress bar is app-wide and not specific to this window.
   * - **Linux**: Only supported desktop environments with `libunity` (e.g. GNOME).
   *
   * @example
   * ```typescript
   * import { getCurrentWindow, ProgressBarStatus } from '@tauri-apps/api/window';
   * await getCurrentWindow().setProgressBar({
   *   status: ProgressBarStatus.Normal,
   *   progress: 50,
   * });
   * ```
   *
   * @return A promise indicating the success or failure of the operation.
   */
  async setProgressBar(state2) {
    return invoke("plugin:window|set_progress_bar", {
      label: this.label,
      value: state2
    });
  }
  /**
   * Sets whether the window should be visible on all workspaces or virtual desktops.
   *
   * #### Platform-specific
   *
   * - **Windows / iOS / Android:** Unsupported.
   *
   * @since 2.0.0
   */
  async setVisibleOnAllWorkspaces(visible) {
    return invoke("plugin:window|set_visible_on_all_workspaces", {
      label: this.label,
      value: visible
    });
  }
  /**
   * Sets the title bar style. **macOS only**.
   *
   * @since 2.0.0
   */
  async setTitleBarStyle(style) {
    return invoke("plugin:window|set_title_bar_style", {
      label: this.label,
      value: style
    });
  }
  /**
   * Set window theme, pass in `null` or `undefined` to follow system theme
   *
   * #### Platform-specific
   *
   * - **Linux / macOS**: Theme is app-wide and not specific to this window.
   * - **iOS / Android:** Unsupported.
   *
   * @since 2.0.0
   */
  async setTheme(theme) {
    return invoke("plugin:window|set_theme", {
      label: this.label,
      value: theme
    });
  }
  // Listeners
  /**
   * Listen to window resize.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from "@tauri-apps/api/window";
   * const unlisten = await getCurrentWindow().onResized(({ payload: size }) => {
   *  console.log('Window resized', size);
   * });
   *
   * // you need to call unlisten if your handler goes out of scope e.g. the component is unmounted
   * unlisten();
   * ```
   *
   * @returns A promise resolving to a function to unlisten to the event.
   * Note that removing the listener is required if your listener goes out of scope e.g. the component is unmounted.
   */
  async onResized(handler) {
    return this.listen(TauriEvent.WINDOW_RESIZED, (e) => {
      e.payload = new PhysicalSize(e.payload);
      handler(e);
    });
  }
  /**
   * Listen to window move.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from "@tauri-apps/api/window";
   * const unlisten = await getCurrentWindow().onMoved(({ payload: position }) => {
   *  console.log('Window moved', position);
   * });
   *
   * // you need to call unlisten if your handler goes out of scope e.g. the component is unmounted
   * unlisten();
   * ```
   *
   * @returns A promise resolving to a function to unlisten to the event.
   * Note that removing the listener is required if your listener goes out of scope e.g. the component is unmounted.
   */
  async onMoved(handler) {
    return this.listen(TauriEvent.WINDOW_MOVED, (e) => {
      e.payload = new PhysicalPosition(e.payload);
      handler(e);
    });
  }
  /**
   * Listen to window close requested. Emitted when the user requests to closes the window.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from "@tauri-apps/api/window";
   * import { confirm } from '@tauri-apps/api/dialog';
   * const unlisten = await getCurrentWindow().onCloseRequested(async (event) => {
   *   const confirmed = await confirm('Are you sure?');
   *   if (!confirmed) {
   *     // user did not confirm closing the window; let's prevent it
   *     event.preventDefault();
   *   }
   * });
   *
   * // you need to call unlisten if your handler goes out of scope e.g. the component is unmounted
   * unlisten();
   * ```
   *
   * @returns A promise resolving to a function to unlisten to the event.
   * Note that removing the listener is required if your listener goes out of scope e.g. the component is unmounted.
   */
  async onCloseRequested(handler) {
    return this.listen(TauriEvent.WINDOW_CLOSE_REQUESTED, async (event) => {
      const evt = new CloseRequestedEvent(event);
      await handler(evt);
      if (!evt.isPreventDefault()) {
        await this.destroy();
      }
    });
  }
  /**
   * Listen to a file drop event.
   * The listener is triggered when the user hovers the selected files on the webview,
   * drops the files or cancels the operation.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from "@tauri-apps/api/webview";
   * const unlisten = await getCurrentWindow().onDragDropEvent((event) => {
   *  if (event.payload.type === 'over') {
   *    console.log('User hovering', event.payload.position);
   *  } else if (event.payload.type === 'drop') {
   *    console.log('User dropped', event.payload.paths);
   *  } else {
   *    console.log('File drop cancelled');
   *  }
   * });
   *
   * // you need to call unlisten if your handler goes out of scope e.g. the component is unmounted
   * unlisten();
   * ```
   *
   * @returns A promise resolving to a function to unlisten to the event.
   * Note that removing the listener is required if your listener goes out of scope e.g. the component is unmounted.
   */
  async onDragDropEvent(handler) {
    const unlistenDrag = await this.listen(TauriEvent.DRAG_ENTER, (event) => {
      handler({
        ...event,
        payload: {
          type: "enter",
          paths: event.payload.paths,
          position: new PhysicalPosition(event.payload.position)
        }
      });
    });
    const unlistenDragOver = await this.listen(TauriEvent.DRAG_OVER, (event) => {
      handler({
        ...event,
        payload: {
          type: "over",
          position: new PhysicalPosition(event.payload.position)
        }
      });
    });
    const unlistenDrop = await this.listen(TauriEvent.DRAG_DROP, (event) => {
      handler({
        ...event,
        payload: {
          type: "drop",
          paths: event.payload.paths,
          position: new PhysicalPosition(event.payload.position)
        }
      });
    });
    const unlistenCancel = await this.listen(TauriEvent.DRAG_LEAVE, (event) => {
      handler({ ...event, payload: { type: "leave" } });
    });
    return () => {
      unlistenDrag();
      unlistenDrop();
      unlistenDragOver();
      unlistenCancel();
    };
  }
  /**
   * Listen to window focus change.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from "@tauri-apps/api/window";
   * const unlisten = await getCurrentWindow().onFocusChanged(({ payload: focused }) => {
   *  console.log('Focus changed, window is focused? ' + focused);
   * });
   *
   * // you need to call unlisten if your handler goes out of scope e.g. the component is unmounted
   * unlisten();
   * ```
   *
   * @returns A promise resolving to a function to unlisten to the event.
   * Note that removing the listener is required if your listener goes out of scope e.g. the component is unmounted.
   */
  async onFocusChanged(handler) {
    const unlistenFocus = await this.listen(TauriEvent.WINDOW_FOCUS, (event) => {
      handler({ ...event, payload: true });
    });
    const unlistenBlur = await this.listen(TauriEvent.WINDOW_BLUR, (event) => {
      handler({ ...event, payload: false });
    });
    return () => {
      unlistenFocus();
      unlistenBlur();
    };
  }
  /**
   * Listen to window scale change. Emitted when the window's scale factor has changed.
   * The following user actions can cause DPI changes:
   * - Changing the display's resolution.
   * - Changing the display's scale factor (e.g. in Control Panel on Windows).
   * - Moving the window to a display with a different scale factor.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from "@tauri-apps/api/window";
   * const unlisten = await getCurrentWindow().onScaleChanged(({ payload }) => {
   *  console.log('Scale changed', payload.scaleFactor, payload.size);
   * });
   *
   * // you need to call unlisten if your handler goes out of scope e.g. the component is unmounted
   * unlisten();
   * ```
   *
   * @returns A promise resolving to a function to unlisten to the event.
   * Note that removing the listener is required if your listener goes out of scope e.g. the component is unmounted.
   */
  async onScaleChanged(handler) {
    return this.listen(TauriEvent.WINDOW_SCALE_FACTOR_CHANGED, handler);
  }
  /**
   * Listen to the system theme change.
   *
   * @example
   * ```typescript
   * import { getCurrentWindow } from "@tauri-apps/api/window";
   * const unlisten = await getCurrentWindow().onThemeChanged(({ payload: theme }) => {
   *  console.log('New theme: ' + theme);
   * });
   *
   * // you need to call unlisten if your handler goes out of scope e.g. the component is unmounted
   * unlisten();
   * ```
   *
   * @returns A promise resolving to a function to unlisten to the event.
   * Note that removing the listener is required if your listener goes out of scope e.g. the component is unmounted.
   */
  async onThemeChanged(handler) {
    return this.listen(TauriEvent.WINDOW_THEME_CHANGED, handler);
  }
};
var BackgroundThrottlingPolicy;
(function(BackgroundThrottlingPolicy2) {
  BackgroundThrottlingPolicy2["Disabled"] = "disabled";
  BackgroundThrottlingPolicy2["Throttle"] = "throttle";
  BackgroundThrottlingPolicy2["Suspend"] = "suspend";
})(BackgroundThrottlingPolicy || (BackgroundThrottlingPolicy = {}));
var ScrollBarStyle;
(function(ScrollBarStyle2) {
  ScrollBarStyle2["Default"] = "default";
  ScrollBarStyle2["FluentOverlay"] = "fluentOverlay";
})(ScrollBarStyle || (ScrollBarStyle = {}));
var Effect;
(function(Effect2) {
  Effect2["AppearanceBased"] = "appearanceBased";
  Effect2["Light"] = "light";
  Effect2["Dark"] = "dark";
  Effect2["MediumLight"] = "mediumLight";
  Effect2["UltraDark"] = "ultraDark";
  Effect2["Titlebar"] = "titlebar";
  Effect2["Selection"] = "selection";
  Effect2["Menu"] = "menu";
  Effect2["Popover"] = "popover";
  Effect2["Sidebar"] = "sidebar";
  Effect2["HeaderView"] = "headerView";
  Effect2["Sheet"] = "sheet";
  Effect2["WindowBackground"] = "windowBackground";
  Effect2["HudWindow"] = "hudWindow";
  Effect2["FullScreenUI"] = "fullScreenUI";
  Effect2["Tooltip"] = "tooltip";
  Effect2["ContentBackground"] = "contentBackground";
  Effect2["UnderWindowBackground"] = "underWindowBackground";
  Effect2["UnderPageBackground"] = "underPageBackground";
  Effect2["Mica"] = "mica";
  Effect2["Blur"] = "blur";
  Effect2["Acrylic"] = "acrylic";
  Effect2["Tabbed"] = "tabbed";
  Effect2["TabbedDark"] = "tabbedDark";
  Effect2["TabbedLight"] = "tabbedLight";
})(Effect || (Effect = {}));
var EffectState;
(function(EffectState2) {
  EffectState2["FollowsWindowActiveState"] = "followsWindowActiveState";
  EffectState2["Active"] = "active";
  EffectState2["Inactive"] = "inactive";
})(EffectState || (EffectState = {}));

// node_modules/exifreader/src/dataview.js
var DataView2 = class {
  constructor(buffer) {
    if (bufferTypeIsUnsupported(buffer)) {
      throw new Error("DataView: Passed buffer type is unsupported.");
    }
    this.buffer = buffer;
    this.byteLength = this.buffer.length;
  }
  getUint8(offset) {
    return this.buffer.readUInt8(offset);
  }
  getUint16(offset, littleEndian) {
    if (littleEndian) {
      return this.buffer.readUInt16LE(offset);
    }
    return this.buffer.readUInt16BE(offset);
  }
  getUint32(offset, littleEndian) {
    if (littleEndian) {
      return this.buffer.readUInt32LE(offset);
    }
    return this.buffer.readUInt32BE(offset);
  }
  getInt32(offset, littleEndian) {
    if (littleEndian) {
      return this.buffer.readInt32LE(offset);
    }
    return this.buffer.readInt32BE(offset);
  }
};
function bufferTypeIsUnsupported(buffer) {
  return typeof buffer !== "object" || buffer.length === void 0 || buffer.readUInt8 === void 0 || buffer.readUInt16LE === void 0 || buffer.readUInt16BE === void 0 || buffer.readUInt32LE === void 0 || buffer.readUInt32BE === void 0 || buffer.readInt32LE === void 0 || buffer.readInt32BE === void 0;
}

// node_modules/exifreader/src/utils.js
function getDataView(data, byteOffset, byteLength) {
  try {
    return new DataView(data, byteOffset, byteLength);
  } catch (error) {
    return new DataView2(data, byteOffset, byteLength);
  }
}
function getStringFromDataView(dataView, offset, length) {
  const chars = [];
  for (let i = 0; i < length && offset + i < dataView.byteLength; i++) {
    chars.push(dataView.getUint8(offset + i));
  }
  return getStringValueFromArray(chars);
}
function getNullTerminatedStringFromDataView(dataView, offset) {
  const chars = [];
  let i = 0;
  while (offset + i < dataView.byteLength) {
    const char = dataView.getUint8(offset + i);
    if (char === 0) {
      break;
    }
    chars.push(char);
    i++;
  }
  return getStringValueFromArray(chars);
}
function getUnicodeStringFromDataView(dataView, offset, length) {
  const chars = [];
  for (let i = 0; i < length && offset + i < dataView.byteLength; i += 2) {
    chars.push(dataView.getUint16(offset + i));
  }
  if (chars[chars.length - 1] === 0) {
    chars.pop();
  }
  return getStringValueFromArray(chars);
}
function getPascalStringFromDataView(dataView, offset) {
  const size = dataView.getUint8(offset);
  const string = getStringFromDataView(dataView, offset + 1, size);
  return [size, string];
}
function getStringValueFromArray(charArray) {
  return charArray.map((charCode) => String.fromCharCode(charCode)).join("");
}
function objectAssign() {
  for (let i = 1; i < arguments.length; i++) {
    for (const property in arguments[i]) {
      arguments[0][property] = arguments[i][property];
    }
  }
  return arguments[0];
}
function deferInit(object, key, initializer) {
  let initialized = false;
  Object.defineProperty(object, key, {
    get() {
      if (!initialized) {
        initialized = true;
        Object.defineProperty(object, key, {
          configurable: true,
          enumerable: true,
          value: initializer.apply(object),
          writable: true
        });
      }
      return object[key];
    },
    configurable: true,
    enumerable: true
  });
}
function getBase64Image(image) {
  if (typeof btoa !== "undefined") {
    if (typeof image === "string") {
      return btoa(image);
    }
    return btoa(Array.prototype.reduce.call(new Uint8Array(image), (data, byte) => data + String.fromCharCode(byte), ""));
  }
  if (typeof Buffer === "undefined") {
    return void 0;
  }
  if (typeof Buffer.from !== "undefined") {
    return Buffer.from(image).toString("base64");
  }
  return new Buffer(image).toString("base64");
}
function dataUriToBuffer(dataUri) {
  const data = dataUri.substring(dataUri.indexOf(",") + 1);
  if (dataUri.indexOf(";base64") !== -1) {
    if (typeof atob !== "undefined") {
      return Uint8Array.from(atob(data), (char) => char.charCodeAt(0)).buffer;
    }
    if (typeof Buffer === "undefined") {
      return void 0;
    }
    if (typeof Buffer.from !== "undefined") {
      return Buffer.from(data, "base64");
    }
    return new Buffer(data, "base64");
  }
  const decodedData = decodeURIComponent(data);
  if (typeof Buffer !== "undefined") {
    if (typeof Buffer.from !== "undefined") {
      return Buffer.from(decodedData);
    }
    return new Buffer(decodedData);
  }
  return Uint8Array.from(decodedData, (char) => char.charCodeAt(0)).buffer;
}
function padStart(string, length, character) {
  const padding = strRepeat(character, length - string.length);
  return padding + string;
}
function parseFloatRadix(string, radix) {
  return parseInt(string.replace(".", ""), radix) / Math.pow(radix, (string.split(".")[1] || "").length);
}
function strRepeat(string, num) {
  return new Array(num + 1).join(string);
}
var COMPRESSION_METHOD_NONE = void 0;
var COMPRESSION_METHOD_DEFLATE = 0;
function decompress(dataView, compressionMethod, encoding, returnType = "string") {
  if (compressionMethod === COMPRESSION_METHOD_DEFLATE) {
    if (typeof DecompressionStream === "function") {
      const decompressionStream = new DecompressionStream("deflate");
      const decompressedStream = new Blob([dataView]).stream().pipeThrough(decompressionStream);
      if (returnType === "dataview") {
        return new Response(decompressedStream).arrayBuffer().then((arrayBuffer) => new DataView(arrayBuffer));
      }
      return new Response(decompressedStream).arrayBuffer().then((buffer) => new TextDecoder(encoding).decode(buffer));
    }
  }
  if (compressionMethod !== void 0) {
    return Promise.reject(`Unknown compression method ${compressionMethod}.`);
  }
  return dataView;
}

// node_modules/exifreader/src/constants.js
var constants_default = {
  USE_FILE: true,
  USE_JFIF: true,
  USE_PNG_FILE: true,
  USE_EXIF: true,
  USE_IPTC: true,
  USE_XMP: true,
  USE_ICC: true,
  USE_MPF: true,
  USE_PHOTOSHOP: true,
  USE_THUMBNAIL: true,
  USE_TIFF: true,
  USE_JPEG: true,
  USE_PNG: true,
  USE_HEIC: true,
  USE_AVIF: true,
  USE_WEBP: true,
  USE_GIF: true,
  USE_MAKER_NOTES: true
};

// node_modules/exifreader/src/tag-names-utils.js
function getStringValue(value) {
  return value.map((charCode) => String.fromCharCode(charCode)).join("");
}
function getEncodedString(value) {
  if (value.length >= 8) {
    const encoding = getStringValue(value.slice(0, 8));
    if (encoding === "ASCII\0\0\0") {
      return getStringValue(value.slice(8));
    } else if (encoding === "JIS\0\0\0\0\0") {
      return "[JIS encoded text]";
    } else if (encoding === "UNICODE\0") {
      return "[Unicode encoded text]";
    } else if (encoding === "\0\0\0\0\0\0\0\0") {
      return "[Undefined encoding]";
    }
  }
  return "Undefined";
}
function getCalculatedGpsValue(value) {
  return value[0][0] / value[0][1] + value[1][0] / value[1][1] / 60 + value[2][0] / value[2][1] / 3600;
}

// node_modules/exifreader/src/byte-order.js
var LITTLE_ENDIAN = 18761;
var BIG_ENDIAN = 19789;
var byte_order_default = {
  BIG_ENDIAN,
  LITTLE_ENDIAN,
  getByteOrder
};
function getByteOrder(dataView, tiffHeaderOffset) {
  if (dataView.getUint16(tiffHeaderOffset) === LITTLE_ENDIAN) {
    return LITTLE_ENDIAN;
  } else if (dataView.getUint16(tiffHeaderOffset) === BIG_ENDIAN) {
    return BIG_ENDIAN;
  }
  throw new Error("Illegal byte order value. Faulty image.");
}

// node_modules/exifreader/src/tiff-constants.js
var TIFF_BYTE_ORDER_OFFSET = 0;
var TIFF_ID_OFFSET = 2;
var TIFF_IFD_OFFSET_OFFSET = 4;
var TIFF_HEADER_LENGTH = 8;
var TIFF_ID = 42;
var IFD_ENTRY_COUNT_LENGTH = 2;
var IFD_ENTRY_LENGTH = 12;
var NEXT_IFD_POINTER_LENGTH = 4;

// node_modules/exifreader/src/image-header-tiff.js
var image_header_tiff_default = {
  isTiffFile,
  findTiffOffsets
};
function isTiffFile(dataView) {
  const MIN_TIFF_DATA_BUFFER_LENGTH = 4;
  return !!dataView && dataView.byteLength >= MIN_TIFF_DATA_BUFFER_LENGTH && hasTiffMarker(dataView);
}
function hasTiffMarker(dataView) {
  const littleEndian = dataView.getUint16(0) === byte_order_default.LITTLE_ENDIAN;
  return dataView.getUint16(TIFF_ID_OFFSET, littleEndian) === TIFF_ID;
}
function findTiffOffsets() {
  const TIFF_FILE_HEADER_OFFSET = 0;
  if (constants_default.USE_EXIF) {
    return {
      hasAppMarkers: true,
      tiffHeaderOffset: TIFF_FILE_HEADER_OFFSET
    };
  }
  return {};
}

// node_modules/exifreader/src/image-header-jpeg.js
var image_header_jpeg_default = {
  isJpegFile,
  findJpegOffsets
};
var MIN_JPEG_DATA_BUFFER_LENGTH = 2;
var JPEG_ID = 65496;
var JPEG_ID_SIZE = 2;
var APP_ID_OFFSET = 4;
var APP_MARKER_SIZE = 2;
var JFIF_DATA_OFFSET = 2;
var TIFF_HEADER_OFFSET = 10;
var IPTC_DATA_OFFSET = 18;
var XMP_DATA_OFFSET = 33;
var XMP_EXTENDED_DATA_OFFSET = 79;
var APP2_ICC_DATA_OFFSET = 18;
var MPF_DATA_OFFSET = 8;
var APP2_ICC_IDENTIFIER = "ICC_PROFILE\0";
var ICC_CHUNK_NUMBER_OFFSET = APP_ID_OFFSET + APP2_ICC_IDENTIFIER.length;
var ICC_TOTAL_CHUNKS_OFFSET = ICC_CHUNK_NUMBER_OFFSET + 1;
var APP2_MPF_IDENTIFIER = "MPF\0";
var SOF0_MARKER = 65472;
var SOF2_MARKER = 65474;
var DHT_MARKER = 65476;
var DQT_MARKER = 65499;
var DRI_MARKER = 65501;
var SOS_MARKER = 65498;
var APP0_MARKER = 65504;
var APP1_MARKER = 65505;
var APP2_MARKER = 65506;
var APP13_MARKER = 65517;
var APP15_MARKER = 65519;
var COMMENT_MARKER = 65534;
var FILL_BYTE = 65535;
var APP0_JFIF_IDENTIFIER = "JFIF";
var APP1_EXIF_IDENTIFIER = "Exif";
var APP1_XMP_IDENTIFIER = "http://ns.adobe.com/xap/1.0/\0";
var APP1_XMP_EXTENDED_IDENTIFIER = "http://ns.adobe.com/xmp/extension/\0";
var APP13_IPTC_IDENTIFIER = "Photoshop 3.0";
function isJpegFile(dataView) {
  return !!dataView && dataView.byteLength >= MIN_JPEG_DATA_BUFFER_LENGTH && dataView.getUint16(0) === JPEG_ID;
}
function findJpegOffsets(dataView) {
  let appMarkerPosition = JPEG_ID_SIZE;
  let fieldLength;
  let sof0DataOffset;
  let sof2DataOffset;
  let jfifDataOffset;
  let tiffHeaderOffset;
  let iptcDataOffset;
  let xmpChunks;
  let iccChunks;
  let mpfDataOffset;
  let exifSegmentCount = 0;
  let bestExifSegmentScore;
  let bestExifSegmentTiffHeaderOffset;
  let bestExifSegmentAppMarkerPosition;
  let bestExifSegmentFieldLength;
  while (appMarkerPosition + APP_ID_OFFSET + 5 <= dataView.byteLength) {
    if (constants_default.USE_FILE && isSOF0Marker(dataView, appMarkerPosition)) {
      fieldLength = dataView.getUint16(appMarkerPosition + APP_MARKER_SIZE);
      sof0DataOffset = appMarkerPosition + APP_MARKER_SIZE;
    } else if (constants_default.USE_FILE && isSOF2Marker(dataView, appMarkerPosition)) {
      fieldLength = dataView.getUint16(appMarkerPosition + APP_MARKER_SIZE);
      sof2DataOffset = appMarkerPosition + APP_MARKER_SIZE;
    } else if (constants_default.USE_JFIF && isApp0JfifMarker(dataView, appMarkerPosition)) {
      fieldLength = dataView.getUint16(appMarkerPosition + APP_MARKER_SIZE);
      jfifDataOffset = appMarkerPosition + JFIF_DATA_OFFSET;
    } else if (constants_default.USE_EXIF && isApp1ExifMarker(dataView, appMarkerPosition)) {
      fieldLength = dataView.getUint16(appMarkerPosition + APP_MARKER_SIZE);
      exifSegmentCount++;
      const currentTiffHeaderOffset = appMarkerPosition + TIFF_HEADER_OFFSET;
      if (exifSegmentCount === 1) {
        bestExifSegmentTiffHeaderOffset = currentTiffHeaderOffset;
        bestExifSegmentAppMarkerPosition = appMarkerPosition;
        bestExifSegmentFieldLength = fieldLength;
      } else if (exifSegmentCount === 2) {
        bestExifSegmentScore = getExifMarkerScore(
          dataView,
          bestExifSegmentAppMarkerPosition,
          bestExifSegmentFieldLength,
          bestExifSegmentTiffHeaderOffset
        );
        const currentExifSegmentScore = getExifMarkerScore(
          dataView,
          appMarkerPosition,
          fieldLength,
          currentTiffHeaderOffset
        );
        if (currentExifSegmentScore > bestExifSegmentScore) {
          bestExifSegmentScore = currentExifSegmentScore;
          bestExifSegmentTiffHeaderOffset = currentTiffHeaderOffset;
          bestExifSegmentAppMarkerPosition = appMarkerPosition;
          bestExifSegmentFieldLength = fieldLength;
        }
      } else {
        const currentExifSegmentScore = getExifMarkerScore(
          dataView,
          appMarkerPosition,
          fieldLength,
          currentTiffHeaderOffset
        );
        if (currentExifSegmentScore > bestExifSegmentScore) {
          bestExifSegmentScore = currentExifSegmentScore;
          bestExifSegmentTiffHeaderOffset = currentTiffHeaderOffset;
          bestExifSegmentAppMarkerPosition = appMarkerPosition;
          bestExifSegmentFieldLength = fieldLength;
        }
      }
      tiffHeaderOffset = bestExifSegmentTiffHeaderOffset;
    } else if (constants_default.USE_XMP && isApp1XmpMarker(dataView, appMarkerPosition)) {
      if (!xmpChunks) {
        xmpChunks = [];
      }
      fieldLength = dataView.getUint16(appMarkerPosition + APP_MARKER_SIZE);
      xmpChunks.push(getXmpChunkDetails(appMarkerPosition, fieldLength));
    } else if (constants_default.USE_XMP && isApp1ExtendedXmpMarker(dataView, appMarkerPosition)) {
      if (!xmpChunks) {
        xmpChunks = [];
      }
      fieldLength = dataView.getUint16(appMarkerPosition + APP_MARKER_SIZE);
      xmpChunks.push(getExtendedXmpChunkDetails(appMarkerPosition, fieldLength));
    } else if (constants_default.USE_IPTC && isApp13PhotoshopMarker(dataView, appMarkerPosition)) {
      fieldLength = dataView.getUint16(appMarkerPosition + APP_MARKER_SIZE);
      iptcDataOffset = appMarkerPosition + IPTC_DATA_OFFSET;
    } else if (constants_default.USE_ICC && isApp2ICCMarker(dataView, appMarkerPosition)) {
      fieldLength = dataView.getUint16(appMarkerPosition + APP_MARKER_SIZE);
      const iccDataOffset = appMarkerPosition + APP2_ICC_DATA_OFFSET;
      const iccDataLength = fieldLength - (APP2_ICC_DATA_OFFSET - APP_MARKER_SIZE);
      const iccChunkNumber = dataView.getUint8(appMarkerPosition + ICC_CHUNK_NUMBER_OFFSET);
      const iccChunksTotal = dataView.getUint8(appMarkerPosition + ICC_TOTAL_CHUNKS_OFFSET);
      if (!iccChunks) {
        iccChunks = [];
      }
      iccChunks.push({ offset: iccDataOffset, length: iccDataLength, chunkNumber: iccChunkNumber, chunksTotal: iccChunksTotal });
    } else if (constants_default.USE_MPF && isApp2MPFMarker(dataView, appMarkerPosition)) {
      fieldLength = dataView.getUint16(appMarkerPosition + APP_MARKER_SIZE);
      mpfDataOffset = appMarkerPosition + MPF_DATA_OFFSET;
    } else if (isAppMarker(dataView, appMarkerPosition)) {
      fieldLength = dataView.getUint16(appMarkerPosition + APP_MARKER_SIZE);
    } else if (isFillByte(dataView, appMarkerPosition)) {
      appMarkerPosition++;
      continue;
    } else {
      break;
    }
    appMarkerPosition += APP_MARKER_SIZE + fieldLength;
  }
  if (exifSegmentCount > 1) {
    warnAboutMultipleExifSegments(exifSegmentCount);
  }
  return {
    hasAppMarkers: appMarkerPosition > JPEG_ID_SIZE,
    fileDataOffset: sof0DataOffset || sof2DataOffset,
    jfifDataOffset,
    tiffHeaderOffset,
    iptcDataOffset,
    xmpChunks,
    iccChunks,
    mpfDataOffset
  };
}
function isSOF0Marker(dataView, appMarkerPosition) {
  return dataView.getUint16(appMarkerPosition) === SOF0_MARKER;
}
function isSOF2Marker(dataView, appMarkerPosition) {
  return dataView.getUint16(appMarkerPosition) === SOF2_MARKER;
}
function isApp2ICCMarker(dataView, appMarkerPosition) {
  const markerIdLength = APP2_ICC_IDENTIFIER.length;
  return dataView.getUint16(appMarkerPosition) === APP2_MARKER && getStringFromDataView(dataView, appMarkerPosition + APP_ID_OFFSET, markerIdLength) === APP2_ICC_IDENTIFIER;
}
function isApp2MPFMarker(dataView, appMarkerPosition) {
  const markerIdLength = APP2_MPF_IDENTIFIER.length;
  return dataView.getUint16(appMarkerPosition) === APP2_MARKER && getStringFromDataView(dataView, appMarkerPosition + APP_ID_OFFSET, markerIdLength) === APP2_MPF_IDENTIFIER;
}
function isApp0JfifMarker(dataView, appMarkerPosition) {
  const markerIdLength = APP0_JFIF_IDENTIFIER.length;
  return dataView.getUint16(appMarkerPosition) === APP0_MARKER && getStringFromDataView(dataView, appMarkerPosition + APP_ID_OFFSET, markerIdLength) === APP0_JFIF_IDENTIFIER && dataView.getUint8(appMarkerPosition + APP_ID_OFFSET + markerIdLength) === 0;
}
function isApp1ExifMarker(dataView, appMarkerPosition) {
  const markerIdLength = APP1_EXIF_IDENTIFIER.length;
  return dataView.getUint16(appMarkerPosition) === APP1_MARKER && getStringFromDataView(dataView, appMarkerPosition + APP_ID_OFFSET, markerIdLength) === APP1_EXIF_IDENTIFIER && dataView.getUint8(appMarkerPosition + APP_ID_OFFSET + markerIdLength) === 0;
}
function isApp1XmpMarker(dataView, appMarkerPosition) {
  return dataView.getUint16(appMarkerPosition) === APP1_MARKER && isXmpIdentifier(dataView, appMarkerPosition);
}
function isXmpIdentifier(dataView, appMarkerPosition) {
  const markerIdLength = APP1_XMP_IDENTIFIER.length;
  return getStringFromDataView(dataView, appMarkerPosition + APP_ID_OFFSET, markerIdLength) === APP1_XMP_IDENTIFIER;
}
function isApp1ExtendedXmpMarker(dataView, appMarkerPosition) {
  return dataView.getUint16(appMarkerPosition) === APP1_MARKER && isExtendedXmpIdentifier(dataView, appMarkerPosition);
}
function isExtendedXmpIdentifier(dataView, appMarkerPosition) {
  const markerIdLength = APP1_XMP_EXTENDED_IDENTIFIER.length;
  return getStringFromDataView(dataView, appMarkerPosition + APP_ID_OFFSET, markerIdLength) === APP1_XMP_EXTENDED_IDENTIFIER;
}
function getXmpChunkDetails(appMarkerPosition, fieldLength) {
  return {
    dataOffset: appMarkerPosition + XMP_DATA_OFFSET,
    length: fieldLength - (XMP_DATA_OFFSET - APP_MARKER_SIZE)
  };
}
function getExtendedXmpChunkDetails(appMarkerPosition, fieldLength) {
  return {
    dataOffset: appMarkerPosition + XMP_EXTENDED_DATA_OFFSET,
    length: fieldLength - (XMP_EXTENDED_DATA_OFFSET - APP_MARKER_SIZE)
  };
}
function isApp13PhotoshopMarker(dataView, appMarkerPosition) {
  const markerIdLength = APP13_IPTC_IDENTIFIER.length;
  return dataView.getUint16(appMarkerPosition) === APP13_MARKER && getStringFromDataView(dataView, appMarkerPosition + APP_ID_OFFSET, markerIdLength) === APP13_IPTC_IDENTIFIER && dataView.getUint8(appMarkerPosition + APP_ID_OFFSET + markerIdLength) === 0;
}
function isAppMarker(dataView, appMarkerPosition) {
  const appMarker = dataView.getUint16(appMarkerPosition);
  return appMarker >= APP0_MARKER && appMarker <= APP15_MARKER || appMarker === COMMENT_MARKER || appMarker === SOF0_MARKER || appMarker === SOF2_MARKER || appMarker === DHT_MARKER || appMarker === DQT_MARKER || appMarker === DRI_MARKER || appMarker === SOS_MARKER;
}
function isFillByte(dataView, appMarkerPosition) {
  return dataView.getUint16(appMarkerPosition) === FILL_BYTE;
}
function getExifMarkerScore(dataView, appMarkerPosition, fieldLength, tiffHeaderOffset) {
  const segmentEnd = appMarkerPosition + APP_MARKER_SIZE + fieldLength;
  const details = getExifTiffHeaderDetails(dataView, tiffHeaderOffset, segmentEnd);
  if (!details) {
    return 0;
  }
  const ifdEntriesScore = Number.isInteger(details.ifdEntries) ? details.ifdEntries : 0;
  return (details.isValid ? 1e9 : 0) + ifdEntriesScore * 1e6 + fieldLength;
}
function getExifTiffHeaderDetails(dataView, tiffHeaderOffset, segmentEnd) {
  try {
    if (tiffHeaderOffset + TIFF_HEADER_LENGTH > segmentEnd) {
      return void 0;
    }
    const byteOrderRaw = dataView.getUint16(
      tiffHeaderOffset + TIFF_BYTE_ORDER_OFFSET
    );
    const isLittleEndian = byteOrderRaw === byte_order_default.LITTLE_ENDIAN;
    if (!isLittleEndian && byteOrderRaw !== byte_order_default.BIG_ENDIAN) {
      return void 0;
    }
    const tiffId = dataView.getUint16(
      tiffHeaderOffset + TIFF_ID_OFFSET,
      isLittleEndian
    );
    if (tiffId !== TIFF_ID) {
      return void 0;
    }
    const ifdOffset = dataView.getUint32(
      tiffHeaderOffset + TIFF_IFD_OFFSET_OFFSET,
      isLittleEndian
    );
    const ifdEntryCountOffset = tiffHeaderOffset + ifdOffset;
    if (ifdEntryCountOffset + IFD_ENTRY_COUNT_LENGTH > segmentEnd) {
      return void 0;
    }
    const ifdEntries = dataView.getUint16(ifdEntryCountOffset, isLittleEndian);
    const ifdTotalLength = IFD_ENTRY_COUNT_LENGTH + ifdEntries * IFD_ENTRY_LENGTH + NEXT_IFD_POINTER_LENGTH;
    const hasFullIfd = ifdEntryCountOffset + ifdTotalLength <= segmentEnd;
    const isValid = hasFullIfd && ifdEntries > 0;
    return { ifdEntries, isValid };
  } catch (error) {
    return void 0;
  }
}
function warnAboutMultipleExifSegments(exifSegmentCount) {
  if (typeof console === "undefined" || typeof console.warn !== "function") {
    return;
  }
  console.warn(
    `ExifReader: Found ${exifSegmentCount} Exif segments (APP1). Will pick the best candidate segment.`
  );
}

// node_modules/exifreader/src/image-header-png.js
var image_header_png_default = {
  isPngFile,
  findPngOffsets
};
var PNG_ID = "\x89PNG\r\n\n";
var PNG_CHUNK_LENGTH_SIZE = 4;
var PNG_CHUNK_TYPE_SIZE = 4;
var PNG_CHUNK_LENGTH_OFFSET = 0;
var PNG_CHUNK_TYPE_OFFSET = PNG_CHUNK_LENGTH_SIZE;
var PNG_CHUNK_DATA_OFFSET = PNG_CHUNK_LENGTH_SIZE + PNG_CHUNK_TYPE_SIZE;
var PNG_XMP_PREFIX = "XML:com.adobe.xmp\0";
var TYPE_TEXT = "tEXt";
var TYPE_ITXT = "iTXt";
var TYPE_ZTXT = "zTXt";
var TYPE_PHYS = "pHYs";
var TYPE_TIME = "tIME";
var TYPE_EXIF = "eXIf";
var TYPE_ICCP = "iCCP";
function isPngFile(dataView) {
  return !!dataView && getStringFromDataView(dataView, 0, PNG_ID.length) === PNG_ID;
}
function findPngOffsets(dataView, async) {
  const PNG_CRC_SIZE = 4;
  const offsets = {
    hasAppMarkers: false
  };
  let offset = PNG_ID.length;
  while (offset + PNG_CHUNK_LENGTH_SIZE + PNG_CHUNK_TYPE_SIZE <= dataView.byteLength) {
    if (constants_default.USE_PNG_FILE && isPngImageHeaderChunk(dataView, offset)) {
      offsets.hasAppMarkers = true;
      offsets.pngHeaderOffset = offset + PNG_CHUNK_DATA_OFFSET;
    } else if (constants_default.USE_XMP && isPngXmpChunk(dataView, offset)) {
      const dataOffset = getPngXmpDataOffset(dataView, offset);
      if (dataOffset !== void 0) {
        offsets.hasAppMarkers = true;
        offsets.xmpChunks = [{
          dataOffset,
          length: dataView.getUint32(offset + PNG_CHUNK_LENGTH_OFFSET) - (dataOffset - (offset + PNG_CHUNK_DATA_OFFSET))
        }];
      }
    } else if (isPngTextChunk(dataView, offset, async)) {
      offsets.hasAppMarkers = true;
      const chunkType = getStringFromDataView(dataView, offset + PNG_CHUNK_TYPE_OFFSET, PNG_CHUNK_TYPE_SIZE);
      if (!offsets.pngTextChunks) {
        offsets.pngTextChunks = [];
      }
      offsets.pngTextChunks.push({
        length: dataView.getUint32(offset + PNG_CHUNK_LENGTH_OFFSET),
        type: chunkType,
        offset: offset + PNG_CHUNK_DATA_OFFSET
      });
    } else if (isPngExifChunk(dataView, offset)) {
      offsets.hasAppMarkers = true;
      offsets.tiffHeaderOffset = offset + PNG_CHUNK_DATA_OFFSET;
    } else if (constants_default.USE_ICC && async && isPngIccpChunk(dataView, offset)) {
      offsets.hasAppMarkers = true;
      const chunkDataLength = dataView.getUint32(offset + PNG_CHUNK_LENGTH_OFFSET);
      const iccHeaderOffset = offset + PNG_CHUNK_DATA_OFFSET;
      const { profileName, compressionMethod, compressedProfileOffset } = parseIccHeader(dataView, iccHeaderOffset);
      if (!offsets.iccChunks) {
        offsets.iccChunks = [];
      }
      offsets.iccChunks.push({
        offset: compressedProfileOffset,
        length: chunkDataLength - (compressedProfileOffset - iccHeaderOffset),
        chunkNumber: 1,
        chunksTotal: 1,
        profileName,
        compressionMethod
      });
    } else if (isPngChunk(dataView, offset)) {
      offsets.hasAppMarkers = true;
      if (!offsets.pngChunkOffsets) {
        offsets.pngChunkOffsets = [];
      }
      offsets.pngChunkOffsets.push(offset + PNG_CHUNK_LENGTH_OFFSET);
    }
    offset += dataView.getUint32(offset + PNG_CHUNK_LENGTH_OFFSET) + PNG_CHUNK_LENGTH_SIZE + PNG_CHUNK_TYPE_SIZE + PNG_CRC_SIZE;
  }
  return offsets;
}
function isPngImageHeaderChunk(dataView, offset) {
  const PNG_CHUNK_TYPE_IMAGE_HEADER = "IHDR";
  return getStringFromDataView(dataView, offset + PNG_CHUNK_TYPE_OFFSET, PNG_CHUNK_TYPE_SIZE) === PNG_CHUNK_TYPE_IMAGE_HEADER;
}
function isPngXmpChunk(dataView, offset) {
  return getStringFromDataView(dataView, offset + PNG_CHUNK_TYPE_OFFSET, PNG_CHUNK_TYPE_SIZE) === TYPE_ITXT && getStringFromDataView(dataView, offset + PNG_CHUNK_DATA_OFFSET, PNG_XMP_PREFIX.length) === PNG_XMP_PREFIX;
}
function isPngTextChunk(dataView, offset, async) {
  const chunkType = getStringFromDataView(dataView, offset + PNG_CHUNK_TYPE_OFFSET, PNG_CHUNK_TYPE_SIZE);
  return chunkType === TYPE_TEXT || chunkType === TYPE_ITXT || chunkType === TYPE_ZTXT && async;
}
function isPngExifChunk(dataView, offset) {
  return getStringFromDataView(dataView, offset + PNG_CHUNK_TYPE_OFFSET, PNG_CHUNK_TYPE_SIZE) === TYPE_EXIF;
}
function isPngIccpChunk(dataView, offset) {
  return getStringFromDataView(dataView, offset + PNG_CHUNK_TYPE_OFFSET, PNG_CHUNK_TYPE_SIZE) === TYPE_ICCP;
}
function isPngChunk(dataView, offset) {
  const SUPPORTED_PNG_CHUNK_TYPES = [TYPE_PHYS, TYPE_TIME];
  const chunkType = getStringFromDataView(dataView, offset + PNG_CHUNK_TYPE_OFFSET, PNG_CHUNK_TYPE_SIZE);
  return SUPPORTED_PNG_CHUNK_TYPES.includes(chunkType);
}
function getPngXmpDataOffset(dataView, offset) {
  const COMPRESSION_FLAG_SIZE = 1;
  const COMPRESSION_METHOD_SIZE = 1;
  offset += PNG_CHUNK_DATA_OFFSET + PNG_XMP_PREFIX.length + COMPRESSION_FLAG_SIZE + COMPRESSION_METHOD_SIZE;
  let numberOfNullSeparators = 0;
  while (numberOfNullSeparators < 2 && offset < dataView.byteLength) {
    if (dataView.getUint8(offset) === 0) {
      numberOfNullSeparators++;
    }
    offset++;
  }
  if (numberOfNullSeparators < 2) {
    return void 0;
  }
  return offset;
}
function parseIccHeader(dataView, offset) {
  const NULL_SEPARATOR_SIZE = 1;
  const COMPRESSION_METHOD_SIZE = 1;
  const profileName = getNullTerminatedStringFromDataView(dataView, offset);
  offset += profileName.length + NULL_SEPARATOR_SIZE;
  const compressionMethod = dataView.getUint8(offset);
  offset += COMPRESSION_METHOD_SIZE;
  return {
    profileName,
    compressionMethod,
    compressedProfileOffset: offset
  };
}

// node_modules/exifreader/src/image-header-iso-bmff-utils.js
function get64BitValue(dataView, offset) {
  return dataView.getUint32(offset + 4);
}

// node_modules/exifreader/src/image-header-iso-bmff-iloc.js
function parseItemLocationBox(dataView, version, contentOffset, boxLength) {
  const FLAGS_SIZE = 3;
  const { offsets, sizes } = getItemLocationBoxOffsetsAndSizes(version, contentOffset + FLAGS_SIZE);
  const offsetSize = dataView.getUint8(offsets.offsetSize) >> 4;
  sizes.item.extent.extentOffset = offsetSize;
  const lengthSize = dataView.getUint8(offsets.lengthSize) & 15;
  sizes.item.extent.extentLength = lengthSize;
  const baseOffsetSize = dataView.getUint8(offsets.baseOffsetSize) >> 4;
  sizes.item.baseOffset = baseOffsetSize;
  const indexSize = getIndexSize(dataView, offsets.indexSize, version);
  sizes.item.extent.extentIndex = indexSize !== void 0 ? indexSize : 0;
  const itemCount = getItemCount(dataView, offsets.itemCount, version);
  return {
    type: "iloc",
    items: getItems(dataView, version, offsets, sizes, offsetSize, lengthSize, indexSize, itemCount),
    length: boxLength
  };
}
function getItemLocationBoxOffsetsAndSizes(version, contentOffset) {
  const sizes = {
    item: {
      dataReferenceIndex: 2,
      extentCount: 2,
      extent: {}
    }
  };
  if (version < 2) {
    sizes.itemCount = 2;
    sizes.item.itemId = 2;
  } else if (version === 2) {
    sizes.itemCount = 4;
    sizes.item.itemId = 4;
  }
  if (version === 1 || version === 2) {
    sizes.item.constructionMethod = 2;
  } else {
    sizes.item.constructionMethod = 0;
  }
  const offsets = {
    offsetSize: contentOffset,
    lengthSize: contentOffset,
    baseOffsetSize: contentOffset + 1,
    indexSize: contentOffset + 1
  };
  offsets.itemCount = contentOffset + 2;
  offsets.items = offsets.itemCount + sizes.itemCount;
  offsets.item = {
    itemId: 0
  };
  offsets.item.constructionMethod = offsets.item.itemId + sizes.item.itemId;
  offsets.item.dataReferenceIndex = offsets.item.constructionMethod + sizes.item.constructionMethod;
  return { offsets, sizes };
}
function getIndexSize(dataView, offset, version) {
  if (version === 1 || version === 2) {
    return dataView.getUint8(offset) & 15;
  }
  return void 0;
}
function getItemCount(dataView, offset, version) {
  if (version < 2) {
    return dataView.getUint16(offset);
  } else if (version === 2) {
    return dataView.getUint32(offset);
  }
  return void 0;
}
function getItems(dataView, version, offsets, sizes, offsetSize, lengthSize, indexSize, itemCount) {
  if (itemCount === void 0) {
    return [];
  }
  const items = [];
  let offset = offsets.items;
  for (let i = 0; i < itemCount; i++) {
    const item = { extents: [] };
    item.itemId = getItemId(dataView, offset, version);
    offset += sizes.item.itemId;
    item.constructionMethod = version === 1 || version === 2 ? dataView.getUint16(offset) & 15 : void 0;
    offset += sizes.item.constructionMethod;
    item.dataReferenceIndex = dataView.getUint16(offset);
    offset += sizes.item.dataReferenceIndex;
    item.baseOffset = getVariableSizedValue(dataView, offset, sizes.item.baseOffset);
    offset += sizes.item.baseOffset;
    item.extentCount = dataView.getUint16(offset);
    offset += sizes.item.extentCount;
    for (let j = 0; j < item.extentCount; j++) {
      const extent = {};
      extent.extentIndex = getExtentIndex(dataView, version, offset, indexSize);
      offset += sizes.item.extent.extentIndex;
      extent.extentOffset = getVariableSizedValue(dataView, offset, offsetSize);
      offset += sizes.item.extent.extentOffset;
      extent.extentLength = getVariableSizedValue(dataView, offset, lengthSize);
      offset += sizes.item.extent.extentLength;
      item.extents.push(extent);
    }
    items.push(item);
  }
  return items;
}
function getItemId(dataView, offset, version) {
  if (version < 2) {
    return dataView.getUint16(offset);
  } else if (version === 2) {
    return dataView.getUint32(offset);
  }
  return void 0;
}
function getExtentIndex(dataView, version, offset, indexSize) {
  if ((version === 1 || version === 2) && indexSize > 0) {
    return getVariableSizedValue(dataView, offset, indexSize);
  }
  return void 0;
}
function getVariableSizedValue(dataView, offset, size) {
  if (size === 4) {
    return dataView.getUint32(offset);
  }
  if (size === 8) {
    console.warn("This file uses an 8-bit offset which is currently not supported by ExifReader. Contact the maintainer to get it fixed.");
    return get64BitValue(dataView, offset);
  }
  return 0;
}

// node_modules/exifreader/src/image-header-iso-bmff.js
var TYPE_FTYP = 1718909296;
var TYPE_IPRP = 1768977008;
var TYPE_META = 1835365473;
var TYPE_ILOC = 1768714083;
var TYPE_IINF = 1768517222;
var TYPE_INFE = 1768842853;
var TYPE_IPCO = 1768973167;
var TYPE_COLR = 1668246642;
var ITEM_INFO_TYPE_EXIF = 1165519206;
var ITEM_INFO_TYPE_MIME = 1835625829;
var ITEM_INFO_TYPE_URI = 1970432288;
function parseBox(dataView, offset) {
  const BOX_TYPE_OFFSET = 4;
  const BOX_MIN_LENGTH = 8;
  const VERSION_SIZE = 1;
  const { length, contentOffset } = getBoxLength(dataView, offset);
  if (length < BOX_MIN_LENGTH) {
    return void 0;
  }
  const type = dataView.getUint32(offset + BOX_TYPE_OFFSET);
  if (type === TYPE_FTYP) {
    return parseFileTypeBox(dataView, contentOffset, length);
  }
  if (type === TYPE_IPRP) {
    return parseItemPropertiesBox(dataView, offset, contentOffset, length);
  }
  if (type === TYPE_IPCO) {
    return parseItemPropertyContainerBox(dataView, offset, contentOffset, length);
  }
  if (type === TYPE_COLR) {
    return parseColorInformationBox(dataView, contentOffset, length);
  }
  const version = dataView.getUint8(contentOffset);
  if (type === TYPE_META) {
    return parseMetadataBox(dataView, offset, contentOffset + VERSION_SIZE, length);
  }
  if (type === TYPE_ILOC) {
    return parseItemLocationBox(dataView, version, contentOffset + VERSION_SIZE, length);
  }
  if (type === TYPE_IINF) {
    return parseItemInformationBox(dataView, offset, version, contentOffset + VERSION_SIZE, length);
  }
  if (type === TYPE_INFE) {
    return parseItemInformationEntryBox(dataView, offset, version, contentOffset + VERSION_SIZE, length);
  }
  return {
    // type: getStringFromDataView(dataView, offset + BOX_TYPE_OFFSET, 4),
    type: void 0,
    length
  };
}
function getBoxLength(dataView, offset) {
  const BOX_LENGTH_SIZE = 4;
  const BOX_TYPE_SIZE = 4;
  const BOX_EXTENDED_SIZE = 8;
  const BOX_EXTENDED_SIZE_LOW_OFFSET = 12;
  const boxLength = dataView.getUint32(offset);
  if (extendsToEndOfFile(boxLength)) {
    return {
      length: dataView.byteLength - offset,
      contentOffset: offset + BOX_LENGTH_SIZE + BOX_TYPE_SIZE
    };
  }
  if (hasExtendedSize(boxLength)) {
    if (hasEmptyHighBits(dataView, offset)) {
      return {
        length: dataView.getUint32(offset + BOX_EXTENDED_SIZE_LOW_OFFSET),
        contentOffset: offset + BOX_LENGTH_SIZE + BOX_TYPE_SIZE + BOX_EXTENDED_SIZE
      };
    }
  }
  return {
    length: boxLength,
    contentOffset: offset + BOX_LENGTH_SIZE + BOX_TYPE_SIZE
  };
}
function extendsToEndOfFile(boxLength) {
  return boxLength === 0;
}
function hasExtendedSize(boxLength) {
  return boxLength === 1;
}
function hasEmptyHighBits(dataView, offset) {
  const BOX_EXTENDED_SIZE_OFFSET = 8;
  return dataView.getUint32(offset + BOX_EXTENDED_SIZE_OFFSET) === 0;
}
function findOffsets(dataView) {
  if (constants_default.USE_EXIF || constants_default.USE_XMP || constants_default.USE_ICC) {
    const offsets = {};
    const metaBox = findMetaBox(dataView);
    if (!metaBox) {
      return { hasAppMarkers: false };
    }
    if (constants_default.USE_EXIF) {
      offsets.tiffHeaderOffset = findExifOffset(dataView, metaBox);
    }
    if (constants_default.USE_XMP) {
      offsets.xmpChunks = findXmpChunks(metaBox);
    }
    if (constants_default.USE_ICC) {
      offsets.iccChunks = findIccChunks(metaBox);
    }
    offsets.hasAppMarkers = offsets.tiffHeaderOffset !== void 0 || offsets.xmpChunks !== void 0 || offsets.iccChunks !== void 0;
    return offsets;
  }
  return {};
}
function findMetaBox(dataView) {
  const BOX_LENGTH_SIZE = 4;
  const BOX_TYPE_SIZE = 4;
  let offset = 0;
  while (offset + BOX_LENGTH_SIZE + BOX_TYPE_SIZE <= dataView.byteLength) {
    const box = parseBox(dataView, offset);
    if (box === void 0) {
      break;
    }
    if (box.type === "meta") {
      return box;
    }
    offset += box.length;
  }
  return void 0;
}
function findExifOffset(dataView, metaBox) {
  try {
    const exifItemId = findIinfExifItemId(metaBox).itemId;
    const ilocItem = findIlocItem(metaBox, exifItemId);
    const exifOffset = ilocItem.baseOffset + ilocItem.extents[0].extentOffset;
    return getTiffHeaderOffset(dataView, exifOffset);
  } catch (error) {
    return void 0;
  }
}
function findIinfExifItemId(metaBox) {
  return metaBox.subBoxes.find((box) => box.type === "iinf").itemInfos.find((itemInfo) => itemInfo.itemType === ITEM_INFO_TYPE_EXIF);
}
function findIlocItem(metaBox, itemId) {
  return metaBox.subBoxes.find((box) => box.type === "iloc").items.find((item) => item.itemId === itemId);
}
function getTiffHeaderOffset(dataView, exifOffset) {
  const TIFF_HEADER_OFFSET_SIZE = 4;
  return exifOffset + TIFF_HEADER_OFFSET_SIZE + dataView.getUint32(exifOffset);
}
function findXmpChunks(metaBox) {
  try {
    const xmpItemId = findIinfXmpItemId(metaBox).itemId;
    const ilocItem = findIlocItem(metaBox, xmpItemId);
    const ilocItemExtent = findIlocItem(metaBox, xmpItemId).extents[0];
    return [
      {
        dataOffset: ilocItem.baseOffset + ilocItemExtent.extentOffset,
        length: ilocItemExtent.extentLength
      }
    ];
  } catch (error) {
    return void 0;
  }
}
function findIinfXmpItemId(metaBox) {
  return metaBox.subBoxes.find((box) => box.type === "iinf").itemInfos.find((itemInfo) => itemInfo.itemType === ITEM_INFO_TYPE_MIME && itemInfo.contentType === "application/rdf+xml");
}
function findIccChunks(metaBox) {
  try {
    const icc = metaBox.subBoxes.find((box) => box.type === "iprp").subBoxes.find((box) => box.type === "ipco").properties.find((box) => box.type === "colr").icc;
    if (icc) {
      return [icc];
    }
  } catch (error) {
  }
  return void 0;
}
function parseFileTypeBox(dataView, contentOffset, boxLength) {
  const MAJOR_BRAND_SIZE = 4;
  const majorBrand = getStringFromDataView(dataView, contentOffset, MAJOR_BRAND_SIZE);
  return {
    type: "ftyp",
    majorBrand,
    length: boxLength
  };
}
function parseItemPropertiesBox(dataView, startOffset, contentOffset, length) {
  return {
    type: "iprp",
    subBoxes: parseSubBoxes(dataView, contentOffset, length - (contentOffset - startOffset)),
    length
  };
}
function parseItemPropertyContainerBox(dataView, startOffset, contentOffset, length) {
  return {
    type: "ipco",
    properties: parseSubBoxes(dataView, contentOffset, length - (contentOffset - startOffset)),
    length
  };
}
function parseColorInformationBox(dataView, contentOffset, length) {
  return {
    type: "colr",
    icc: parseIcc(dataView, contentOffset),
    length
  };
}
function parseIcc(dataView, contentOffset) {
  const COLOR_TYPE_SIZE = 4;
  const colorType = getStringFromDataView(dataView, contentOffset, COLOR_TYPE_SIZE);
  if (colorType !== "prof" && colorType !== "rICC") {
    return void 0;
  }
  return {
    offset: contentOffset + COLOR_TYPE_SIZE,
    length: dataView.getUint32(contentOffset + COLOR_TYPE_SIZE),
    chunkNumber: 1,
    chunksTotal: 1
  };
}
function parseMetadataBox(dataView, startOffset, contentOffset, length) {
  const FLAGS_SIZE = 3;
  return {
    type: "meta",
    subBoxes: parseSubBoxes(dataView, contentOffset + FLAGS_SIZE, length - (contentOffset + FLAGS_SIZE - startOffset)),
    length
  };
}
function parseSubBoxes(dataView, offset, length) {
  const ACCEPTED_ITEM_INFO_TYPES = [
    ITEM_INFO_TYPE_EXIF,
    ITEM_INFO_TYPE_MIME
  ];
  const subBoxes = [];
  let currentOffset = offset;
  while (currentOffset < offset + length) {
    const box = parseBox(dataView, currentOffset);
    if (box === void 0) {
      break;
    }
    if (box.type !== void 0 && (box.itemType === void 0 || ACCEPTED_ITEM_INFO_TYPES.indexOf(box.itemType) !== -1)) {
      subBoxes.push(box);
    }
    currentOffset += box.length;
  }
  return subBoxes;
}
function parseItemInformationBox(dataView, startOffset, version, contentOffset, length) {
  const { offsets } = getItemInformationBoxOffsetsAndSizes(version, contentOffset);
  return {
    type: "iinf",
    itemInfos: parseSubBoxes(dataView, offsets.itemInfos, length - (offsets.itemInfos - startOffset)),
    length
  };
}
function getItemInformationBoxOffsetsAndSizes(version, contentOffset) {
  const FLAGS_SIZE = 3;
  const offsets = { entryCount: contentOffset + FLAGS_SIZE };
  const sizes = {};
  if (version === 0) {
    sizes.entryCount = 2;
  } else {
    sizes.entryCount = 4;
  }
  offsets.itemInfos = offsets.entryCount + sizes.entryCount;
  return { offsets };
}
function parseItemInformationEntryBox(dataView, startOffset, version, contentOffset, length) {
  const FLAGS_SIZE = 3;
  contentOffset += FLAGS_SIZE;
  const entry = { type: "infe", length };
  if (version === 0 || version === 1) {
    entry.itemId = dataView.getUint16(contentOffset);
    contentOffset += 2;
    entry.itemProtectionIndex = dataView.getUint16(contentOffset);
    contentOffset += 2;
    entry.itemName = getNullTerminatedStringFromDataView(dataView, contentOffset);
    contentOffset += entry.itemName.length + 1;
  }
  if (version >= 2) {
    if (version === 2) {
      entry.itemId = dataView.getUint16(contentOffset);
      contentOffset += 2;
    } else if (version === 3) {
      entry.itemId = dataView.getUint32(contentOffset);
      contentOffset += 4;
    }
    entry.itemProtectionIndex = dataView.getUint16(contentOffset);
    contentOffset += 2;
    entry.itemType = dataView.getUint32(contentOffset);
    contentOffset += 4;
    entry.itemName = getNullTerminatedStringFromDataView(dataView, contentOffset);
    contentOffset += entry.itemName.length + 1;
    if (entry.itemType === ITEM_INFO_TYPE_MIME) {
      entry.contentType = getNullTerminatedStringFromDataView(dataView, contentOffset);
      contentOffset += entry.contentType.length + 1;
      if (startOffset + length > contentOffset) {
        entry.contentEncoding = getNullTerminatedStringFromDataView(dataView, contentOffset);
        contentOffset += entry.contentEncoding.length + 1;
      }
    } else if (entry.itemType === ITEM_INFO_TYPE_URI) {
      entry.itemUri = getNullTerminatedStringFromDataView(dataView, contentOffset);
      contentOffset += entry.itemUri.length + 1;
    }
  }
  return entry;
}

// node_modules/exifreader/src/image-header-heic.js
var image_header_heic_default = {
  isHeicFile,
  findHeicOffsets
};
function isHeicFile(dataView) {
  if (!dataView) {
    return false;
  }
  const HEIC_MAJOR_BRANDS = ["heic", "heix", "hevc", "hevx", "heim", "heis", "hevm", "hevs", "mif1"];
  try {
    const headerBox = parseBox(dataView, 0);
    return headerBox && HEIC_MAJOR_BRANDS.indexOf(headerBox.majorBrand) !== -1;
  } catch (error) {
    return false;
  }
}
function findHeicOffsets(dataView) {
  return findOffsets(dataView);
}

// node_modules/exifreader/src/image-header-avif.js
var image_header_avif_default = {
  isAvifFile,
  findAvifOffsets
};
function isAvifFile(dataView) {
  if (!dataView) {
    return false;
  }
  try {
    const headerBox = parseBox(dataView, 0);
    return headerBox && headerBox.majorBrand === "avif";
  } catch (error) {
    return false;
  }
}
function findAvifOffsets(dataView) {
  return findOffsets(dataView);
}

// node_modules/exifreader/src/image-header-webp.js
var image_header_webp_default = {
  isWebpFile,
  findOffsets: findOffsets2
};
function isWebpFile(dataView) {
  const RIFF_ID_OFFSET = 0;
  const RIFF_ID = "RIFF";
  const WEBP_MARKER_OFFSET = 8;
  const WEBP_MARKER = "WEBP";
  return !!dataView && getStringFromDataView(dataView, RIFF_ID_OFFSET, RIFF_ID.length) === RIFF_ID && getStringFromDataView(dataView, WEBP_MARKER_OFFSET, WEBP_MARKER.length) === WEBP_MARKER;
}
function findOffsets2(dataView) {
  const SUB_CHUNK_START_OFFSET = 12;
  const CHUNK_SIZE_OFFSET = 4;
  const EXIF_IDENTIFIER = "Exif\0\0";
  const CHUNK_HEADER_SIZE = 8;
  let offset = SUB_CHUNK_START_OFFSET;
  let hasAppMarkers = false;
  let tiffHeaderOffset;
  let xmpChunks;
  let iccChunks;
  let vp8xChunkOffset;
  while (offset + CHUNK_HEADER_SIZE < dataView.byteLength) {
    const chunkId = getStringFromDataView(dataView, offset, 4);
    const chunkSize = dataView.getUint32(offset + CHUNK_SIZE_OFFSET, true);
    if (constants_default.USE_EXIF && chunkId === "EXIF") {
      hasAppMarkers = true;
      if (getStringFromDataView(dataView, offset + CHUNK_HEADER_SIZE, EXIF_IDENTIFIER.length) === EXIF_IDENTIFIER) {
        tiffHeaderOffset = offset + CHUNK_HEADER_SIZE + EXIF_IDENTIFIER.length;
      } else {
        tiffHeaderOffset = offset + CHUNK_HEADER_SIZE;
      }
    } else if (constants_default.USE_XMP && chunkId === "XMP ") {
      hasAppMarkers = true;
      xmpChunks = [{
        dataOffset: offset + CHUNK_HEADER_SIZE,
        length: chunkSize
      }];
    } else if (constants_default.USE_ICC && chunkId === "ICCP") {
      hasAppMarkers = true;
      iccChunks = [{
        offset: offset + CHUNK_HEADER_SIZE,
        length: chunkSize,
        chunkNumber: 1,
        chunksTotal: 1
      }];
    } else if (chunkId === "VP8X") {
      hasAppMarkers = true;
      vp8xChunkOffset = offset + CHUNK_HEADER_SIZE;
    }
    offset += CHUNK_HEADER_SIZE + (chunkSize % 2 === 0 ? chunkSize : chunkSize + 1);
  }
  return {
    hasAppMarkers,
    tiffHeaderOffset,
    xmpChunks,
    iccChunks,
    vp8xChunkOffset
  };
}

// node_modules/exifreader/src/image-header-gif.js
var image_header_gif_default = {
  isGifFile,
  findOffsets: findOffsets3
};
var GIF_SIGNATURE_SIZE = 6;
var GIF_SIGNATURES = ["GIF87a", "GIF89a"];
function isGifFile(dataView) {
  return !!dataView && GIF_SIGNATURES.includes(getStringFromDataView(dataView, 0, GIF_SIGNATURE_SIZE));
}
function findOffsets3() {
  return {
    gifHeaderOffset: 0
  };
}

// node_modules/exifreader/src/xml.js
var xml_default = {
  isXMLFile,
  findOffsets: findOffsets4
};
var XML_MARKER_OFFSET = 0;
var XML_MARKER = "<?xpacket begin";
function isXMLFile(dataView) {
  return !!dataView && getStringFromDataView(dataView, XML_MARKER_OFFSET, XML_MARKER.length) === XML_MARKER;
}
function findOffsets4(dataView) {
  const xmpChunks = [];
  xmpChunks.push({ dataOffset: XML_MARKER_OFFSET, length: dataView.byteLength });
  return {
    xmpChunks
  };
}

// node_modules/exifreader/src/image-header.js
var image_header_default = {
  parseAppMarkers
};
function parseAppMarkers(dataView, async) {
  if (constants_default.USE_TIFF && image_header_tiff_default.isTiffFile(dataView)) {
    return addFileType(image_header_tiff_default.findTiffOffsets(), "tiff", "TIFF");
  }
  if (constants_default.USE_JPEG && image_header_jpeg_default.isJpegFile(dataView)) {
    return addFileType(image_header_jpeg_default.findJpegOffsets(dataView), "jpeg", "JPEG");
  }
  if (constants_default.USE_PNG && image_header_png_default.isPngFile(dataView)) {
    return addFileType(image_header_png_default.findPngOffsets(dataView, async), "png", "PNG");
  }
  if (constants_default.USE_HEIC && image_header_heic_default.isHeicFile(dataView)) {
    return addFileType(image_header_heic_default.findHeicOffsets(dataView), "heic", "HEIC");
  }
  if (constants_default.USE_AVIF && image_header_avif_default.isAvifFile(dataView)) {
    return addFileType(image_header_avif_default.findAvifOffsets(dataView), "avif", "AVIF");
  }
  if (constants_default.USE_WEBP && image_header_webp_default.isWebpFile(dataView)) {
    return addFileType(image_header_webp_default.findOffsets(dataView), "webp", "WebP");
  }
  if (constants_default.USE_GIF && image_header_gif_default.isGifFile(dataView)) {
    return addFileType(image_header_gif_default.findOffsets(dataView), "gif", "GIF");
  }
  if (constants_default.USE_XMP && xml_default.isXMLFile(dataView)) {
    return addFileType(xml_default.findOffsets(dataView), "xml", "XML");
  }
  throw new Error("Invalid image format");
}
function addFileType(offsets, fileType, fileTypeDescription) {
  return objectAssign({}, offsets, { fileType: { value: fileType, description: fileTypeDescription } });
}

// node_modules/exifreader/src/tag-names-common.js
var tag_names_common_default = {
  ApertureValue: (value) => Math.pow(Math.sqrt(2), value[0] / value[1]).toFixed(2),
  ColorSpace(value) {
    if (value === 1) {
      return "sRGB";
    } else if (value === 65535) {
      return "Uncalibrated";
    }
    return "Unknown";
  },
  ComponentsConfiguration(value) {
    return value.map((character) => {
      if (character === 49) {
        return "Y";
      } else if (character === 50) {
        return "Cb";
      } else if (character === 51) {
        return "Cr";
      } else if (character === 52) {
        return "R";
      } else if (character === 53) {
        return "G";
      } else if (character === 54) {
        return "B";
      }
    }).join("");
  },
  Contrast(value) {
    if (value === 0) {
      return "Normal";
    } else if (value === 1) {
      return "Soft";
    } else if (value === 2) {
      return "Hard";
    }
    return "Unknown";
  },
  CustomRendered(value) {
    if (value === 0) {
      return "Normal process";
    } else if (value === 1) {
      return "Custom process";
    }
    return "Unknown";
  },
  ExposureMode(value) {
    if (value === 0) {
      return "Auto exposure";
    } else if (value === 1) {
      return "Manual exposure";
    } else if (value === 2) {
      return "Auto bracket";
    }
    return "Unknown";
  },
  ExposureProgram(value) {
    if (value === 0) {
      return "Undefined";
    } else if (value === 1) {
      return "Manual";
    } else if (value === 2) {
      return "Normal program";
    } else if (value === 3) {
      return "Aperture priority";
    } else if (value === 4) {
      return "Shutter priority";
    } else if (value === 5) {
      return "Creative program";
    } else if (value === 6) {
      return "Action program";
    } else if (value === 7) {
      return "Portrait mode";
    } else if (value === 8) {
      return "Landscape mode";
    } else if (value === 9) {
      return "Bulb";
    }
    return "Unknown";
  },
  ExposureTime(value) {
    if (value[0] / value[1] > 0.25) {
      const decimal = value[0] / value[1];
      if (Number.isInteger(decimal)) {
        return "" + decimal;
      }
      return decimal.toFixed(1);
    }
    if (value[0] !== 0) {
      return `1/${Math.round(value[1] / value[0])}`;
    }
    return `0/${value[1]}`;
  },
  FNumber: (value) => `f/${Number(value[0] / value[1]).toFixed(1)}`,
  FocalLength: (value) => value[0] / value[1] + " mm",
  FocalPlaneResolutionUnit(value) {
    if (value === 2) {
      return "inches";
    } else if (value === 3) {
      return "centimeters";
    } else if (value === 4) {
      return "millimeters";
    }
    return "Unknown";
  },
  LightSource: (value) => {
    if (value === 1) {
      return "Daylight";
    } else if (value === 2) {
      return "Fluorescent";
    } else if (value === 3) {
      return "Tungsten (incandescent light)";
    } else if (value === 4) {
      return "Flash";
    } else if (value === 9) {
      return "Fine weather";
    } else if (value === 10) {
      return "Cloudy weather";
    } else if (value === 11) {
      return "Shade";
    } else if (value === 12) {
      return "Daylight fluorescent (D 5700 \u2013 7100K)";
    } else if (value === 13) {
      return "Day white fluorescent (N 4600 \u2013 5400K)";
    } else if (value === 14) {
      return "Cool white fluorescent (W 3900 \u2013 4500K)";
    } else if (value === 15) {
      return "White fluorescent (WW 3200 \u2013 3700K)";
    } else if (value === 17) {
      return "Standard light A";
    } else if (value === 18) {
      return "Standard light B";
    } else if (value === 19) {
      return "Standard light C";
    } else if (value === 20) {
      return "D55";
    } else if (value === 21) {
      return "D65";
    } else if (value === 22) {
      return "D75";
    } else if (value === 23) {
      return "D50";
    } else if (value === 24) {
      return "ISO studio tungsten";
    } else if (value === 255) {
      return "Other light source";
    }
    return "Unknown";
  },
  MeteringMode(value) {
    if (value === 1) {
      return "Average";
    } else if (value === 2) {
      return "CenterWeightedAverage";
    } else if (value === 3) {
      return "Spot";
    } else if (value === 4) {
      return "MultiSpot";
    } else if (value === 5) {
      return "Pattern";
    } else if (value === 6) {
      return "Partial";
    } else if (value === 255) {
      return "Other";
    }
    return "Unknown";
  },
  ResolutionUnit(value) {
    if (value === 2) {
      return "inches";
    }
    if (value === 3) {
      return "centimeters";
    }
    return "Unknown";
  },
  Saturation(value) {
    if (value === 0) {
      return "Normal";
    } else if (value === 1) {
      return "Low saturation";
    } else if (value === 2) {
      return "High saturation";
    }
    return "Unknown";
  },
  FocalLengthIn35mmFilm(value) {
    if (value === 0) {
      return "Unknown";
    }
    return value + " mm";
  },
  SceneCaptureType(value) {
    if (value === 0) {
      return "Standard";
    } else if (value === 1) {
      return "Landscape";
    } else if (value === 2) {
      return "Portrait";
    } else if (value === 3) {
      return "Night scene";
    }
    return "Unknown";
  },
  Sharpness(value) {
    if (value === 0) {
      return "Normal";
    } else if (value === 1) {
      return "Soft";
    } else if (value === 2) {
      return "Hard";
    }
    return "Unknown";
  },
  ShutterSpeedValue(value) {
    const denominator = Math.pow(2, value[0] / value[1]);
    if (denominator <= 1) {
      return `${Math.round(1 / denominator)}`;
    }
    return `1/${Math.round(denominator)}`;
  },
  WhiteBalance(value) {
    if (value === 0) {
      return "Auto white balance";
    } else if (value === 1) {
      return "Manual white balance";
    }
    return "Unknown";
  },
  XResolution: (value) => "" + Math.round(value[0] / value[1]),
  YResolution: (value) => "" + Math.round(value[0] / value[1])
};

// node_modules/exifreader/src/tag-names-0th-ifd.js
var tag_names_0th_ifd_default = {
  11: "ProcessingSoftware",
  254: {
    name: "SubfileType",
    description: (value) => ({
      0: "Full-resolution image",
      1: "Reduced-resolution image",
      2: "Single page of multi-page image",
      3: "Single page of multi-page reduced-resolution image",
      4: "Transparency mask",
      5: "Transparency mask of reduced-resolution image",
      6: "Transparency mask of multi-page image",
      7: "Transparency mask of reduced-resolution multi-page image",
      65537: "Alternate reduced-resolution image",
      4294967295: "Invalid"
    })[value] || "Unknown"
  },
  255: {
    name: "OldSubfileType",
    description: (value) => ({
      0: "Full-resolution image",
      1: "Reduced-resolution image",
      2: "Single page of multi-page image"
    })[value] || "Unknown"
  },
  256: "ImageWidth",
  257: "ImageLength",
  258: "BitsPerSample",
  259: "Compression",
  262: "PhotometricInterpretation",
  263: {
    name: "Thresholding",
    description: (value) => ({
      1: "No dithering or halftoning",
      2: "Ordered dither or halfton",
      3: "Randomized dither"
    })[value] || "Unknown"
  },
  264: "CellWidth",
  265: "CellLength",
  266: {
    name: "FillOrder",
    description: (value) => ({
      1: "Normal",
      2: "Reversed"
    })[value] || "Unknown"
  },
  269: "DocumentName",
  270: "ImageDescription",
  271: "Make",
  272: "Model",
  273: "StripOffsets",
  274: {
    name: "Orientation",
    description: (value) => {
      if (value === 1) {
        return "top-left";
      }
      if (value === 2) {
        return "top-right";
      }
      if (value === 3) {
        return "bottom-right";
      }
      if (value === 4) {
        return "bottom-left";
      }
      if (value === 5) {
        return "left-top";
      }
      if (value === 6) {
        return "right-top";
      }
      if (value === 7) {
        return "right-bottom";
      }
      if (value === 8) {
        return "left-bottom";
      }
      return "Undefined";
    }
  },
  277: "SamplesPerPixel",
  278: "RowsPerStrip",
  279: "StripByteCounts",
  280: "MinSampleValue",
  281: "MaxSampleValue",
  282: {
    "name": "XResolution",
    "description": tag_names_common_default.XResolution
  },
  283: {
    "name": "YResolution",
    "description": tag_names_common_default.YResolution
  },
  284: "PlanarConfiguration",
  285: "PageName",
  286: {
    "name": "XPosition",
    "description": (value) => {
      return "" + Math.round(value[0] / value[1]);
    }
  },
  287: {
    "name": "YPosition",
    "description": (value) => {
      return "" + Math.round(value[0] / value[1]);
    }
  },
  290: {
    name: "GrayResponseUnit",
    description: (value) => ({
      1: "0.1",
      2: "0.001",
      3: "0.0001",
      4: "1e-05",
      5: "1e-06"
    })[value] || "Unknown"
  },
  296: {
    name: "ResolutionUnit",
    description: tag_names_common_default.ResolutionUnit
  },
  297: "PageNumber",
  301: "TransferFunction",
  305: "Software",
  306: "DateTime",
  315: "Artist",
  316: "HostComputer",
  317: "Predictor",
  318: {
    "name": "WhitePoint",
    "description": (values) => {
      return values.map((value) => `${value[0]}/${value[1]}`).join(", ");
    }
  },
  319: {
    "name": "PrimaryChromaticities",
    "description": (values) => {
      return values.map((value) => `${value[0]}/${value[1]}`).join(", ");
    }
  },
  321: "HalftoneHints",
  322: "TileWidth",
  323: "TileLength",
  330: "A100DataOffset",
  332: {
    name: "InkSet",
    description: (value) => ({
      1: "CMYK",
      2: "Not CMYK"
    })[value] || "Unknown"
  },
  337: "TargetPrinter",
  338: {
    name: "ExtraSamples",
    description: (value) => ({
      0: "Unspecified",
      1: "Associated Alpha",
      2: "Unassociated Alpha"
    })[value] || "Unknown"
  },
  339: {
    name: "SampleFormat",
    description: (value) => {
      const formats = {
        1: "Unsigned",
        2: "Signed",
        3: "Float",
        4: "Undefined",
        5: "Complex int",
        6: "Complex float"
      };
      if (!Array.isArray(value)) {
        return "Unknown";
      }
      return value.map((sample) => formats[sample] || "Unknown").join(", ");
    }
  },
  513: "JPEGInterchangeFormat",
  514: "JPEGInterchangeFormatLength",
  529: {
    "name": "YCbCrCoefficients",
    "description": (values) => {
      return values.map((value) => "" + value[0] / value[1]).join("/");
    }
  },
  530: "YCbCrSubSampling",
  531: {
    name: "YCbCrPositioning",
    description: (value) => {
      if (value === 1) {
        return "centered";
      }
      if (value === 2) {
        return "co-sited";
      }
      return "undefined " + value;
    }
  },
  532: {
    "name": "ReferenceBlackWhite",
    "description": (values) => {
      return values.map((value) => "" + value[0] / value[1]).join(", ");
    }
  },
  700: "ApplicationNotes",
  18246: "Rating",
  18249: "RatingPercent",
  33432: {
    name: "Copyright",
    description: (value) => value.join("; ")
  },
  33550: "PixelScale",
  33723: "IPTC-NAA",
  33920: "IntergraphMatrix",
  33922: "ModelTiePoint",
  34118: "SEMInfo",
  34264: "ModelTransform",
  34377: "PhotoshopSettings",
  34665: "Exif IFD Pointer",
  34675: "ICC_Profile",
  34735: "GeoTiffDirectory",
  34736: "GeoTiffDoubleParams",
  34737: "GeoTiffAsciiParams",
  34853: "GPS Info IFD Pointer",
  40091: {
    name: "XPTitle",
    description: decodeXPValue
  },
  40092: {
    name: "XPComment",
    description: decodeXPValue
  },
  40093: {
    name: "XPAuthor",
    description: decodeXPValue
  },
  40094: {
    name: "XPKeywords",
    description: decodeXPValue
  },
  40095: {
    name: "XPSubject",
    description: decodeXPValue
  },
  42112: "GDALMetadata",
  42113: "GDALNoData",
  50341: "PrintIM",
  50707: "DNGBackwardVersion",
  50708: "UniqueCameraModel",
  50709: "LocalizedCameraModel",
  50721: "ColorMatrix1",
  50722: "ColorMatrix2",
  50723: "CameraCalibration1",
  50724: "CameraCalibration2",
  50725: "ReductionMatrix1",
  50726: "ReductionMatrix2",
  50727: "AnalogBalance",
  50728: "AsShotNeutral",
  50729: "AsShotWhiteXY",
  50730: "BaselineExposure",
  50731: "BaselineNoise",
  50732: "BaselineSharpness",
  50734: "LinearResponseLimit",
  50735: "CameraSerialNumber",
  50736: "DNGLensInfo",
  50739: "ShadowScale",
  50741: {
    name: "MakerNoteSafety",
    description: (value) => ({
      0: "Unsafe",
      1: "Safe"
    })[value] || "Unknown"
  },
  50778: {
    name: "CalibrationIlluminant1",
    description: tag_names_common_default["LightSource"]
  },
  50779: {
    name: "CalibrationIlluminant2",
    description: tag_names_common_default["LightSource"]
  },
  50781: "RawDataUniqueID",
  50827: "OriginalRawFileName",
  50828: "OriginalRawFileData",
  50831: "AsShotICCProfile",
  50832: "AsShotPreProfileMatrix",
  50833: "CurrentICCProfile",
  50834: "CurrentPreProfileMatrix",
  50879: "ColorimetricReference",
  50885: "SRawType",
  50898: "PanasonicTitle",
  50899: "PanasonicTitle2",
  50931: "CameraCalibrationSig",
  50932: "ProfileCalibrationSig",
  50933: "ProfileIFD",
  50934: "AsShotProfileName",
  50936: "ProfileName",
  50937: "ProfileHueSatMapDims",
  50938: "ProfileHueSatMapData1",
  50939: "ProfileHueSatMapData2",
  50940: "ProfileToneCurve",
  50941: {
    name: "ProfileEmbedPolicy",
    description: (value) => ({
      0: "Allow Copying",
      1: "Embed if Used",
      2: "Never Embed",
      3: "No Restrictions"
    })[value] || "Unknown"
  },
  50942: "ProfileCopyright",
  50964: "ForwardMatrix1",
  50965: "ForwardMatrix2",
  50966: "PreviewApplicationName",
  50967: "PreviewApplicationVersion",
  50968: "PreviewSettingsName",
  50969: "PreviewSettingsDigest",
  50970: {
    name: "PreviewColorSpace",
    description: (value) => ({
      1: "Gray Gamma 2.2",
      2: "sRGB",
      3: "Adobe RGB",
      4: "ProPhoto RGB"
    })[value] || "Unknown"
  },
  50971: "PreviewDateTime",
  50972: "RawImageDigest",
  50973: "OriginalRawFileDigest",
  50981: "ProfileLookTableDims",
  50982: "ProfileLookTableData",
  51043: "TimeCodes",
  51044: "FrameRate",
  51058: "TStop",
  51081: "ReelName",
  51089: "OriginalDefaultFinalSize",
  51090: "OriginalBestQualitySize",
  51091: "OriginalDefaultCropSize",
  51105: "CameraLabel",
  51107: {
    name: "ProfileHueSatMapEncoding",
    description: (value) => ({
      0: "Linear",
      1: "sRGB"
    })[value] || "Unknown"
  },
  51108: {
    name: "ProfileLookTableEncoding",
    description: (value) => ({
      0: "Linear",
      1: "sRGB"
    })[value] || "Unknown"
  },
  51109: "BaselineExposureOffset",
  51110: {
    name: "DefaultBlackRender",
    description: (value) => ({
      0: "Auto",
      1: "None"
    })[value] || "Unknown"
  },
  51111: "NewRawImageDigest",
  51112: "RawToPreviewGain"
};
function decodeXPValue(value) {
  const decodedValue = new TextDecoder("utf-16").decode(new Uint8Array(value));
  return decodedValue.replace(/\u0000+$/, "");
}

// node_modules/exifreader/src/tag-names-exif-ifd.js
var tag_names_exif_ifd_default = {
  33434: {
    "name": "ExposureTime",
    "description": tag_names_common_default.ExposureTime
  },
  33437: {
    "name": "FNumber",
    "description": tag_names_common_default.FNumber
  },
  34850: {
    "name": "ExposureProgram",
    "description": tag_names_common_default.ExposureProgram
  },
  34852: "SpectralSensitivity",
  34855: "ISOSpeedRatings",
  34856: {
    "name": "OECF",
    "description": () => "[Raw OECF table data]"
  },
  34858: "TimeZoneOffset",
  34859: "SelfTimerMode",
  34864: {
    name: "SensitivityType",
    description: (value) => ({
      1: "Standard Output Sensitivity",
      2: "Recommended Exposure Index",
      3: "ISO Speed",
      4: "Standard Output Sensitivity and Recommended Exposure Index",
      5: "Standard Output Sensitivity and ISO Speed",
      6: "Recommended Exposure Index and ISO Speed",
      7: "Standard Output Sensitivity, Recommended Exposure Index and ISO Speed"
    })[value] || "Unknown"
  },
  34865: "StandardOutputSensitivity",
  34866: "RecommendedExposureIndex",
  34867: "ISOSpeed",
  34868: "ISOSpeedLatitudeyyy",
  34869: "ISOSpeedLatitudezzz",
  36864: {
    "name": "ExifVersion",
    "description": (value) => getStringValue(value)
  },
  36867: "DateTimeOriginal",
  36868: "DateTimeDigitized",
  36873: "GooglePlusUploadCode",
  36880: "OffsetTime",
  36881: "OffsetTimeOriginal",
  36882: "OffsetTimeDigitized",
  37121: {
    "name": "ComponentsConfiguration",
    "description": tag_names_common_default.ComponentsConfiguration
  },
  37122: "CompressedBitsPerPixel",
  37377: {
    "name": "ShutterSpeedValue",
    "description": tag_names_common_default.ShutterSpeedValue
  },
  37378: {
    "name": "ApertureValue",
    "description": tag_names_common_default.ApertureValue
  },
  37379: "BrightnessValue",
  37380: "ExposureBiasValue",
  37381: {
    "name": "MaxApertureValue",
    "description": (value) => {
      return Math.pow(Math.sqrt(2), value[0] / value[1]).toFixed(2);
    }
  },
  37382: {
    "name": "SubjectDistance",
    "description": (value) => value[0] / value[1] + " m"
  },
  37383: {
    "name": "MeteringMode",
    "description": tag_names_common_default.MeteringMode
  },
  37384: {
    "name": "LightSource",
    description: tag_names_common_default.LightSource
  },
  37385: {
    "name": "Flash",
    "description": (value) => {
      if (value === 0) {
        return "Flash did not fire";
      } else if (value === 1) {
        return "Flash fired";
      } else if (value === 5) {
        return "Strobe return light not detected";
      } else if (value === 7) {
        return "Strobe return light detected";
      } else if (value === 9) {
        return "Flash fired, compulsory flash mode";
      } else if (value === 13) {
        return "Flash fired, compulsory flash mode, return light not detected";
      } else if (value === 15) {
        return "Flash fired, compulsory flash mode, return light detected";
      } else if (value === 16) {
        return "Flash did not fire, compulsory flash mode";
      } else if (value === 24) {
        return "Flash did not fire, auto mode";
      } else if (value === 25) {
        return "Flash fired, auto mode";
      } else if (value === 29) {
        return "Flash fired, auto mode, return light not detected";
      } else if (value === 31) {
        return "Flash fired, auto mode, return light detected";
      } else if (value === 32) {
        return "No flash function";
      } else if (value === 65) {
        return "Flash fired, red-eye reduction mode";
      } else if (value === 69) {
        return "Flash fired, red-eye reduction mode, return light not detected";
      } else if (value === 71) {
        return "Flash fired, red-eye reduction mode, return light detected";
      } else if (value === 73) {
        return "Flash fired, compulsory flash mode, red-eye reduction mode";
      } else if (value === 77) {
        return "Flash fired, compulsory flash mode, red-eye reduction mode, return light not detected";
      } else if (value === 79) {
        return "Flash fired, compulsory flash mode, red-eye reduction mode, return light detected";
      } else if (value === 89) {
        return "Flash fired, auto mode, red-eye reduction mode";
      } else if (value === 93) {
        return "Flash fired, auto mode, return light not detected, red-eye reduction mode";
      } else if (value === 95) {
        return "Flash fired, auto mode, return light detected, red-eye reduction mode";
      }
      return "Unknown";
    }
  },
  37386: {
    "name": "FocalLength",
    "description": tag_names_common_default.FocalLength
  },
  37393: "ImageNumber",
  37394: {
    name: "SecurityClassification",
    description: (value) => ({
      "C": "Confidential",
      "R": "Restricted",
      "S": "Secret",
      "T": "Top Secret",
      "U": "Unclassified"
    })[value] || "Unknown"
  },
  37395: "ImageHistory",
  37396: {
    "name": "SubjectArea",
    "description": (value) => {
      if (value.length === 2) {
        return `Location; X: ${value[0]}, Y: ${value[1]}`;
      } else if (value.length === 3) {
        return `Circle; X: ${value[0]}, Y: ${value[1]}, diameter: ${value[2]}`;
      } else if (value.length === 4) {
        return `Rectangle; X: ${value[0]}, Y: ${value[1]}, width: ${value[2]}, height: ${value[3]}`;
      }
      return "Unknown";
    }
  },
  37500: {
    "name": "MakerNote",
    "description": () => "[Raw maker note data]"
  },
  37510: {
    "name": "UserComment",
    "description": getEncodedString
  },
  37520: "SubSecTime",
  37521: "SubSecTimeOriginal",
  37522: "SubSecTimeDigitized",
  37724: "ImageSourceData",
  37888: {
    "name": "AmbientTemperature",
    "description": (value) => value[0] / value[1] + " \xB0C"
  },
  37889: {
    "name": "Humidity",
    "description": (value) => value[0] / value[1] + " %"
  },
  37890: {
    "name": "Pressure",
    "description": (value) => value[0] / value[1] + " hPa"
  },
  37891: {
    "name": "WaterDepth",
    "description": (value) => value[0] / value[1] + " m"
  },
  37892: {
    "name": "Acceleration",
    "description": (value) => value[0] / value[1] + " mGal"
  },
  37893: {
    "name": "CameraElevationAngle",
    "description": (value) => value[0] / value[1] + " \xB0"
  },
  40960: {
    "name": "FlashpixVersion",
    "description": (value) => value.map((charCode) => String.fromCharCode(charCode)).join("")
  },
  40961: {
    "name": "ColorSpace",
    "description": tag_names_common_default.ColorSpace
  },
  40962: "PixelXDimension",
  40963: "PixelYDimension",
  40964: "RelatedSoundFile",
  40965: "Interoperability IFD Pointer",
  41483: "FlashEnergy",
  41484: {
    "name": "SpatialFrequencyResponse",
    "description": () => "[Raw SFR table data]"
  },
  41486: "FocalPlaneXResolution",
  41487: "FocalPlaneYResolution",
  41488: {
    "name": "FocalPlaneResolutionUnit",
    "description": tag_names_common_default.FocalPlaneResolutionUnit
  },
  41492: {
    "name": "SubjectLocation",
    "description": ([x, y]) => `X: ${x}, Y: ${y}`
  },
  41493: "ExposureIndex",
  41495: {
    "name": "SensingMethod",
    "description": (value) => {
      if (value === 1) {
        return "Undefined";
      } else if (value === 2) {
        return "One-chip color area sensor";
      } else if (value === 3) {
        return "Two-chip color area sensor";
      } else if (value === 4) {
        return "Three-chip color area sensor";
      } else if (value === 5) {
        return "Color sequential area sensor";
      } else if (value === 7) {
        return "Trilinear sensor";
      } else if (value === 8) {
        return "Color sequential linear sensor";
      }
      return "Unknown";
    }
  },
  41728: {
    "name": "FileSource",
    "description": (value) => {
      if (value === 3) {
        return "DSC";
      }
      return "Unknown";
    }
  },
  41729: {
    "name": "SceneType",
    "description": (value) => {
      if (value === 1) {
        return "A directly photographed image";
      }
      return "Unknown";
    }
  },
  41730: {
    "name": "CFAPattern",
    "description": () => "[Raw CFA pattern table data]"
  },
  41985: {
    "name": "CustomRendered",
    "description": tag_names_common_default.CustomRendered
  },
  41986: {
    "name": "ExposureMode",
    "description": tag_names_common_default.ExposureMode
  },
  41987: {
    "name": "WhiteBalance",
    "description": tag_names_common_default.WhiteBalance
  },
  41988: {
    "name": "DigitalZoomRatio",
    "description": (value) => {
      if (value[0] === 0) {
        return "Digital zoom was not used";
      }
      return "" + value[0] / value[1];
    }
  },
  41989: {
    "name": "FocalLengthIn35mmFilm",
    // Sometimes called FocalLengthIn35mmFormat.
    "description": tag_names_common_default.FocalLengthIn35mmFilm
  },
  41990: {
    "name": "SceneCaptureType",
    "description": tag_names_common_default.SceneCaptureType
  },
  41991: {
    "name": "GainControl",
    "description": (value) => {
      if (value === 0) {
        return "None";
      } else if (value === 1) {
        return "Low gain up";
      } else if (value === 2) {
        return "High gain up";
      } else if (value === 3) {
        return "Low gain down";
      } else if (value === 4) {
        return "High gain down";
      }
      return "Unknown";
    }
  },
  41992: {
    "name": "Contrast",
    "description": tag_names_common_default.Contrast
  },
  41993: {
    "name": "Saturation",
    "description": tag_names_common_default.Saturation
  },
  41994: {
    "name": "Sharpness",
    "description": tag_names_common_default.Sharpness
  },
  41995: {
    "name": "DeviceSettingDescription",
    "description": () => "[Raw device settings table data]"
  },
  41996: {
    "name": "SubjectDistanceRange",
    "description": (value) => {
      if (value === 1) {
        return "Macro";
      } else if (value === 2) {
        return "Close view";
      } else if (value === 3) {
        return "Distant view";
      }
      return "Unknown";
    }
  },
  42016: "ImageUniqueID",
  42032: "CameraOwnerName",
  42033: "BodySerialNumber",
  42034: {
    "name": "LensSpecification",
    "description": (value) => {
      const focalLengthFrom = parseFloat((value[0][0] / value[0][1]).toFixed(5));
      const focalLengthTo = parseFloat((value[1][0] / value[1][1]).toFixed(5));
      const focalLengths = `${focalLengthFrom}-${focalLengthTo} mm`;
      if (value[3][1] === 0) {
        return `${focalLengths} f/?`;
      }
      const maxAperture = 1 / (value[2][1] / value[2][1] / (value[3][0] / value[3][1]));
      return `${focalLengths} f/${parseFloat(maxAperture.toFixed(5))}`;
    }
  },
  42035: "LensMake",
  42036: "LensModel",
  42037: "LensSerialNumber",
  42080: {
    name: "CompositeImage",
    description: (value) => ({
      1: "Not a Composite Image",
      2: "General Composite Image",
      3: "Composite Image Captured While Shooting"
    })[value] || "Unknown"
  },
  42081: "SourceImageNumberOfCompositeImage",
  42082: "SourceExposureTimesOfCompositeImage",
  42240: "Gamma",
  59932: "Padding",
  59933: "OffsetSchema",
  65e3: "OwnerName",
  65001: "SerialNumber",
  65002: "Lens",
  65100: "RawFile",
  65101: "Converter",
  65102: "WhiteBalance",
  65105: "Exposure",
  65106: "Shadows",
  65107: "Brightness",
  65108: "Contrast",
  65109: "Saturation",
  65110: "Sharpness",
  65111: "Smoothness",
  65112: "MoireFilter"
};

// node_modules/exifreader/src/tag-names-gps-ifd.js
var tag_names_gps_ifd_default = {
  0: {
    "name": "GPSVersionID",
    "description": (value) => {
      if (value[0] === 2 && value[1] === 2 && value[2] === 0 && value[3] === 0) {
        return "Version 2.2";
      }
      return "Unknown";
    }
  },
  1: {
    "name": "GPSLatitudeRef",
    "description": (value) => {
      const ref = value.join("");
      if (ref === "N") {
        return "North latitude";
      } else if (ref === "S") {
        return "South latitude";
      }
      return "Unknown";
    }
  },
  2: {
    "name": "GPSLatitude",
    "description": getCalculatedGpsValue
  },
  3: {
    "name": "GPSLongitudeRef",
    "description": (value) => {
      const ref = value.join("");
      if (ref === "E") {
        return "East longitude";
      } else if (ref === "W") {
        return "West longitude";
      }
      return "Unknown";
    }
  },
  4: {
    "name": "GPSLongitude",
    "description": getCalculatedGpsValue
  },
  5: {
    "name": "GPSAltitudeRef",
    "description": (value) => {
      if (value === 0) {
        return "Sea level";
      } else if (value === 1) {
        return "Sea level reference (negative value)";
      }
      return "Unknown";
    }
  },
  6: {
    "name": "GPSAltitude",
    "description": (value) => {
      return value[0] / value[1] + " m";
    }
  },
  7: {
    "name": "GPSTimeStamp",
    "description": (values) => {
      return values.map(([numerator, denominator]) => {
        const num = numerator / denominator;
        if (/^\d(\.|$)/.test(`${num}`)) {
          return `0${num}`;
        }
        return num;
      }).join(":");
    }
  },
  8: "GPSSatellites",
  9: {
    "name": "GPSStatus",
    "description": (value) => {
      const status = value.join("");
      if (status === "A") {
        return "Measurement in progress";
      } else if (status === "V") {
        return "Measurement Interoperability";
      }
      return "Unknown";
    }
  },
  10: {
    "name": "GPSMeasureMode",
    "description": (value) => {
      const mode = value.join("");
      if (mode === "2") {
        return "2-dimensional measurement";
      } else if (mode === "3") {
        return "3-dimensional measurement";
      }
      return "Unknown";
    }
  },
  11: "GPSDOP",
  12: {
    "name": "GPSSpeedRef",
    "description": (value) => {
      const ref = value.join("");
      if (ref === "K") {
        return "Kilometers per hour";
      } else if (ref === "M") {
        return "Miles per hour";
      } else if (ref === "N") {
        return "Knots";
      }
      return "Unknown";
    }
  },
  13: "GPSSpeed",
  14: {
    "name": "GPSTrackRef",
    "description": (value) => {
      const ref = value.join("");
      if (ref === "T") {
        return "True direction";
      } else if (ref === "M") {
        return "Magnetic direction";
      }
      return "Unknown";
    }
  },
  15: "GPSTrack",
  16: {
    "name": "GPSImgDirectionRef",
    "description": (value) => {
      const ref = value.join("");
      if (ref === "T") {
        return "True direction";
      } else if (ref === "M") {
        return "Magnetic direction";
      }
      return "Unknown";
    }
  },
  17: "GPSImgDirection",
  18: "GPSMapDatum",
  19: {
    "name": "GPSDestLatitudeRef",
    "description": (value) => {
      const ref = value.join("");
      if (ref === "N") {
        return "North latitude";
      } else if (ref === "S") {
        return "South latitude";
      }
      return "Unknown";
    }
  },
  20: {
    "name": "GPSDestLatitude",
    "description": (value) => {
      return value[0][0] / value[0][1] + value[1][0] / value[1][1] / 60 + value[2][0] / value[2][1] / 3600;
    }
  },
  21: {
    "name": "GPSDestLongitudeRef",
    "description": (value) => {
      const ref = value.join("");
      if (ref === "E") {
        return "East longitude";
      } else if (ref === "W") {
        return "West longitude";
      }
      return "Unknown";
    }
  },
  22: {
    "name": "GPSDestLongitude",
    "description": (value) => {
      return value[0][0] / value[0][1] + value[1][0] / value[1][1] / 60 + value[2][0] / value[2][1] / 3600;
    }
  },
  23: {
    "name": "GPSDestBearingRef",
    "description": (value) => {
      const ref = value.join("");
      if (ref === "T") {
        return "True direction";
      } else if (ref === "M") {
        return "Magnetic direction";
      }
      return "Unknown";
    }
  },
  24: "GPSDestBearing",
  25: {
    "name": "GPSDestDistanceRef",
    "description": (value) => {
      const ref = value.join("");
      if (ref === "K") {
        return "Kilometers";
      } else if (ref === "M") {
        return "Miles";
      } else if (ref === "N") {
        return "Knots";
      }
      return "Unknown";
    }
  },
  26: "GPSDestDistance",
  27: {
    "name": "GPSProcessingMethod",
    "description": getEncodedString
  },
  28: {
    "name": "GPSAreaInformation",
    "description": getEncodedString
  },
  29: "GPSDateStamp",
  30: {
    "name": "GPSDifferential",
    "description": (value) => {
      if (value === 0) {
        return "Measurement without differential correction";
      } else if (value === 1) {
        return "Differential correction applied";
      }
      return "Unknown";
    }
  },
  31: "GPSHPositioningError"
};

// node_modules/exifreader/src/tag-names-interoperability-ifd.js
var tag_names_interoperability_ifd_default = {
  1: "InteroperabilityIndex",
  2: {
    name: "InteroperabilityVersion",
    description: (value) => getStringValue(value)
  },
  4096: "RelatedImageFileFormat",
  4097: "RelatedImageWidth",
  4098: "RelatedImageHeight"
};

// node_modules/exifreader/src/tag-names-mpf-ifd.js
var tag_names_mpf_ifd_default = {
  45056: {
    "name": "MPFVersion",
    "description": (value) => getStringValue(value)
  },
  45057: "NumberOfImages",
  45058: "MPEntry",
  45059: "ImageUIDList",
  45060: "TotalFrames"
};

// node_modules/exifreader/src/tag-names-canon-ifd.js
var tag_names_canon_ifd_default = {
  4: {
    "name": "ShotInfo",
    "description": (value) => value
  }
};

// node_modules/exifreader/src/tag-names-pentax-ifd.js
var tag_names_pentax_ifd_default = {
  0: {
    "name": "PentaxVersion",
    "description": (value) => value.join(".")
  },
  5: "PentaxModelID",
  555: "LevelInfo"
};

// node_modules/exifreader/src/tag-names.js
var tagNames0thExifIfds = objectAssign({}, tag_names_0th_ifd_default, tag_names_exif_ifd_default);
var IFD_TYPE_0TH = "0th";
var IFD_TYPE_1ST = "1st";
var IFD_TYPE_EXIF = "exif";
var IFD_TYPE_GPS = "gps";
var IFD_TYPE_INTEROPERABILITY = "interoperability";
var IFD_TYPE_MPF = "mpf";
var IFD_TYPE_CANON = "canon";
var IFD_TYPE_PENTAX = "pentax";
var tag_names_default = {
  [IFD_TYPE_0TH]: tagNames0thExifIfds,
  [IFD_TYPE_1ST]: tag_names_0th_ifd_default,
  [IFD_TYPE_EXIF]: tagNames0thExifIfds,
  [IFD_TYPE_GPS]: tag_names_gps_ifd_default,
  [IFD_TYPE_INTEROPERABILITY]: tag_names_interoperability_ifd_default,
  [IFD_TYPE_MPF]: constants_default.USE_MPF ? tag_names_mpf_ifd_default : {},
  [IFD_TYPE_CANON]: constants_default.USE_MAKER_NOTES ? tag_names_canon_ifd_default : {},
  [IFD_TYPE_PENTAX]: constants_default.USE_MAKER_NOTES ? tag_names_pentax_ifd_default : {}
};

// node_modules/exifreader/src/types.js
var typeSizes = {
  1: 1,
  // BYTE
  2: 1,
  // ASCII
  3: 2,
  // SHORT
  4: 4,
  // LONG
  5: 8,
  // RATIONAL
  7: 1,
  // UNDEFINED
  9: 4,
  // SLONG
  10: 8,
  // SRATIONAL
  13: 4
  // IFD
};
var tagTypes = {
  "BYTE": 1,
  "ASCII": 2,
  "SHORT": 3,
  "LONG": 4,
  "RATIONAL": 5,
  "UNDEFINED": 7,
  "SLONG": 9,
  "SRATIONAL": 10,
  "IFD": 13
};
var types_default = {
  getAsciiValue,
  getByteAt,
  getAsciiAt,
  getShortAt,
  getLongAt,
  getRationalAt,
  getUndefinedAt,
  getSlongAt,
  getSrationalAt,
  getIfdPointerAt,
  typeSizes,
  tagTypes,
  getTypeSize
};
function getAsciiValue(charArray) {
  return charArray.map((charCode) => String.fromCharCode(charCode));
}
function getByteAt(dataView, offset) {
  return dataView.getUint8(offset);
}
function getAsciiAt(dataView, offset) {
  return dataView.getUint8(offset);
}
function getShortAt(dataView, offset, byteOrder) {
  return dataView.getUint16(offset, byteOrder === byte_order_default.LITTLE_ENDIAN);
}
function getLongAt(dataView, offset, byteOrder) {
  return dataView.getUint32(offset, byteOrder === byte_order_default.LITTLE_ENDIAN);
}
function getRationalAt(dataView, offset, byteOrder) {
  return [getLongAt(dataView, offset, byteOrder), getLongAt(dataView, offset + 4, byteOrder)];
}
function getUndefinedAt(dataView, offset) {
  return getByteAt(dataView, offset);
}
function getSlongAt(dataView, offset, byteOrder) {
  return dataView.getInt32(offset, byteOrder === byte_order_default.LITTLE_ENDIAN);
}
function getSrationalAt(dataView, offset, byteOrder) {
  return [getSlongAt(dataView, offset, byteOrder), getSlongAt(dataView, offset + 4, byteOrder)];
}
function getIfdPointerAt(dataView, offset, byteOrder) {
  return getLongAt(dataView, offset, byteOrder);
}
function getTypeSize(typeName) {
  if (tagTypes[typeName] === void 0) {
    throw new Error("No such type found.");
  }
  return typeSizes[tagTypes[typeName]];
}

// node_modules/exifreader/src/tags-helpers.js
var getTagValueAt = {
  1: types_default.getByteAt,
  2: types_default.getAsciiAt,
  3: types_default.getShortAt,
  4: types_default.getLongAt,
  5: types_default.getRationalAt,
  7: types_default.getUndefinedAt,
  9: types_default.getSlongAt,
  10: types_default.getSrationalAt,
  13: types_default.getIfdPointerAt
};
function get0thIfdOffset(dataView, tiffHeaderOffset, byteOrder) {
  return tiffHeaderOffset + types_default.getLongAt(
    dataView,
    tiffHeaderOffset + TIFF_IFD_OFFSET_OFFSET,
    byteOrder
  );
}
function readIfd(dataView, ifdType, offsetOrigin, offset, byteOrder, includeUnknown, computed = false) {
  const FIELD_COUNT_SIZE = types_default.getTypeSize("SHORT");
  const FIELD_SIZE = IFD_ENTRY_LENGTH;
  const tags = {};
  const numberOfFields = getNumberOfFields(dataView, offset, byteOrder);
  offset += FIELD_COUNT_SIZE;
  for (let fieldIndex = 0; fieldIndex < numberOfFields; fieldIndex++) {
    if (offset + FIELD_SIZE > dataView.byteLength) {
      break;
    }
    const tag = readTag(dataView, ifdType, offsetOrigin, offset, byteOrder, includeUnknown);
    if (tag !== void 0) {
      tags[tag.name] = {
        "id": tag.id,
        "value": tag.value,
        "description": tag.description
      };
      if (computed) {
        tags[tag.name].computed = getComputedTagValue(tag.tagType, tag.value);
      }
      if (tag.name === "MakerNote" || ifdType === IFD_TYPE_PENTAX && tag.name === "LevelInfo") {
        tags[tag.name].__offset = tag.__offset;
      }
    }
    offset += FIELD_SIZE;
  }
  if (constants_default.USE_THUMBNAIL && offset < dataView.byteLength - types_default.getTypeSize("LONG")) {
    const nextIfdOffset = types_default.getLongAt(dataView, offset, byteOrder);
    if (nextIfdOffset !== 0 && ifdType === IFD_TYPE_0TH) {
      tags["Thumbnail"] = readIfd(
        dataView,
        IFD_TYPE_1ST,
        offsetOrigin,
        offsetOrigin + nextIfdOffset,
        byteOrder,
        includeUnknown,
        computed
      );
    }
  }
  return tags;
}
function getNumberOfFields(dataView, offset, byteOrder) {
  if (offset + types_default.getTypeSize("SHORT") <= dataView.byteLength) {
    return types_default.getShortAt(dataView, offset, byteOrder);
  }
  return 0;
}
function readTag(dataView, ifdType, offsetOrigin, offset, byteOrder, includeUnknown) {
  const TAG_CODE_IPTC_NAA = 33723;
  const TAG_TYPE_OFFSET = types_default.getTypeSize("SHORT");
  const TAG_COUNT_OFFSET = TAG_TYPE_OFFSET + types_default.getTypeSize("SHORT");
  const TAG_VALUE_OFFSET = TAG_COUNT_OFFSET + types_default.getTypeSize("LONG");
  const tagCode = types_default.getShortAt(dataView, offset, byteOrder);
  const tagType = types_default.getShortAt(dataView, offset + TAG_TYPE_OFFSET, byteOrder);
  const tagCount = types_default.getLongAt(dataView, offset + TAG_COUNT_OFFSET, byteOrder);
  let tagValue;
  let tagValueOffset;
  if (types_default.typeSizes[tagType] === void 0 || !includeUnknown && tag_names_default[ifdType][tagCode] === void 0) {
    return void 0;
  }
  if (tagValueFitsInOffsetSlot(tagType, tagCount)) {
    tagValueOffset = offset + TAG_VALUE_OFFSET;
    tagValue = getTagValue(dataView, tagValueOffset, tagType, tagCount, byteOrder);
  } else {
    tagValueOffset = types_default.getLongAt(dataView, offset + TAG_VALUE_OFFSET, byteOrder);
    if (tagValueFitsInDataView(dataView, offsetOrigin, tagValueOffset, tagType, tagCount)) {
      const forceByteType = tagCode === TAG_CODE_IPTC_NAA;
      tagValue = getTagValue(dataView, offsetOrigin + tagValueOffset, tagType, tagCount, byteOrder, forceByteType);
    } else {
      tagValue = "<faulty value>";
    }
  }
  if (tagType === types_default.tagTypes["ASCII"]) {
    tagValue = splitNullSeparatedAsciiString(tagValue);
    tagValue = decodeAsciiValue(tagValue);
  }
  let tagName = `undefined-${tagCode}`;
  let tagDescription = tagValue;
  if (tag_names_default[ifdType][tagCode] !== void 0) {
    if (tag_names_default[ifdType][tagCode]["name"] !== void 0 && tag_names_default[ifdType][tagCode]["description"] !== void 0) {
      tagName = tag_names_default[ifdType][tagCode]["name"];
      try {
        tagDescription = tag_names_default[ifdType][tagCode]["description"](tagValue);
      } catch (error) {
        tagDescription = getDescriptionFromTagValue(tagValue);
      }
    } else if (tagType === types_default.tagTypes["RATIONAL"] || tagType === types_default.tagTypes["SRATIONAL"]) {
      tagName = tag_names_default[ifdType][tagCode];
      tagDescription = "" + tagValue[0] / tagValue[1];
    } else {
      tagName = tag_names_default[ifdType][tagCode];
      tagDescription = getDescriptionFromTagValue(tagValue);
    }
  }
  return {
    id: tagCode,
    name: tagName,
    value: tagValue,
    description: tagDescription,
    tagType,
    __offset: tagValueOffset
  };
}
function tagValueFitsInOffsetSlot(tagType, tagCount) {
  return types_default.typeSizes[tagType] * tagCount <= types_default.getTypeSize("LONG");
}
function getTagValue(dataView, offset, type, count, byteOrder, forceByteType = false) {
  let value = [];
  if (forceByteType) {
    count = count * types_default.typeSizes[type];
    type = types_default.tagTypes["BYTE"];
  }
  for (let valueIndex = 0; valueIndex < count; valueIndex++) {
    value.push(getTagValueAt[type](dataView, offset, byteOrder));
    offset += types_default.typeSizes[type];
  }
  if (type === types_default.tagTypes["ASCII"]) {
    value = types_default.getAsciiValue(value);
  } else if (value.length === 1) {
    value = value[0];
  }
  return value;
}
function tagValueFitsInDataView(dataView, offsetOrigin, tagValueOffset, tagType, tagCount) {
  return offsetOrigin + tagValueOffset + types_default.typeSizes[tagType] * tagCount <= dataView.byteLength;
}
function splitNullSeparatedAsciiString(string) {
  const tagValue = [];
  let i = 0;
  for (let j = 0; j < string.length; j++) {
    if (string[j] === "\0") {
      i++;
      continue;
    }
    if (tagValue[i] === void 0) {
      tagValue[i] = "";
    }
    tagValue[i] += string[j];
  }
  return tagValue;
}
function decodeAsciiValue(asciiValue) {
  try {
    return asciiValue.map((value) => decodeURIComponent(escape(value)));
  } catch (error) {
    return asciiValue;
  }
}
function getDescriptionFromTagValue(tagValue) {
  if (tagValue instanceof Array) {
    return tagValue.join(", ");
  }
  return tagValue;
}
function getComputedTagValue(tagType, value) {
  if (tagType === types_default.tagTypes["ASCII"]) {
    if (Array.isArray(value) && value.length === 1) {
      return value[0];
    }
    return value;
  }
  if (tagType === types_default.tagTypes["RATIONAL"] || tagType === types_default.tagTypes["SRATIONAL"]) {
    if (isSingleRationalValue(value)) {
      return getComputedRationalValue(value);
    }
    if (Array.isArray(value)) {
      return value.map((rational) => getComputedRationalValue(rational));
    }
    return value;
  }
  return value;
}
function isSingleRationalValue(value) {
  if (!Array.isArray(value) || value.length !== 2) {
    return false;
  }
  return typeof value[0] === "number" && typeof value[1] === "number";
}
function getComputedRationalValue(rational) {
  if (!Array.isArray(rational) || rational.length !== 2) {
    return rational;
  }
  const numerator = rational[0];
  const denominator = rational[1];
  if (!Number.isFinite(numerator) || !Number.isFinite(denominator)) {
    return rational;
  }
  if (denominator === 0) {
    return null;
  }
  return numerator / denominator;
}

// node_modules/exifreader/src/tags.js
var EXIF_IFD_POINTER_KEY = "Exif IFD Pointer";
var GPS_INFO_IFD_POINTER_KEY = "GPS Info IFD Pointer";
var INTEROPERABILITY_IFD_POINTER_KEY = "Interoperability IFD Pointer";
var tags_default = {
  read
};
function read(dataView, tiffHeaderOffset, includeUnknown, computed = false) {
  const byteOrder = byte_order_default.getByteOrder(dataView, tiffHeaderOffset);
  let tags = read0thIfd(dataView, tiffHeaderOffset, byteOrder, includeUnknown, computed);
  tags = readExifIfd(tags, dataView, tiffHeaderOffset, byteOrder, includeUnknown, computed);
  tags = readGpsIfd(tags, dataView, tiffHeaderOffset, byteOrder, includeUnknown, computed);
  tags = readInteroperabilityIfd(tags, dataView, tiffHeaderOffset, byteOrder, includeUnknown, computed);
  return { tags, byteOrder };
}
function read0thIfd(dataView, tiffHeaderOffset, byteOrder, includeUnknown, computed) {
  return readIfd(dataView, IFD_TYPE_0TH, tiffHeaderOffset, get0thIfdOffset(dataView, tiffHeaderOffset, byteOrder), byteOrder, includeUnknown, computed);
}
function readExifIfd(tags, dataView, tiffHeaderOffset, byteOrder, includeUnknown, computed) {
  if (tags[EXIF_IFD_POINTER_KEY] !== void 0) {
    return objectAssign(
      tags,
      readIfd(
        dataView,
        IFD_TYPE_EXIF,
        tiffHeaderOffset,
        tiffHeaderOffset + tags[EXIF_IFD_POINTER_KEY].value,
        byteOrder,
        includeUnknown,
        computed
      )
    );
  }
  return tags;
}
function readGpsIfd(tags, dataView, tiffHeaderOffset, byteOrder, includeUnknown, computed) {
  if (tags[GPS_INFO_IFD_POINTER_KEY] !== void 0) {
    return objectAssign(
      tags,
      readIfd(
        dataView,
        IFD_TYPE_GPS,
        tiffHeaderOffset,
        tiffHeaderOffset + tags[GPS_INFO_IFD_POINTER_KEY].value,
        byteOrder,
        includeUnknown,
        computed
      )
    );
  }
  return tags;
}
function readInteroperabilityIfd(tags, dataView, tiffHeaderOffset, byteOrder, includeUnknown, computed) {
  if (tags[INTEROPERABILITY_IFD_POINTER_KEY] !== void 0) {
    return objectAssign(
      tags,
      readIfd(
        dataView,
        IFD_TYPE_INTEROPERABILITY,
        tiffHeaderOffset,
        tiffHeaderOffset + tags[INTEROPERABILITY_IFD_POINTER_KEY].value,
        byteOrder,
        includeUnknown,
        computed
      )
    );
  }
  return tags;
}

// node_modules/exifreader/src/mpf-tags.js
var mpf_tags_default = {
  read: read2
};
var ENTRY_SIZE = 16;
function read2(dataView, dataOffset, includeUnknown, computed = false) {
  const byteOrder = byte_order_default.getByteOrder(dataView, dataOffset);
  const tags = readIfd(
    dataView,
    IFD_TYPE_MPF,
    dataOffset,
    get0thIfdOffset(dataView, dataOffset, byteOrder),
    byteOrder,
    includeUnknown,
    computed
  );
  return addMpfImages(dataView, dataOffset, tags, byteOrder);
}
function addMpfImages(dataView, dataOffset, tags, byteOrder) {
  if (!tags["MPEntry"]) {
    return tags;
  }
  const images = [];
  for (let i = 0; i < Math.ceil(tags["MPEntry"].value.length / ENTRY_SIZE); i++) {
    images[i] = {};
    const attributes = getImageNumberValue(tags["MPEntry"].value, i * ENTRY_SIZE, types_default.getTypeSize("LONG"), byteOrder);
    images[i]["ImageFlags"] = getImageFlags(attributes);
    images[i]["ImageFormat"] = getImageFormat(attributes);
    images[i]["ImageType"] = getImageType(attributes);
    const imageSize = getImageNumberValue(tags["MPEntry"].value, i * ENTRY_SIZE + 4, types_default.getTypeSize("LONG"), byteOrder);
    images[i]["ImageSize"] = {
      value: imageSize,
      description: "" + imageSize
    };
    const imageOffset = getImageOffset(i, tags["MPEntry"], byteOrder, dataOffset);
    images[i]["ImageOffset"] = {
      value: imageOffset,
      description: "" + imageOffset
    };
    const dependentImage1EntryNumber = getImageNumberValue(tags["MPEntry"].value, i * ENTRY_SIZE + 12, types_default.getTypeSize("SHORT"), byteOrder);
    images[i]["DependentImage1EntryNumber"] = {
      value: dependentImage1EntryNumber,
      description: "" + dependentImage1EntryNumber
    };
    const dependentImage2EntryNumber = getImageNumberValue(tags["MPEntry"].value, i * ENTRY_SIZE + 14, types_default.getTypeSize("SHORT"), byteOrder);
    images[i]["DependentImage2EntryNumber"] = {
      value: dependentImage2EntryNumber,
      description: "" + dependentImage2EntryNumber
    };
    images[i].image = dataView.buffer.slice(imageOffset, imageOffset + imageSize);
    deferInit(images[i], "base64", function() {
      return getBase64Image(this.image);
    });
  }
  tags["Images"] = images;
  return tags;
}
function getImageNumberValue(entries, offset, size, byteOrder) {
  if (byteOrder === byte_order_default.LITTLE_ENDIAN) {
    let value2 = 0;
    for (let i = 0; i < size; i++) {
      value2 += entries[offset + i] << 8 * i;
    }
    return value2;
  }
  let value = 0;
  for (let i = 0; i < size; i++) {
    value += entries[offset + i] << 8 * (size - 1 - i);
  }
  return value;
}
function getImageFlags(attributes) {
  const flags = [
    attributes >> 31 & 1,
    attributes >> 30 & 1,
    attributes >> 29 & 1
  ];
  const flagsDescription = [];
  if (flags[0]) {
    flagsDescription.push("Dependent Parent Image");
  }
  if (flags[1]) {
    flagsDescription.push("Dependent Child Image");
  }
  if (flags[2]) {
    flagsDescription.push("Representative Image");
  }
  return {
    value: flags,
    description: flagsDescription.join(", ") || "None"
  };
}
function getImageFormat(attributes) {
  const imageFormat = attributes >> 24 & 7;
  return {
    value: imageFormat,
    description: imageFormat === 0 ? "JPEG" : "Unknown"
  };
}
function getImageType(attributes) {
  const type = attributes & 16777215;
  const descriptions = {
    196608: "Baseline MP Primary Image",
    65537: "Large Thumbnail (VGA equivalent)",
    65538: "Large Thumbnail (Full HD equivalent)",
    131073: "Multi-Frame Image (Panorama)",
    131074: "Multi-Frame Image (Disparity)",
    131075: "Multi-Frame Image (Multi-Angle)",
    0: "Undefined"
  };
  return {
    value: type,
    description: descriptions[type] || "Unknown"
  };
}
function getImageOffset(imageIndex, mpEntry, byteOrder, dataOffset) {
  if (isFirstIndividualImage(imageIndex)) {
    return 0;
  }
  return getImageNumberValue(mpEntry.value, imageIndex * ENTRY_SIZE + 8, types_default.getTypeSize("LONG"), byteOrder) + dataOffset;
}
function isFirstIndividualImage(imageIndex) {
  return imageIndex === 0;
}

// node_modules/exifreader/src/file-tags.js
var file_tags_default = {
  read: read3
};
function read3(dataView, fileDataOffset) {
  const length = getLength(dataView, fileDataOffset);
  const numberOfColorComponents = getNumberOfColorComponents(dataView, fileDataOffset, length);
  return {
    "Bits Per Sample": getDataPrecision(dataView, fileDataOffset, length),
    "Image Height": getImageHeight(dataView, fileDataOffset, length),
    "Image Width": getImageWidth(dataView, fileDataOffset, length),
    "Color Components": numberOfColorComponents,
    "Subsampling": numberOfColorComponents && getSubsampling(dataView, fileDataOffset, numberOfColorComponents.value, length)
  };
}
function getLength(dataView, fileDataOffset) {
  return types_default.getShortAt(dataView, fileDataOffset);
}
function getDataPrecision(dataView, fileDataOffset, length) {
  const OFFSET = 2;
  const SIZE = 1;
  if (OFFSET + SIZE > length) {
    return void 0;
  }
  const value = types_default.getByteAt(dataView, fileDataOffset + OFFSET);
  return {
    value,
    description: "" + value
  };
}
function getImageHeight(dataView, fileDataOffset, length) {
  const OFFSET = 3;
  const SIZE = 2;
  if (OFFSET + SIZE > length) {
    return void 0;
  }
  const value = types_default.getShortAt(dataView, fileDataOffset + OFFSET);
  return {
    value,
    description: `${value}px`
  };
}
function getImageWidth(dataView, fileDataOffset, length) {
  const OFFSET = 5;
  const SIZE = 2;
  if (OFFSET + SIZE > length) {
    return void 0;
  }
  const value = types_default.getShortAt(dataView, fileDataOffset + OFFSET);
  return {
    value,
    description: `${value}px`
  };
}
function getNumberOfColorComponents(dataView, fileDataOffset, length) {
  const OFFSET = 7;
  const SIZE = 1;
  if (OFFSET + SIZE > length) {
    return void 0;
  }
  const value = types_default.getByteAt(dataView, fileDataOffset + OFFSET);
  return {
    value,
    description: "" + value
  };
}
function getSubsampling(dataView, fileDataOffset, numberOfColorComponents, length) {
  const OFFSET = 8;
  const SIZE = 3 * numberOfColorComponents;
  if (OFFSET + SIZE > length) {
    return void 0;
  }
  const components = [];
  for (let i = 0; i < numberOfColorComponents; i++) {
    const componentOffset = fileDataOffset + OFFSET + i * 3;
    components.push([
      types_default.getByteAt(dataView, componentOffset),
      types_default.getByteAt(dataView, componentOffset + 1),
      types_default.getByteAt(dataView, componentOffset + 2)
    ]);
  }
  return {
    value: components,
    description: components.length > 1 ? getComponentIds(components) + getSamplingType(components) : ""
  };
}
function getComponentIds(components) {
  const ids = {
    1: "Y",
    2: "Cb",
    3: "Cr",
    4: "I",
    5: "Q"
  };
  return components.map((compontent) => ids[compontent[0]]).join("");
}
function getSamplingType(components) {
  const types = {
    17: "4:4:4 (1 1)",
    18: "4:4:0 (1 2)",
    20: "4:4:1 (1 4)",
    33: "4:2:2 (2 1)",
    34: "4:2:0 (2 2)",
    36: "4:2:1 (2 4)",
    65: "4:1:1 (4 1)",
    66: "4:1:0 (4 2)"
  };
  if (components.length === 0 || components[0][1] === void 0 || types[components[0][1]] === void 0) {
    return "";
  }
  return types[components[0][1]];
}

// node_modules/exifreader/src/jfif-tags.js
var jfif_tags_default = {
  read: read4
};
function read4(dataView, jfifDataOffset) {
  const length = getLength2(dataView, jfifDataOffset);
  const thumbnailWidth = getThumbnailWidth(dataView, jfifDataOffset, length);
  const thumbnailHeight = getThumbnailHeight(dataView, jfifDataOffset, length);
  const tags = {
    "JFIF Version": getVersion(dataView, jfifDataOffset, length),
    "Resolution Unit": getResolutionUnit(dataView, jfifDataOffset, length),
    "XResolution": getXResolution(dataView, jfifDataOffset, length),
    "YResolution": getYResolution(dataView, jfifDataOffset, length),
    "JFIF Thumbnail Width": thumbnailWidth,
    "JFIF Thumbnail Height": thumbnailHeight
  };
  if (thumbnailWidth !== void 0 && thumbnailHeight !== void 0) {
    const thumbnail = getThumbnail(dataView, jfifDataOffset, 3 * thumbnailWidth.value * thumbnailHeight.value, length);
    if (thumbnail) {
      tags["JFIF Thumbnail"] = thumbnail;
    }
  }
  for (const tagName in tags) {
    if (tags[tagName] === void 0) {
      delete tags[tagName];
    }
  }
  return tags;
}
function getLength2(dataView, jfifDataOffset) {
  return types_default.getShortAt(dataView, jfifDataOffset);
}
function getVersion(dataView, jfifDataOffset, length) {
  const OFFSET = 7;
  const SIZE = 2;
  if (OFFSET + SIZE > length) {
    return void 0;
  }
  const majorVersion = types_default.getByteAt(dataView, jfifDataOffset + OFFSET);
  const minorVersion = types_default.getByteAt(dataView, jfifDataOffset + OFFSET + 1);
  return {
    value: majorVersion * 256 + minorVersion,
    description: majorVersion + "." + minorVersion
  };
}
function getResolutionUnit(dataView, jfifDataOffset, length) {
  const OFFSET = 9;
  const SIZE = 1;
  if (OFFSET + SIZE > length) {
    return void 0;
  }
  const value = types_default.getByteAt(dataView, jfifDataOffset + OFFSET);
  return {
    value,
    description: getResolutionUnitDescription(value)
  };
}
function getResolutionUnitDescription(value) {
  if (value === 0) {
    return "None";
  }
  if (value === 1) {
    return "inches";
  }
  if (value === 2) {
    return "cm";
  }
  return "Unknown";
}
function getXResolution(dataView, jfifDataOffset, length) {
  const OFFSET = 10;
  const SIZE = 2;
  if (OFFSET + SIZE > length) {
    return void 0;
  }
  const value = types_default.getShortAt(dataView, jfifDataOffset + OFFSET);
  return {
    value,
    description: "" + value
  };
}
function getYResolution(dataView, jfifDataOffset, length) {
  const OFFSET = 12;
  const SIZE = 2;
  if (OFFSET + SIZE > length) {
    return void 0;
  }
  const value = types_default.getShortAt(dataView, jfifDataOffset + OFFSET);
  return {
    value,
    description: "" + value
  };
}
function getThumbnailWidth(dataView, jfifDataOffset, length) {
  const OFFSET = 14;
  const SIZE = 1;
  if (OFFSET + SIZE > length) {
    return void 0;
  }
  const value = types_default.getByteAt(dataView, jfifDataOffset + OFFSET);
  return {
    value,
    description: `${value}px`
  };
}
function getThumbnailHeight(dataView, jfifDataOffset, length) {
  const OFFSET = 15;
  const SIZE = 1;
  if (OFFSET + SIZE > length) {
    return void 0;
  }
  const value = types_default.getByteAt(dataView, jfifDataOffset + OFFSET);
  return {
    value,
    description: `${value}px`
  };
}
function getThumbnail(dataView, jfifDataOffset, thumbnailLength, length) {
  const OFFSET = 16;
  if (thumbnailLength === 0 || OFFSET + thumbnailLength > length) {
    return void 0;
  }
  const value = dataView.buffer.slice(jfifDataOffset + OFFSET, jfifDataOffset + OFFSET + thumbnailLength);
  return {
    value,
    description: "<24-bit RGB pixel data>"
  };
}

// node_modules/exifreader/src/iptc-tag-names.js
var iptc_tag_names_default = {
  "iptc": {
    256: {
      "name": "Model Version",
      "description": (value) => {
        return ((value[0] << 8) + value[1]).toString();
      }
    },
    261: {
      "name": "Destination",
      "repeatable": true
    },
    276: {
      "name": "File Format",
      "description": (value) => {
        return ((value[0] << 8) + value[1]).toString();
      }
    },
    278: {
      "name": "File Format Version",
      "description": (value) => {
        return ((value[0] << 8) + value[1]).toString();
      }
    },
    286: "Service Identifier",
    296: "Envelope Number",
    306: "Product ID",
    316: "Envelope Priority",
    326: {
      "name": "Date Sent",
      "description": getCreationDate
    },
    336: {
      "name": "Time Sent",
      "description": getCreationTime
    },
    346: {
      "name": "Coded Character Set",
      "description": getEncodingName,
      "encoding_name": getEncodingName
    },
    356: "UNO",
    376: {
      "name": "ARM Identifier",
      "description": (value) => {
        return ((value[0] << 8) + value[1]).toString();
      }
    },
    378: {
      "name": "ARM Version",
      "description": (value) => {
        return ((value[0] << 8) + value[1]).toString();
      }
    },
    512: {
      "name": "Record Version",
      "description": (value) => {
        return ((value[0] << 8) + value[1]).toString();
      }
    },
    515: "Object Type Reference",
    516: "Object Attribute Reference",
    517: "Object Name",
    519: "Edit Status",
    520: {
      "name": "Editorial Update",
      "description": (value) => {
        if (getStringValue(value) === "01") {
          return "Additional Language";
        }
        return "Unknown";
      }
    },
    522: "Urgency",
    524: {
      "name": "Subject Reference",
      "repeatable": true,
      "description": (value) => {
        const parts = getStringValue(value).split(":");
        return parts[2] + (parts[3] ? "/" + parts[3] : "") + (parts[4] ? "/" + parts[4] : "");
      }
    },
    527: "Category",
    532: {
      "name": "Supplemental Category",
      "repeatable": true
    },
    534: "Fixture Identifier",
    537: {
      "name": "Keywords",
      "repeatable": true
    },
    538: {
      "name": "Content Location Code",
      "repeatable": true
    },
    539: {
      "name": "Content Location Name",
      "repeatable": true
    },
    542: "Release Date",
    547: "Release Time",
    549: "Expiration Date",
    550: "Expiration Time",
    552: "Special Instructions",
    554: {
      "name": "Action Advised",
      "description": (value) => {
        const string = getStringValue(value);
        if (string === "01") {
          return "Object Kill";
        } else if (string === "02") {
          return "Object Replace";
        } else if (string === "03") {
          return "Object Append";
        } else if (string === "04") {
          return "Object Reference";
        }
        return "Unknown";
      }
    },
    557: {
      "name": "Reference Service",
      "repeatable": true
    },
    559: {
      "name": "Reference Date",
      "repeatable": true
    },
    562: {
      "name": "Reference Number",
      "repeatable": true
    },
    567: {
      "name": "Date Created",
      "description": getCreationDate
    },
    572: {
      "name": "Time Created",
      "description": getCreationTime
    },
    574: {
      "name": "Digital Creation Date",
      "description": getCreationDate
    },
    575: {
      "name": "Digital Creation Time",
      "description": getCreationTime
    },
    577: "Originating Program",
    582: "Program Version",
    587: {
      "name": "Object Cycle",
      "description": (value) => {
        const string = getStringValue(value);
        if (string === "a") {
          return "morning";
        } else if (string === "p") {
          return "evening";
        } else if (string === "b") {
          return "both";
        }
        return "Unknown";
      }
    },
    592: {
      "name": "By-line",
      "repeatable": true
    },
    597: {
      "name": "By-line Title",
      "repeatable": true
    },
    602: "City",
    604: "Sub-location",
    607: "Province/State",
    612: "Country/Primary Location Code",
    613: "Country/Primary Location Name",
    615: "Original Transmission Reference",
    617: "Headline",
    622: "Credit",
    627: "Source",
    628: "Copyright Notice",
    630: {
      "name": "Contact",
      "repeatable": true
    },
    632: "Caption/Abstract",
    634: {
      "name": "Writer/Editor",
      "repeatable": true
    },
    637: {
      "name": "Rasterized Caption",
      "description": (value) => value
    },
    642: "Image Type",
    643: {
      "name": "Image Orientation",
      "description": (value) => {
        const string = getStringValue(value);
        if (string === "P") {
          return "Portrait";
        } else if (string === "L") {
          return "Landscape";
        } else if (string === "S") {
          return "Square";
        }
        return "Unknown";
      }
    },
    647: "Language Identifier",
    662: {
      "name": "Audio Type",
      "description": (value) => {
        const stringValue = getStringValue(value);
        const character0 = stringValue.charAt(0);
        const character1 = stringValue.charAt(1);
        let description = "";
        if (character0 === "1") {
          description += "Mono";
        } else if (character0 === "2") {
          description += "Stereo";
        }
        if (character1 === "A") {
          description += ", actuality";
        } else if (character1 === "C") {
          description += ", question and answer session";
        } else if (character1 === "M") {
          description += ", music, transmitted by itself";
        } else if (character1 === "Q") {
          description += ", response to a question";
        } else if (character1 === "R") {
          description += ", raw sound";
        } else if (character1 === "S") {
          description += ", scener";
        } else if (character1 === "V") {
          description += ", voicer";
        } else if (character1 === "W") {
          description += ", wrap";
        }
        if (description !== "") {
          return description;
        }
        return stringValue;
      }
    },
    663: {
      "name": "Audio Sampling Rate",
      "description": (value) => parseInt(getStringValue(value), 10) + " Hz"
    },
    664: {
      "name": "Audio Sampling Resolution",
      "description": (value) => {
        const bits = parseInt(getStringValue(value), 10);
        return bits + (bits === 1 ? " bit" : " bits");
      }
    },
    665: {
      "name": "Audio Duration",
      "description": (value) => {
        const duration = getStringValue(value);
        if (duration.length >= 6) {
          return duration.substr(0, 2) + ":" + duration.substr(2, 2) + ":" + duration.substr(4, 2);
        }
        return duration;
      }
    },
    666: "Audio Outcue",
    698: "Short Document ID",
    699: "Unique Document ID",
    700: "Owner ID",
    712: {
      "name": (value) => {
        if (value.length === 2) {
          return "ObjectData Preview File Format";
        }
        return "Record 2 destination";
      },
      "description": (value) => {
        if (value.length === 2) {
          const intValue = (value[0] << 8) + value[1];
          if (intValue === 0) {
            return "No ObjectData";
          } else if (intValue === 1) {
            return "IPTC-NAA Digital Newsphoto Parameter Record";
          } else if (intValue === 2) {
            return "IPTC7901 Recommended Message Format";
          } else if (intValue === 3) {
            return "Tagged Image File Format (Adobe/Aldus Image data)";
          } else if (intValue === 4) {
            return "Illustrator (Adobe Graphics data)";
          } else if (intValue === 5) {
            return "AppleSingle (Apple Computer Inc)";
          } else if (intValue === 6) {
            return "NAA 89-3 (ANPA 1312)";
          } else if (intValue === 7) {
            return "MacBinary II";
          } else if (intValue === 8) {
            return "IPTC Unstructured Character Oriented File Format (UCOFF)";
          } else if (intValue === 9) {
            return "United Press International ANPA 1312 variant";
          } else if (intValue === 10) {
            return "United Press International Down-Load Message";
          } else if (intValue === 11) {
            return "JPEG File Interchange (JFIF)";
          } else if (intValue === 12) {
            return "Photo-CD Image-Pac (Eastman Kodak)";
          } else if (intValue === 13) {
            return "Microsoft Bit Mapped Graphics File [*.BMP]";
          } else if (intValue === 14) {
            return "Digital Audio File [*.WAV] (Microsoft & Creative Labs)";
          } else if (intValue === 15) {
            return "Audio plus Moving Video [*.AVI] (Microsoft)";
          } else if (intValue === 16) {
            return "PC DOS/Windows Executable Files [*.COM][*.EXE]";
          } else if (intValue === 17) {
            return "Compressed Binary File [*.ZIP] (PKWare Inc)";
          } else if (intValue === 18) {
            return "Audio Interchange File Format AIFF (Apple Computer Inc)";
          } else if (intValue === 19) {
            return "RIFF Wave (Microsoft Corporation)";
          } else if (intValue === 20) {
            return "Freehand (Macromedia/Aldus)";
          } else if (intValue === 21) {
            return 'Hypertext Markup Language "HTML" (The Internet Society)';
          } else if (intValue === 22) {
            return "MPEG 2 Audio Layer 2 (Musicom), ISO/IEC";
          } else if (intValue === 23) {
            return "MPEG 2 Audio Layer 3, ISO/IEC";
          } else if (intValue === 24) {
            return "Portable Document File (*.PDF) Adobe";
          } else if (intValue === 25) {
            return "News Industry Text Format (NITF)";
          } else if (intValue === 26) {
            return "Tape Archive (*.TAR)";
          } else if (intValue === 27) {
            return "Tidningarnas Telegrambyr\xE5 NITF version (TTNITF DTD)";
          } else if (intValue === 28) {
            return "Ritzaus Bureau NITF version (RBNITF DTD)";
          } else if (intValue === 29) {
            return "Corel Draw [*.CDR]";
          }
          return `Unknown format ${intValue}`;
        }
        return getStringValue(value);
      }
    },
    713: {
      "name": "ObjectData Preview File Format Version",
      "description": (value, tags) => {
        const formatVersions = {
          "00": { "00": "1" },
          "01": { "01": "1", "02": "2", "03": "3", "04": "4" },
          "02": { "04": "4" },
          "03": { "01": "5.0", "02": "6.0" },
          "04": { "01": "1.40" },
          "05": { "01": "2" },
          "06": { "01": "1" },
          "11": { "01": "1.02" },
          "20": { "01": "3.1", "02": "4.0", "03": "5.0", "04": "5.5" },
          "21": { "02": "2.0" }
        };
        const stringValue = getStringValue(value);
        if (tags["ObjectData Preview File Format"]) {
          const objectDataPreviewFileFormat = getStringValue(tags["ObjectData Preview File Format"].value);
          if (formatVersions[objectDataPreviewFileFormat] && formatVersions[objectDataPreviewFileFormat][stringValue]) {
            return formatVersions[objectDataPreviewFileFormat][stringValue];
          }
        }
        return stringValue;
      }
    },
    714: "ObjectData Preview Data",
    1802: {
      "name": "Size Mode",
      "description": (value) => {
        return value[0].toString();
      }
    },
    1812: {
      "name": "Max Subfile Size",
      "description": (value) => {
        let n = 0;
        for (let i = 0; i < value.length; i++) {
          n = (n << 8) + value[i];
        }
        return n.toString();
      }
    },
    1882: {
      "name": "ObjectData Size Announced",
      "description": (value) => {
        let n = 0;
        for (let i = 0; i < value.length; i++) {
          n = (n << 8) + value[i];
        }
        return n.toString();
      }
    },
    1887: {
      "name": "Maximum ObjectData Size",
      "description": (value) => {
        let n = 0;
        for (let i = 0; i < value.length; i++) {
          n = (n << 8) + value[i];
        }
        return n.toString();
      }
    }
  }
};
function getCreationDate(value) {
  const date = getStringValue(value);
  if (date.length >= 8) {
    return date.substr(0, 4) + "-" + date.substr(4, 2) + "-" + date.substr(6, 2);
  }
  return date;
}
function getCreationTime(value) {
  const time = getStringValue(value);
  let parsedTime = time;
  if (time.length >= 6) {
    parsedTime = time.substr(0, 2) + ":" + time.substr(2, 2) + ":" + time.substr(4, 2);
    if (time.length === 11) {
      parsedTime += time.substr(6, 1) + time.substr(7, 2) + ":" + time.substr(9, 2);
    }
  }
  return parsedTime;
}
function getEncodingName(value) {
  const string = getStringValue(value);
  if (string === "\x1B%G") {
    return "UTF-8";
  } else if (string === "\x1B%5") {
    return "Windows-1252";
  } else if (string === "\x1B%/G") {
    return "UTF-8 Level 1";
  } else if (string === "\x1B%/H") {
    return "UTF-8 Level 2";
  } else if (string === "\x1B%/I") {
    return "UTF-8 Level 3";
  } else if (string === "\x1B/A") {
    return "ISO-8859-1";
  } else if (string === "\x1B/B") {
    return "ISO-8859-2";
  } else if (string === "\x1B/C") {
    return "ISO-8859-3";
  } else if (string === "\x1B/D") {
    return "ISO-8859-4";
  } else if (string === "\x1B/@") {
    return "ISO-8859-5";
  } else if (string === "\x1B/G") {
    return "ISO-8859-6";
  } else if (string === "\x1B/F") {
    return "ISO-8859-7";
  } else if (string === "\x1B/H") {
    return "ISO-8859-8";
  }
  return "Unknown";
}

// node_modules/exifreader/src/text-decoder.js
var text_decoder_default = {
  get
};
function get() {
  if (typeof TextDecoder !== "undefined") {
    return TextDecoder;
  }
  return void 0;
}

// node_modules/exifreader/src/tag-decoder.js
var TAG_HEADER_SIZE = 5;
var tag_decoder_default = {
  decode,
  TAG_HEADER_SIZE
};
function decode(encoding, tagValue) {
  const Decoder = text_decoder_default.get();
  if (typeof Decoder !== "undefined" && encoding !== void 0) {
    try {
      return new Decoder(encoding).decode(tagValue instanceof DataView ? tagValue.buffer : Uint8Array.from(tagValue));
    } catch (error) {
    }
  }
  const stringValue = tagValue.map((charCode) => String.fromCharCode(charCode)).join("");
  return decodeAsciiValue2(stringValue);
}
function decodeAsciiValue2(asciiValue) {
  try {
    return decodeURIComponent(escape(asciiValue));
  } catch (error) {
    return asciiValue;
  }
}

// node_modules/exifreader/src/iptc-tags.js
var BYTES_8BIM = 943868237;
var BYTES_8BIM_SIZE = 4;
var RESOURCE_ID_SIZE = 2;
var RESOURCE_NAME_SIZE_SIZE = 1;
var RESOURCE_NAME_MIN_SIZE = 2;
var RESOURCE_SIZE_SIZE = 4;
var RESOURCE_BLOCK_MIN_HEADER_SIZE = BYTES_8BIM_SIZE + RESOURCE_ID_SIZE + RESOURCE_NAME_MIN_SIZE + RESOURCE_SIZE_SIZE;
var NAA_RESOURCE_BLOCK_TYPE = 1028;
var TAG_HEADER_SIZE2 = 5;
var iptc_tags_default = {
  read: read5
};
function read5(dataView, dataOffset, includeUnknown) {
  try {
    if (Array.isArray(dataView)) {
      return parseTags(new DataView(Uint8Array.from(dataView).buffer), { size: dataView.length }, 0, includeUnknown);
    }
    const { naaBlock, dataOffset: newDataOffset } = getNaaResourceBlock(dataView, dataOffset);
    return parseTags(dataView, naaBlock, newDataOffset, includeUnknown);
  } catch (error) {
    return {};
  }
}
function getNaaResourceBlock(dataView, dataOffset) {
  while (dataOffset + RESOURCE_BLOCK_MIN_HEADER_SIZE <= dataView.byteLength) {
    const resourceBlock = getResourceBlock(dataView, dataOffset);
    if (isNaaResourceBlock(resourceBlock)) {
      return { naaBlock: resourceBlock, dataOffset: dataOffset + resourceBlock.headerSize };
    }
    dataOffset += resourceBlock.headerSize + resourceBlock.size + getBlockPadding(resourceBlock);
  }
  throw new Error("No IPTC NAA resource block.");
}
function getResourceBlock(dataView, dataOffset) {
  if (dataView.getUint32(dataOffset, false) !== BYTES_8BIM) {
    throw new Error("Not an IPTC resource block.");
  }
  const resourceNameSize = dataView.getUint8(dataOffset + BYTES_8BIM_SIZE + RESOURCE_ID_SIZE);
  const resourceNameTotalSize = (resourceNameSize % 2 === 0 ? resourceNameSize + 1 : resourceNameSize) + RESOURCE_NAME_SIZE_SIZE;
  return {
    headerSize: BYTES_8BIM_SIZE + RESOURCE_ID_SIZE + resourceNameTotalSize + RESOURCE_SIZE_SIZE,
    type: dataView.getUint16(dataOffset + BYTES_8BIM_SIZE),
    size: dataView.getUint32(dataOffset + BYTES_8BIM_SIZE + RESOURCE_ID_SIZE + resourceNameTotalSize)
  };
}
function isNaaResourceBlock(resourceBlock) {
  return resourceBlock.type === NAA_RESOURCE_BLOCK_TYPE;
}
function getBlockPadding(resourceBlock) {
  if (resourceBlock.size % 2 !== 0) {
    return 1;
  }
  return 0;
}
function parseTags(dataView, naaBlock, dataOffset, includeUnknown) {
  const tags = {};
  let encoding = void 0;
  const endOfBlockOffset = dataOffset + naaBlock["size"];
  while (dataOffset < endOfBlockOffset && dataOffset < dataView.byteLength) {
    const { tag, tagSize } = readTag2(dataView, dataOffset, tags, encoding, includeUnknown);
    if (tag === null) {
      break;
    }
    if (tag) {
      if ("encoding" in tag) {
        encoding = tag.encoding;
      }
      if (tags[tag.name] === void 0 || tag["repeatable"] === void 0) {
        tags[tag.name] = {
          id: tag.id,
          value: tag.value,
          description: tag.description
        };
      } else {
        if (!(tags[tag.name] instanceof Array)) {
          tags[tag.name] = [{
            id: tags[tag.name].id,
            value: tags[tag.name].value,
            description: tags[tag.name].description
          }];
        }
        tags[tag.name].push({
          id: tag.id,
          value: tag.value,
          description: tag.description
        });
      }
    }
    dataOffset += TAG_HEADER_SIZE2 + tagSize;
  }
  return tags;
}
function readTag2(dataView, dataOffset, tags, encoding, includeUnknown) {
  const TAG_CODE_OFFSET = 1;
  const TAG_SIZE_OFFSET = 3;
  if (leadByteIsMissing(dataView, dataOffset)) {
    return { tag: null, tagSize: 0 };
  }
  const tagCode = dataView.getUint16(dataOffset + TAG_CODE_OFFSET);
  const tagSize = dataView.getUint16(dataOffset + TAG_SIZE_OFFSET);
  if (!includeUnknown && !iptc_tag_names_default["iptc"][tagCode]) {
    return { tag: void 0, tagSize };
  }
  const tagValue = getTagValue2(dataView, dataOffset + TAG_HEADER_SIZE2, tagSize);
  const tag = {
    id: tagCode,
    name: getTagName(iptc_tag_names_default["iptc"][tagCode], tagCode, tagValue),
    value: tagValue,
    description: getTagDescription(iptc_tag_names_default["iptc"][tagCode], tagValue, tags, encoding)
  };
  if (tagIsRepeatable(tagCode)) {
    tag["repeatable"] = true;
  }
  if (tagContainsEncoding(tagCode)) {
    tag["encoding"] = iptc_tag_names_default["iptc"][tagCode]["encoding_name"](tagValue);
  }
  return { tag, tagSize };
}
function leadByteIsMissing(dataView, dataOffset) {
  const TAG_LEAD_BYTE = 28;
  return dataView.getUint8(dataOffset) !== TAG_LEAD_BYTE;
}
function getTagValue2(dataView, offset, size) {
  const value = [];
  for (let valueIndex = 0; valueIndex < size; valueIndex++) {
    value.push(dataView.getUint8(offset + valueIndex));
  }
  return value;
}
function getTagName(tag, tagCode, tagValue) {
  if (!tag) {
    return `undefined-${tagCode}`;
  }
  if (tagIsName(tag)) {
    return tag;
  }
  if (hasDynamicName(tag)) {
    return tag["name"](tagValue);
  }
  return tag["name"];
}
function tagIsName(tag) {
  return typeof tag === "string";
}
function hasDynamicName(tag) {
  return typeof tag["name"] === "function";
}
function getTagDescription(tag, tagValue, tags, encoding) {
  if (hasDescriptionProperty(tag)) {
    try {
      return tag["description"](tagValue, tags);
    } catch (error) {
    }
  }
  if (tagValueIsText(tag, tagValue)) {
    return tag_decoder_default.decode(encoding, tagValue);
  }
  return tagValue;
}
function tagValueIsText(tag, tagValue) {
  return tag && tagValue instanceof Array;
}
function hasDescriptionProperty(tag) {
  return tag && tag["description"] !== void 0;
}
function tagIsRepeatable(tagCode) {
  return iptc_tag_names_default["iptc"][tagCode] && iptc_tag_names_default["iptc"][tagCode]["repeatable"];
}
function tagContainsEncoding(tagCode) {
  return iptc_tag_names_default["iptc"][tagCode] && iptc_tag_names_default["iptc"][tagCode]["encoding_name"] !== void 0;
}

// node_modules/exifreader/src/xmp-tag-names.js
var xmp_tag_names_default = {
  "tiff:Orientation"(value) {
    if (value === "1") {
      return "Horizontal (normal)";
    }
    if (value === "2") {
      return "Mirror horizontal";
    }
    if (value === "3") {
      return "Rotate 180";
    }
    if (value === "4") {
      return "Mirror vertical";
    }
    if (value === "5") {
      return "Mirror horizontal and rotate 270 CW";
    }
    if (value === "6") {
      return "Rotate 90 CW";
    }
    if (value === "7") {
      return "Mirror horizontal and rotate 90 CW";
    }
    if (value === "8") {
      return "Rotate 270 CW";
    }
    return value;
  },
  "tiff:ResolutionUnit": (value) => tag_names_common_default.ResolutionUnit(parseInt(value, 10)),
  "tiff:XResolution": (value) => fraction(tag_names_common_default.XResolution, value),
  "tiff:YResolution": (value) => fraction(tag_names_common_default.YResolution, value),
  "exif:ApertureValue": (value) => fraction(tag_names_common_default.ApertureValue, value),
  "exif:GPSLatitude": calculateGPSValue,
  "exif:GPSLongitude": calculateGPSValue,
  "exif:FNumber": (value) => fraction(tag_names_common_default.FNumber, value),
  "exif:FocalLength": (value) => fraction(tag_names_common_default.FocalLength, value),
  "exif:FocalPlaneResolutionUnit": (value) => tag_names_common_default.FocalPlaneResolutionUnit(parseInt(value, 10)),
  "exif:ColorSpace": (value) => tag_names_common_default.ColorSpace(parseNumber(value)),
  "exif:ComponentsConfiguration"(value, description) {
    if (/^\d, \d, \d, \d$/.test(description)) {
      const numbers = description.split(", ").map((number) => number.charCodeAt(0));
      return tag_names_common_default.ComponentsConfiguration(numbers);
    }
    return description;
  },
  "exif:Contrast": (value) => tag_names_common_default.Contrast(parseInt(value, 10)),
  "exif:CustomRendered": (value) => tag_names_common_default.CustomRendered(parseInt(value, 10)),
  "exif:ExposureMode": (value) => tag_names_common_default.ExposureMode(parseInt(value, 10)),
  "exif:ExposureProgram": (value) => tag_names_common_default.ExposureProgram(parseInt(value, 10)),
  "exif:ExposureTime"(value) {
    if (isFraction(value)) {
      return tag_names_common_default.ExposureTime(value.split("/").map((number) => parseInt(number, 10)));
    }
    return value;
  },
  "exif:MeteringMode": (value) => tag_names_common_default.MeteringMode(parseInt(value, 10)),
  "exif:Saturation": (value) => tag_names_common_default.Saturation(parseInt(value, 10)),
  "exif:SceneCaptureType": (value) => tag_names_common_default.SceneCaptureType(parseInt(value, 10)),
  "exif:Sharpness": (value) => tag_names_common_default.Sharpness(parseInt(value, 10)),
  "exif:ShutterSpeedValue": (value) => fraction(tag_names_common_default.ShutterSpeedValue, value),
  "exif:WhiteBalance": (value) => tag_names_common_default.WhiteBalance(parseInt(value, 10))
};
function fraction(func, value) {
  if (isFraction(value)) {
    return func(value.split("/"));
  }
  return value;
}
function parseNumber(value) {
  if (value.substring(0, 2) === "0x") {
    return parseInt(value.substring(2), 16);
  }
  return parseInt(value, 10);
}
function isFraction(value) {
  return /^-?\d+\/-?\d+$/.test(value);
}
function calculateGPSValue(value) {
  const [degreesString, minutesString] = value.split(",");
  if (degreesString !== void 0 && minutesString !== void 0) {
    const degrees = parseFloat(degreesString);
    const minutes = parseFloat(minutesString);
    const ref = minutesString.charAt(minutesString.length - 1);
    if (!Number.isNaN(degrees) && !Number.isNaN(minutes)) {
      return "" + (degrees + minutes / 60) + ref;
    }
  }
  return value;
}

// node_modules/exifreader/src/dom-parser.js
var dom_parser_default = {
  get: get2
};
function get2(domParser) {
  if (domParser) {
    return domParser;
  }
  if (typeof DOMParser !== "undefined") {
    return new DOMParser();
  }
  try {
    const { DOMParser: DOMParser2, onErrorStopParsing } = __non_webpack_require__("@xmldom/xmldom");
    return new DOMParser2({ onError: onErrorStopParsing });
  } catch (error) {
    return void 0;
  }
}

// node_modules/exifreader/src/xmp-namespaces.js
function isMissingNamespaceError(error) {
  const missingNamespaceStrings = [
    // @xmldom/xmldom
    "prefix is non-null and namespace is null",
    // Firefox
    "prefix not bound to a namespace",
    // en
    "prefix inte bundet till en namnrymd",
    // sv
    // Chrome
    /Namespace prefix .+ is not defined/
  ];
  for (let i = 0; i < missingNamespaceStrings.length; i++) {
    const regexp = new RegExp(missingNamespaceStrings[i]);
    if (regexp.test(error.message)) {
      return true;
    }
  }
  return false;
}
function addMissingNamespaces(xmlString) {
  const rootTagMatch = xmlString.match(/<([A-Za-z_][A-Za-z0-9._-]*)([^>]*)>/);
  if (!rootTagMatch) {
    return xmlString;
  }
  const rootTagName = rootTagMatch[1];
  const declaredPrefixes = getAllDeclaredNamespacePrefixes(xmlString);
  const usedPrefixes = getUsedNamespacePrefixes(xmlString);
  const missingPrefixes = usedPrefixes.filter((prefix) => declaredPrefixes.indexOf(prefix) === -1);
  if (missingPrefixes.length === 0) {
    return xmlString;
  }
  const namespaceDeclarations = createNamespaceDeclarations(missingPrefixes);
  return insertDeclarationsIntoRoot(xmlString, rootTagName, namespaceDeclarations);
}
function getAllDeclaredNamespacePrefixes(xmlContent) {
  const prefixes = [];
  const namespaceDeclarationRegex = /xmlns:([\w-]+)=["'][^"']+["']/g;
  let match;
  while ((match = namespaceDeclarationRegex.exec(xmlContent)) !== null) {
    if (prefixes.indexOf(match[1]) === -1) {
      prefixes.push(match[1]);
    }
  }
  return prefixes;
}
function getUsedNamespacePrefixes(xmlContent) {
  const prefixes = [];
  const prefixUsageRegex = /\b([A-Za-z_][A-Za-z0-9._-]*):[A-Za-z_][A-Za-z0-9._-]*\b/g;
  let match;
  while ((match = prefixUsageRegex.exec(xmlContent)) !== null) {
    const prefix = match[1];
    if (prefix === "xmlns" || prefix === "xml") {
      continue;
    }
    if (prefixes.indexOf(prefix) === -1) {
      prefixes.push(prefix);
    }
  }
  return prefixes;
}
var KNOWN_NAMESPACE_URIS = {
  xmp: "http://ns.adobe.com/xap/1.0/",
  tiff: "http://ns.adobe.com/tiff/1.0/",
  exif: "http://ns.adobe.com/exif/1.0/",
  dc: "http://purl.org/dc/elements/1.1/",
  xmpMM: "http://ns.adobe.com/xap/1.0/mm/",
  stEvt: "http://ns.adobe.com/xap/1.0/sType/ResourceEvent#",
  stRef: "http://ns.adobe.com/xap/1.0/sType/ResourceRef#",
  photoshop: "http://ns.adobe.com/photoshop/1.0/"
};
function createNamespaceDeclarations(prefixes) {
  const declarations = [];
  for (let i = 0; i < prefixes.length; i++) {
    const prefix = prefixes[i];
    const uri = KNOWN_NAMESPACE_URIS[prefix] || "http://fallback.namespace/" + prefix;
    declarations.push(" xmlns:" + prefix + '="' + uri + '"');
  }
  return declarations.join("");
}
function insertDeclarationsIntoRoot(xmlString, rootTagName, declarations) {
  const rootTagPattern = new RegExp("<" + rootTagName + "([^>]*)>");
  return xmlString.replace(rootTagPattern, "<" + rootTagName + "$1" + declarations + ">");
}

// node_modules/exifreader/src/xmp-tags.js
var xmp_tags_default = {
  read: read6
};
var ParseError = class extends Error {
  constructor(message) {
    super(message);
    this.name = "ParseError";
  }
};
function read6(dataView, chunks, domParser) {
  const tags = {};
  if (typeof dataView === "string") {
    readTags(tags, dataView, domParser);
    return tags;
  }
  const [standardXmp, extendedXmp] = extractCompleteChunks(dataView, chunks);
  const hasStandardTags = readTags(tags, standardXmp, domParser);
  if (extendedXmp) {
    const hasExtendedTags = readTags(tags, extendedXmp, domParser);
    if (!hasStandardTags && !hasExtendedTags) {
      delete tags._raw;
      readTags(tags, combineChunks(dataView, chunks), domParser);
    }
  }
  return tags;
}
function extractCompleteChunks(dataView, chunks) {
  if (chunks.length === 0) {
    return [];
  }
  const completeChunks = [combineChunks(dataView, chunks.slice(0, 1))];
  if (chunks.length > 1) {
    completeChunks.push(combineChunks(dataView, chunks.slice(1)));
  }
  return completeChunks;
}
function combineChunks(dataView, chunks) {
  const totalLength = chunks.reduce((size, chunk) => size + chunk.length, 0);
  const combinedChunks = new Uint8Array(totalLength);
  let offset = 0;
  for (let i = 0; i < chunks.length; i++) {
    const chunk = chunks[i];
    const slice = dataView.buffer.slice(chunk.dataOffset, chunk.dataOffset + chunk.length);
    combinedChunks.set(new Uint8Array(slice), offset);
    offset += chunk.length;
  }
  return new DataView(combinedChunks.buffer);
}
function readTags(tags, chunkDataView, domParser) {
  try {
    const { doc, raw } = getDocument(chunkDataView, domParser);
    tags._raw = (tags._raw || "") + raw;
    const rdf = getRDF(doc);
    objectAssign(tags, parseXMPObject(convertToObject(rdf, true)));
    return true;
  } catch (error) {
    return false;
  }
}
function getDocument(chunkDataView, _domParser) {
  const domParser = dom_parser_default.get(_domParser);
  if (!domParser) {
    console.warn("Warning: DOMParser is not available. It is needed to be able to parse XMP tags.");
    throw new Error();
  }
  const xmlString = typeof chunkDataView === "string" ? chunkDataView : getStringFromDataView(chunkDataView, 0, chunkDataView.byteLength);
  const doc = parseFromString(domParser, trimXmlSource(xmlString));
  return {
    doc,
    raw: xmlString
  };
}
function trimXmlSource(xmlSource) {
  return xmlSource.replace(/^.+(<\?xpacket begin)/, "$1").replace(/(<\?xpacket end=".*"\?>).+$/, "$1");
}
function parseFromString(domParser, xmlString, isRetry = false) {
  try {
    const doc = domParser.parseFromString(xmlString, "application/xml");
    const errors = doc.getElementsByTagName("parsererror");
    if (errors.length > 0) {
      throw new ParseError(errors[0].textContent);
    }
    return doc;
  } catch (error) {
    if (error.name === "ParseError" && isMissingNamespaceError(error) && !isRetry) {
      return parseFromString(domParser, addMissingNamespaces(xmlString), true);
    }
    throw error;
  }
}
function getRDF(node) {
  for (let i = 0; i < node.childNodes.length; i++) {
    if (node.childNodes[i].tagName === "x:xmpmeta") {
      return getRDF(node.childNodes[i]);
    }
    if (node.childNodes[i].tagName === "rdf:RDF") {
      return node.childNodes[i];
    }
  }
  throw new Error();
}
function convertToObject(node, isTopNode = false) {
  const childNodes = getChildNodes(node);
  if (hasTextOnlyContent(childNodes)) {
    if (isTopNode) {
      return {};
    }
    return getTextValue(childNodes[0]);
  }
  return getElementsFromNodes(childNodes);
}
function getChildNodes(node) {
  const elements2 = [];
  for (let i = 0; i < node.childNodes.length; i++) {
    elements2.push(node.childNodes[i]);
  }
  return elements2;
}
function hasTextOnlyContent(nodes) {
  return nodes.length === 1 && nodes[0].nodeName === "#text";
}
function getTextValue(node) {
  return node.nodeValue;
}
function getElementsFromNodes(nodes) {
  const elements2 = {};
  nodes.forEach((node) => {
    if (isElement(node)) {
      const nodeElement = getElementFromNode(node);
      if (elements2[node.nodeName] !== void 0) {
        if (!Array.isArray(elements2[node.nodeName])) {
          elements2[node.nodeName] = [elements2[node.nodeName]];
        }
        elements2[node.nodeName].push(nodeElement);
      } else {
        elements2[node.nodeName] = nodeElement;
      }
    }
  });
  return elements2;
}
function isElement(node) {
  return node.nodeName && node.nodeName !== "#text";
}
function getElementFromNode(node) {
  return {
    attributes: getAttributes(node),
    value: convertToObject(node)
  };
}
function getAttributes(element) {
  const attributes = {};
  for (let i = 0; i < element.attributes.length; i++) {
    attributes[element.attributes[i].nodeName] = decodeURIComponent(escape(element.attributes[i].value));
  }
  return attributes;
}
function parseXMPObject(xmpObject) {
  const tags = {};
  if (typeof xmpObject === "string") {
    return xmpObject;
  }
  for (const nodeName in xmpObject) {
    let nodes = xmpObject[nodeName];
    if (!Array.isArray(nodes)) {
      nodes = [nodes];
    }
    nodes.forEach((node) => {
      objectAssign(tags, parseNodeAttributesAsTags(node.attributes));
      if (typeof node.value === "object") {
        objectAssign(tags, parseNodeChildrenAsTags(node.value));
      }
    });
  }
  return tags;
}
function parseNodeAttributesAsTags(attributes) {
  const tags = {};
  for (const name in attributes) {
    try {
      if (isTagAttribute(name)) {
        tags[getLocalName(name)] = {
          value: attributes[name],
          attributes: {},
          description: getDescription(attributes[name], name)
        };
      }
    } catch (error) {
    }
  }
  return tags;
}
function isTagAttribute(name) {
  return name !== "rdf:parseType" && !isNamespaceDefinition(name);
}
function isNamespaceDefinition(name) {
  return name.split(":")[0] === "xmlns";
}
function getLocalName(name) {
  if (/^MicrosoftPhoto(_\d+_)?:Rating$/i.test(name)) {
    return "RatingPercent";
  }
  return name.split(":")[1];
}
function getDescription(value, name = void 0) {
  if (Array.isArray(value)) {
    const arrayDescription = getDescriptionOfArray(value);
    if (name && typeof xmp_tag_names_default[name] === "function") {
      return xmp_tag_names_default[name](value, arrayDescription);
    }
    return arrayDescription;
  }
  if (typeof value === "object") {
    return getDescriptionOfObject(value);
  }
  try {
    if (name && typeof xmp_tag_names_default[name] === "function") {
      return xmp_tag_names_default[name](value);
    }
    return decodeURIComponent(escape(value));
  } catch (error) {
    return value;
  }
}
function getDescriptionOfArray(value) {
  return value.map((item) => {
    if (item.value !== void 0) {
      return getDescription(item.value);
    }
    return getDescription(item);
  }).join(", ");
}
function getDescriptionOfObject(value) {
  const descriptions = [];
  for (const key in value) {
    descriptions.push(`${getClearTextKey(key)}: ${getDescription(value[key].value)}`);
  }
  return descriptions.join("; ");
}
function getClearTextKey(key) {
  if (key === "CiAdrCity") {
    return "CreatorCity";
  }
  if (key === "CiAdrCtry") {
    return "CreatorCountry";
  }
  if (key === "CiAdrExtadr") {
    return "CreatorAddress";
  }
  if (key === "CiAdrPcode") {
    return "CreatorPostalCode";
  }
  if (key === "CiAdrRegion") {
    return "CreatorRegion";
  }
  if (key === "CiEmailWork") {
    return "CreatorWorkEmail";
  }
  if (key === "CiTelWork") {
    return "CreatorWorkPhone";
  }
  if (key === "CiUrlWork") {
    return "CreatorWorkUrl";
  }
  return key;
}
function parseNodeChildrenAsTags(children) {
  const tags = {};
  for (const name in children) {
    try {
      if (!isNamespaceDefinition(name)) {
        tags[getLocalName(name)] = parseNodeAsTag(children[name], name);
      }
    } catch (error) {
    }
  }
  return tags;
}
function parseNodeAsTag(node, name) {
  if (isDuplicateTag(node)) {
    return parseNodeAsDuplicateTag(node, name);
  }
  if (isEmptyResourceTag(node)) {
    return { value: "", attributes: {}, description: "" };
  }
  if (hasNestedSimpleRdfDescription(node)) {
    return parseNodeAsSimpleRdfDescription(node, name);
  }
  if (hasNestedStructureRdfDescription(node)) {
    return parseNodeAsStructureRdfDescription(node, name);
  }
  if (isCompactStructure(node)) {
    return parseNodeAsCompactStructure(node, name);
  }
  if (isArray(node)) {
    return parseNodeAsArray(node, name);
  }
  return parseNodeAsSimpleValue(node, name);
}
function isEmptyResourceTag(node) {
  return node.attributes["rdf:parseType"] === "Resource" && typeof node.value === "string" && node.value.trim() === "";
}
function isDuplicateTag(node) {
  return Array.isArray(node);
}
function parseNodeAsDuplicateTag(node, name) {
  return parseNodeAsSimpleValue(node[node.length - 1], name);
}
function hasNestedSimpleRdfDescription(node) {
  return node.attributes["rdf:parseType"] === "Resource" && node.value["rdf:value"] !== void 0 || node.value["rdf:Description"] !== void 0 && node.value["rdf:Description"].value["rdf:value"] !== void 0;
}
function parseNodeAsSimpleRdfDescription(node, name) {
  const attributes = parseNodeAttributes(node);
  if (node.value["rdf:Description"] !== void 0) {
    node = node.value["rdf:Description"];
  }
  objectAssign(attributes, parseNodeAttributes(node), parseNodeChildrenAsAttributes(node));
  const value = parseRdfValue(node);
  return {
    value,
    attributes,
    description: getDescription(value, name)
  };
}
function parseNodeAttributes(node) {
  const attributes = {};
  for (const name in node.attributes) {
    if (name !== "rdf:parseType" && name !== "rdf:resource" && !isNamespaceDefinition(name)) {
      attributes[getLocalName(name)] = node.attributes[name];
    }
  }
  return attributes;
}
function parseNodeChildrenAsAttributes(node) {
  const attributes = {};
  for (const name in node.value) {
    if (name !== "rdf:value" && !isNamespaceDefinition(name)) {
      attributes[getLocalName(name)] = node.value[name].value;
    }
  }
  return attributes;
}
function parseRdfValue(node) {
  return getURIValue(node.value["rdf:value"]) || node.value["rdf:value"].value;
}
function hasNestedStructureRdfDescription(node) {
  return node.attributes["rdf:parseType"] === "Resource" || node.value["rdf:Description"] !== void 0 && node.value["rdf:Description"].value["rdf:value"] === void 0;
}
function parseNodeAsStructureRdfDescription(node, name) {
  const tag = {
    value: {},
    attributes: {}
  };
  if (node.value["rdf:Description"] !== void 0) {
    objectAssign(tag.value, parseNodeAttributesAsTags(node.value["rdf:Description"].attributes));
    objectAssign(tag.attributes, parseNodeAttributes(node));
    node = node.value["rdf:Description"];
  }
  objectAssign(tag.value, parseNodeChildrenAsTags(node.value));
  tag.description = getDescription(tag.value, name);
  return tag;
}
function isCompactStructure(node) {
  return Object.keys(node.value).length === 0 && node.attributes["xml:lang"] === void 0 && node.attributes["rdf:resource"] === void 0;
}
function parseNodeAsCompactStructure(node, name) {
  const value = parseNodeAttributesAsTags(node.attributes);
  return {
    value,
    attributes: {},
    description: getDescription(value, name)
  };
}
function isArray(node) {
  return getArrayChild(node.value) !== void 0;
}
function getArrayChild(value) {
  return value["rdf:Bag"] || value["rdf:Seq"] || value["rdf:Alt"];
}
function parseNodeAsArray(node, name) {
  let items = getArrayChild(node.value).value["rdf:li"];
  const attributes = parseNodeAttributes(node);
  const value = [];
  if (items === void 0) {
    items = [];
  } else if (!Array.isArray(items)) {
    items = [items];
  }
  items.forEach((item) => {
    value.push(parseArrayValue(item));
  });
  return {
    value,
    attributes,
    description: getDescription(value, name)
  };
}
function parseArrayValue(item) {
  if (hasNestedSimpleRdfDescription(item)) {
    return parseNodeAsSimpleRdfDescription(item);
  }
  if (hasNestedStructureRdfDescription(item)) {
    return parseNodeAsStructureRdfDescription(item).value;
  }
  if (isCompactStructure(item)) {
    return parseNodeAsCompactStructure(item).value;
  }
  return parseNodeAsSimpleValue(item);
}
function parseNodeAsSimpleValue(node, name) {
  const value = getURIValue(node) || parseXMPObject(node.value);
  return {
    value,
    attributes: parseNodeAttributes(node),
    description: getDescription(value, name)
  };
}
function getURIValue(node) {
  return node.attributes && node.attributes["rdf:resource"];
}

// node_modules/exifreader/src/photoshop-tag-names.js
var PathRecordTypes = {
  CLOSED_SUBPATH_LENGTH: 0,
  CLOSED_SUBPATH_BEZIER_LINKED: 1,
  CLOSED_SUBPATH_BEZIER_UNLINKED: 2,
  OPEN_SUBPATH_LENGTH: 3,
  OPEN_SUBPATH_BEZIER_LINKED: 4,
  OPEN_SUBPATH_BEZIER_UNLINKED: 5,
  FILL_RULE: 6,
  CLIPBOARD: 7,
  INITIAL_FILL_RULE: 8
};
var PATH_RECORD_SIZE = 24;
var photoshop_tag_names_default = {
  // 0x0425: {
  //     name: 'CaptionDigest',
  //     description(dataView) {
  //         let description = '';
  //         for (let i = 0; i < dataView.byteLength; i++) {
  //             const byte = dataView.getUint8(i);
  //             description += padStart(byte.toString(16), 2, '0');
  //         }
  //         return description;
  //     }
  // },
  // Commented out for now to lower bundle size until someone asks for it.
  // 0x043a: {
  //     name: 'PrintInformation',
  //     description: parseDescriptor
  // },
  // 0x043b: {
  //     name: 'PrintStyle',
  //     description: parseDescriptor
  // },
  2e3: {
    name: "PathInformation",
    description: pathResource
  },
  2999: {
    name: "ClippingPathName",
    description(dataView) {
      const [, string] = getPascalStringFromDataView(dataView, 0);
      return string;
    }
  }
};
function pathResource(dataView) {
  const TYPE_SIZE = 2;
  const types = {};
  const paths = [];
  for (let offset = 0; offset < dataView.byteLength; offset += TYPE_SIZE + PATH_RECORD_SIZE) {
    const type = types_default.getShortAt(dataView, offset);
    if (PATH_RECORD_TYPES[type]) {
      if (!types[type]) {
        types[type] = PATH_RECORD_TYPES[type].description;
      }
      paths.push({
        type,
        path: PATH_RECORD_TYPES[type].path(dataView, offset + TYPE_SIZE)
      });
    }
  }
  return JSON.stringify({ types, paths });
}
var PATH_RECORD_TYPES = {
  [PathRecordTypes.CLOSED_SUBPATH_LENGTH]: {
    description: "Closed subpath length",
    path: (dataView, offset) => [types_default.getShortAt(dataView, offset)]
  },
  [PathRecordTypes.CLOSED_SUBPATH_BEZIER_LINKED]: {
    description: "Closed subpath Bezier knot, linked",
    path: parseBezierKnot
  },
  [PathRecordTypes.CLOSED_SUBPATH_BEZIER_UNLINKED]: {
    description: "Closed subpath Bezier knot, unlinked",
    path: parseBezierKnot
  },
  [PathRecordTypes.OPEN_SUBPATH_LENGTH]: {
    description: "Open subpath length",
    path: (dataView, offset) => [types_default.getShortAt(dataView, offset)]
  },
  [PathRecordTypes.OPEN_SUBPATH_BEZIER_LINKED]: {
    description: "Open subpath Bezier knot, linked",
    path: parseBezierKnot
  },
  [PathRecordTypes.OPEN_SUBPATH_BEZIER_UNLINKED]: {
    description: "Open subpath Bezier knot, unlinked",
    path: parseBezierKnot
  },
  [PathRecordTypes.FILL_RULE]: {
    description: "Path fill rule",
    path: () => []
  },
  [PathRecordTypes.INITIAL_FILL_RULE]: {
    description: "Initial fill rule",
    path: (dataView, offset) => [types_default.getShortAt(dataView, offset)]
  },
  [PathRecordTypes.CLIPBOARD]: {
    description: "Clipboard",
    path: parseClipboard
  }
};
function parseBezierKnot(dataView, offset) {
  const PATH_POINT_SIZE = 8;
  const path = [];
  for (let i = 0; i < PATH_RECORD_SIZE; i += PATH_POINT_SIZE) {
    path.push(parsePathPoint(dataView, offset + i));
  }
  return path;
}
function parsePathPoint(dataView, offset) {
  const vertical = getFixedPointNumber(dataView, offset, 8);
  const horizontal = getFixedPointNumber(dataView, offset + 4, 8);
  return [horizontal, vertical];
}
function parseClipboard(dataView, offset) {
  return [
    [
      getFixedPointNumber(dataView, offset, 8),
      // Top
      getFixedPointNumber(dataView, offset + 4, 8),
      // Left
      getFixedPointNumber(dataView, offset + 8, 8),
      // Botton
      getFixedPointNumber(dataView, offset + 12, 8)
      // Right
    ],
    getFixedPointNumber(dataView, offset + 16, 8)
    // Resolution
  ];
}
function getFixedPointNumber(dataView, offset, binaryPoint) {
  const number = types_default.getLongAt(dataView, offset);
  const sign = number >>> 31 === 0 ? 1 : -1;
  const integer = (number & 2130706432) >>> 32 - binaryPoint;
  const fraction2 = number & parseInt(strRepeat("1", 32 - binaryPoint), 2);
  return sign * parseFloatRadix(integer.toString(2) + "." + padStart(fraction2.toString(2), 32 - binaryPoint, "0"), 2);
}

// node_modules/exifreader/src/photoshop-tags.js
var photoshop_tags_default = {
  read: read7
};
var SIGNATURE = "8BIM";
var TAG_ID_SIZE = 2;
var RESOURCE_LENGTH_SIZE = 4;
var SIGNATURE_SIZE = SIGNATURE.length;
function read7(bytes, includeUnknown) {
  const dataView = getDataView(new Uint8Array(bytes).buffer);
  const tags = {};
  let offset = 0;
  while (offset < bytes.length) {
    const signature = getStringFromDataView(dataView, offset, SIGNATURE_SIZE);
    offset += SIGNATURE_SIZE;
    const tagId = types_default.getShortAt(dataView, offset);
    offset += TAG_ID_SIZE;
    const { tagName, tagNameSize } = getTagName2(dataView, offset);
    offset += tagNameSize;
    const resourceSize = types_default.getLongAt(dataView, offset);
    offset += RESOURCE_LENGTH_SIZE;
    if (signature === SIGNATURE) {
      const valueDataView = getDataView(dataView.buffer, offset, resourceSize);
      const tag = {
        id: tagId,
        value: getStringFromDataView(valueDataView, 0, resourceSize)
      };
      if (photoshop_tag_names_default[tagId]) {
        try {
          tag.description = photoshop_tag_names_default[tagId].description(valueDataView);
        } catch (error) {
          tag.description = "<no description formatter>";
        }
        tags[tagName ? tagName : photoshop_tag_names_default[tagId].name] = tag;
      } else if (includeUnknown) {
        tags[`undefined-${tagId}`] = tag;
      }
    }
    offset += resourceSize + resourceSize % 2;
  }
  return tags;
}
function getTagName2(dataView, offset) {
  const [stringSize, string] = getPascalStringFromDataView(dataView, offset);
  return {
    tagName: string,
    tagNameSize: 1 + stringSize + (stringSize % 2 === 0 ? 1 : 0)
  };
}

// node_modules/exifreader/src/icc-tag-names.js
var iccTags = {
  "desc": {
    "name": "ICC Description"
  },
  "cprt": {
    "name": "ICC Copyright"
  },
  "dmdd": {
    "name": "ICC Device Model Description"
  },
  "vued": {
    "name": "ICC Viewing Conditions Description"
  },
  "dmnd": {
    "name": "ICC Device Manufacturer for Display"
  },
  "tech": {
    "name": "Technology"
  }
};
var iccProfile = {
  4: {
    "name": "Preferred CMM type",
    "value": (dataView, offset) => getStringFromDataView(dataView, offset, 4),
    "description": (value) => value !== null ? toCompany(value) : ""
  },
  8: {
    "name": "Profile Version",
    "value": (dataView, offset) => {
      return dataView.getUint8(offset).toString(10) + "." + (dataView.getUint8(offset + 1) >> 4).toString(10) + "." + (dataView.getUint8(offset + 1) % 16).toString(10);
    }
  },
  12: {
    "name": "Profile/Device class",
    "value": (dataView, offset) => getStringFromDataView(dataView, offset, 4),
    "description": (value) => {
      switch (value.toLowerCase()) {
        case "scnr":
          return "Input Device profile";
        case "mntr":
          return "Display Device profile";
        case "prtr":
          return "Output Device profile";
        case "link":
          return "DeviceLink profile";
        case "abst":
          return "Abstract profile";
        case "spac":
          return "ColorSpace profile";
        case "nmcl":
          return "NamedColor profile";
        case "cenc":
          return "ColorEncodingSpace profile";
        case "mid ":
          return "MultiplexIdentification profile";
        case "mlnk":
          return "MultiplexLink profile";
        case "mvis":
          return "MultiplexVisualization profile";
        default:
          return value;
      }
    }
  },
  16: {
    "name": "Color Space",
    "value": (dataView, offset) => getStringFromDataView(dataView, offset, 4)
  },
  20: {
    "name": "Connection Space",
    "value": (dataView, offset) => getStringFromDataView(dataView, offset, 4)
  },
  24: {
    "name": "ICC Profile Date",
    "value": (dataView, offset) => parseDate(dataView, offset).toISOString()
  },
  36: {
    "name": "ICC Signature",
    "value": (dataView, offset) => sliceToString(dataView.buffer.slice(offset, offset + 4))
  },
  40: {
    "name": "Primary Platform",
    "value": (dataView, offset) => getStringFromDataView(dataView, offset, 4),
    "description": (value) => toCompany(value)
  },
  48: {
    "name": "Device Manufacturer",
    "value": (dataView, offset) => getStringFromDataView(dataView, offset, 4),
    "description": (value) => toCompany(value)
  },
  52: {
    "name": "Device Model Number",
    "value": (dataView, offset) => getStringFromDataView(dataView, offset, 4)
  },
  64: {
    "name": "Rendering Intent",
    "value": (dataView, offset) => dataView.getUint32(offset),
    "description": (value) => {
      switch (value) {
        case 0:
          return "Perceptual";
        case 1:
          return "Relative Colorimetric";
        case 2:
          return "Saturation";
        case 3:
          return "Absolute Colorimetric";
        default:
          return value;
      }
    }
  },
  80: {
    "name": "Profile Creator",
    "value": (dataView, offset) => getStringFromDataView(dataView, offset, 4)
  }
};
function parseDate(dataView, offset) {
  const year = dataView.getUint16(offset);
  const month = dataView.getUint16(offset + 2) - 1;
  const day = dataView.getUint16(offset + 4);
  const hours = dataView.getUint16(offset + 6);
  const minutes = dataView.getUint16(offset + 8);
  const seconds = dataView.getUint16(offset + 10);
  return new Date(Date.UTC(year, month, day, hours, minutes, seconds));
}
function sliceToString(slice) {
  return String.fromCharCode.apply(null, new Uint8Array(slice));
}
function toCompany(value) {
  switch (value.toLowerCase()) {
    case "appl":
      return "Apple";
    case "adbe":
      return "Adobe";
    case "msft":
      return "Microsoft";
    case "sunw":
      return "Sun Microsystems";
    case "sgi":
      return "Silicon Graphics";
    case "tgnt":
      return "Taligent";
    default:
      return value;
  }
}

// node_modules/exifreader/src/icc-tags.js
var icc_tags_default = {
  read: read8
};
var PROFILE_HEADER_LENGTH = 84;
var ICC_TAG_COUNT_OFFSET = 128;
var ICC_SIGNATURE = "acsp";
var TAG_TYPE_DESC = "desc";
var TAG_TYPE_MULTI_LOCALIZED_UNICODE_TYPE = "mluc";
var TAG_TYPE_TEXT = "text";
var TAG_TYPE_SIGNATURE = "sig ";
var TAG_TABLE_SINGLE_TAG_DATA = 12;
function read8(dataView, iccData, async) {
  if (async && iccData[0].compressionMethod !== COMPRESSION_METHOD_NONE) {
    return readCompressedIcc(dataView, iccData);
  }
  return readIcc(dataView, iccData);
}
function readCompressedIcc(dataView, iccData) {
  if (!compressionMethodIsSupported(iccData[0].compressionMethod)) {
    return {};
  }
  const compressedDataView = new DataView(dataView.buffer.slice(iccData[0].offset, iccData[0].offset + iccData[0].length));
  return decompress(compressedDataView, iccData[0].compressionMethod, "utf-8", "dataview").then(parseTags2).catch(() => ({}));
}
function compressionMethodIsSupported(compressionMethod) {
  return compressionMethod === COMPRESSION_METHOD_DEFLATE;
}
function readIcc(dataView, iccData) {
  try {
    const totalIccProfileLength = iccData.reduce((sum, icc) => sum + icc.length, 0);
    const iccBinaryData = new Uint8Array(totalIccProfileLength);
    let offset = 0;
    const buffer = getBuffer(dataView);
    for (let chunkNumber = 1; chunkNumber <= iccData.length; chunkNumber++) {
      const iccDataChunk = iccData.find((x) => x.chunkNumber === chunkNumber);
      if (!iccDataChunk) {
        throw new Error(`ICC chunk ${chunkNumber} not found`);
      }
      const data = buffer.slice(iccDataChunk.offset, iccDataChunk.offset + iccDataChunk.length);
      const chunkData = new Uint8Array(data);
      iccBinaryData.set(chunkData, offset);
      offset += chunkData.length;
    }
    return parseTags2(new DataView(iccBinaryData.buffer));
  } catch (error) {
    return {};
  }
}
function getBuffer(dataView) {
  if (Array.isArray(dataView)) {
    return new DataView(Uint8Array.from(dataView).buffer).buffer;
  }
  return dataView.buffer;
}
function iccDoesNotHaveTagCount(buffer) {
  return buffer.length < ICC_TAG_COUNT_OFFSET + 4;
}
function hasTagsData(buffer, tagHeaderOffset) {
  return buffer.length < tagHeaderOffset + TAG_TABLE_SINGLE_TAG_DATA;
}
function parseTags2(dataView) {
  const buffer = dataView.buffer;
  const length = dataView.getUint32();
  if (dataView.byteLength !== length) {
    throw new Error("ICC profile length not matching");
  }
  if (dataView.byteLength < PROFILE_HEADER_LENGTH) {
    throw new Error("ICC profile too short");
  }
  const tags = {};
  const iccProfileKeys = Object.keys(iccProfile);
  for (let i = 0; i < iccProfileKeys.length; i++) {
    const offset = iccProfileKeys[i];
    const profileEntry = iccProfile[offset];
    const value = profileEntry.value(dataView, parseInt(offset, 10));
    let description = value;
    if (profileEntry.description) {
      description = profileEntry.description(value);
    }
    tags[profileEntry.name] = {
      value,
      description
    };
  }
  const signature = sliceToString2(buffer.slice(36, 40));
  if (signature !== ICC_SIGNATURE) {
    throw new Error("ICC profile: missing signature");
  }
  if (iccDoesNotHaveTagCount(buffer)) {
    return tags;
  }
  const tagCount = dataView.getUint32(128);
  let tagHeaderOffset = 132;
  for (let i = 0; i < tagCount; i++) {
    if (hasTagsData(buffer, tagHeaderOffset)) {
      return tags;
    }
    const tagSignature = getStringFromDataView(dataView, tagHeaderOffset, 4);
    const tagOffset = dataView.getUint32(tagHeaderOffset + 4);
    const tagSize = dataView.getUint32(tagHeaderOffset + 8);
    if (tagOffset > buffer.length) {
      return tags;
    }
    const tagType = getStringFromDataView(dataView, tagOffset, 4);
    if (tagType === TAG_TYPE_DESC) {
      const tagValueSize = dataView.getUint32(tagOffset + 8);
      if (tagValueSize > tagSize) {
        return tags;
      }
      const val = sliceToString2(buffer.slice(tagOffset + 12, tagOffset + tagValueSize + 11));
      addTag(tags, tagSignature, val);
    } else if (tagType === TAG_TYPE_MULTI_LOCALIZED_UNICODE_TYPE) {
      const numRecords = dataView.getUint32(tagOffset + 8);
      const recordSize = dataView.getUint32(tagOffset + 12);
      let offset = tagOffset + 16;
      const val = [];
      for (let recordNum = 0; recordNum < numRecords; recordNum++) {
        const languageCode = getStringFromDataView(dataView, offset + 0, 2);
        const countryCode = getStringFromDataView(dataView, offset + 2, 2);
        const textLength = dataView.getUint32(offset + 4);
        const textOffset = dataView.getUint32(offset + 8);
        const text = getUnicodeStringFromDataView(dataView, tagOffset + textOffset, textLength);
        val.push({ languageCode, countryCode, text });
        offset += recordSize;
      }
      if (numRecords === 1) {
        addTag(tags, tagSignature, val[0].text);
      } else {
        const valObj = {};
        for (let valIndex = 0; valIndex < val.length; valIndex++) {
          valObj[`${val[valIndex].languageCode}-${val[valIndex].countryCode}`] = val[valIndex].text;
        }
        addTag(tags, tagSignature, valObj);
      }
    } else if (tagType === TAG_TYPE_TEXT) {
      const val = sliceToString2(buffer.slice(tagOffset + 8, tagOffset + tagSize - 7));
      addTag(tags, tagSignature, val);
    } else if (tagType === TAG_TYPE_SIGNATURE) {
      const val = sliceToString2(buffer.slice(tagOffset + 8, tagOffset + 12));
      addTag(tags, tagSignature, val);
    }
    tagHeaderOffset = tagHeaderOffset + 12;
  }
  return tags;
}
function sliceToString2(slice) {
  return String.fromCharCode.apply(null, new Uint8Array(slice));
}
function addTag(tags, tagSignature, value) {
  if (iccTags[tagSignature]) {
    tags[iccTags[tagSignature].name] = { value, description: value };
  } else {
    tags[tagSignature] = { value, description: value };
  }
}

// node_modules/exifreader/src/canon-tags.js
var SHOT_INFO_AUTO_ROTATE = 27;
var canon_tags_default = {
  read: read9,
  SHOT_INFO_AUTO_ROTATE
};
function read9(dataView, tiffHeaderOffset, offset, byteOrder, includeUnknown, computed = false) {
  let tags = readIfd(dataView, IFD_TYPE_CANON, tiffHeaderOffset, tiffHeaderOffset + offset, byteOrder, includeUnknown, computed);
  if (tags["ShotInfo"]) {
    tags = objectAssign({}, tags, parseShotInfo(tags["ShotInfo"].value));
    delete tags["ShotInfo"];
  }
  return tags;
}
function parseShotInfo(shotInfoData) {
  const tags = {};
  if (shotInfoData[SHOT_INFO_AUTO_ROTATE] !== void 0) {
    tags["AutoRotate"] = {
      value: shotInfoData[SHOT_INFO_AUTO_ROTATE],
      description: getAutoRotateDescription(shotInfoData[SHOT_INFO_AUTO_ROTATE])
    };
  }
  return tags;
}
function getAutoRotateDescription(autoRotate) {
  if (autoRotate === 0) {
    return "None";
  }
  if (autoRotate === 1) {
    return "Rotate 90 CW";
  }
  if (autoRotate === 2) {
    return "Rotate 180";
  }
  if (autoRotate === 3) {
    return "Rotate 270 CW";
  }
  return "Unknown";
}

// node_modules/exifreader/src/pentax-tags.js
var BYTE_ORDER_OFFSET = 8;
var PENTAX_IFD_OFFSET = BYTE_ORDER_OFFSET + 2;
var MODEL_ID = {
  K3_III: 78420
};
var LIK3III = {
  CAMERA_ORIENTATION: 1,
  ROLL_ANGLE: 3,
  PITCH_ANGLE: 5
};
var pentax_tags_default = {
  read: read10,
  PENTAX_IFD_OFFSET,
  MODEL_ID,
  LIK3III
};
function read10(dataView, tiffHeaderOffset, offset, includeUnknown, computed = false) {
  const byteOrder = byte_order_default.getByteOrder(dataView, tiffHeaderOffset + offset + BYTE_ORDER_OFFSET);
  const originOffset = tiffHeaderOffset + offset;
  let tags = readIfd(
    dataView,
    IFD_TYPE_PENTAX,
    originOffset,
    originOffset + PENTAX_IFD_OFFSET,
    byteOrder,
    includeUnknown,
    computed
  );
  if (hasLevelInfoK3III(tags)) {
    tags = objectAssign({}, tags, parseLevelInfoK3III(dataView, originOffset + tags["LevelInfo"].__offset, byteOrder));
    delete tags["LevelInfo"];
  }
  return tags;
}
function hasLevelInfoK3III(tags) {
  return tags["PentaxModelID"] && tags["PentaxModelID"].value === MODEL_ID.K3_III && tags["LevelInfo"];
}
function parseLevelInfoK3III(dataView, levelInfoOffset, byteOrder) {
  const tags = {};
  if (levelInfoOffset + 7 > dataView.byteLength) {
    return tags;
  }
  const cameraOrientation = dataView.getInt8(levelInfoOffset + LIK3III.CAMERA_ORIENTATION);
  tags["CameraOrientation"] = {
    value: cameraOrientation,
    description: getOrientationDescription(cameraOrientation)
  };
  const rollAngle = dataView.getInt16(levelInfoOffset + LIK3III.ROLL_ANGLE, byteOrder === byte_order_default.LITTLE_ENDIAN);
  tags["RollAngle"] = {
    value: rollAngle,
    description: getRollAngleDescription(rollAngle)
  };
  const pitchAngle = dataView.getInt16(levelInfoOffset + LIK3III.PITCH_ANGLE, byteOrder === byte_order_default.LITTLE_ENDIAN);
  tags["PitchAngle"] = {
    value: pitchAngle,
    description: getPitchAngleDescription(pitchAngle)
  };
  return tags;
}
function getOrientationDescription(orientation) {
  if (orientation === 0) {
    return "Horizontal (normal)";
  }
  if (orientation === 1) {
    return "Rotate 270 CW";
  }
  if (orientation === 2) {
    return "Rotate 180";
  }
  if (orientation === 3) {
    return "Rotate 90 CW";
  }
  if (orientation === 4) {
    return "Upwards";
  }
  if (orientation === 5) {
    return "Downwards";
  }
  return "Unknown";
}
function getRollAngleDescription(rollAngle) {
  return "" + rollAngle * -0.5;
}
function getPitchAngleDescription(pitchAngle) {
  return "" + pitchAngle * -0.5;
}

// node_modules/exifreader/src/png-file-tags.js
var png_file_tags_default = {
  read: read11
};
function read11(dataView, fileDataOffset) {
  return {
    "Image Width": getImageWidth2(dataView, fileDataOffset),
    "Image Height": getImageHeight2(dataView, fileDataOffset),
    "Bit Depth": getBitDepth(dataView, fileDataOffset),
    "Color Type": getColorType(dataView, fileDataOffset),
    "Compression": getCompression(dataView, fileDataOffset),
    "Filter": getFilter(dataView, fileDataOffset),
    "Interlace": getInterlace(dataView, fileDataOffset)
  };
}
function getImageWidth2(dataView, fileDataOffset) {
  const OFFSET = 0;
  const SIZE = 4;
  if (fileDataOffset + OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const value = types_default.getLongAt(dataView, fileDataOffset);
  return {
    value,
    description: `${value}px`
  };
}
function getImageHeight2(dataView, fileDataOffset) {
  const OFFSET = 4;
  const SIZE = 4;
  if (fileDataOffset + OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const value = types_default.getLongAt(dataView, fileDataOffset + OFFSET);
  return {
    value,
    description: `${value}px`
  };
}
function getBitDepth(dataView, fileDataOffset) {
  const OFFSET = 8;
  const SIZE = 1;
  if (fileDataOffset + OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const value = types_default.getByteAt(dataView, fileDataOffset + OFFSET);
  return {
    value,
    description: `${value}`
  };
}
function getColorType(dataView, fileDataOffset) {
  const OFFSET = 9;
  const SIZE = 1;
  const COLOR_TYPES = {
    0: "Grayscale",
    2: "RGB",
    3: "Palette",
    4: "Grayscale with Alpha",
    6: "RGB with Alpha"
  };
  if (fileDataOffset + OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const value = types_default.getByteAt(dataView, fileDataOffset + OFFSET);
  return {
    value,
    description: COLOR_TYPES[value] || "Unknown"
  };
}
function getCompression(dataView, fileDataOffset) {
  const OFFSET = 10;
  const SIZE = 1;
  if (fileDataOffset + OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const value = types_default.getByteAt(dataView, fileDataOffset + OFFSET);
  return {
    value,
    description: value === 0 ? "Deflate/Inflate" : "Unknown"
  };
}
function getFilter(dataView, fileDataOffset) {
  const OFFSET = 11;
  const SIZE = 1;
  if (fileDataOffset + OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const value = types_default.getByteAt(dataView, fileDataOffset + OFFSET);
  return {
    value,
    description: value === 0 ? "Adaptive" : "Unknown"
  };
}
function getInterlace(dataView, fileDataOffset) {
  const OFFSET = 12;
  const SIZE = 1;
  const INTERLACE_TYPES = {
    0: "Noninterlaced",
    1: "Adam7 Interlace"
  };
  if (fileDataOffset + OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const value = types_default.getByteAt(dataView, fileDataOffset + OFFSET);
  return {
    value,
    description: INTERLACE_TYPES[value] || "Unknown"
  };
}

// node_modules/exifreader/src/png-text-tags.js
var png_text_tags_default = {
  read: read12
};
var STATE_KEYWORD = "STATE_KEYWORD";
var STATE_COMPRESSION = "STATE_COMPRESSION";
var STATE_LANG = "STATE_LANG";
var STATE_TRANSLATED_KEYWORD = "STATE_TRANSLATED_KEYWORD";
var STATE_TEXT = "STATE_TEXT";
var COMPRESSION_SECTION_ITXT_EXTRA_BYTE = 1;
var COMPRESSION_FLAG_COMPRESSED = 1;
var EXIF_OFFSET = 6;
function read12(dataView, pngTextChunks, async, includeUnknown, computed = false) {
  const tags = {};
  const tagsPromises = [];
  for (let i = 0; i < pngTextChunks.length; i++) {
    const { offset, length, type } = pngTextChunks[i];
    const nameAndValue = getNameAndValue(dataView, offset, length, type, async);
    if (nameAndValue instanceof Promise) {
      tagsPromises.push(nameAndValue.then(({ name, value, description }) => {
        try {
          if (constants_default.USE_EXIF && isExifGroupTag(name, value)) {
            return {
              __exif: tags_default.read(
                decodeRawData(value),
                EXIF_OFFSET,
                includeUnknown,
                computed
              ).tags
            };
          } else if (constants_default.USE_IPTC && isIptcGroupTag(name, value)) {
            return {
              __iptc: iptc_tags_default.read(decodeRawData(value), 0, includeUnknown)
            };
          } else if (name && !isExifGroupTag(name, value) && !isIptcGroupTag(name, value)) {
            return {
              [name]: {
                value,
                description
              }
            };
          }
        } catch (error) {
        }
        return {};
      }));
    } else {
      const { name, value, description } = nameAndValue;
      if (name) {
        tags[name] = {
          value,
          description
        };
      }
    }
  }
  return {
    readTags: tags,
    readTagsPromise: tagsPromises.length > 0 ? Promise.all(tagsPromises) : void 0
  };
}
function getNameAndValue(dataView, offset, length, type, async) {
  const keywordChars = [];
  const langChars = [];
  const translatedKeywordChars = [];
  let valueChars;
  let parsingState = STATE_KEYWORD;
  let compressionMethod = COMPRESSION_METHOD_NONE;
  for (let i = 0; i < length && offset + i < dataView.byteLength; i++) {
    if (parsingState === STATE_COMPRESSION) {
      compressionMethod = getCompressionMethod({ type, dataView, offset: offset + i });
      if (type === TYPE_ITXT) {
        i += COMPRESSION_SECTION_ITXT_EXTRA_BYTE;
      }
      parsingState = moveToNextState(type, parsingState);
      continue;
    } else if (parsingState === STATE_TEXT) {
      valueChars = new DataView(dataView.buffer.slice(offset + i, offset + length));
      break;
    }
    const byte = dataView.getUint8(offset + i);
    if (byte === 0) {
      parsingState = moveToNextState(type, parsingState);
    } else if (parsingState === STATE_KEYWORD) {
      keywordChars.push(byte);
    } else if (parsingState === STATE_LANG) {
      langChars.push(byte);
    } else if (parsingState === STATE_TRANSLATED_KEYWORD) {
      translatedKeywordChars.push(byte);
    }
  }
  if (compressionMethod !== COMPRESSION_METHOD_NONE && !async) {
    return {};
  }
  const decompressedValueChars = decompress(valueChars, compressionMethod, getEncodingFromType(type));
  if (decompressedValueChars instanceof Promise) {
    return decompressedValueChars.then((_decompressedValueChars) => constructTag(_decompressedValueChars, type, langChars, keywordChars)).catch(() => constructTag("<text using unknown compression>".split(""), type, langChars, keywordChars));
  }
  return constructTag(decompressedValueChars, type, langChars, keywordChars);
}
function getCompressionMethod({ type, dataView, offset }) {
  if (type === TYPE_ITXT) {
    if (dataView.getUint8(offset) === COMPRESSION_FLAG_COMPRESSED) {
      return dataView.getUint8(offset + 1);
    }
  } else if (type === TYPE_ZTXT) {
    return dataView.getUint8(offset);
  }
  return COMPRESSION_METHOD_NONE;
}
function moveToNextState(type, parsingState) {
  if (parsingState === STATE_KEYWORD && [TYPE_ITXT, TYPE_ZTXT].includes(type)) {
    return STATE_COMPRESSION;
  }
  if (parsingState === STATE_COMPRESSION) {
    if (type === TYPE_ITXT) {
      return STATE_LANG;
    }
    return STATE_TEXT;
  }
  if (parsingState === STATE_LANG) {
    return STATE_TRANSLATED_KEYWORD;
  }
  return STATE_TEXT;
}
function getEncodingFromType(type) {
  if (type === TYPE_TEXT || type === TYPE_ZTXT) {
    return "latin1";
  }
  return "utf-8";
}
function constructTag(valueChars, type, langChars, keywordChars) {
  const value = getValue(valueChars);
  return {
    name: getName(type, langChars, keywordChars),
    value,
    description: type === TYPE_ITXT ? getDescription2(valueChars) : value
  };
}
function getName(type, langChars, keywordChars) {
  const name = getStringValueFromArray(keywordChars);
  if (type === TYPE_TEXT || langChars.length === 0) {
    return name;
  }
  const lang = getStringValueFromArray(langChars);
  return `${name} (${lang})`;
}
function getValue(valueChars) {
  if (valueChars instanceof DataView) {
    return getStringFromDataView(valueChars, 0, valueChars.byteLength);
  }
  return valueChars;
}
function getDescription2(valueChars) {
  return tag_decoder_default.decode("UTF-8", valueChars);
}
function isExifGroupTag(name, value) {
  return name.toLowerCase() === "raw profile type exif" && value.substring(1, 5) === "exif";
}
function isIptcGroupTag(name, value) {
  return name.toLowerCase() === "raw profile type iptc" && value.substring(1, 5) === "iptc";
}
function decodeRawData(value) {
  const parts = value.match(/\n(exif|iptc)\n\s*\d+\n([\s\S]*)$/);
  return hexToDataView(parts[2].replace(/\n/g, ""));
}
function hexToDataView(hex) {
  const dataView = new DataView(new ArrayBuffer(hex.length / 2));
  for (let i = 0; i < hex.length; i += 2) {
    dataView.setUint8(i / 2, parseInt(hex.substring(i, i + 2), 16));
  }
  return dataView;
}

// node_modules/exifreader/src/png-tags.js
var png_tags_default = {
  read: read13
};
function read13(dataView, chunkOffsets) {
  const tags = {};
  for (let i = 0; i < chunkOffsets.length; i++) {
    const chunkLength = types_default.getLongAt(dataView, chunkOffsets[i] + PNG_CHUNK_LENGTH_OFFSET);
    const chunkType = getStringFromDataView(dataView, chunkOffsets[i] + PNG_CHUNK_TYPE_OFFSET, PNG_CHUNK_TYPE_SIZE);
    if (chunkType === TYPE_PHYS) {
      tags["Pixels Per Unit X"] = getPixelsPerUnitX(dataView, chunkOffsets[i], chunkLength);
      tags["Pixels Per Unit Y"] = getPixelsPerUnitY(dataView, chunkOffsets[i], chunkLength);
      tags["Pixel Units"] = getPixelUnits(dataView, chunkOffsets[i], chunkLength);
    } else if (chunkType === TYPE_TIME) {
      tags["Modify Date"] = getModifyDate(dataView, chunkOffsets[i], chunkLength);
    }
  }
  return tags;
}
function getPixelsPerUnitX(dataView, chunkOffset, chunkLength) {
  const TAG_OFFSET = 0;
  const TAG_SIZE = 4;
  if (!tagFitsInBuffer(dataView, chunkOffset, chunkLength, TAG_OFFSET, TAG_SIZE)) {
    return void 0;
  }
  const value = types_default.getLongAt(dataView, chunkOffset + PNG_CHUNK_DATA_OFFSET + TAG_OFFSET);
  return {
    value,
    description: "" + value
  };
}
function getPixelsPerUnitY(dataView, chunkOffset, chunkLength) {
  const TAG_OFFSET = 4;
  const TAG_SIZE = 4;
  if (!tagFitsInBuffer(dataView, chunkOffset, chunkLength, TAG_OFFSET, TAG_SIZE)) {
    return void 0;
  }
  const value = types_default.getLongAt(dataView, chunkOffset + PNG_CHUNK_DATA_OFFSET + TAG_OFFSET);
  return {
    value,
    description: "" + value
  };
}
function getPixelUnits(dataView, chunkOffset, chunkLength) {
  const TAG_OFFSET = 8;
  const TAG_SIZE = 1;
  if (!tagFitsInBuffer(dataView, chunkOffset, chunkLength, TAG_OFFSET, TAG_SIZE)) {
    return void 0;
  }
  const value = types_default.getByteAt(dataView, chunkOffset + PNG_CHUNK_DATA_OFFSET + TAG_OFFSET);
  return {
    value,
    description: value === 1 ? "meters" : "Unknown"
  };
}
function getModifyDate(dataView, chunkOffset, chunkLength) {
  const TIME_TAG_SIZE = 7;
  if (!tagFitsInBuffer(dataView, chunkOffset, chunkLength, 0, TIME_TAG_SIZE)) {
    return void 0;
  }
  const year = types_default.getShortAt(dataView, chunkOffset + PNG_CHUNK_DATA_OFFSET);
  const month = types_default.getByteAt(dataView, chunkOffset + PNG_CHUNK_DATA_OFFSET + 2);
  const day = types_default.getByteAt(dataView, chunkOffset + PNG_CHUNK_DATA_OFFSET + 3);
  const hours = types_default.getByteAt(dataView, chunkOffset + PNG_CHUNK_DATA_OFFSET + 4);
  const minutes = types_default.getByteAt(dataView, chunkOffset + PNG_CHUNK_DATA_OFFSET + 5);
  const seconds = types_default.getByteAt(dataView, chunkOffset + PNG_CHUNK_DATA_OFFSET + 6);
  return {
    value: [year, month, day, hours, minutes, seconds],
    description: `${pad(year, 4)}-${pad(month, 2)}-${pad(day, 2)} ${pad(hours, 2)}:${pad(minutes, 2)}:${pad(seconds, 2)}`
  };
}
function tagFitsInBuffer(dataView, chunkOffset, chunkLength, tagOffset, tagSize) {
  return tagOffset + tagSize <= chunkLength && chunkOffset + PNG_CHUNK_DATA_OFFSET + tagOffset + tagSize <= dataView.byteLength;
}
function pad(number, size) {
  return `${"0".repeat(size - ("" + number).length)}${number}`;
}

// node_modules/exifreader/src/vp8x-tags.js
var vp8x_tags_default = {
  read: read14
};
var IMAGE_WIDTH_OFFSET = 4;
var IMAGE_HEIGHT_OFFSET = 7;
function read14(dataView, chunkOffset) {
  const tags = {};
  const flags = types_default.getByteAt(dataView, chunkOffset);
  tags["Alpha"] = getAlpha(flags);
  tags["Animation"] = getAnimation(flags);
  tags["ImageWidth"] = getThreeByteValue(dataView, chunkOffset + IMAGE_WIDTH_OFFSET);
  tags["ImageHeight"] = getThreeByteValue(dataView, chunkOffset + IMAGE_HEIGHT_OFFSET);
  return tags;
}
function getAlpha(flags) {
  const value = flags & 16;
  return {
    value: value ? 1 : 0,
    description: value ? "Yes" : "No"
  };
}
function getAnimation(flags) {
  const value = flags & 2;
  return {
    value: value ? 1 : 0,
    description: value ? "Yes" : "No"
  };
}
function getThreeByteValue(dataView, offset) {
  const value = types_default.getByteAt(dataView, offset) + 256 * types_default.getByteAt(dataView, offset + 1) + 256 * 256 * types_default.getByteAt(dataView, offset + 2) + 1;
  return {
    value,
    description: value + "px"
  };
}

// node_modules/exifreader/src/gif-file-tags.js
var gif_file_tags_default = {
  read: read15
};
function read15(dataView) {
  return {
    "GIF Version": getGifVersion(dataView),
    "Image Width": getImageWidth3(dataView),
    "Image Height": getImageHeight3(dataView),
    "Global Color Map": getGlobalColorMap(dataView),
    "Bits Per Pixel": getBitDepth2(dataView),
    "Color Resolution Depth": getColorResolution(dataView)
  };
}
function getGifVersion(dataView) {
  const OFFSET = 3;
  const SIZE = 3;
  if (OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const value = getStringFromDataView(dataView, OFFSET, SIZE);
  return {
    value,
    description: value
  };
}
function getImageWidth3(dataView) {
  const OFFSET = 6;
  const SIZE = 2;
  if (OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const value = dataView.getUint16(OFFSET, true);
  return {
    value,
    description: `${value}px`
  };
}
function getImageHeight3(dataView) {
  const OFFSET = 8;
  const SIZE = 2;
  if (OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const value = dataView.getUint16(OFFSET, true);
  return {
    value,
    description: `${value}px`
  };
}
function getGlobalColorMap(dataView) {
  const OFFSET = 10;
  const SIZE = 1;
  if (OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const byteValue = dataView.getUint8(OFFSET);
  const value = (byteValue & 128) >>> 7;
  return {
    value,
    description: value === 1 ? "Yes" : "No"
  };
}
function getColorResolution(dataView) {
  const OFFSET = 10;
  const SIZE = 1;
  if (OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const byteValue = dataView.getUint8(OFFSET);
  const value = ((byteValue & 112) >>> 4) + 1;
  return {
    value,
    description: `${value} ${value === 1 ? "bit" : "bits"}`
  };
}
function getBitDepth2(dataView) {
  const OFFSET = 10;
  const SIZE = 1;
  if (OFFSET + SIZE > dataView.byteLength) {
    return void 0;
  }
  const byteValue = dataView.getUint8(OFFSET);
  const value = (byteValue & 7) + 1;
  return {
    value,
    description: `${value} ${value === 1 ? "bit" : "bits"}`
  };
}

// node_modules/exifreader/src/thumbnail.js
var COMPRESSION_JPEG = [6, 7, 99];
var thumbnail_default = {
  get: get3
};
function get3(dataView, thumbnailTags, tiffHeaderOffset) {
  if (hasJpegThumbnail(thumbnailTags)) {
    thumbnailTags.type = "image/jpeg";
    const offset = tiffHeaderOffset + thumbnailTags.JPEGInterchangeFormat.value;
    thumbnailTags.image = dataView.buffer.slice(offset, offset + thumbnailTags.JPEGInterchangeFormatLength.value);
    deferInit(thumbnailTags, "base64", function() {
      return getBase64Image(this.image);
    });
  }
  return thumbnailTags;
}
function hasJpegThumbnail(tags) {
  return tags && (tags.Compression === void 0 || COMPRESSION_JPEG.includes(tags.Compression.value)) && tags.JPEGInterchangeFormat && tags.JPEGInterchangeFormat.value && tags.JPEGInterchangeFormatLength && tags.JPEGInterchangeFormatLength.value;
}

// node_modules/exifreader/src/composite.js
var FOCAL_PLANE_RESOLUTION_UNIT = {
  INCHES: 2,
  CENTIMETERS: 3,
  MILLIMETERS: 4
};
var UNIT_FACTORS = {
  INCHES_TO_MM: 25.4,
  // 1 inch = 25.4 mm
  CM_TO_MM: 10,
  // 1 cm = 10 mm
  MM_TO_MM: 1
  // Already in mm
};
var composite_default = {
  get: get4
};
function get4(tags, expanded) {
  const compositeTags = {};
  let hasCompositeTags = false;
  const focalLength = getTagValue3(tags, "exif", "FocalLength", expanded);
  const focalPlaneXResolution = getTagValue3(tags, "exif", "FocalPlaneXResolution", expanded);
  const focalPlaneYResolution = getTagValue3(tags, "exif", "FocalPlaneYResolution", expanded);
  const focalPlaneResolutionUnit = getTagValue3(tags, "exif", "FocalPlaneResolutionUnit", expanded);
  const imageWidth = getTagValue3(tags, "file", "Image Width", expanded);
  const imageHeight = getTagValue3(tags, "file", "Image Height", expanded);
  const focalLengthIn35mmFilm = getTagValue3(tags, "exif", "FocalLengthIn35mmFilm", expanded) || getFocalLengthIn35mmFilmValue(focalPlaneXResolution, focalPlaneYResolution, focalPlaneResolutionUnit, imageWidth, imageHeight, focalLength);
  if (focalLengthIn35mmFilm) {
    compositeTags.FocalLength35efl = {
      value: focalLengthIn35mmFilm,
      description: tag_names_common_default.FocalLengthIn35mmFilm(focalLengthIn35mmFilm)
    };
    hasCompositeTags = true;
  }
  const scaleFactorTo35mmEquivalent = getScaleFactorTo35mmEquivalent(focalLength, focalLengthIn35mmFilm);
  if (scaleFactorTo35mmEquivalent) {
    compositeTags.ScaleFactorTo35mmEquivalent = scaleFactorTo35mmEquivalent;
    hasCompositeTags = true;
  }
  const fieldOfView = getFieldOfView(focalLengthIn35mmFilm);
  if (fieldOfView) {
    compositeTags.FieldOfView = fieldOfView;
    hasCompositeTags = true;
  }
  if (hasCompositeTags) {
    return compositeTags;
  }
  return void 0;
}
function getTagValue3(tags, group, tagName, expanded) {
  if (expanded && tags[group] && tags[group][tagName]) {
    return tags[group][tagName].value;
  }
  if (!expanded && tags[tagName]) {
    return tags[tagName].value;
  }
  return void 0;
}
function getFocalLengthIn35mmFilmValue(focalPlaneXResolution, focalPlaneYResolution, focalPlaneResolutionUnit, imageWidth, imageHeight, focalLength) {
  const DIAGONAL_35mm = 43.27;
  if (focalPlaneXResolution && focalPlaneYResolution && focalPlaneResolutionUnit && imageWidth && imageHeight && focalLength) {
    try {
      let resolutionUnitFactor;
      switch (focalPlaneResolutionUnit) {
        case FOCAL_PLANE_RESOLUTION_UNIT.INCHES:
          resolutionUnitFactor = UNIT_FACTORS.INCHES_TO_MM;
          break;
        case FOCAL_PLANE_RESOLUTION_UNIT.CENTIMETERS:
          resolutionUnitFactor = UNIT_FACTORS.CM_TO_MM;
          break;
        case FOCAL_PLANE_RESOLUTION_UNIT.MILLIMETERS:
          resolutionUnitFactor = UNIT_FACTORS.MM_TO_MM;
          break;
        default:
          return void 0;
      }
      const focalPlaneXResolutionMm = focalPlaneXResolution[0] / focalPlaneXResolution[1] * resolutionUnitFactor;
      const focalPlaneYResolutionMm = focalPlaneYResolution[0] / focalPlaneYResolution[1] * resolutionUnitFactor;
      const sensorWidthMm = imageWidth / focalPlaneXResolutionMm;
      const sensorHeightMm = imageHeight / focalPlaneYResolutionMm;
      const sensorDiagonal = Math.sqrt(sensorWidthMm ** 2 + sensorHeightMm ** 2);
      const focalLength35mm = focalLength[0] / focalLength[1] * (DIAGONAL_35mm / sensorDiagonal);
      return focalLength35mm;
    } catch (error) {
    }
  }
  return void 0;
}
function getScaleFactorTo35mmEquivalent(focalLength, focalLengthIn35mmFilm) {
  if (focalLength && focalLengthIn35mmFilm) {
    try {
      const value = focalLengthIn35mmFilm / (focalLength[0] / focalLength[1]);
      return {
        value,
        description: value.toFixed(1)
      };
    } catch (error) {
    }
  }
  return void 0;
}
function getFieldOfView(focalLengthIn35mmFilm) {
  const FULL_FRAME_SENSOR_WIDTH_MM = 36;
  if (focalLengthIn35mmFilm) {
    try {
      const value = 2 * Math.atan(FULL_FRAME_SENSOR_WIDTH_MM / (2 * focalLengthIn35mmFilm)) * (180 / Math.PI);
      return {
        value,
        description: value.toFixed(1) + " deg"
      };
    } catch (error) {
    }
  }
  return void 0;
}

// node_modules/exifreader/src/errors.js
function MetadataMissingError(message) {
  this.name = "MetadataMissingError";
  this.message = message || "No Exif data";
  this.stack = new Error().stack;
}
MetadataMissingError.prototype = new Error();
var errors_default = {
  MetadataMissingError
};

// node_modules/exifreader/src/exif-reader.js
var exif_reader_default = {
  load,
  loadView,
  errors: errors_default
};
function load(data, options = {}) {
  if (isFilePathOrURL(data)) {
    options.async = true;
    return loadFile(data, options).then((fileContents) => loadFromData(fileContents, options));
  }
  if (isBrowserFileObject(data)) {
    options.async = true;
    return loadFileObject(data, options).then((fileContents) => loadFromData(fileContents, options));
  }
  return loadFromData(data, options);
}
function isFilePathOrURL(data) {
  return typeof data === "string";
}
function loadFile(filename, options) {
  if (/^\w+:\/\//.test(filename)) {
    if (typeof fetch !== "undefined") {
      return fetchRemoteFile(filename, options);
    }
    return nodeGetRemoteFile(filename, options);
  }
  if (isDataUri(filename)) {
    return Promise.resolve(dataUriToBuffer(filename));
  }
  return loadLocalFile(filename, options);
}
function fetchRemoteFile(url, { length } = {}) {
  const options = { method: "GET" };
  if (Number.isInteger(length) && length >= 0) {
    options.headers = {
      range: `bytes=0-${length - 1}`
    };
  }
  return fetch(url, options).then((response) => response.arrayBuffer());
}
function nodeGetRemoteFile(url, { length } = {}) {
  return new Promise((resolve, reject) => {
    const options = {};
    if (Number.isInteger(length) && length >= 0) {
      options.headers = {
        range: `bytes=0-${length - 1}`
      };
    }
    const get5 = requireNodeGet(url);
    get5(url, options, (response) => {
      if (response.statusCode >= 200 && response.statusCode <= 299) {
        const data = [];
        response.on("data", (chunk) => data.push(Buffer.from(chunk)));
        response.on("error", (error) => reject(error));
        response.on("end", () => resolve(Buffer.concat(data)));
      } else {
        reject(`Could not fetch file: ${response.statusCode} ${response.statusMessage}`);
        response.resume();
      }
    }).on("error", (error) => reject(error));
  });
}
function requireNodeGet(url) {
  if (/^https:\/\//.test(url)) {
    return __non_webpack_require__("https").get;
  }
  return __non_webpack_require__("http").get;
}
function isDataUri(filename) {
  return /^data:[^;,]*(;base64)?,/.test(filename);
}
function loadLocalFile(filename, { length } = {}) {
  return new Promise((resolve, reject) => {
    const fs = requireNodeFs();
    fs.open(filename, (error, fd) => {
      if (error) {
        reject(error);
      } else {
        fs.stat(filename, (error2, stat) => {
          if (error2) {
            reject(error2);
          } else {
            const size = Math.min(stat.size, length !== void 0 ? length : stat.size);
            const buffer = Buffer.alloc(size);
            const options = {
              buffer,
              length: size
            };
            fs.read(fd, options, (error3) => {
              if (error3) {
                reject(error3);
              } else {
                fs.close(fd, (error4) => {
                  if (error4) {
                    console.warn(`Could not close file ${filename}:`, error4);
                  }
                  resolve(buffer);
                });
              }
            });
          }
        });
      }
    });
  });
}
function requireNodeFs() {
  try {
    return __non_webpack_require__("fs");
  } catch (error) {
    return void 0;
  }
}
function isBrowserFileObject(data) {
  return typeof File !== "undefined" && data instanceof File;
}
function loadFileObject(file, { length }) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (readerEvent) => resolve(readerEvent.target.result);
    reader.onerror = () => reject(reader.error);
    if (Number.isInteger(length) && length >= 0 && file.slice !== void 0) {
      reader.readAsArrayBuffer(file.slice(0, length));
    } else {
      reader.readAsArrayBuffer(file);
    }
  });
}
function loadFromData(data, options) {
  if (isNodeBuffer(data)) {
    data = new Uint8Array(data).buffer;
  }
  return loadView(getDataView2(data), options);
}
function isNodeBuffer(data) {
  try {
    return Buffer.isBuffer(data);
  } catch (error) {
    return false;
  }
}
function getDataView2(data) {
  try {
    return new DataView(data);
  } catch (error) {
    return new DataView2(data);
  }
}
function loadView(dataView, {
  expanded = false,
  async = false,
  computed = false,
  includeUnknown = false,
  domParser = void 0
} = {
  expanded: false,
  async: false,
  computed: false,
  includeUnknown: false,
  domParser: void 0
}) {
  let foundMetaData = false;
  let tags = {};
  const tagsPromises = [];
  const {
    fileType,
    fileDataOffset,
    jfifDataOffset,
    tiffHeaderOffset,
    iptcDataOffset,
    xmpChunks,
    iccChunks,
    mpfDataOffset,
    pngHeaderOffset,
    pngTextChunks,
    pngChunkOffsets,
    vp8xChunkOffset,
    gifHeaderOffset
  } = image_header_default.parseAppMarkers(dataView, async);
  if (constants_default.USE_JPEG && constants_default.USE_FILE && hasFileData(fileDataOffset)) {
    foundMetaData = true;
    const readTags2 = file_tags_default.read(dataView, fileDataOffset);
    if (expanded) {
      tags.file = readTags2;
    } else {
      tags = objectAssign({}, tags, readTags2);
    }
  }
  if (constants_default.USE_JPEG && constants_default.USE_JFIF && hasJfifData(jfifDataOffset)) {
    foundMetaData = true;
    const readTags2 = jfif_tags_default.read(dataView, jfifDataOffset);
    if (expanded) {
      tags.jfif = readTags2;
    } else {
      tags = objectAssign({}, tags, readTags2);
    }
  }
  if (constants_default.USE_EXIF && hasExifData(tiffHeaderOffset)) {
    foundMetaData = true;
    const { tags: readTags2, byteOrder } = tags_default.read(
      dataView,
      tiffHeaderOffset,
      includeUnknown,
      computed
    );
    if (readTags2.Thumbnail) {
      tags.Thumbnail = readTags2.Thumbnail;
      delete readTags2.Thumbnail;
    }
    if (expanded) {
      tags.exif = readTags2;
      addGpsGroup(tags);
    } else {
      tags = objectAssign({}, tags, readTags2);
    }
    if (constants_default.USE_TIFF && constants_default.USE_IPTC && readTags2["IPTC-NAA"] && !hasIptcData(iptcDataOffset)) {
      const readIptcTags = iptc_tags_default.read(readTags2["IPTC-NAA"].value, 0, includeUnknown);
      if (expanded) {
        tags.iptc = readIptcTags;
      } else {
        tags = objectAssign({}, tags, readIptcTags);
      }
    }
    if (constants_default.USE_TIFF && constants_default.USE_XMP && readTags2["ApplicationNotes"] && !hasXmpData(xmpChunks)) {
      const readXmpTags = xmp_tags_default.read(getStringValueFromArray(readTags2["ApplicationNotes"].value), void 0, domParser);
      if (expanded) {
        tags.xmp = readXmpTags;
      } else {
        delete readXmpTags._raw;
        tags = objectAssign({}, tags, readXmpTags);
      }
    }
    if (constants_default.USE_PHOTOSHOP && readTags2["ImageSourceData"] && readTags2["PhotoshopSettings"]) {
      const readPhotoshopTags = photoshop_tags_default.read(readTags2["PhotoshopSettings"].value, includeUnknown);
      if (expanded) {
        tags.photoshop = readPhotoshopTags;
      } else {
        tags = objectAssign({}, tags, readPhotoshopTags);
      }
    }
    if (constants_default.USE_TIFF && constants_default.USE_ICC && readTags2["ICC_Profile"] && !hasIccData(iccChunks)) {
      const readIccTags = icc_tags_default.read(
        readTags2["ICC_Profile"].value,
        [{
          offset: 0,
          length: readTags2["ICC_Profile"].value.length,
          chunkNumber: 1,
          chunksTotal: 1
        }]
      );
      if (expanded) {
        tags.icc = readIccTags;
      } else {
        tags = objectAssign({}, tags, readIccTags);
      }
    }
    if (constants_default.USE_MAKER_NOTES && readTags2["MakerNote"]) {
      if (hasCanonData(readTags2)) {
        const readCanonTags = canon_tags_default.read(
          dataView,
          tiffHeaderOffset,
          readTags2["MakerNote"].__offset,
          byteOrder,
          includeUnknown,
          computed
        );
        if (expanded) {
          tags.makerNotes = readCanonTags;
        } else {
          tags = objectAssign({}, tags, readCanonTags);
        }
      } else if (hasPentaxType1Data(readTags2)) {
        const readPentaxTags = pentax_tags_default.read(
          dataView,
          tiffHeaderOffset,
          readTags2["MakerNote"].__offset,
          includeUnknown,
          computed
        );
        if (expanded) {
          tags.makerNotes = readPentaxTags;
        } else {
          tags = objectAssign({}, tags, readPentaxTags);
        }
      }
    }
    if (readTags2["MakerNote"]) {
      delete readTags2["MakerNote"].__offset;
    }
  }
  if (constants_default.USE_JPEG && constants_default.USE_IPTC && hasIptcData(iptcDataOffset)) {
    foundMetaData = true;
    const readTags2 = iptc_tags_default.read(dataView, iptcDataOffset, includeUnknown);
    if (expanded) {
      tags.iptc = readTags2;
    } else {
      tags = objectAssign({}, tags, readTags2);
    }
  }
  if (constants_default.USE_XMP && hasXmpData(xmpChunks)) {
    foundMetaData = true;
    const readTags2 = xmp_tags_default.read(dataView, xmpChunks, domParser);
    if (expanded) {
      tags.xmp = readTags2;
    } else {
      delete readTags2._raw;
      tags = objectAssign({}, tags, readTags2);
    }
  }
  if ((constants_default.USE_JPEG || constants_default.USE_WEBP) && constants_default.USE_ICC && hasIccData(iccChunks)) {
    foundMetaData = true;
    const readTags2 = icc_tags_default.read(dataView, iccChunks, async);
    if (readTags2 instanceof Promise) {
      tagsPromises.push(readTags2.then(addIccTags));
    } else {
      addIccTags(readTags2);
    }
  }
  if (constants_default.USE_MPF && hasMpfData(mpfDataOffset)) {
    foundMetaData = true;
    const readMpfTags = mpf_tags_default.read(dataView, mpfDataOffset, includeUnknown, computed);
    if (expanded) {
      tags.mpf = readMpfTags;
    } else {
      tags = objectAssign({}, tags, readMpfTags);
    }
  }
  if (constants_default.USE_PNG && constants_default.USE_PNG_FILE && hasPngFileData(pngHeaderOffset)) {
    foundMetaData = true;
    const readTags2 = png_file_tags_default.read(dataView, pngHeaderOffset);
    if (expanded) {
      tags.png = !tags.png ? readTags2 : objectAssign({}, tags.png, readTags2);
      tags.pngFile = readTags2;
    } else {
      tags = objectAssign({}, tags, readTags2);
    }
  }
  if (constants_default.USE_PNG && hasPngTextData(pngTextChunks)) {
    foundMetaData = true;
    const { readTags: readTags2, readTagsPromise } = png_text_tags_default.read(dataView, pngTextChunks, async, includeUnknown, computed);
    addPngTextTags(readTags2);
    if (readTagsPromise) {
      tagsPromises.push(readTagsPromise.then((tagList) => tagList.forEach(addPngTextTags)));
    }
  }
  if (constants_default.USE_PNG && hasPngData(pngChunkOffsets)) {
    foundMetaData = true;
    const readTags2 = png_tags_default.read(dataView, pngChunkOffsets);
    if (expanded) {
      tags.png = !tags.png ? readTags2 : objectAssign({}, tags.png, readTags2);
    } else {
      tags = objectAssign({}, tags, readTags2);
    }
  }
  if (constants_default.USE_WEBP && hasVp8xData(vp8xChunkOffset)) {
    foundMetaData = true;
    const readTags2 = vp8x_tags_default.read(dataView, vp8xChunkOffset);
    if (expanded) {
      tags.riff = !tags.riff ? readTags2 : objectAssign({}, tags.riff, readTags2);
    } else {
      tags = objectAssign({}, tags, readTags2);
    }
  }
  if (constants_default.USE_GIF && hasGifFileData(gifHeaderOffset)) {
    foundMetaData = true;
    const readTags2 = gif_file_tags_default.read(dataView, gifHeaderOffset);
    if (expanded) {
      tags.gif = !tags.gif ? readTags2 : objectAssign({}, tags.gif, readTags2);
    } else {
      tags = objectAssign({}, tags, readTags2);
    }
  }
  const composite = composite_default.get(tags, expanded);
  if (composite) {
    if (expanded) {
      tags.composite = composite;
    } else {
      tags = objectAssign({}, tags, composite);
    }
  }
  const thumbnail = (constants_default.USE_JPEG || constants_default.USE_WEBP) && constants_default.USE_EXIF && constants_default.USE_THUMBNAIL && thumbnail_default.get(dataView, tags.Thumbnail, tiffHeaderOffset);
  if (thumbnail) {
    foundMetaData = true;
    tags.Thumbnail = thumbnail;
  } else {
    delete tags.Thumbnail;
  }
  if (fileType) {
    if (expanded) {
      if (!tags.file) {
        tags.file = {};
      }
      tags.file.FileType = fileType;
    } else {
      tags.FileType = fileType;
    }
    foundMetaData = true;
  }
  if (!foundMetaData) {
    throw new errors_default.MetadataMissingError();
  }
  if (async) {
    return Promise.all(tagsPromises).then(() => tags);
  }
  return tags;
  function addIccTags(readTags2) {
    if (expanded) {
      tags.icc = readTags2;
    } else {
      tags = objectAssign({}, tags, readTags2);
    }
  }
  function addPngTextTags(readTags2) {
    if (expanded) {
      for (const group of ["exif", "iptc"]) {
        const groupKey = `__${group}`;
        if (readTags2[groupKey]) {
          tags[group] = !tags[group] ? readTags2[groupKey] : objectAssign({}, tags.exif, readTags2[groupKey]);
          delete readTags2[groupKey];
        }
      }
      tags.png = !tags.png ? readTags2 : objectAssign({}, tags.png, readTags2);
      tags.pngText = !tags.pngText ? readTags2 : objectAssign({}, tags.png, readTags2);
    } else {
      tags = objectAssign(
        {},
        tags,
        readTags2.__exif ? readTags2.__exif : {},
        readTags2.__iptc ? readTags2.__iptc : {},
        readTags2
      );
      delete tags.__exif;
      delete tags.__iptc;
    }
  }
}
function hasFileData(fileDataOffset) {
  return fileDataOffset !== void 0;
}
function hasJfifData(jfifDataOffset) {
  return jfifDataOffset !== void 0;
}
function hasExifData(tiffHeaderOffset) {
  return tiffHeaderOffset !== void 0;
}
function addGpsGroup(tags) {
  if (tags.exif) {
    if (tags.exif.GPSLatitude && tags.exif.GPSLatitudeRef) {
      try {
        tags.gps = tags.gps || {};
        tags.gps.Latitude = getCalculatedGpsValue(tags.exif.GPSLatitude.value);
        if (tags.exif.GPSLatitudeRef.value.join("") === "S") {
          tags.gps.Latitude = -tags.gps.Latitude;
        }
      } catch (error) {
      }
    }
    if (tags.exif.GPSLongitude && tags.exif.GPSLongitudeRef) {
      try {
        tags.gps = tags.gps || {};
        tags.gps.Longitude = getCalculatedGpsValue(tags.exif.GPSLongitude.value);
        if (tags.exif.GPSLongitudeRef.value.join("") === "W") {
          tags.gps.Longitude = -tags.gps.Longitude;
        }
      } catch (error) {
      }
    }
    if (tags.exif.GPSAltitude && tags.exif.GPSAltitudeRef) {
      try {
        tags.gps = tags.gps || {};
        tags.gps.Altitude = tags.exif.GPSAltitude.value[0] / tags.exif.GPSAltitude.value[1];
        if (tags.exif.GPSAltitudeRef.value === 1) {
          tags.gps.Altitude = -tags.gps.Altitude;
        }
      } catch (error) {
      }
    }
  }
}
function hasIptcData(iptcDataOffset) {
  return iptcDataOffset !== void 0;
}
function hasXmpData(xmpChunks) {
  return Array.isArray(xmpChunks) && xmpChunks.length > 0;
}
function hasIccData(iccDataOffsets) {
  return Array.isArray(iccDataOffsets) && iccDataOffsets.length > 0;
}
function hasCanonData(tags) {
  return tags["Make"] && tags["Make"].value && Array.isArray(tags["Make"].value) && tags["Make"].value[0] === "Canon" && tags["MakerNote"] && tags["MakerNote"].__offset;
}
function hasPentaxType1Data(tags) {
  const PENTAX_ID_STRING = "PENTAX ";
  return tags["MakerNote"].value.length > PENTAX_ID_STRING.length && getStringValueFromArray(tags["MakerNote"].value.slice(0, PENTAX_ID_STRING.length)) === PENTAX_ID_STRING && tags["MakerNote"].__offset;
}
function hasMpfData(mpfDataOffset) {
  return mpfDataOffset !== void 0;
}
function hasPngFileData(pngFileDataOffset) {
  return pngFileDataOffset !== void 0;
}
function hasPngTextData(pngTextChunks) {
  return pngTextChunks !== void 0;
}
function hasPngData(pngChunkOffsets) {
  return pngChunkOffsets !== void 0;
}
function hasVp8xData(vp8xChunkOffset) {
  return vp8xChunkOffset !== void 0;
}
function hasGifFileData(gifHeaderOffset) {
  return gifHeaderOffset !== void 0;
}

// png-metadata.ts
function parsePngMetadata(buffer) {
  try {
    const tags = exif_reader_default.load(buffer);
    const result = {};
    const getText = (key) => {
      const tag = tags[key];
      if (tag && typeof tag === "object" && "value" in tag) {
        return String(tag.value);
      }
      return void 0;
    };
    const getInt = (key) => {
      const text = getText(key);
      if (text !== void 0) {
        const num = parseInt(text, 10);
        if (!isNaN(num)) {
          return num;
        }
      }
      return void 0;
    };
    const prompt = getText("Prompt");
    if (prompt !== void 0) result.prompt = prompt;
    const model = getText("Model");
    if (model !== void 0) result.model = model;
    const seed = getInt("Seed");
    if (seed !== void 0) result.seed = seed;
    const aspectRatio = getText("AspectRatio");
    if (aspectRatio !== void 0) result.aspectRatio = aspectRatio;
    const width = getInt("Width");
    if (width !== void 0) result.width = width;
    const height = getInt("Height");
    if (height !== void 0) result.height = height;
    const generatedWidth = getInt("GeneratedWidth");
    if (generatedWidth !== void 0) result.generatedWidth = generatedWidth;
    const generatedHeight = getInt("GeneratedHeight");
    if (generatedHeight !== void 0) result.generatedHeight = generatedHeight;
    return result;
  } catch (error) {
    console.warn("Failed to parse PNG metadata:", error);
    return {};
  }
}
async function fetchAndParsePngMetadata(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      console.warn(`Failed to fetch PNG: ${response.status} ${response.statusText}`);
      return {};
    }
    const buffer = await response.arrayBuffer();
    return parsePngMetadata(buffer);
  } catch (error) {
    console.warn("Failed to fetch and parse PNG metadata:", error);
    return {};
  }
}

// main.ts
var appWindow = getCurrentWindow();
var state = {
  currentImage: null,
  backendState: null,
  // null until first state_changed(loading) event arrives from backend
  isPaused: false,
  // DEPRECATED - kept for compatibility, use backendState.state === "paused"
  isTransitioning: false,
  prompt: "",
  generationPrompt: "",
  aspectRatio: "1:1",
  width: 1024,
  height: 1024,
  outputPath: null,
  actionQueue: Promise.resolve(),
  currentBlobUrl: null,
  imageList: [],
  currentIndex: -1
};
var elements = {
  app: null,
  headerBar: null,
  viewer: null,
  imageContainer: null,
  currentImage: null,
  loadingOverlay: null,
  loadingSpinner: null,
  loadingLabel: null,
  loadingPrompt: null,
  navIndicator: null,
  navDots: null,
  statusBar: null,
  promptDisplay: null,
  promptInput: null,
  aspectRatioRadios: null,
  aspectRatioControls: null,
  resolutionControls: null,
  dimensionDisplay: null,
  resolutionDecrease: null,
  resolutionIncrease: null,
  validationError: null,
  fontSizeRadios: null,
  imagePathDisplay: null,
  pathText: null,
  copyPathBtn: null,
  controls: null,
  prevButton: null,
  nextButton: null,
  acceptButton: null,
  deleteButton: null,
  abortButton: null,
  pauseButton: null,
  pauseIcon: null,
  pauseLabel: null,
  themeToggle: null,
  magnifierLens: null
};
var magnifierActive = false;
var MAGNIFIER_SIZE = 200;
var MAGNIFICATION = 3;
var imageReadyQueue = Promise.resolve();
var pendingDisplayRequest = null;
var recoveryAttempted = false;
var initPromise = null;
var messageListenerInitialized = false;
var buttonListenersInitialized = false;
var keyboardListenersInitialized = false;
function cacheElements() {
  elements.app = document.getElementById("app");
  elements.headerBar = document.querySelector(".header-bar");
  elements.viewer = document.querySelector(".viewer");
  elements.imageContainer = document.querySelector(".image-container");
  elements.currentImage = document.querySelector(".current-image");
  elements.loadingOverlay = document.getElementById("loading-overlay");
  elements.loadingSpinner = document.querySelector(".spinner");
  elements.loadingLabel = document.querySelector(".loading-label");
  elements.loadingPrompt = document.getElementById("loading-prompt");
  elements.navIndicator = document.getElementById("nav-indicator");
  elements.navDots = document.getElementById("nav-dots");
  elements.statusBar = document.querySelector(".status-bar");
  elements.promptDisplay = document.getElementById("prompt-display");
  elements.promptInput = document.getElementById("prompt-input");
  elements.aspectRatioRadios = document.querySelectorAll('input[name="aspect-ratio"]');
  elements.aspectRatioControls = document.querySelector(".aspect-ratio-control");
  elements.resolutionControls = document.querySelector(".resolution-control");
  elements.dimensionDisplay = document.getElementById("dimension-display");
  elements.resolutionDecrease = document.getElementById("resolution-decrease");
  elements.resolutionIncrease = document.getElementById("resolution-increase");
  elements.validationError = document.getElementById("validation-error");
  elements.fontSizeRadios = document.querySelectorAll('input[name="font-size"]');
  elements.imagePathDisplay = document.getElementById("image-path-display");
  elements.pathText = document.getElementById("path-text");
  elements.copyPathBtn = document.getElementById("copy-path-btn");
  elements.controls = document.querySelector(".controls");
  elements.prevButton = document.getElementById("prev-btn");
  elements.nextButton = document.getElementById("next-btn");
  elements.acceptButton = document.getElementById("accept-btn");
  elements.deleteButton = document.getElementById("delete-btn");
  elements.abortButton = document.getElementById("abort-btn");
  elements.pauseButton = document.getElementById("pause-btn");
  elements.pauseIcon = document.getElementById("pause-icon");
  elements.pauseLabel = document.getElementById("pause-label");
  elements.themeToggle = document.getElementById("theme-toggle");
  elements.magnifierLens = document.getElementById("magnifier-lens");
}
function allElementsPresent() {
  return Object.values(elements).every((el) => el !== null);
}
async function init() {
  if (initPromise) {
    return initPromise;
  }
  initPromise = (async () => {
    console.log("Textbrush UI initializing...");
    try {
      initTheme();
      initFontSize();
      cacheElements();
      if (!allElementsPresent()) {
        const missing = Object.entries(elements).filter(([, el]) => el === null).map(([key]) => key);
        console.error("Missing DOM elements:", missing);
        throw new Error(`Missing DOM elements: ${missing.join(", ")}`);
      }
      console.log("DOM elements cached, getting launch args...");
      const launchArgs = await invoke("get_launch_args");
      console.log("Launch args received:", launchArgs);
      state.prompt = launchArgs.prompt || "";
      state.generationPrompt = launchArgs.prompt || "";
      state.aspectRatio = launchArgs.aspect_ratio || "1:1";
      state.outputPath = launchArgs.output_path || null;
      if (elements.promptDisplay) {
        elements.promptDisplay.textContent = `Prompt: ${state.prompt}`;
      }
      state.width = launchArgs.width;
      state.height = launchArgs.height;
      initConfigControls(
        state.prompt,
        state.aspectRatio,
        launchArgs.width,
        launchArgs.height,
        state,
        elements
      );
      setupMessageListener();
      setupButtonListeners();
      setupKeyboardListeners();
      await invoke("init_generation", {
        prompt: state.prompt,
        outputPath: launchArgs.output_path || null,
        seed: launchArgs.seed || null,
        aspectRatio: launchArgs.aspect_ratio || "1:1",
        width: launchArgs.width,
        height: launchArgs.height
      });
      console.log("Application initialized successfully");
    } catch (error) {
      console.error("Initialization failed:", error);
      if (elements.loadingPrompt) {
        elements.loadingPrompt.textContent = `Error: ${error instanceof Error ? error.message : String(error)}`;
      }
    }
  })();
  return initPromise;
}
function setupMessageListener() {
  if (messageListenerInitialized) {
    return;
  }
  messageListenerInitialized = true;
  console.log("Setting up sidecar message listener...");
  listen("sidecar-message", (event) => {
    const msg = event.payload;
    console.log("Received sidecar message:", msg.type, msg);
    handleMessage(msg);
  }).catch((err) => {
    console.error("Failed to setup message listener:", err);
  });
}
function handleMessage(msg) {
  if (!msg || !msg.type) {
    console.warn("Invalid message format:", msg);
    return;
  }
  switch (msg.type) {
    case "state_changed":
      handleStateChanged(msg.payload);
      break;
    case "image_ready":
      imageReadyQueue = imageReadyQueue.then(() => handleImageReady(msg.payload)).catch((err) => {
        console.error("Failed to handle image_ready event:", err);
      });
      break;
    case "image_list":
      void handleImageList(msg.payload);
      break;
    case "accepted":
      void handleAccepted(msg.payload);
      break;
    case "aborted":
      handleAborted();
      break;
    case "delete_ack":
      handleDeleteAck(msg.payload);
      break;
    case "error":
      handleErrorMessage(msg.payload);
      break;
    default: {
      const unknownMsg = msg;
      console.warn("Unknown message type:", unknownMsg.type);
    }
  }
}
function handleStateChanged(payload) {
  state.backendState = payload;
  state.isPaused = payload.state === "paused";
  if (payload.state === "generating" && "prompt" in payload) {
    state.generationPrompt = payload.prompt;
  }
  if (payload.state === "error" && "fatal" in payload && payload.fatal) {
    handleFatalError(payload.message);
    return;
  }
  updateLoadingOverlayForState();
  updatePauseButton();
  if (!recoveryAttempted && payload.state !== "loading" && state.imageList.length === 0) {
    recoveryAttempted = true;
    invoke("get_image_list").catch((err) => {
      console.warn("get_image_list recovery call failed (non-fatal):", err);
    });
  }
  console.log("Backend state changed:", payload.state, payload);
}
function handleFatalError(message) {
  console.error("Fatal error received:", message);
  const buttons = [
    elements.prevButton,
    elements.nextButton,
    elements.acceptButton,
    elements.deleteButton,
    elements.abortButton,
    elements.pauseButton,
    elements.themeToggle,
    elements.resolutionDecrease,
    elements.resolutionIncrease,
    elements.copyPathBtn
  ];
  buttons.forEach((btn) => {
    if (btn) btn.disabled = true;
  });
  if (elements.promptInput) {
    elements.promptInput.disabled = true;
  }
  if (elements.aspectRatioRadios) {
    elements.aspectRatioRadios.forEach((radio) => {
      radio.disabled = true;
    });
  }
  showLoading(true);
  if (elements.loadingSpinner) {
    elements.loadingSpinner.classList.add("hidden");
  }
  if (elements.loadingLabel) {
    elements.loadingLabel.textContent = `Fatal Error: ${message}`;
    elements.loadingLabel.classList.add("error");
  }
  if (elements.loadingPrompt) {
    elements.loadingPrompt.textContent = "Application will close shortly...";
    elements.loadingPrompt.classList.remove("hidden");
  }
  setTimeout(() => {
    void appWindow.close();
  }, 3e3);
}
function handleErrorMessage(payload) {
  if (payload.fatal) {
    handleFatalError(payload.message);
  } else {
    console.warn("Non-fatal backend error:", payload.message);
    if (elements.loadingPrompt) {
      const original = elements.loadingPrompt.textContent;
      elements.loadingPrompt.textContent = `Error: ${payload.message}`;
      elements.loadingPrompt.classList.remove("hidden");
      setTimeout(() => {
        if (elements.loadingPrompt) {
          elements.loadingPrompt.textContent = original;
        }
      }, 3e3);
    }
  }
}
async function handleImageReady(payload) {
  state.currentImage = payload;
  const assetUrl = convertFileSrc(payload.path);
  console.log("Loading image from:", payload.path, "-> asset URL:", assetUrl);
  const metadata = await fetchAndParsePngMetadata(assetUrl);
  console.log("Parsed metadata:", metadata);
  const record = {
    index: payload.index,
    // NEW: Store backend index for deletion
    path: payload.path,
    displayPath: payload.display_path,
    seed: metadata.seed ?? 0,
    blobUrl: assetUrl,
    prompt: metadata.prompt ?? "",
    model: metadata.model ?? "",
    aspectRatio: metadata.aspectRatio ?? state.aspectRatio,
    width: metadata.width ?? 0,
    height: metadata.height ?? 0,
    generatedWidth: metadata.generatedWidth,
    generatedHeight: metadata.generatedHeight
  };
  state.imageList.push(record);
  state.currentIndex = state.imageList.length - 1;
  updateNavDots();
  void displayImageRecord(record);
  showLoading(false);
  enableAcceptButton();
}
async function handleImageList(payload) {
  const entries = payload.images ?? [];
  console.log("Received image_list event with", entries.length, "entries");
  const activeEntries = entries.filter((entry) => !entry.deleted);
  if (activeEntries.length === 0) {
    console.log("image_list: no active images, skipping rebuild");
    return;
  }
  const newImageList = [];
  for (const entry of activeEntries) {
    const assetUrl = convertFileSrc(entry.path);
    let metadata;
    try {
      metadata = await fetchAndParsePngMetadata(assetUrl);
    } catch (err) {
      console.warn("image_list: failed to parse metadata for", entry.path, err);
      metadata = {};
    }
    const record = {
      index: entry.index,
      path: entry.path,
      displayPath: entry.display_path,
      seed: metadata.seed ?? 0,
      blobUrl: assetUrl,
      prompt: metadata.prompt ?? "",
      model: metadata.model ?? "",
      aspectRatio: metadata.aspectRatio ?? state.aspectRatio,
      width: metadata.width ?? 0,
      height: metadata.height ?? 0,
      generatedWidth: metadata.generatedWidth,
      generatedHeight: metadata.generatedHeight
    };
    newImageList.push(record);
  }
  state.imageList = newImageList;
  state.currentIndex = newImageList.length - 1;
  const currentRecord = state.imageList[state.currentIndex];
  if (currentRecord) {
    void displayImageRecord(currentRecord, state.currentIndex);
    showLoading(false);
    enableAcceptButton();
  }
  updateNavDots();
  console.log("image_list: rebuilt imageList with", newImageList.length, "images, currentIndex=", state.currentIndex);
}
async function handleAccepted(payload) {
  const retainedPaths = payload.paths || [];
  visualSuccessFeedback();
  setTimeout(() => {
    void (async () => {
      try {
        if (retainedPaths.length === 0) {
          await invoke("abort_exit");
        } else {
          await invoke("print_paths_and_exit", { paths: retainedPaths });
        }
      } catch (err) {
        console.error("Failed to call exit handler:", err);
        await appWindow.close();
      }
    })();
  }, 500);
}
function handleAborted() {
  setTimeout(() => {
    void (async () => {
      try {
        await invoke("abort_exit");
      } catch (err) {
        console.error("Failed to call abort_exit:", err);
        await appWindow.close();
      }
    })();
  }, 500);
}
function handleDeleteAck(payload) {
  const index = payload.index;
  console.log("Image deleted from backend, index:", index);
  const imageIndex = state.imageList.findIndex((img) => img.index === index);
  if (imageIndex !== -1) {
    state.imageList.splice(imageIndex, 1);
    if (state.imageList.length === 0) {
      state.currentIndex = -1;
    } else if (imageIndex < state.currentIndex) {
      state.currentIndex--;
    } else if (imageIndex === state.currentIndex) {
      if (state.currentIndex >= state.imageList.length) {
        state.currentIndex = state.imageList.length - 1;
      }
    }
    if (state.imageList.length === 0) {
      showLoadingPlaceholder();
    } else {
      const currentRecord = state.imageList[state.currentIndex];
      if (currentRecord) {
        void displayImageRecord(currentRecord);
      }
    }
    updateNavDots();
  }
}
function updateLoadingOverlayForState() {
  if (!state.backendState) {
    return;
  }
  const backendStateValue = state.backendState.state;
  const spinnerVisible = backendStateValue === "loading" || backendStateValue === "generating";
  if (elements.loadingSpinner) {
    if (spinnerVisible) {
      elements.loadingSpinner.classList.remove("hidden");
    } else {
      elements.loadingSpinner.classList.add("hidden");
    }
  }
  if (elements.loadingLabel && !elements.loadingOverlay?.classList.contains("hidden")) {
    let labelText;
    switch (state.backendState.state) {
      case "loading":
        labelText = "loading model";
        break;
      case "idle":
        labelText = "ready";
        break;
      case "generating":
        labelText = "generating";
        break;
      case "paused":
        labelText = "generation paused";
        break;
      case "error":
        labelText = state.backendState.message || "error";
        break;
      default:
        labelText = backendStateValue;
    }
    elements.loadingLabel.textContent = labelText;
  }
  if (elements.loadingPrompt) {
    if (state.backendState.state === "generating") {
      elements.loadingPrompt.textContent = state.backendState.prompt;
      elements.loadingPrompt.classList.remove("hidden");
    } else {
      elements.loadingPrompt.classList.add("hidden");
    }
  }
}
function updatePauseButton() {
  if (!elements.pauseIcon || !elements.pauseLabel) {
    return;
  }
  if (state.isPaused) {
    elements.pauseIcon.textContent = "\u25B6";
    elements.pauseLabel.textContent = "Resume";
    if (elements.pauseButton) {
      elements.pauseButton.classList.add("paused");
    }
  } else {
    elements.pauseIcon.textContent = "\u23F8";
    elements.pauseLabel.textContent = "Pause";
    if (elements.pauseButton) {
      elements.pauseButton.classList.remove("paused");
    }
  }
}
async function displayImageRecord(record, listIdx = null) {
  console.log("displayImageRecord called, seed:", record.seed, "path:", record.path);
  if (state.isTransitioning) {
    pendingDisplayRequest = { record, listIdx };
    console.log("Queued display request - transition in progress");
    return;
  }
  state.isTransitioning = true;
  try {
    const fadeOutDuration = 100;
    const fadeInDuration = 200;
    if (elements.currentImage && elements.currentImage.src) {
      elements.currentImage.classList.add("image-exit");
      await new Promise((resolve) => setTimeout(resolve, fadeOutDuration));
    }
    state.currentBlobUrl = record.blobUrl;
    if (elements.currentImage && record.blobUrl) {
      console.log("Setting image src to asset URL:", record.blobUrl);
      elements.currentImage.src = record.blobUrl;
    } else {
      console.warn("Cannot display image - missing element or blobUrl:", {
        hasElement: !!elements.currentImage,
        hasBlobUrl: !!record.blobUrl
      });
    }
    if (elements.currentImage) {
      elements.currentImage.classList.remove("image-exit");
      elements.currentImage.classList.add("image-enter");
      await new Promise((resolve) => setTimeout(resolve, fadeInDuration));
      elements.currentImage.classList.remove("image-enter");
    }
    const idx = listIdx !== null ? listIdx : state.currentIndex;
    updateMetadataPanelFromRecord(record, idx);
    updateNavDots();
  } catch (error) {
    console.error("Error displaying image:", error);
  } finally {
    state.isTransitioning = false;
    if (pendingDisplayRequest) {
      const nextRequest = pendingDisplayRequest;
      pendingDisplayRequest = null;
      void displayImageRecord(nextRequest.record, nextRequest.listIdx);
    }
  }
}
function updateMetadataPanelFromRecord(record, _listIdx = null) {
  const metadataPrompt = document.getElementById("metadata-prompt");
  const metadataModel = document.getElementById("metadata-model");
  const metadataSeed = document.getElementById("metadata-seed");
  const metadataGeneratedSize = document.getElementById("metadata-generated-size");
  const metadataFinalSize = document.getElementById("metadata-final-size");
  if (!metadataPrompt || !metadataModel || !metadataSeed || !metadataGeneratedSize || !metadataFinalSize) {
    return;
  }
  if (record) {
    metadataPrompt.textContent = record.prompt || "\u2014";
    metadataModel.textContent = record.model || "\u2014";
    metadataSeed.textContent = record.seed !== void 0 ? String(record.seed) : "\u2014";
    if (record.generatedWidth !== void 0 && record.generatedHeight !== void 0) {
      metadataGeneratedSize.textContent = `${record.generatedWidth}\xD7${record.generatedHeight}`;
    } else {
      metadataGeneratedSize.textContent = "\u2014";
    }
    if (record.width && record.height) {
      metadataFinalSize.textContent = `${record.width}\xD7${record.height}`;
    } else {
      metadataFinalSize.textContent = "\u2014";
    }
    const displayPathStr = record.displayPath || "\u2014";
    const absolutePath = record.path || "";
    if (elements.pathText) {
      elements.pathText.textContent = displayPathStr;
    }
    if (elements.copyPathBtn) {
      elements.copyPathBtn.style.display = absolutePath ? "inline-flex" : "none";
    }
  } else {
    metadataPrompt.textContent = "\u2014";
    metadataModel.textContent = "\u2014";
    metadataSeed.textContent = "\u2014";
    metadataGeneratedSize.textContent = "\u2014";
    metadataFinalSize.textContent = "\u2014";
    if (elements.pathText) {
      elements.pathText.textContent = "\u2014";
    }
    if (elements.copyPathBtn) {
      elements.copyPathBtn.style.display = "none";
    }
  }
}
function clearMetadataPanel() {
  updateMetadataPanelFromRecord(null, null);
}
var MAX_VISIBLE_DOTS = 25;
function updateNavDots() {
  if (!elements.navDots) {
    return;
  }
  const imageCount = state.imageList.length;
  const totalPositions = imageCount + 1;
  const isViewingSpinner = elements.loadingOverlay && !elements.loadingOverlay.classList.contains("hidden");
  let activePosition;
  if (imageCount === 0 || isViewingSpinner) {
    activePosition = imageCount;
  } else {
    activePosition = state.currentIndex;
  }
  elements.navDots.innerHTML = "";
  if (totalPositions <= MAX_VISIBLE_DOTS) {
    for (let i = 0; i < totalPositions; i++) {
      const isSpinner = i === imageCount;
      const dot = createNavDot(i, i === activePosition, isSpinner);
      elements.navDots.appendChild(dot);
    }
    announceNavigation(activePosition, totalPositions);
    return;
  }
  const edgeDots = 3;
  const activeRadius = 2;
  const indicesToShow = /* @__PURE__ */ new Set();
  for (let i = 0; i < Math.min(edgeDots, imageCount); i++) {
    indicesToShow.add(i);
  }
  if (activePosition < imageCount) {
    const activeStart = Math.max(0, activePosition - activeRadius);
    const activeEnd = Math.min(imageCount - 1, activePosition + activeRadius);
    for (let i = activeStart; i <= activeEnd; i++) {
      indicesToShow.add(i);
    }
  }
  const lastEdgeStart = Math.max(0, imageCount - edgeDots);
  for (let i = lastEdgeStart; i < imageCount; i++) {
    indicesToShow.add(i);
  }
  const sortedIndices = Array.from(indicesToShow).sort((a, b) => a - b);
  const dotsToShow = [];
  for (let i = 0; i < sortedIndices.length; i++) {
    const idx = sortedIndices[i];
    const prevIdx = sortedIndices[i - 1];
    if (i > 0 && prevIdx !== void 0 && idx > prevIdx + 1) {
      dotsToShow.push("gap");
    }
    dotsToShow.push(idx);
  }
  const lastImageIdx = sortedIndices[sortedIndices.length - 1];
  if (lastImageIdx !== void 0 && lastImageIdx < imageCount - 1) {
    dotsToShow.push("gap");
  }
  dotsToShow.push(imageCount);
  for (const item of dotsToShow) {
    if (item === "gap") {
      elements.navDots.appendChild(createGapIndicator());
    } else {
      const isSpinner = item === imageCount;
      const dot = createNavDot(item, item === activePosition, isSpinner);
      elements.navDots.appendChild(dot);
    }
  }
  announceNavigation(activePosition, totalPositions);
}
function createGapIndicator() {
  const gap = document.createElement("span");
  gap.className = "nav-gap";
  gap.setAttribute("aria-hidden", "true");
  for (let i = 0; i < 3; i++) {
    const dot = document.createElement("span");
    dot.className = "nav-gap-dot";
    gap.appendChild(dot);
  }
  return gap;
}
function announceNavigation(activePosition, totalPositions) {
  const navIndicator = elements.navIndicator;
  if (!navIndicator) return;
  const imageCount = totalPositions - 1;
  let announcement;
  if (activePosition === imageCount) {
    if (imageCount === 0) {
      announcement = "Waiting for first image";
    } else {
      announcement = `Waiting for next image, ${imageCount} image${imageCount !== 1 ? "s" : ""} available`;
    }
  } else {
    announcement = `Image ${activePosition + 1} of ${imageCount}`;
  }
  navIndicator.setAttribute("aria-label", announcement);
}
function createNavDot(index, isActive, isSpinner) {
  const dot = document.createElement("span");
  dot.className = "nav-dot";
  if (isActive) {
    dot.classList.add("active");
  }
  if (isSpinner) {
    dot.classList.add("spinner-dot");
  }
  dot.setAttribute("role", "button");
  if (isSpinner) {
    dot.setAttribute("aria-label", "Go to loading screen");
  } else {
    dot.setAttribute("aria-label", `Go to image ${index + 1}`);
  }
  dot.setAttribute("tabindex", "0");
  dot.addEventListener("click", () => {
    navigateToIndex(index, isSpinner);
  });
  dot.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      navigateToIndex(index, isSpinner);
    }
  });
  return dot;
}
function navigateToIndex(index, isSpinner = false) {
  if (state.isTransitioning) {
    return;
  }
  const isViewingSpinner = elements.loadingOverlay && !elements.loadingOverlay.classList.contains("hidden");
  if (isSpinner) {
    if (isViewingSpinner) {
      return;
    }
    showLoadingPlaceholder();
    return;
  }
  if (index < 0 || index >= state.imageList.length) {
    return;
  }
  if (index === state.currentIndex && !isViewingSpinner) {
    return;
  }
  state.currentIndex = index;
  const entry = state.imageList[index];
  if (entry) {
    showLoading(false);
    void displayImageRecord(entry, index);
  }
}
function showLoading(show) {
  if (!elements.loadingOverlay) {
    return;
  }
  if (show) {
    elements.loadingOverlay.classList.remove("hidden");
    if (elements.currentImage) {
      elements.currentImage.classList.add("hidden");
    }
  } else {
    elements.loadingOverlay.classList.add("hidden");
    if (elements.currentImage) {
      elements.currentImage.classList.remove("hidden");
    }
  }
}
function isMagnifierActive() {
  return magnifierActive;
}
function toggleMagnifier() {
  if (!elements.magnifierLens || !elements.currentImage) {
    return;
  }
  if (!elements.currentImage.src || elements.currentImage.classList.contains("hidden")) {
    return;
  }
  magnifierActive = !magnifierActive;
  if (!magnifierActive) {
    elements.magnifierLens.classList.add("hidden");
  }
}
function updateMagnifierPosition(e) {
  if (!magnifierActive || !elements.magnifierLens || !elements.currentImage || !elements.imageContainer) {
    return;
  }
  const imgRect = elements.currentImage.getBoundingClientRect();
  const containerRect = elements.imageContainer.getBoundingClientRect();
  const mouseX = e.clientX - imgRect.left;
  const mouseY = e.clientY - imgRect.top;
  if (mouseX < 0 || mouseX > imgRect.width || mouseY < 0 || mouseY > imgRect.height) {
    elements.magnifierLens.classList.add("hidden");
    return;
  }
  elements.magnifierLens.classList.remove("hidden");
  const lensRadius = MAGNIFIER_SIZE / 2;
  const lensX = e.clientX - containerRect.left - lensRadius;
  const lensY = e.clientY - containerRect.top - lensRadius;
  elements.magnifierLens.style.left = `${lensX}px`;
  elements.magnifierLens.style.top = `${lensY}px`;
  elements.magnifierLens.style.backgroundImage = `url(${elements.currentImage.src})`;
  const bgWidth = imgRect.width * MAGNIFICATION;
  const bgHeight = imgRect.height * MAGNIFICATION;
  const bgX = mouseX / imgRect.width * bgWidth - lensRadius;
  const bgY = mouseY / imgRect.height * bgHeight - lensRadius;
  elements.magnifierLens.style.backgroundSize = `${bgWidth}px ${bgHeight}px`;
  elements.magnifierLens.style.backgroundPosition = `-${bgX}px -${bgY}px`;
}
function hideMagnifier() {
  if (!elements.magnifierLens) {
    return;
  }
  elements.magnifierLens.classList.add("hidden");
}
function deactivateMagnifier() {
  magnifierActive = false;
  hideMagnifier();
}
function visualSuccessFeedback() {
  if (elements.imageContainer) {
    elements.imageContainer.style.boxShadow = "0 0 20px rgba(34, 197, 94, 0.5)";
  }
}
function prev() {
  if (state.isTransitioning) {
    return;
  }
  const isViewingSpinner = elements.loadingOverlay && !elements.loadingOverlay.classList.contains("hidden");
  if (isViewingSpinner && state.imageList.length > 0) {
    state.currentIndex = state.imageList.length - 1;
    const entry = state.imageList[state.currentIndex];
    showLoading(false);
    if (entry) {
      void displayImageRecord(entry, state.currentIndex);
    }
    updateNavDots();
    return;
  }
  const navigated = navigateToPrev(state, (entry) => {
    void displayImageRecord(entry, state.currentIndex);
  });
  if (!navigated) {
    console.log("At beginning of list, cannot go back");
  }
}
function next() {
  if (state.isTransitioning) {
    return;
  }
  const isAlreadyGenerating = state.backendState !== null && (state.backendState.state === "generating" || state.backendState.state === "loading");
  if (isAlreadyGenerating && state.currentIndex >= state.imageList.length - 1) {
    console.log("Already waiting for next image");
    return;
  }
  const requestNextImage = () => {
    showLoadingPlaceholder();
    state.actionQueue = state.actionQueue.then(async () => {
      await invoke("skip_image");
    }).catch((err) => {
      console.error("Next failed:", err);
      if (state.imageList.length > 0) {
        const entry = state.imageList[state.currentIndex];
        showLoading(false);
        if (entry) {
          void displayImageRecord(entry, state.currentIndex);
        }
      }
    });
  };
  navigateToNext(
    state,
    (entry) => {
      void displayImageRecord(entry, state.currentIndex);
    },
    requestNextImage
  );
}
function showLoadingPlaceholder() {
  if (elements.currentImage) {
    elements.currentImage.classList.add("hidden");
  }
  if (elements.loadingOverlay) {
    elements.loadingOverlay.classList.remove("hidden");
  }
  if (elements.loadingLabel) {
    elements.loadingLabel.textContent = "waiting for image";
  }
  if (elements.loadingPrompt) {
    elements.loadingPrompt.textContent = state.generationPrompt || state.prompt;
  }
  clearMetadataPanel();
  updateNavDots();
}
function accept() {
  if (elements.acceptButton && !state.isTransitioning) {
    elements.acceptButton.disabled = true;
    invoke("accept_image").catch((err) => {
      console.error("Accept failed:", err);
      if (elements.acceptButton) {
        elements.acceptButton.disabled = false;
      }
    });
  }
}
function abort() {
  if (state.isTransitioning) {
    return;
  }
  invoke("abort_generation").catch((err) => {
    console.error("Abort failed:", err);
  });
}
function togglePause() {
  invoke("pause_generation").catch((err) => {
    console.error("Pause toggle failed:", err);
  });
}
function deleteCurrentImage() {
  if (state.isTransitioning) {
    return;
  }
  if (state.currentIndex < 0 || state.currentIndex >= state.imageList.length) {
    return;
  }
  const imageToDelete = state.imageList[state.currentIndex];
  if (!imageToDelete) {
    return;
  }
  state.actionQueue = state.actionQueue.then(async () => {
    try {
      await invoke("delete_image", { index: imageToDelete.index });
      console.log("Delete command sent, waiting for backend acknowledgment");
    } catch (err) {
      console.error("Delete failed:", err);
      if (elements.loadingPrompt) {
        elements.loadingPrompt.textContent = `Delete failed: ${err instanceof Error ? err.message : String(err)}`;
        setTimeout(() => {
          if (elements.loadingPrompt && state.backendState !== null && state.backendState.state === "generating") {
            elements.loadingPrompt.textContent = state.backendState.prompt;
          }
        }, 2e3);
      }
    }
  }).catch((err) => {
    console.error("Delete action queue error:", err);
  });
}
function enableAcceptButton() {
  if (elements.acceptButton) {
    elements.acceptButton.disabled = false;
  }
}
function setupButtonListeners() {
  if (buttonListenersInitialized) {
    return;
  }
  buttonListenersInitialized = true;
  if (elements.prevButton) {
    elements.prevButton.addEventListener("click", prev);
  }
  if (elements.nextButton) {
    elements.nextButton.addEventListener("click", next);
  }
  if (elements.acceptButton) {
    elements.acceptButton.addEventListener("click", accept);
  }
  if (elements.deleteButton) {
    elements.deleteButton.addEventListener("click", deleteCurrentImage);
  }
  if (elements.abortButton) {
    elements.abortButton.addEventListener("click", abort);
  }
  if (elements.pauseButton) {
    elements.pauseButton.addEventListener("click", togglePause);
  }
  if (elements.themeToggle) {
    elements.themeToggle.addEventListener("click", () => {
      toggleTheme();
    });
  }
  if (elements.currentImage) {
    elements.currentImage.addEventListener("click", toggleMagnifier);
  }
  if (elements.imageContainer) {
    elements.imageContainer.addEventListener("mousemove", updateMagnifierPosition);
    elements.imageContainer.addEventListener("mouseleave", hideMagnifier);
  }
  if (elements.copyPathBtn) {
    elements.copyPathBtn.addEventListener("click", () => {
      const idx = state.currentIndex;
      const entry = idx >= 0 && idx < state.imageList.length ? state.imageList[idx] : null;
      const path = entry?.path;
      if (path) {
        navigator.clipboard.writeText(path).then(() => {
          const original = elements.pathText?.textContent;
          if (elements.pathText) {
            elements.pathText.textContent = "Copied!";
            setTimeout(() => {
              if (elements.pathText && original) {
                elements.pathText.textContent = original;
              }
            }, 1e3);
          }
        }).catch((err) => {
          console.error("Failed to copy path:", err);
        });
      }
    });
  }
  if (elements.fontSizeRadios) {
    const currentSize = getCurrentFontSize();
    elements.fontSizeRadios.forEach((radio) => {
      radio.checked = radio.value === currentSize;
      radio.addEventListener("change", () => {
        if (radio.checked) {
          setFontSize(radio.value);
        }
      });
    });
  }
}
function setupKeyboardListeners() {
  if (keyboardListenersInitialized) {
    return;
  }
  keyboardListenersInitialized = true;
  document.addEventListener("keydown", (e) => {
    const eventTarget = e.target;
    const target = eventTarget instanceof HTMLElement ? eventTarget : null;
    const isTextInput = target?.tagName === "INPUT" && target.type === "text";
    const isInteractiveControl = target?.tagName === "BUTTON" || target?.tagName === "SELECT" || target?.tagName === "TEXTAREA" || target?.tagName === "INPUT" && !isTextInput || target?.getAttribute("role") === "button" || target?.isContentEditable === true;
    if (isTextInput || isInteractiveControl) {
      return;
    }
    if (e.repeat) {
      return;
    }
    const ctrlOrCmd = e.ctrlKey || e.metaKey;
    flashButtonForKey(e.key, ctrlOrCmd);
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      prev();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      next();
    } else if (e.key === "Enter") {
      e.preventDefault();
      accept();
    } else if (e.key === "Escape") {
      e.preventDefault();
      if (isMagnifierActive()) {
        deactivateMagnifier();
      } else {
        abort();
      }
    } else if ((e.key === "Delete" || e.key === "Backspace") && ctrlOrCmd) {
      e.preventDefault();
      deleteCurrentImage();
    } else if (e.key === " ") {
      e.preventDefault();
      togglePause();
    }
  });
}
if (typeof window !== "undefined") {
  window.textbrushApp = {
    state,
    elements,
    init,
    handleMessage,
    handleImageList,
    displayImageRecord,
    updateNavDots,
    navigateToIndex,
    showLoading,
    showLoadingPlaceholder,
    prev,
    next,
    accept,
    abort,
    togglePause,
    updatePauseButton,
    deleteCurrentImage,
    cacheElements,
    allElementsPresent,
    isMagnifierActive,
    toggleMagnifier,
    deactivateMagnifier
  };
}
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => void init());
} else {
  void init();
}
