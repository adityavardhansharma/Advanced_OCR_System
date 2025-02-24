// static/js/main.js

// Grab the drop area and file input elements
const dropArea = document.getElementById('dropArea');
const fileInput = document.getElementById('fileInp');
const fileNameDisplay = document.getElementById('fileName');

// Clicking on the drop area triggers the file input
dropArea.addEventListener('click', () => {
  fileInput.click();
});

// When a file is selected, update the displayed file name
fileInput.addEventListener('change', () => {
  if (fileInput.files && fileInput.files[0]) {
    fileNameDisplay.textContent = fileInput.files[0].name;
  } else {
    fileNameDisplay.textContent = "No file selected";
  }
});

// Add visual highlighting for drag events
['dragenter', 'dragover'].forEach(eventName => {
  dropArea.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropArea.classList.add('highlight');
  }, false);
});

['dragleave', 'drop'].forEach(eventName => {
  dropArea.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropArea.classList.remove('highlight');
  }, false);
});

// Handle dropped files
dropArea.addEventListener('drop', (e) => {
  let files = e.dataTransfer.files;
  fileInput.files = files;
  if (files.length > 0) {
    fileNameDisplay.textContent = files[0].name;
  }
});
