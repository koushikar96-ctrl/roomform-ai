const form = document.querySelector("#redesign-form");
const imageInput = document.querySelector("#image-input");
const uploadBox = document.querySelector("#upload-box");
const uploadPrompt = document.querySelector("#upload-prompt");
const previewImage = document.querySelector("#preview-image");
const submitButton = document.querySelector("#submit-button");
const formStatus = document.querySelector("#form-status");
const resultPanel = document.querySelector("#result-panel");
const resultImage = document.querySelector("#result-image");
const downloadLink = document.querySelector("#download-link");

let previewUrl;

function setStatus(message, isError = false) {
  formStatus.textContent = message;
  formStatus.classList.toggle("error", isError);
  formStatus.hidden = !message;
}

function clearPreview() {
  previewImage.removeAttribute("src");
  previewImage.hidden = true;
  uploadPrompt.hidden = false;
  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
    previewUrl = undefined;
  }
}

function showSelectedImage(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    setStatus("Choose a valid image file.", true);
    imageInput.value = "";
    clearPreview();
    return;
  }
  if (file.size > 12 * 1024 * 1024) {
    setStatus("Choose an image smaller than 12 MB.", true);
    imageInput.value = "";
    clearPreview();
    return;
  }
  setStatus("");
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  previewImage.src = previewUrl;
  previewImage.hidden = false;
  uploadPrompt.hidden = true;
}

imageInput.addEventListener("change", () => showSelectedImage(imageInput.files[0]));

for (const eventName of ["dragenter", "dragover"]) {
  uploadBox.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadBox.classList.add("dragging");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  uploadBox.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadBox.classList.remove("dragging");
  });
}
uploadBox.addEventListener("drop", (event) => {
  const [file] = event.dataTransfer.files;
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  imageInput.files = transfer.files;
  showSelectedImage(file);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!imageInput.files.length) {
    imageInput.focus();
    setStatus("Choose a room photo before redesigning.", true);
    return;
  }

  submitButton.disabled = true;
  submitButton.querySelector("span:first-child").textContent = "Redesigning…";
  setStatus("Your room is being redesigned. This can take a few minutes.");
  resultPanel.hidden = true;
  try {
    const response = await fetch("/api/redesign", {
      method: "POST",
      body: new FormData(form),
    });
    const payload = await response.json().catch(() => ({}));
    if (response.status === 404) {
      throw new Error("This page is connected to an older server. Restart the app from this project folder, then refresh the page.");
    }
    if (!response.ok) throw new Error(payload.detail || "Redesign failed. Check the server output.");

    resultImage.src = payload.image_url;
    downloadLink.href = payload.image_url;
    downloadLink.download = payload.download_name;
    resultPanel.hidden = false;
    setStatus("");
    resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setStatus(error.message || "Could not connect to the redesign service.", true);
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector("span:first-child").textContent = "Upload & redesign";
  }
});

document.querySelector("#start-over").addEventListener("click", () => {
  form.reset();
  imageInput.value = "";
  clearPreview();
  resultImage.removeAttribute("src");
  resultPanel.hidden = true;
  setStatus("");
});
