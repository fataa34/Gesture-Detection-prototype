const video = document.getElementById("video");
const canvas = document.getElementById("snapshotCanvas");
const ctx = canvas.getContext("2d");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const saveBtn = document.getElementById("saveBtn");
const statusMessage = document.getElementById("statusMessage");
const cameraPlaceholder = document.getElementById("cameraPlaceholder");
const cameraBadge = document.getElementById("cameraBadge");
const videoOverlay = document.getElementById("videoOverlay");
const overlayLabel = document.getElementById("overlayLabel");

let stream = null;
let running = false;
let timer = null;
let busy = false;
let latestFrame = null;
let latestResult = null;
let lastRequestAt = 0;

// Interval 300 ms (~3.3 request/detik) untuk mengurangi beban server.
const DETECT_INTERVAL_MS = 300;

function setStatus(message) {
  statusMessage.textContent = message;
}

function setCameraState(active) {
  cameraBadge.textContent = active ? "Kamera aktif" : "Kamera mati";
  cameraBadge.className = active ? "badge badge-green" : "badge badge-muted";
  startBtn.disabled = active;
  stopBtn.disabled = !active;
  cameraPlaceholder.hidden = active;
  videoOverlay.hidden = !active;
}

function updateResult(result) {
  latestResult = result;
  document.getElementById("gestureName").textContent = result.name;
  document.getElementById("recognitionStatus").textContent =
    result.recognized ? "Dikenali" : "Belum dikenali";
  document.getElementById("fingerPattern").textContent =
    result.pattern ? result.pattern.join(" - ") : "—";
  document.getElementById("confidence").textContent =
    result.score == null ? "—" : `${(result.score * 100).toFixed(1)}%`;

  const sourceBadge = document.getElementById("sourceBadge");
  const dot = document.getElementById("resultDot");
  if (result.recognized && result.source === "model") {
    sourceBadge.textContent = "Isyarat bawaan model";
    sourceBadge.className = "badge badge-green";
    dot.textContent = "✓";
    dot.style.background = "#e1f5e9";
    dot.style.color = "#167347";
    overlayLabel.textContent = result.name;
  } else if (result.recognized && result.source === "custom") {
    sourceBadge.textContent = "Isyarat custom";
    sourceBadge.className = "badge badge-orange";
    dot.textContent = "✋";
    dot.style.background = "#fff0df";
    dot.style.color = "#a95208";
    overlayLabel.textContent = result.name;
  } else {
    sourceBadge.textContent = "Belum dikenali";
    sourceBadge.className = "badge badge-red";
    dot.textContent = "?";
    dot.style.background = "#fde8e9";
    dot.style.color = "#b02a37";
    overlayLabel.textContent = "Menunggu isyarat...";
  }

  saveBtn.disabled = !result.recognized || !latestFrame;
}

async function detectLoop() {
  if (!running || busy || !video.videoWidth) return;
  const now = Date.now();
  if (now - lastRequestAt < DETECT_INTERVAL_MS) return;

  busy = true;
  lastRequestAt = now;
  try {
    // Kirim frame ukuran sedang agar lebih ringan.
    const maxWidth = 640;
    const scale = Math.min(1, maxWidth / video.videoWidth);
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    latestFrame = canvas.toDataURL("image/jpeg", 0.78);

    const response = await fetch("/api/detect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: latestFrame })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Deteksi gagal.");
    updateResult(data);
  } catch (error) {
    setStatus(error.message || "Tidak dapat menghubungi server.");
  } finally {
    busy = false;
  }
}

async function startCamera() {
  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Browser tidak mendukung kamera. Gunakan HTTPS atau localhost.");
    }
    stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } }
    });
    video.srcObject = stream;
    await video.play();
    running = true;
    setCameraState(true);
    setStatus("Kamera aktif. Tunjukkan satu tangan ke kamera.");
    timer = window.setInterval(detectLoop, 100);
  } catch (error) {
    setStatus(`Kamera tidak dapat dibuka: ${error.message}`);
    stopCamera();
  }
}

function stopCamera() {
  running = false;
  if (timer) window.clearInterval(timer);
  timer = null;
  if (stream) stream.getTracks().forEach(track => track.stop());
  stream = null;
  video.srcObject = null;
  latestFrame = null;
  latestResult = null;
  saveBtn.disabled = true;
  setCameraState(false);
  document.getElementById("gestureName").textContent = "Belum ada hasil";
  document.getElementById("recognitionStatus").textContent = "Menunggu";
  document.getElementById("fingerPattern").textContent = "—";
  document.getElementById("confidence").textContent = "—";
  document.getElementById("sourceBadge").textContent = "Menunggu kamera";
  document.getElementById("sourceBadge").className = "badge badge-muted";
  document.getElementById("resultDot").textContent = "?";
  document.getElementById("resultDot").style.background = "#edf1f7";
  document.getElementById("resultDot").style.color = "#53627a";
  setStatus("Kamera dihentikan.");
}

async function savePhoto() {
  if (!latestResult || !latestResult.recognized || !latestFrame) return;
  saveBtn.disabled = true;
  setStatus("Menyimpan foto...");
  try {
    const response = await fetch("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image: latestFrame,
        label: latestResult.name,
        source: latestResult.source,
        recognized: latestResult.recognized
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Gagal menyimpan foto.");
    setStatus(data.message);
    await loadGallery();
  } catch (error) {
    setStatus(error.message);
  } finally {
    saveBtn.disabled = !(latestResult && latestResult.recognized && latestFrame);
  }
}

async function loadGallery() {
  const gallery = document.getElementById("gallery");
  try {
    const response = await fetch("/api/gallery");
    if (!response.ok) throw new Error("Galeri tidak dapat dimuat.");
    const photos = await response.json();
    gallery.replaceChildren();
    if (!photos.length) {
      const empty = document.createElement("p");
      empty.className = "empty-gallery";
      empty.textContent = "Belum ada foto. Kenali isyarat lalu tekan Simpan Foto.";
      gallery.appendChild(empty);
      return;
    }
    photos.forEach(photo => {
      const card = document.createElement("article");
      card.className = "gallery-item";
      const img = document.createElement("img");
      img.src = photo.url;
      img.alt = `Foto ${photo.filename}`;
      img.loading = "lazy";
      const caption = document.createElement("p");
      caption.textContent = `${photo.filename} · ${photo.created}`;
      card.append(img, caption);
      gallery.appendChild(card);
    });
  } catch (error) {
    gallery.textContent = error.message;
  }
}

startBtn.addEventListener("click", startCamera);
stopBtn.addEventListener("click", stopCamera);
saveBtn.addEventListener("click", savePhoto);
document.getElementById("refreshGalleryBtn").addEventListener("click", loadGallery);
window.addEventListener("beforeunload", () => {
  if (stream) stream.getTracks().forEach(track => track.stop());
});

setCameraState(false);
loadGallery();
