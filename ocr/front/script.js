document.addEventListener("DOMContentLoaded", () => {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const selectFileBtn = document.getElementById("selectFileBtn");

  const resultJson = document.getElementById("resultJson");

  // Handle file selection button click
  selectFileBtn.addEventListener("click", () => {
    fileInput.click();
  });

  // Handle file input change for multiple files
  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFiles(e.target.files);
    }
  });

  // Handle drag and drop for multiple files
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");

    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  });

  // Handle multiple files
  function handleFiles(files) {
    Array.from(files).forEach((file) => {
      uploadFile(file);
    });
  }

  // Display each file's status
  function addFileStatus(file, message) {
    const fileStatus = document.createElement("div");
    fileStatus.classList.add("file-status");
    fileStatus.dataset.fileName = file.name;
    fileStatus.innerHTML = `<strong>${file.name}</strong>: <span>${message}</span>`;
    fileStatus.style.padding = "10px";
    fileStatus.style.marginBottom = "5px";
    fileStatus.style.backgroundColor = "#f0f0f0";
    fileStatus.style.borderRadius = "4px";
    resultJson.appendChild(fileStatus);
  }

  // Update status of a specific file
  function updateFileStatus(file, message) {
    const fileStatus = document.querySelector(
      `.file-status[data-file-name="${file.name}"]`,
    );
    if (fileStatus) {
      fileStatus.querySelector("span").textContent = message;
    }
  }

  async function uploadFile(file) {
    if (file.type !== "application/pdf") {
      alert("Please upload a PDF file");
      return;
    }

    addFileStatus(file, "Uploading...");

    const formData = new FormData();
    formData.append("file", file);

    // Get selected tasks
    const selectedTasks = getSelectedTasks();
    if (selectedTasks.length > 0) {
      formData.append("tasks", selectedTasks.join(","));
    }

    try {
      const response = await fetch("/api/upload-pdf/", {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        const errorData = await response.json();
        updateFileStatus(
          file,
          `Upload failed: ${errorData.detail || "Unknown error"}`,
        );
        return;
      }

      const data = await response.json();

      if (
        (response.status === 202 || response.status === 200) &&
        data.file_id
      ) {
        updateFileStatus(file, "Processing...");
        pollStatus(file, data.file_id);
      } else {
        updateFileStatus(file, "Upload failed: Invalid response");
      }
    } catch (error) {
      console.error("Upload error:", error);
      updateFileStatus(file, `Network error: ${error.message}`);
    }
  }

  async function pollStatus(file, fileId) {
    try {
      const response = await fetch(`/api/status/${fileId}`, {
        credentials: "include",
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        updateFileStatus(file, `Status check failed: ${response.status}`);
        return;
      }

      const data = await response.json();

      if (data.status === "processing") {
        updateFileStatus(file, "Processing...");
        setTimeout(() => pollStatus(file, fileId), 2000); // Poll every 2 seconds
      } else if (data.status === "completed") {
        updateFileStatus(file, "Completed ✓");
        const codeElement = resultJson.querySelector("code");
        codeElement.textContent = JSON.stringify(data, null, 2);
      } else if (data.status === "failed") {
        updateFileStatus(
          file,
          `Processing failed: ${data.error_message || "Unknown error"}`,
        );
      } else {
        updateFileStatus(file, `Unknown status: ${data.status}`);
      }
    } catch (error) {
      console.error("Status polling error:", error);
      updateFileStatus(file, `Error checking status: ${error.message}`);
    }
  }

  // Function to get selected tasks
  function getSelectedTasks() {
    const checkboxes = document.querySelectorAll(".task-checkbox:checked");
    return Array.from(checkboxes).map((checkbox) => checkbox.value);
  }
});
