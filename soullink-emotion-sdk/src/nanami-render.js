import {
  getVADPreset,
  motionStylePresets,
  SoullinkRuntime
} from "@soullink-emotion/engine";
import {
  createScriptTagCubismLoader,
  Live2DRenderer
} from "@soullink-emotion/live2d-pixi";

// 模型配置：换模型时改这里（或由 Python 通过 URL 参数覆盖 model）
const params = new URLSearchParams(window.location.search);
const modelId = params.get("model") || "LSS";
const MODEL_URL = `/l2d/${modelId}/${modelId}.model3.json`;
const PROFILE_URL = `/l2d/${modelId}/soullink.profile.json`;
const CORE_URL = "/live2dcubismcore.min.js";

let runtime = null;
let renderer = null;
let startTime = performance.now() / 1000;
let lastFrameTime = startTime;
let voiceTimer = null;

const stage = document.getElementById("stage");

function nowSeconds() {
  return performance.now() / 1000 - startTime;
}

function estimateSpeechMs(text) {
  return Math.max(1500, text.length * 220 + 600);
}

function animate(timestamp) {
  const now = timestamp / 1000 - startTime;
  const absoluteNow = timestamp / 1000;
  const delta = Math.min(0.05, Math.max(1 / 240, absoluteNow - lastFrameTime));
  lastFrameTime = absoluteNow;

  const snapshot = runtime.update(now, delta);
  renderer.setParameters(snapshot.live2dParams);
  renderer.applyNativeAnimation(snapshot.nativeAnimation);

  requestAnimationFrame(animate);
}

function nanamiSpeak(text, emotion, durationMs) {
  const now = nowSeconds();
  const emotionName = emotion || "neutral";
  const vad = getVADPreset(emotionName);
  runtime.triggerIntent(
    {
      emotion: emotionName,
      naturalEmotion: emotionName,
      naturalVAD: vad,
      intensity: 0.75,
      contextTags: ["speech"],
      sourceMessage: text || ""
    },
    now,
    { vadTarget: vad }
  );
  runtime.applyVADTarget(vad, 1);
  runtime.setVoicePlaybackActive(true);

  if (voiceTimer) clearTimeout(voiceTimer);
  const ms = durationMs || estimateSpeechMs(text || "");
  voiceTimer = setTimeout(() => {
    runtime.setVoicePlaybackActive(false);
  }, ms);
}

function nanamiSetEmotion(emotion, variant, intensity) {
  const now = nowSeconds();
  const emotionName = emotion || "neutral";
  const vad = getVADPreset(emotionName, variant);
  runtime.triggerIntent(
    {
      emotion: emotionName,
      variant,
      naturalEmotion: emotionName,
      naturalVAD: vad,
      intensity: intensity || 0.7,
      contextTags: ["external"]
    },
    now,
    { vadTarget: vad }
  );
  runtime.applyVADTarget(vad, 1);
}

function nanamiStopVoice() {
  runtime.setVoicePlaybackActive(false);
  if (voiceTimer) clearTimeout(voiceTimer);
}

window.nanamiSpeak = nanamiSpeak;
window.nanamiSetEmotion = nanamiSetEmotion;
window.nanamiStopVoice = nanamiStopVoice;

// QWebChannel：JS → Python（点击角色等）
if (window.qt && qt.webChannelTransport) {
  new QWebChannel(qt.webChannelTransport, (channel) => {
    window.bridge = channel.objects.bridge;
  });
}
stage.addEventListener("click", () => {
  if (window.bridge) window.bridge.notifyCharacterClicked();
});

async function init() {
  try {
    const resp = await fetch(PROFILE_URL, { cache: "no-store" });
    if (!resp.ok) throw new Error(`profile HTTP ${resp.status}`);
    const profile = await resp.json();

    runtime = new SoullinkRuntime({
      profile,
      motionStyle: { ...motionStylePresets.natural }
    });
    renderer = new Live2DRenderer(stage, {
      cubismLoader: createScriptTagCubismLoader(CORE_URL)
    });

    const parameters = await renderer.load(MODEL_URL);
    runtime.setPrivateVADParameters(parameters);
    requestAnimationFrame(animate);
    window.nanamiReady = true;
  } catch (error) {
    console.error("[Nanami] 渲染层初始化失败", error);
    window.nanamiError = String(error);
  }
}

init();
